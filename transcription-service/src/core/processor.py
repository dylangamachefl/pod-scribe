"""
Episode Processing Module
High-level orchestration of the transcription pipeline.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import uuid

import feedparser
import requests

from config import TranscriptionConfig
from core.audio import download_audio, transcribe_audio
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


def publish_transcription_event(
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
        success = event_bus.publish(event_bus.CHANNEL_TRANSCRIBED, event)
        
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
    """Load RSS feed subscriptions from config.
    
    Args:
        config: Transcription configuration
        
    Returns:
        List of active subscription dicts
    """
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
    """Load processing history to avoid duplicates.
    
    Args:
        config: Transcription configuration
        
    Returns:
        History dict with processed_episodes list
    """
    if not config.history_file.exists():
        return {"processed_episodes": []}
    
    with open(config.history_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_history(config: TranscriptionConfig, history: Dict):
    """Save updated processing history.
    
    Args:
        config: Transcription configuration
        history: History dict to save
    """
    with open(config.history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)


def process_episode(episode_data: Dict, config: TranscriptionConfig, 
                   history: Dict, from_queue: bool = False) -> Tuple[bool, str]:
    """Process a single podcast episode.
    
    Args:
        episode_data: Episode data (either from RSS feed entry or from pending queue)
        config: Transcription configuration
        history: Processing history dict
        from_queue: True if processing from pending queue, False if from RSS feed
    
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
    
    print(f"\n{'='*60}")
    print(f"📻 Processing: {episode_title}")
    print(f"{'='*60}")
    
    # Update status with current episode
    update_progress("preparing", 0.0)
    
    # Determine file extension
    extension = '.mp3'
    if '.m4a' in audio_url.lower():
        extension = '.m4a'
    
    # Download audio
    safe_filename = sanitize_filename(episode_title)
    temp_audio = config.temp_dir / f"{safe_filename}{extension}"
    
    if not download_audio(audio_url, temp_audio):
        return False, guid
    
    try:
        # Transcribe
        transcript_result = transcribe_audio(
            temp_audio, 
            config.whisper_model,
            config.device,
            config.compute_type,
            config.batch_size
        )
        if not transcript_result:
            return False, guid
        
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
        
        # Save transcript to database
        import asyncio
        from podcast_transcriber_shared.database import save_transcript as db_save_transcript
        
        # Prepare metadata for database
        metadata = {
            "title": episode_title,
            "podcast_name": feed_title,
            "audio_url": audio_url if 'audio_url' in locals() else None,
            "diarization_failed": diarization_failed,
            "processed_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        try:
            # Save to database using async operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            episode = loop.run_until_complete(
                db_save_transcript(
                    episode_id=guid,
                    transcript_text=transcript_text,
                    metadata=metadata
                )
            )
            loop.close()
            
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
        
        # Publish transcription event for downstream services
        print(f"📤 Publishing transcription event...")
        publish_transcription_event(
            transcript_path="",  # No longer used
            episode_id=guid,
            episode_title=episode_title,
            podcast_name=feed_title,
            config=config,
            audio_url=audio_url if 'audio_url' in locals() else None,
            diarization_failed=diarization_failed
        )

        
        # Update history
        history['processed_episodes'].append(guid)
        save_history(config, history)
        
        # Clean up temp file
        temp_audio.unlink()
        
        return True, guid
    
    except Exception as e:
        print(f"❌ Processing failed: {e}")
        # Clean up temp file on error
        if temp_audio.exists():
            temp_audio.unlink()
        return False, guid


def process_feed(subscription: Dict, config: TranscriptionConfig, history: Dict):
    """Process all new episodes from a podcast feed.
    
    Args:
        subscription: Subscription dict with url and title
        config: Transcription configuration
        history: Processing history dict
    """
    url = subscription.get('url')
    title = subscription.get('title', 'Unknown Podcast')
    
    print(f"\n📡 Checking feed: {title}")
    print(f"   URL: {url}")
    
    try:
        feed = feedparser.parse(url)
        
        if feed.bozo:
            print(f"⚠️  Feed parse warning: {feed.bozo_exception}")
        
        entries = feed.get('entries', [])
        if not entries:
            print(f"⚠️  No episodes found in feed")
            return
        
        print(f"📋 Found {len(entries)} episode(s) in feed")
        
        # Use feed title if not specified in subscription
        if title == 'Unknown Podcast' and feed.feed.get('title'):
            title = feed.feed.get('title')
        
        # Process each episode
        processed_count = 0
        for entry in entries:
            # Add feed_title to entry for process_episode
            entry['feed_title'] = title
            success, _ = process_episode(entry, config, history, from_queue=False)
            if success:
                processed_count += 1
        
        print(f"✅ Processed {processed_count} new episode(s) from {title}")
    
    except Exception as e:
        print(f"❌ Feed processing failed: {e}")


def process_selected_episodes(config: TranscriptionConfig):
    """Process only selected episodes from the pending queue.
    
    Args:
        config: Transcription configuration
    """
    import torch
    import sys
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║          Podcast Transcription Engine v1.0                  ║
║          Processing Selected Episodes                        ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Check CUDA availability and set device
    if torch.cuda.is_available():
        device = "cuda"
        gpu_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"🎮 GPU: {gpu_name}")
        print(f"💾 VRAM: {vram:.1f} GB\n")
    else:
        device = "cpu"
        print("⚠️  WARNING: CUDA not available, falling back to CPU")
        print("   Transcription will be significantly slower on CPU")
        print("   For GPU support, ensure CUDA drivers are installed\n")

    
    # Load selected episodes
    selected = get_selected_episodes()
    
    if not selected:
        print("⚠️  No episodes selected for transcription.")
        print("   Use the web dashboard to select episodes from the queue.")
        print("   Open the frontend at http://localhost:3000 and go to the Queue page")
        return
    
    print(f"📋 Found {len(selected)} selected episode(s) to process\n")
    
    history = load_history(config)
    
    # Initialize status
    write_status(
        is_running=True,
        current_episode="Starting...",
        current_podcast="",
        stage="preparing",
        progress=0.0,
        episodes_completed=0,
        episodes_total=len(selected)
    )
    
    # Process each selected episode
    start_time = datetime.now()
    processed_count = 0
    processed_ids = []
    
    for idx, episode in enumerate(selected):
        # Update status for current episode
        write_status(
            is_running=True,
            current_episode=episode.get('episode_title', 'Unknown'),
            current_podcast=episode.get('feed_title', 'Unknown'),
            stage="processing",
            progress=0.0,
            episodes_completed=processed_count,
            episodes_total=len(selected)
        )
        
        success, episode_id = process_episode(episode, config, history, from_queue=True)
        if success:
            processed_count += 1
            processed_ids.append(episode_id)
    
    # Remove processed episodes from queue
    if processed_ids:
        clear_processed_episodes(processed_ids)
        print(f"\n🧹 Removed {len(processed_ids)} processed episode(s) from queue")
    
    # Clear status when complete
    clear_status()
    
    duration = (datetime.now() - start_time).total_seconds()
    print(f"\n{'='*60}")
    print(f"✅ Processing complete!")
    print(f"📊 Processed {processed_count}/{len(selected)} episode(s)")
    print(f"⏱️  Total time: {duration/60:.1f} minutes")
    print(f"{'='*60}\n")
