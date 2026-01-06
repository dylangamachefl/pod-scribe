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

from config import TranscriptionConfig
from core.audio import download_audio, TranscriptionWorker
from core.diarization import diarize_transcript
from core.formatting import sanitize_filename, format_transcript
from managers.status_monitor import update_progress
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
        
        # Create event (ID-only, no file paths)
        event = EpisodeTranscribed(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            service="transcription",
            episode_id=episode_id,
            episode_title=episode_title,
            podcast_name=podcast_name,
            diarization_failed=diarization_failed
        )
        
        # Publish to Stream
        success = await event_bus.publish(event_bus.STREAM_TRANSCRIBED, event)
        
        if success:
            print(f"   📤 Published EpisodeTranscribed event to stream: {event.event_id}")
            if diarization_failed:
                print(f"   ⚠️  Event flagged: diarization_failed=True")
        else:
            print(f"   ⚠️  Failed to publish event (Redis stream entry failed)")
        
        return success
        
    except Exception as e:
        print(f"   ⚠️  Event publishing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# Note: load_history and save_history DELETED in favor of database state


def transcribe_episode_task(
    episode_id: str,
    episode_title: str,
    temp_audio: Path,
    config: TranscriptionConfig,
    worker: TranscriptionWorker
) -> Tuple[Optional[str], bool]:
    """
    Blocking task for transcription and diarization.
    This function should be run in a thread executor.
    
    Args:
        episode_id: Unique episode identifier
        episode_title: Title of the episode
        temp_audio: Path to the local audio file
        config: Transcription configuration
        worker: Initialized TranscriptionWorker instance

    Returns:
        (transcript_text, diarization_failed) or (None, False) on failure
    """
    print(f"\n{'='*60}")
    print(f"📻 Processing: {episode_title}")
    print(f"{'='*60}")

    if not temp_audio.exists():
        print(f"❌ Processing task failed: Audio file not found: {temp_audio}")
        return None, False

    update_progress("preparing", 0.0, log=f"Starting processing: {episode_title}", episode_id=episode_id)
    update_progress("preparing", 0.0, log=f"Starting processing: {episode_title}", episode_id="current")

    # Heavy transcription and diarization work starts here

    try:
        # Transcribe using persistent worker
        update_progress("transcribing", 0.2, log="Running Whisper transcription (this may take a while)...", episode_id=episode_id)
        update_progress("transcribing", 0.2, log="Running Whisper transcription (this may take a while)...", episode_id="current")
        transcript_result = worker.process(temp_audio)

        if not transcript_result:
            return None, False

        # Diarize
        update_progress("diarizing", 0.6, log="Running speaker diarization...", episode_id=episode_id)
        update_progress("diarizing", 0.6, log="Running speaker diarization...", episode_id="current")
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
        update_progress("saving", 0.9, log="Formatting and saving transcript...", episode_id=episode_id)
        update_progress("saving", 0.9, log="Formatting and saving transcript...", episode_id="current")
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
    worker: TranscriptionWorker,
    from_queue: bool = False
) -> Tuple[bool, str]:
    """
    Process a single podcast episode asynchronously.
    
    Args:
        episode_data: Episode data
        config: Transcription configuration
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
    
    if not audio_url:
        print(f"⚠️  No audio found for: {episode_title}")
        return False, guid
    
    # 1. Determine local file path
    extension = '.mp3'
    if '.m4a' in audio_url.lower():
        extension = '.m4a'
    
    safe_filename = sanitize_filename(episode_title)
    temp_audio = config.temp_dir / f"{safe_filename}{extension}"
    
    # 2. Download audio (Proper Async I/O)
    update_progress("downloading", 0.1, log="Downloading audio file...", episode_id=guid)
    update_progress("downloading", 0.1, log="Downloading audio file...", episode_id="current")
    
    try:
        if not await download_audio(audio_url, temp_audio):
            print(f"❌ Download failed for: {episode_title}")
            return False, guid
    except Exception as e:
        print(f"❌ Exception during download: {e}")
        return False, guid
    
    # 3. Offload the heavy lifting to a thread pool
    loop = asyncio.get_running_loop()
    
    # Execute the blocking transcription task
    transcript_text, diarization_failed = await loop.run_in_executor(
        None,
        lambda: transcribe_episode_task(guid, episode_title, temp_audio, config, worker)
    )
    
    if not transcript_text:
        # Transcription failed
        return False, guid

    # Save transcript to database (Async directly)
    print(f"💾 Saving transcript to database for episode: {guid}")
    await db_save_transcript(
        episode_id=guid,
        transcript_text=transcript_text,
        metadata={
            "diarization_failed": diarization_failed
        }
    )
    print(f"✅ Saved transcript to database: {episode_title}")
    update_progress("saving", 1.0, episode_id=guid)
    update_progress("saving", 1.0, episode_id="current")
    
    # Publish transcription event (Async directly)
    print(f"📤 Publishing transcription event...")
    update_progress("saving", 0.95, log="Publishing completion event...", episode_id=guid)
    update_progress("saving", 0.95, log="Publishing completion event...", episode_id="current")
    await publish_transcription_event(
        transcript_path="",  # No longer used
        episode_id=guid,
        episode_title=episode_title,
        podcast_name=feed_title,
        config=config,
        audio_url=audio_url,
        diarization_failed=diarization_failed
    )

    return True, guid
