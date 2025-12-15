"""
Episode Processing Module
High-level orchestration of the transcription pipeline.
"""
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import uuid

import feedparser
import requests

from config import TranscriptionConfig
from core.audio import download_audio, TranscriptionWorker
from core.diarization import diarize_transcript
from core.formatting import sanitize_filename, format_transcript
from managers.episode_manager import (
    get_selected_episodes,
    clear_processed_episodes,
    fetch_episodes_from_feed,
    add_episode_to_queue
)
from managers.status_monitor import write_status, clear_status, update_progress
from podcast_transcriber_shared.events import get_event_bus, EpisodeTranscribed
from podcast_transcriber_shared.database import save_transcript as db_save_transcript


async def publish_transcription_event(
    transcript_path: str,  # Deprecated, kept for backward compatibility
    episode_id: str,
    episode_title: str,
    podcast_name: str,
    config: TranscriptionConfig,
    audio_url: Optional[str] = None,
    diarization_failed: bool = False
) -> bool:
    """
    Publish EpisodeTranscribed event to notify downstream services.
    
    This replaces the direct HTTP call to RAG service with event-driven architecture.
    Services (RAG, Summarization) subscribe to this event and process asynchronously.
    
    Args:
        transcript_path: Deprecated (file path no longer used)
        episode_id: Unique episode identifier
        episode_title: Title of the episode
        podcast_name: Name of the podcast
        config: Transcription configuration
        audio_url: Optional URL to the audio file
        diarization_failed: True if speaker diarization failed
        
    Returns:
        True if published successfully, False otherwise
    """
    try:
        # Get event bus
        event_bus = get_event_bus()
        
        # Create event (no file paths, database lookup by episode_id)
        event = EpisodeTranscribed(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            service="transcription",
            episode_id=episode_id,
            episode_title=episode_title,
            podcast_name=podcast_name,
            audio_url=audio_url,
            diarization_failed=diarization_failed
        )
        
        # Publish event
        success = await event_bus.publish(event_bus.CHANNEL_TRANSCRIBED, event)
        
        if success:
            print(f"   📤 Published EpisodeTranscribed event: {event.event_id}")
            if diarization_failed:
                print(f"   ⚠️  Event flagged: diarization_failed=True")
            print(f"   ℹ️  RAG and Summarization services will process asynchronously")
        else:
            print(f"   ⚠️  Failed to publish event (Redis may be unavailable)")
        
        return success
        
    except Exception as e:
        print(f"   ⚠️  Event publishing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_subscriptions(config: TranscriptionConfig) -> List[Dict]:
    """Load RSS feed subscriptions from config."""
    if not config.subscriptions_file.exists():
        print(f"⚠️  No subscriptions found at {config.subscriptions_file}")
        return []
    
    with open(config.subscriptions_file, 'r', encoding='utf-8') as f:
        subscriptions = json.load(f)
    
    # Filter active subscriptions
    active_subs = [sub for sub in subscriptions if sub.get('active', True)]
    print(f"📡 Loaded {len(active_subs)} active subscription(s)")
    return active_subs


def load_history(config: TranscriptionConfig) -> Dict:
    """Load processing history to avoid duplicates."""
    if not config.history_file.exists():
        return {"processed_episodes": []}
    
    with open(config.history_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_history(config: TranscriptionConfig, history: Dict):
    """Save updated processing history."""
    with open(config.history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)


def transcribe_episode_task(
    episode_title: str,
    audio_url: str,
    config: TranscriptionConfig,
    worker: TranscriptionWorker
) -> Tuple[Optional[str], bool]:
    """
    Blocking task for download, transcription, and diarization.
    This function should be run in a thread executor.
    
    Args:
        episode_title: Title of the episode
        audio_url: URL to audio file
        config: Transcription configuration
        worker: Initialized TranscriptionWorker instance

    Returns:
        (transcript_text, diarization_failed) or (None, False) on failure
    """
    print(f"\n{'='*60}")
    print(f"📻 Processing: {episode_title}")
    print(f"{'='*60}")

    update_progress("preparing", 0.0)

    # Determine file extension
    extension = '.mp3'
    if '.m4a' in audio_url.lower():
        extension = '.m4a'

    # Download audio
    safe_filename = sanitize_filename(episode_title)
    temp_audio = config.temp_dir / f"{safe_filename}{extension}"

    if not download_audio(audio_url, temp_audio):
        return None, False

    try:
        # Transcribe using persistent worker
        transcript_result = worker.process(temp_audio)

        if not transcript_result:
            return None, False

        # Diarize
        diarization_failed = False
        diarized_result = diarize_transcript(
            temp_audio,
            transcript_result,
            config.huggingface_token,
            config.device
        )
        if not diarized_result:
            # Fall back to non-diarized if diarization fails
            print("⚠️  Diarization failed, falling back to raw transcript (no speaker labels)")
            diarized_result = transcript_result
            diarization_failed = True

        # Format transcript
        update_progress("saving", 0.5)
        transcript_text = format_transcript(diarized_result)

        # Clean up temp file
        if temp_audio.exists():
            temp_audio.unlink()

        return transcript_text, diarization_failed

    except Exception as e:
        print(f"❌ Processing task failed: {e}")
        # Clean up temp file on error
        if temp_audio.exists():
            try:
                temp_audio.unlink()
            except:
                pass
        return None, False


async def process_episode_async(
    episode_data: Dict,
    config: TranscriptionConfig,
    history: Dict,
    worker: TranscriptionWorker,
    from_queue: bool = False
) -> Tuple[bool, str]:
    """
    Process a single podcast episode asynchronously.
    
    Args:
        episode_data: Episode data
        config: Transcription configuration
        history: Processing history dict
        worker: Initialized TranscriptionWorker instance
        from_queue: True if processing from pending queue
    
    Returns:
        (success: bool, episode_id: str)
    """
    # Extract episode info based on source
    if from_queue:
        episode_title = episode_data.get('episode_title', 'Untitled Episode')
        guid = episode_data.get('id', '')
        audio_url = episode_data.get('audio_url')
        feed_title = episode_data.get('feed_title', 'Unknown Podcast')
    else:
        episode_title = episode_data.get('title', 'Untitled Episode')
        guid = episode_data.get('id', episode_data.get('link', ''))
        feed_title = episode_data.get('feed_title', 'Unknown Podcast')
        
        # Find audio enclosure
        audio_url = None
        for enclosure in episode_data.get('enclosures', []):
            if enclosure.get('type', '').startswith('audio/'):
                audio_url = enclosure.get('href')
                break
        
        # If no audio enclosure, check if it's a YouTube video
        if not audio_url:
            link = episode_data.get('link', '')
            if 'youtube.com' in link or 'youtu.be' in link:
                audio_url = link
    
    # Check if already processed
    if guid in history['processed_episodes']:
        print(f"⏭️  Skipping (already processed): {episode_title}")
        return False, guid
    
    if not audio_url:
        print(f"⚠️  No audio found for: {episode_title}")
        return False, guid
    
    # Run the heavy lifting in a thread pool
    loop = asyncio.get_running_loop()
    
    # Execute the blocking transcription task
    transcript_text, diarization_failed = await loop.run_in_executor(
        None,
        lambda: transcribe_episode_task(episode_title, audio_url, config, worker)
    )
    
    if not transcript_text:
        # Transcription failed
        return False, guid

    # Save transcript to database (Async directly)
    metadata = {
        "title": episode_title,
        "podcast_name": feed_title,
        "audio_url": audio_url,
        "diarization_failed": diarization_failed,
        "processed_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    try:
        episode = await db_save_transcript(
            episode_id=guid,
            transcript_text=transcript_text,
            metadata=metadata
        )
        
        if episode:
            print(f"💾 Saved transcript to database: {episode_title}")
            update_progress("saving", 1.0)
        else:
            print(f"⚠️  Failed to save transcript: episode not found in database")
            return False, guid
        
    except Exception as e:
        print(f"❌ Database save failed: {e}")
        import traceback
        traceback.print_exc()
        return False, guid

    # Publish transcription event (Async directly)
    print(f"📤 Publishing transcription event...")
    await publish_transcription_event(
        transcript_path="",  # No longer used
        episode_id=guid,
        episode_title=episode_title,
        podcast_name=feed_title,
        config=config,
        audio_url=audio_url,
        diarization_failed=diarization_failed
    )

    # Update history
    history['processed_episodes'].append(guid)
    save_history(config, history)
    
    return True, guid

#
# Legacy wrappers for CLI compatibility
#
def process_episode(episode_data: Dict, config: TranscriptionConfig,
                   history: Dict, from_queue: bool = False) -> Tuple[bool, str]:
    """
    Legacy synchronous wrapper for process_episode_async.
    Used by CLI which isn't fully async yet.
    """
    # Create a temporary worker for this single run (inefficient but compatible)
    print("⚠️  Using legacy process_episode wrapper (inefficient)")

    worker = TranscriptionWorker(
        whisper_model=config.whisper_model,
        device=config.device,
        compute_type=config.compute_type,
        batch_size=config.batch_size
    )

    try:
        return asyncio.run(process_episode_async(
            episode_data, config, history, worker, from_queue
        ))
    finally:
        del worker


def process_feed(subscription: Dict, config: TranscriptionConfig, history: Dict):
    """Process all new episodes from a podcast feed (Legacy CLI)."""
    url = subscription.get('url')
    title = subscription.get('title', 'Unknown Podcast')
    
    print(f"\n📡 Checking feed: {title}")
    
    try:
        feed = feedparser.parse(url)
        entries = feed.get('entries', [])

        if not entries:
            return

        if title == 'Unknown Podcast' and feed.feed.get('title'):
            title = feed.feed.get('title')
        
        # Instantiate worker once for the whole feed
        worker = TranscriptionWorker(
            whisper_model=config.whisper_model,
            device=config.device,
            compute_type=config.compute_type,
            batch_size=config.batch_size
        )
        
        try:
            processed_count = 0
            for entry in entries:
                entry['feed_title'] = title
                # Run async process in sync wrapper
                success, _ = asyncio.run(process_episode_async(
                    entry, config, history, worker, from_queue=False
                ))
                if success:
                    processed_count += 1

            print(f"✅ Processed {processed_count} new episode(s) from {title}")
        finally:
            del worker

    except Exception as e:
        print(f"❌ Feed processing failed: {e}")


def process_selected_episodes(config: TranscriptionConfig):
    """Process only selected episodes from the pending queue (Legacy CLI)."""
    selected = get_selected_episodes()
    if not selected:
        print("⚠️  No episodes selected for transcription.")
        return
    
    history = load_history(config)
    
    # Instantiate worker once
    worker = TranscriptionWorker(
        whisper_model=config.whisper_model,
        device=config.device,
        compute_type=config.compute_type,
        batch_size=config.batch_size
    )
    
    try:
        processed_count = 0
        for episode in selected:
            write_status(
                is_running=True,
                current_episode=episode.get('episode_title', 'Unknown'),
                current_podcast=episode.get('feed_title', 'Unknown'),
                stage="processing",
                progress=0.0,
                episodes_completed=processed_count,
                episodes_total=len(selected)
            )

            success, _ = asyncio.run(process_episode_async(
                episode, config, history, worker, from_queue=True
            ))

            if success:
                processed_count += 1
                clear_processed_episodes([episode.get('id', '')])
        
        clear_status()

    finally:
        del worker
