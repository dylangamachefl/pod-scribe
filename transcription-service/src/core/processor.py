"""
Episode Processing Module
High-level orchestration of the transcription pipeline.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

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


def publish_transcription_event(
    transcript_path: Path,
    episode_id: str,
    episode_title: str,
    podcast_name: str,
    config: TranscriptionConfig,
    audio_url: Optional[str] = None
) -> bool:
    """
    Publish EpisodeTranscribed event to notify downstream services.
    
    This replaces the direct HTTP call to RAG service with event-driven architecture.
    Services (RAG, Summarization) subscribe to this event and process asynchronously.
    
    Args:
        transcript_path: Absolute path to transcript file
        episode_id: Unique episode identifier
        episode_title: Title of the episode
        podcast_name: Name of the podcast
        config: Transcription configuration
        audio_url: Optional URL to the audio file
        
    Returns:
        True if published successfully, False otherwise
    """
    try:
        # Import event bus (lazy import to avoid circular dependencies)
        import sys
        sys.path.insert(0, str(config.root_dir / "shared"))
        from events import get_event_bus, EpisodeTranscribed
        import uuid
        
        # Get event bus
        event_bus = get_event_bus()
        
        # Convert to Docker path for container services
        try:
            docker_path = config.get_docker_path(transcript_path)
        except ValueError as e:
            print(f"   ⚠️  Path conversion error: {e}")
            return False
        
        # Create event
        event = EpisodeTranscribed(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            service="transcription",
            episode_id=episode_id,
            episode_title=episode_title,
            podcast_name=podcast_name,
            transcript_path=str(transcript_path),
            docker_transcript_path=docker_path,
            audio_url=audio_url
        )
        
        # Publish event
        success = event_bus.publish(event_bus.CHANNEL_TRANSCRIBED, event)
        
        if success:
            print(f"   📤 Published EpisodeTranscribed event: {event.event_id}")
            print(f"   ℹ️  RAG and Summarization services will process asynchronously")
        else:
            print(f"   ⚠️  Failed to publish event (Redis may be unavailable)")
            print(f"   ℹ️  Services will rely on file watcher as backup")
        
        return success
        
    except Exception as e:
        print(f"   ⚠️  Event publishing failed: {e}")
        print(f"   ℹ️  Services will rely on file watcher as backup")
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
        diarized_result = diarize_transcript(
            temp_audio, 
            transcript_result,
            config.huggingface_token,
            config.device
        )
        if not diarized_result:
            # Fall back to non-diarized if diarization fails
            diarized_result = transcript_result
        
        # Format and save
        update_progress("saving", 0.5)
        transcript_text = format_transcript(diarized_result)
        
        # Create output directory for this podcast
        podcast_dir = config.output_dir / sanitize_filename(feed_title)
        podcast_dir.mkdir(exist_ok=True)
        
        # Write to temporary file first (atomic write pattern)
        # This prevents file watcher from reading partially-written files
        output_file = podcast_dir / f"{safe_filename}.txt"
        temp_output_file = podcast_dir / f"{safe_filename}.tmp"
        
        try:
            # Write complete content to .tmp file
            with open(temp_output_file, 'w', encoding='utf-8') as f:
                f.write(f"Title: {episode_title}\n")
                f.write(f"Podcast: {feed_title}\n")
                f.write(f"Processed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"\n{'='*60}\n\n")
                f.write(transcript_text)
            
            # Atomic rename from .tmp to .txt
            # This ensures file watcher only sees complete files
            temp_output_file.replace(output_file)
            
            print(f"💾 Saved transcript: {output_file}")
            update_progress("saving", 1.0)
            
        except Exception as e:
            # Clean up temp file if something goes wrong
            if temp_output_file.exists():
                temp_output_file.unlink()
            raise
        
        # Publish transcription event for downstream services
        print(f"📤 Publishing transcription event...")
        publish_transcription_event(
            transcript_path=output_file,
            episode_id=guid,
            episode_title=episode_title,
            podcast_name=feed_title,
            config=config,
            audio_url=audio_url if 'audio_url' in locals() else None
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
    
    # Check CUDA availability
    if not torch.cuda.is_available():
        print("❌ CUDA not available! Please check your GPU drivers.")
        sys.exit(1)
    
    gpu_name = torch.cuda.get_device_name(0)
    print(f"🎮 GPU: {gpu_name}")
    print(f"💾 VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB\n")
    
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
