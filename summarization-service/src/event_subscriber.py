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

# Global state for cancellation
_active_batch_task = None
_active_episode_id = None
_shutdown_event = asyncio.Event()


async def process_batch_transcribed_event(event_data: dict):
    """
    Process a BatchTranscribed event asynchronously.
    Summarizes all episodes in the batch sequentially.
    """
    global _active_batch_task, _active_episode_id
    _active_batch_task = asyncio.current_task()
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
            manager = get_pipeline_status_manager()
            for episode_id in event.episode_ids:
                _active_episode_id = episode_id
                # Check for cancellation signals
                # Check for cancellation signals
                if manager.is_stopped():
                    logger.info("pipeline_stopped_skipping_summarization", episode_id=episode_id)
                    manager.update_service_status('summarization', episode_id, "stopped", progress=0.0, log_message="Pipeline stopped by user")
                    continue

                if manager.is_batch_cancelled(event.batch_id):
                    logger.info("batch_cancelled_skipping_summarization", episode_id=episode_id, batch_id=event.batch_id)
                    manager.update_service_status('summarization', episode_id, "cancelled", progress=0.0, log_message=f"Batch {event.batch_id} cancelled by user")
                    continue

                # result of True means "handled" (either summarized or gracefully skipped)
                # result of False means "failed" (infrastructure/model error)
                success = await summarize_single_episode(episode_id, event.batch_id)
                if success:
                    # Check if it was actually summarized (by checking DB or state)
                    # For now, we only add to processed_episodes if it was a real success.
                    # We'll use a slightly different return pattern in summarize_single_episode.
                    pass 

            # Refactored: check which ones actually have summaries in DB now
            from podcast_transcriber_shared.database import get_summary_by_episode_id
            for episode_id in event.episode_ids:
                summary = await get_summary_by_episode_id(episode_id)
                if summary:
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
                logger.info("batch_summarized_event_published", batch_id=event.batch_id, count=len(processed_episodes))
            else:
                logger.info("batch_summarization_complete_no_episodes_processed", batch_id=event.batch_id)
            
            return True

    except asyncio.CancelledError:
        logger.info("batch_summarization_cancelled", batch_id=event.batch_id)
        raise
    except Exception as e:
        logger.error("batch_summarization_error", error=str(e), exc_info=True)
        return False


async def summarize_single_episode(episode_id: str, batch_id: str = "default") -> bool:
    """Helper to summarize a single episode. Returns True if handled (even if skipped)."""
    try:
        # Fetch episode from database
        from podcast_transcriber_shared.database import (
            get_episode_by_id, 
            save_summary as db_save_summary, 
            get_summary_by_episode_id,
            update_episode_status,
            EpisodeStatus
        )
        
        # Check if already summarized
        existing = await get_summary_by_episode_id(episode_id)
        if existing:
            logger.info("episode_already_summarized", episode_id=episode_id)
            return True

        episode = await get_episode_by_id(episode_id, load_transcript=True)
        if not episode:
            logger.warning("episode_not_found", episode_id=episode_id)
            return True # Skip missing episodes gracefully

        if not episode.transcript_text or len(episode.transcript_text.split()) < 50:
            logger.warning("episode_unsuitable_for_summarization", 
                           episode_id=episode_id, 
                           reason="transcript_missing_or_too_short",
                           status=episode.status)
            return True # Handle gracefully by skipping

        # Report status
        await update_episode_status(episode_id, EpisodeStatus.SUMMARIZING)
        manager = get_pipeline_status_manager()
        manager.update_service_status('summarization', episode_id, "summarizing", progress=0.1, log_message=f"Generating summary for: {episode.title}", additional_data={
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
        await update_episode_status(episode_id, EpisodeStatus.SUMMARIZED)
        
        # Cleanup status
        manager.update_service_status('summarization', episode_id, "completed", progress=1.0, log_message=f"Summarization complete: {episode.title}")
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

async def stop_monitor():
    """Background monitor to cancel active task on stop signal."""
    while not _shutdown_event.is_set():
        await asyncio.sleep(2)
        try:
            manager = get_pipeline_status_manager()
            if manager.is_stopped():
                global _active_batch_task, _active_episode_id
                if _active_batch_task and not _active_batch_task.done():
                    logger.critical("cancelling_summarization_due_to_stop_signal", episode_id=_active_episode_id)
                    
                    # Mark current episode as failed
                    if _active_episode_id:
                        try:
                            from podcast_transcriber_shared.database import update_episode_status, EpisodeStatus
                            await update_episode_status(_active_episode_id, EpisodeStatus.FAILED)
                        except Exception as e:
                            logger.error("failed_to_update_episode_status_during_cancel", error=str(e))
                        
                        manager.update_service_status('summarization', _active_episode_id, "cancelled", progress=0.0, log_message="Aborted: Stop signal received")

                    _active_batch_task.cancel()
        except Exception as e:
            logger.error("stop_monitor_error", error=str(e))


async def recover_stuck_episodes():
    """
    Recover episodes that were transcribed but not summarized (e.g. due to restart).
    Also picks up 'SUMMARIZING' episodes effectively resetting them.
    """
    try:
        from podcast_transcriber_shared.database import list_episodes, EpisodeStatus
        from podcast_transcriber_shared.gpu_lock import get_gpu_lock
        
        logger.info("checking_for_stuck_episodes")
        
        # Find episodes that are ready for summarization or got stuck during it
        stuck_transcribed = await list_episodes(status=EpisodeStatus.TRANSCRIBED)
        stuck_summarizing = await list_episodes(status=EpisodeStatus.SUMMARIZING)
        
        stuck_episodes = stuck_transcribed + stuck_summarizing
        
        if not stuck_episodes:
            logger.info("no_stuck_episodes_found")
            return

        logger.info("found_stuck_episodes", count=len(stuck_episodes), ids=[e.id for e in stuck_episodes])
        
        # Acquire GPU lock for the recovery batch
        async with get_gpu_lock().acquire():
            logger.info("gpu_lock_acquired_for_recovery")
            
            for episode in stuck_episodes:
                logger.info("recovering_episode", episode_id=episode.id, status=episode.status)
                await summarize_single_episode(episode.id, batch_id="recovery_startup")
                
        logger.info("recovery_batch_complete")
            
    except Exception as e:
        logger.error("recovery_failed", error=str(e), exc_info=True)


if __name__ == "__main__":
    import asyncio
    
    # Initialize services before subscribing
    logger.info("initializing_summarization_services")
    get_ollama_service()
    logger.info("services_initialized")
    
    # Run recovery and then subscriber
    async def main():
        monitor_task = asyncio.create_task(stop_monitor())
        try:
            await recover_stuck_episodes()
            await start_summarization_event_subscriber()
        finally:
            _shutdown_event.set()
            monitor_task.cancel()
            await monitor_task

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
