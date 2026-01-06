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


async def process_batch_transcribed_event(event_data: dict):
    """
    Process a BatchTranscribed event asynchronously.
    Summarizes all episodes in the batch sequentially.
    """
    try:
        from podcast_transcriber_shared.events import BatchTranscribed, EpisodeSummarized
        event = BatchTranscribed(**event_data)
        
        bind_correlation_id(event.event_id)
        logger.info("batch_transcribed_event_received", 
                    batch_id=event.batch_id, 
                    episode_count=len(event.episode_ids))

        # Acquire GPU Lock once for the entire batch
        from podcast_transcriber_shared.gpu_lock import get_gpu_lock
        async with get_gpu_lock().acquire():
            logger.info("gpu_lock_acquired_for_batch_summarization", batch_id=event.batch_id)
            
            processed_episodes = []
            for episode_id in event.episode_ids:
                success = await summarize_single_episode(episode_id, event.batch_id)
                if success:
                    processed_episodes.append(episode_id)

            # Publish BatchSummarized event
            if processed_episodes:
                from podcast_transcriber_shared.events import BatchSummarized
                eb = get_event_bus()
                batch_event = BatchSummarized(
                    event_id=f"batch_sum_{uuid.uuid4().hex[:8]}",
                    service="summarization-service",
                    batch_id=event.batch_id,
                    episode_ids=processed_episodes
                )
                await eb.publish(eb.STREAM_BATCH_SUMMARIZED, batch_event)
                logger.info("batch_summarized_event_published", batch_id=event.batch_id)

    except Exception as e:
        logger.error("batch_summarization_error", error=str(e), exc_info=True)


async def summarize_single_episode(episode_id: str, batch_id: str = "default") -> bool:
    """Helper to summarize a single episode (refactored from previous process_transcription_event)."""
    try:
        # Fetch episode from database
        from podcast_transcriber_shared.database import get_episode_by_id, save_summary as db_save_summary
        
        episode = await get_episode_by_id(episode_id, load_transcript=True)
        if not episode or not episode.transcript_text:
            logger.error("episode_unsuitable_for_summarization", episode_id=episode_id)
            return False

        # Report status
        manager = get_pipeline_status_manager()
        manager.update_service_status('summarization', episode_id, "summarizing", progress=0.1, additional_data={
            "episode_title": episode.title,
            "podcast_name": episode.podcast_name
        })

        # Summarize
        logger.info("generating_summary", episode_id=episode_id, title=episode.title)
        ollama_service = get_ollama_service()
        summary_result = await ollama_service.summarize_transcript(
            transcript_text=episode.transcript_text,
            episode_title=episode.title,
            podcast_name=episode.podcast_name
        )
        
        # Save to DB
        complete_summary_data = {
            "episode_title": episode.title,
            "podcast_name": episode.podcast_name,
            **summary_result.model_dump(),
            "audio_url": episode.url,
        }
        await db_save_summary(episode_id, complete_summary_data)
        
        # Cleanup status
        manager.clear_service_status('summarization', episode_id)
        manager.redis.incr(f"{manager.SERVICE_STATS_PREFIX}summarization:completed") if manager.redis else None
        
        return True

    except Exception as e:
        logger.error("single_episode_summarization_failed", episode_id=episode_id, error=str(e))
        return False


async def start_summarization_event_subscriber():
    """Start the summarization event subscriber (async)."""
    logger.info("summarization_event_subscriber_starting", stream="STREAM_TRANSCRIBED", group="summarization_service_group")
    
    event_bus = get_event_bus()
    
    # Use Redis Streams with a consumer group for reliability
    await event_bus.subscribe(
        stream=event_bus.STREAM_BATCH_TRANSCRIBED,
        group_name="summarization_service_group",
        consumer_name="summarization_worker_1",
        callback=process_batch_transcribed_event
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
