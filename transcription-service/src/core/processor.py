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
    diarization_failed: bool = False,
    duration_seconds: Optional[float] = None,
    speaker_count: Optional[int] = None
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
        duration_seconds: Duration of the audio in seconds
        speaker_count: Number of unique speakers detected
        
    Returns:
        True if published successfully, False otherwise
    """
    try:
        # Get event bus
        event_bus = get_event_bus()
        
        # Create event with enriched fields
        event = EpisodeTranscribed(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            service="transcription",
            episode_id=episode_id,
            episode_title=episode_title,
            podcast_name=podcast_name,
            diarization_failed=diarization_failed,
            audio_url=audio_url,
            duration_seconds=duration_seconds,
            speaker_count=speaker_count
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


def extract_duration_from_audio(audio_path: Path) -> Optional[float]:
    """
    Extract audio duration in seconds using ffprobe or fallback methods.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Duration in seconds, or None if unable to determine
    """
    try:
        import subprocess
        # Try ffprobe first (most reliable)
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
             '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_path)],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.SubprocessError, ValueError, FileNotFoundError):
        pass
    
    # Fallback: estimate from file size (very rough)
    # Assume ~128kbps MP3 encoding: 1 second ≈ 16KB
    try:
        file_size_kb = audio_path.stat().st_size / 1024
        estimated_duration = file_size_kb / 16  # Rough estimate
        return estimated_duration
    except:
        return None


def extract_speaker_count_from_transcript(transcript_text: str) -> Optional[int]:
    """
    Extract number of unique speakers from formatted transcript.
    
    Args:
        transcript_text: Formatted transcript with speaker labels
        
    Returns:
        Number of unique speakers, or None if unable to determine
    """
    try:
        import re
        # Match speaker labels like "SPEAKER_00:", "SPEAKER_01:", etc.
        speaker_pattern = r'SPEAKER_\d+:'
        speakers = set(re.findall(speaker_pattern, transcript_text))
        return len(speakers) if speakers else None
    except:
        return None


# Note: load_history and save_history DELETED in favor of database state


def transcribe_episode_task(
    episode_id: str,
    episode_title: str,
    temp_audio: Path,
    config: TranscriptionConfig,
    worker: TranscriptionWorker
) -> Tuple[Optional[str], bool, Optional[float], Optional[int]]:
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
        (transcript_text, diarization_failed, duration_seconds, speaker_count) or (None, False, None, None) on failure
    """
    print(f"\n{'='*60}")
    print(f"📻 Processing: {episode_title}")
    print(f"{'='*60}")

    if not temp_audio.exists():
        print(f"❌ Processing task failed: Audio file not found: {temp_audio}")
        return None, False, None, None

    update_progress("preparing", 0.0, log=f"Starting processing: {episode_title}", episode_id=episode_id)
    update_progress("preparing", 0.0, log=f"Starting processing: {episode_title}", episode_id="current")
    
    # Extract audio duration before processing
    duration_seconds = extract_duration_from_audio(temp_audio)

    # Heavy transcription and diarization work starts here

    try:
        # Transcribe using persistent worker
        update_progress("transcribing", 0.2, log="Running Whisper transcription (this may take a while)...", episode_id=episode_id)
        update_progress("transcribing", 0.2, log="Running Whisper transcription (this may take a while)...", episode_id="current")
        transcript_result = worker.process(temp_audio)

        if not transcript_result:
            return None, False, duration_seconds, None

        # Diarize
        update_progress("diarizing", 0.6, log="Running speaker diarization...", episode_id=episode_id)
        update_progress("diarizing", 0.6, log="Running speaker diarization...", episode_id="current")
        diarization_failed = False
        diarized_result = diarize_transcript(
            temp_audio,
            transcript_result,
            worker.diarize_model,
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
        
        # Extract speaker count from formatted transcript
        speaker_count = extract_speaker_count_from_transcript(transcript_text)

        # Clean up temp file
        if temp_audio.exists():
            temp_audio.unlink()

        return transcript_text, diarization_failed, duration_seconds, speaker_count

    except Exception as e:
        print(f"❌ Processing task failed: {e}")
        # Clean up temp file on error
        if temp_audio.exists():
            try:
                temp_audio.unlink()
            except:
                pass
        return None, False, duration_seconds, None


async def process_episode_async(
    episode_data: Dict,
    config: TranscriptionConfig,
    worker: TranscriptionWorker,
    from_queue: bool = False
) -> Tuple[bool, str]:
    """
    Process a single podcast episode asynchronously.
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
    
    # 3. Offload the heavy lifting to a thread pool with a heartbeat task
    loop = asyncio.get_running_loop()
    
    # Define Heartbeat task
    from podcast_transcriber_shared.database import update_episode_heartbeat
    
    async def heartbeat_loop(episode_id: str):
        try:
            while True:
                await update_episode_heartbeat(episode_id)
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"⚠️  Heartbeat task failed: {e}")

    # Start heartbeat
    heartbeat_task = asyncio.create_task(heartbeat_loop(guid))
    
    try:
        # Execute the blocking transcription task
        transcript_text, diarization_failed, duration_seconds, speaker_count = await loop.run_in_executor(
            None,
            lambda: transcribe_episode_task(guid, episode_title, temp_audio, config, worker)
        )
    finally:
        # Stop heartbeat
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
    
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
        diarization_failed=diarization_failed,
        duration_seconds=duration_seconds,
        speaker_count=speaker_count
    )

    return True, guid
