"""
Summarization Event Subscriber
Listens for EpisodeTranscribed events and generates summaries.
"""
import asyncio
from pathlib import Path
import uuid
import json

from podcast_transcriber_shared.events import get_event_bus, EpisodeTranscribed, EpisodeSummarized
from podcast_transcriber_shared.status_monitor import get_pipeline_status_manager
from services.ollama_service import get_ollama_service
from utils.transcript_parser import extract_metadata_from_transcript
from config import SUMMARY_OUTPUT_PATH


async def process_transcription_event(event_data: dict):
    """
    Process an EpisodeTranscribed event asynchronously.
    
    Called when a new transcript is available.
    Generates a structured summary using Ollama.
    
    Args:
        event_data: Event data dictionary from Redis
    """
    try:
        # Parse event
        event = EpisodeTranscribed(**event_data)
        
        print(f"\n{'='*60}")
        print(f"📥 Received EpisodeTranscribed event")
        print(f"   Event ID: {event.event_id}")
        print(f"   Episode: {event.episode_title}")
        print(f"   Podcast: {event.podcast_name}")
        print(f"{'='*60}")
        
        # Report status (Async)
        manager = get_pipeline_status_manager()
        manager.update_service_status('summarization', event.episode_id, "summarizing", progress=0.1, additional_data={
            "episode_title": event.episode_title,
            "podcast_name": event.podcast_name
        })
        
        # Fetch transcript from database
        # Database operations are async, so we just await them directly!
        from podcast_transcriber_shared.database import get_episode_by_id, get_summary_by_episode_id, save_summary as db_save_summary
        
        # Check if summary already exists
        existing_summary = await get_summary_by_episode_id(event.episode_id)
        
        if existing_summary:
            print(f"⏭️  Summary already exists, skipping: {event.episode_title}")
            return
        
        # Fetch episode from database
        episode = await get_episode_by_id(event.episode_id, load_transcript=True)
        
        if not episode:
            print(f"❌ Episode not found in database: {event.episode_id}")
            return
        
        if not episode.transcript_text:
            print(f"❌ No transcript text for episode: {event.episode_id}")
            return
        
        content = episode.transcript_text
        metadata = episode.meta_data or {}
        
        print(f"📄 Episode: {metadata.get('episode_title', event.episode_title)}")
        print(f"🎙️  Podcast: {metadata.get('podcast_name', event.podcast_name)}")
        
        # Generate summary with Ollama (Async)
        print(f"🤖 Generating summary with Ollama...")
        ollama_service = get_ollama_service()
        
        summary_result = await ollama_service.summarize_transcript(
            transcript_text=content,
            episode_title=metadata.get("episode_title", event.episode_title),
            podcast_name=metadata.get("podcast_name", event.podcast_name)
        )
        
        # Prepare summary data
        complete_summary_data = {
            "episode_title": metadata.get("episode_title", event.episode_title),
            "podcast_name": metadata.get("podcast_name", event.podcast_name),
            "processed_date": metadata.get("processed_date"),
            "created_at": metadata.get("processed_date"),
            # Unpack all structured summary fields
            **summary_result.model_dump(),
            # Add metadata fields
            "speakers": metadata.get("speakers", []),
            "duration": metadata.get("duration"),
            "audio_url": episode.url,  # Use URL from database as source of truth
        }
        
        # Save summary to database (async)
        summary = await db_save_summary(event.episode_id, complete_summary_data)
        
        print(f"✅ Summary saved to database for episode: {event.episode_id}")
        
        # Update progress in manager
        from podcast_transcriber_shared.database import get_session_maker, Episode as EpisodeModel
        from sqlalchemy import select, func
        session_maker = get_session_maker()
        async with session_maker() as session:
             # This is a bit expensive but accurate for batch progress
             pass # In a real system we'd use a counter in Redis, but for now let's just clear individual status
        
        # Clear individual status for this episode in this service
        manager.clear_service_status('summarization', event.episode_id)
        # We also need to increment the completed count for summarization
        manager.redis.incr(f"{manager.SERVICE_STATS_PREFIX}summarization:completed") if manager.redis else None
        
        # Publish EpisodeSummarized event
        try:
            event_bus = get_event_bus()

            summarized_event = EpisodeSummarized(
                event_id=f"evt_{uuid.uuid4().hex[:12]}",
                service="summarization",
                episode_id=event.episode_id,
                episode_title=event.episode_title,
                podcast_name=event.podcast_name
            )
            await event_bus.publish(event_bus.STREAM_SUMMARIZED, summarized_event)
            print(f"📤 Published EpisodeSummarized event to stream")
        except Exception as e:
            print(f"⚠️  Failed to publish EpisodeSummarized event: {e}")
        
        print(f"{'='*60}")
        print(f"✅ Event processing complete: {event.episode_title}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ Error processing transcription event: {e}")
        import traceback
        traceback.print_exc()


async def start_summarization_event_subscriber():
    """Start the summarization event subscriber (async)."""
    print("\n" + "="*60)
    print("🚀 Starting Summarization Event Subscriber (Streams)")
    print("="*60)
    
    event_bus = get_event_bus()
    
    # Use Redis Streams with a consumer group for reliability
    await event_bus.subscribe(
        stream=event_bus.STREAM_TRANSCRIBED,
        group_name="summarization_service_group",
        consumer_name="summarization_worker_1",
        callback=process_transcription_event
    )


if __name__ == "__main__":
    import asyncio
    
    # Initialize services before subscribing
    print("📦 Initializing Summarization services...")
    get_ollama_service()
    print("✅ Services initialized\n")
    
    # Run async subscriber
    try:
        asyncio.run(start_summarization_event_subscriber())
    except KeyboardInterrupt:
        pass
