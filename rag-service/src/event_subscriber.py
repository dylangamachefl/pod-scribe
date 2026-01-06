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
            
            for episode_id in event.episode_ids:
                await index_single_episode(episode_id, event.batch_id)

        logger.info("batch_rag_indexing_complete", batch_id=event.batch_id)

    except Exception as e:
        logger.error("batch_rag_indexing_error", error=str(e), exc_info=True)


async def index_single_episode(episode_id: str, batch_id: str = "default") -> bool:
    """Helper to index a single episode (refactored from previous process_summary_event)."""
    try:
        from podcast_transcriber_shared.database import get_episode_by_id, get_summary_by_episode_id
        
        episode = await get_episode_by_id(episode_id, load_transcript=True)
        summary_record = await get_summary_by_episode_id(episode_id)
        
        if not episode or not episode.transcript_text:
            logger.error("episode_unsuitable_for_rag", episode_id=episode_id)
            return False

        # Report status
        manager = get_pipeline_status_manager()
        manager.update_service_status('rag', episode_id, "indexing", progress=0.1, additional_data={
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
        
        # Cleanup
        manager.clear_service_status('rag', episode_id)
        manager.redis.incr(f"{manager.SERVICE_STATS_PREFIX}rag:completed") if manager.redis else None
        
        return True

    except Exception as e:
        logger.error("single_episode_rag_indexing_failed", episode_id=episode_id, error=str(e))
        return False
        
    except Exception as e:
        logger.error("rag_event_processing_error", episode_id=event.episode_id, error=str(e), exc_info=True)
        return False


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


if __name__ == "__main__":
    # Initialize services
    logger.info("initializing_rag_services")
    get_embedding_service()
    get_qdrant_service()
    
    # Run async subscriber
    try:
        asyncio.run(start_rag_event_subscriber())
    except KeyboardInterrupt:
        pass
