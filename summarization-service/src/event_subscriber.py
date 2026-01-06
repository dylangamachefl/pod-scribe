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
from podcast_transcriber_shared.logging_config import configure_logging, get_logger, bind_correlation_id
from services.ollama_service import get_ollama_service
from utils.transcript_parser import extract_metadata_from_transcript
from config import SUMMARY_OUTPUT_PATH

# Configure structured logging
configure_logging("summarization-service")
logger = get_logger(__name__)


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
        
        # Bind correlation ID for tracking
        bind_correlation_id(event.event_id)
        logger.info("episode_transcribed_event_received",
                   event_id=event.event_id,
                   episode_id=event.episode_id,
                   episode_title=event.episode_title,
                   podcast_name=event.podcast_name)
        
        # Report status (Async)
        manager = get_pipeline_status_manager()
        manager.update_service_status('summarization', event.episode_id, "summarizing", progress=0.1, additional_data={
            "episode_title": event.episode_title,
            "podcast_name": event.podcast_name
        })
        
        # === ATOMIC IDEMPOTENCY CHECK ===
        from podcast_transcriber_shared.idempotency import get_idempotency_manager
        
        idempotency_manager = get_idempotency_manager()
        idempotency_key = idempotency_manager.make_key("summarization", "transcribed", event.episode_id)
        
        # Atomic check-and-set: returns True if this is the first time processing
        is_first_time = await idempotency_manager.check_and_set(idempotency_key, ttl=86400)
        
        if not is_first_time:
            logger.info("episode_already_processed_skipping", 
                       episode_id=event.episode_id, 
                       title=event.episode_title,
                       idempotency_key=idempotency_key)
            return True
        
        # Fetch episode from database
        episode = await get_episode_by_id(event.episode_id, load_transcript=True)
        
        if not episode:
            logger.error("episode_not_found_in_database", episode_id=event.episode_id)
            return
        
        if not episode.transcript_text:
            logger.error("no_transcript_text_for_episode", episode_id=event.episode_id)
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
        
        logger.info("summary_saved_to_database", episode_id=event.episode_id)
        
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
            logger.info("episode_summarized_event_published", episode_id=event.episode_id)
        except Exception as e:
            logger.warning("failed_to_publish_summarized_event", episode_id=event.episode_id, error=str(e))
        
        logger.info("summarization_processing_complete", episode_id=event.episode_id, title=event.episode_title)
        
    except Exception as e:
        logger.error("summarization_event_processing_error", error=str(e), exc_info=True)


async def start_summarization_event_subscriber():
    """Start the summarization event subscriber (async)."""
    logger.info("summarization_event_subscriber_starting", stream="STREAM_TRANSCRIBED", group="summarization_service_group")
    
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
    logger.info("initializing_summarization_services")
    get_ollama_service()
    logger.info("services_initialized")
    
    # Run async subscriber
    try:
        asyncio.run(start_summarization_event_subscriber())
    except KeyboardInterrupt:
        pass
