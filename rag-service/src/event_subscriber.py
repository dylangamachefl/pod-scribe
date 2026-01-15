"""
RAG Event Subscriber
Listens for EpisodeTranscribed events and processes transcripts for RAG.
"""
import asyncio
from pathlib import Path

from podcast_transcriber_shared.events import get_event_bus, EpisodeSummarized
from podcast_transcriber_shared.status_monitor import get_pipeline_status_manager
from podcast_transcriber_shared.logging_config import configure_logging, get_logger, bind_correlation_id
from services.embeddings import get_embedding_service
from services.qdrant_service import get_qdrant_service
from services.hybrid_retriever import get_hybrid_retriever_service
from utils.chunking import (
    extract_metadata_from_transcript,
    get_transcript_body,
    chunk_by_speaker_turns
)
from langchain_core.documents import Document
from qdrant_client.models import Filter, FieldCondition, MatchValue
# Removed: from qdrant_client.models import Filter, FieldCondition, MatchValue

# Configure structured logging
configure_logging("rag-service")
logger = get_logger(__name__)

# Global state for cancellation
_active_batch_task = None
_active_episode_id = None
_shutdown_event = asyncio.Event()


async def heartbeat_loop(episode_id: str, stop_event: asyncio.Event):
    """Background heartbeat loop for an active RAG indexing job."""
    from podcast_transcriber_shared.database import update_episode_heartbeat
    while not stop_event.is_set():
        try:
            await update_episode_heartbeat(episode_id)
            logger.debug("heartbeat_pulse", episode_id=episode_id)
        except Exception as e:
            logger.warning("heartbeat_pulse_failed", episode_id=episode_id, error=str(e))
        
        # Wait for 30 seconds or until stop event is set
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass


async def heartbeat_reaper():
    """Background task to reset stuck INDEXING jobs."""
    logger.info("heartbeat_reaper_starting")
    while not _shutdown_event.is_set():
        try:
            from podcast_transcriber_shared.database import get_session_maker, Episode, EpisodeStatus
            from sqlalchemy import select, and_
            from datetime import datetime, timedelta
            
            session_maker = get_session_maker()
            async with session_maker() as session:
                stale_threshold = datetime.utcnow() - timedelta(minutes=5)
                
                # Query for INDEXING episodes with stale heartbeat
                # Use scalar_one_or_none handles cases where no heartbeat is set at all
                query = select(Episode).where(
                    and_(
                        Episode.status == EpisodeStatus.INDEXING,
                        (Episode.heartbeat < stale_threshold) | (Episode.heartbeat == None)
                    )
                )
                
                result = await session.execute(query)
                stale_episodes = result.scalars().all()
                
                if stale_episodes:
                    logger.info("reaper_found_stale_indexing_jobs", count=len(stale_episodes))
                    for ep in stale_episodes:
                        logger.info("reaper_resetting_stale_job", episode_id=ep.id)
                        ep.status = EpisodeStatus.SUMMARIZED  # Reset to SUMMARIZED to allow retry
                        ep.heartbeat = None
                    await session.commit()
            
        except Exception as e:
            logger.error("heartbeat_reaper_error", error=str(e))
        
        # Check every 60 seconds
        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass
    logger.info("heartbeat_reaper_stopped")


async def _episode_already_ingested(episode_id: str, qdrant_service) -> bool:
    """Check if episode already exists in Qdrant (async)."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    try:
        # Query Qdrant for any chunks with this episode_id
        results, _ = await qdrant_service.scroll(
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="episode_id",
                        match=MatchValue(value=episode_id)
                    )
                ]
            ),
            limit=1  # Just need to know if any exist
        )
        return len(results) > 0
    except Exception as e:
        logger.warning("idempotency_check_failed", episode_id=episode_id, error=str(e))
        # Fail-open: proceed with ingestion if check fails
        return False


async def process_batch_summarized_event(event_data: dict):
    """
    Process a BatchSummarized event asynchronously.
    Indexes all episodes in the batch sequentially for RAG.
    """
    global _active_batch_task, _active_episode_id
    _active_batch_task = asyncio.current_task()
    try:
        from podcast_transcriber_shared.events import BatchSummarized
        event = BatchSummarized(**event_data)
        
        bind_correlation_id(event.event_id)
        logger.info("batch_summarized_event_received", 
                    batch_id=event.batch_id, 
                    episode_count=len(event.episode_ids))

        # Acquire GPU Lock once for the entire batch (for embeddings)
        from podcast_transcriber_shared.gpu_lock import get_gpu_lock
        async with get_gpu_lock().acquire():
            logger.info("gpu_lock_acquired_for_batch_rag_indexing", batch_id=event.batch_id)
            
            manager = get_pipeline_status_manager()
            for episode_id in event.episode_ids:
                _active_episode_id = episode_id
                # Checks for cancellation signals are now handled by stop_monitor task
                # but we leave a check here as a fast-path for the next episode in queue
                if manager.is_stopped():
                    logger.info("pipeline_stopped_skipping_rag", episode_id=episode_id)
                    manager.update_service_status('rag', episode_id, "stopped", progress=0.0, log_message="Pipeline stopped by user")
                    continue

                await index_single_episode(episode_id, event.batch_id)

        logger.info("batch_rag_indexing_complete", batch_id=event.batch_id)
        return True

    except asyncio.CancelledError:
        logger.info("batch_rag_indexing_cancelled", batch_id=event.batch_id)
        raise
    except Exception as e:
        logger.error("batch_rag_indexing_error", error=str(e), exc_info=True)
        return False


async def index_single_episode(episode_id: str, batch_id: str = "default") -> bool:
    """Helper to index a single episode (refactored from previous process_summary_event)."""
    try:
        from podcast_transcriber_shared.database import (
            get_episode_by_id, 
            get_summary_by_episode_id,
            update_episode_status,
            EpisodeStatus
        )
        
        # Start heartbeat loop in background
        heartbeat_stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(heartbeat_loop(episode_id, heartbeat_stop))
        
        try:
            episode = await get_episode_by_id(episode_id, load_transcript=True)
            summary_record = await get_summary_by_episode_id(episode_id)
            
            if not episode or not episode.transcript_text:
                logger.error("episode_unsuitable_for_rag", episode_id=episode_id)
                return False

            # Report status
            await update_episode_status(episode_id, EpisodeStatus.INDEXING)
            manager = get_pipeline_status_manager()
            manager.update_service_status('rag', episode_id, "indexing", progress=0.1, log_message=f"Indexing (RAG) for: {episode.title}", additional_data={
                "episode_title": episode.title,
                "podcast_name": episode.podcast_name
            })

            summary_content = summary_record.content if summary_record else {}
            
            # Prepare metadata
            metadata = (episode.meta_data or {}).copy()
            metadata.update({
                "source_file": f"db://episodes/{episode_id}",
                "episode_title": episode.title,
                "podcast_name": episode.podcast_name,
                "episode_id": episode_id,
                "audio_url": episode.url,
                "summary_hook": summary_content.get("hook", ""),
                "key_takeaways": summary_content.get("key_takeaways", [])
            })
            
            # Chunking
            transcript_lines = get_transcript_body(episode.transcript_text)
            chunks = chunk_by_speaker_turns(transcript_lines)
            
            # Embed
            embedding_service = get_embedding_service()
            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings = await embedding_service.embed_batch(chunk_texts)
            
            # Qdrant
            qdrant_service = get_qdrant_service()
            num_inserted = await qdrant_service.insert_chunks(chunks, embeddings, metadata)
            
            # BM25
            try:
                hybrid_service = get_hybrid_retriever_service(
                    embeddings_service=embedding_service,
                    qdrant_service=qdrant_service
                )
                new_documents = [
                    Document(page_content=c["text"], metadata={**metadata, "speaker": c.get("speaker", "UNKNOWN"), "timestamp": c.get("timestamp", "00:00:00"), "chunk_index": i})
                    for i, c in enumerate(chunks)
                ]
                hybrid_service.add_documents(new_documents)
            except Exception as e:
                logger.warning("bm25_update_failed", episode_id=episode_id, error=str(e))
            
            # Cleanup and finalize
            await update_episode_status(episode_id, EpisodeStatus.INDEXED)
            await update_episode_status(episode_id, EpisodeStatus.COMPLETED) # Final stage
            # Cleanup status
            manager.update_service_status('rag', episode_id, "completed", progress=1.0, log_message=f"Indexing complete: {episode.title}")
            manager.clear_service_status('rag', episode_id)
            manager.redis.incr(f"{manager.SERVICE_STATS_PREFIX}rag:completed") if manager.redis else None
            
            return True
        
    except asyncio.CancelledError:
        logger.info("rag_indexing_cancelled", episode_id=episode_id)
        raise
    except Exception as e:
        logger.error("single_episode_rag_indexing_failed", episode_id=episode_id, error=str(e))
        return False
    finally:
        # Ensure heartbeat stops
        heartbeat_stop.set()
        await heartbeat_task
        


async def start_rag_event_subscriber():
    """Start the RAG event subscriber (Async)."""
    logger.info("rag_event_subscriber_starting", stream="STREAM_SUMMARIZED", group="rag_service_group")
    
    event_bus = get_event_bus()
    
    # Use Redis Streams with a consumer group for reliability
    await event_bus.subscribe(
        stream=event_bus.STREAM_BATCH_SUMMARIZED,
        group_name="rag_service_group",
        consumer_name="rag_worker_1",
        callback=process_batch_summarized_event
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
                    logger.critical("cancelling_rag_due_to_stop_signal", episode_id=_active_episode_id)
                    
                    # Mark current episode as failed
                    if _active_episode_id:
                        try:
                            from podcast_transcriber_shared.database import update_episode_status, EpisodeStatus
                            await update_episode_status(_active_episode_id, EpisodeStatus.FAILED)
                        except Exception as e:
                            logger.error("failed_to_update_episode_status_during_cancel", error=str(e))
                        
                        manager.update_service_status('rag', _active_episode_id, "cancelled", progress=0.0, log_message="Aborted: Stop signal received")

                    _active_batch_task.cancel()
        except Exception as e:
            logger.error("stop_monitor_error", error=str(e))


async def recover_stuck_episodes():
    """
    Recover episodes that were summarized but not indexed (e.g. due to restart).
    Also picks up 'INDEXING' episodes effectively resetting them.
    """
    try:
        from podcast_transcriber_shared.database import list_episodes, EpisodeStatus
        from podcast_transcriber_shared.gpu_lock import get_gpu_lock
        
        logger.info("checking_for_stuck_rag_episodes")
        
        # Find episodes that are ready for indexing or got stuck during it
        stuck_summarized = await list_episodes(status=EpisodeStatus.SUMMARIZED)
        stuck_indexing = await list_episodes(status=EpisodeStatus.INDEXING)
        
        stuck_episodes = stuck_summarized + stuck_indexing
        
        if not stuck_episodes:
            logger.info("no_stuck_rag_episodes_found")
            return

        logger.info("found_stuck_rag_episodes", count=len(stuck_episodes), ids=[e.id for e in stuck_episodes])
        
        # Acquire GPU lock for the recovery batch
        async with get_gpu_lock().acquire():
            logger.info("gpu_lock_acquired_for_rag_recovery")
            
            for episode in stuck_episodes:
                logger.info("recovering_rag_episode", episode_id=episode.id, status=episode.status)
                await index_single_episode(episode.id, batch_id="recovery_startup")
                
        logger.info("rag_recovery_batch_complete")
            
    except Exception as e:
        logger.error("rag_recovery_failed", error=str(e), exc_info=True)


if __name__ == "__main__":
    # Initialize services
    logger.info("initializing_rag_services")
    get_embedding_service()
    get_qdrant_service()
    
    # Run recovery and then subscriber
    async def main():
        monitor_task = asyncio.create_task(stop_monitor())
        try:
            await recover_stuck_episodes()
            await start_rag_event_subscriber()
        finally:
            _shutdown_event.set()
            monitor_task.cancel()
            await monitor_task

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
