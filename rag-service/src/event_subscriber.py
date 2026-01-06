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


async def process_summary_event(event_data: dict) -> bool:
    """
    Process an EpisodeSummarized event asynchronously.
    Returns True if successful, False otherwise.
    """
    try:
        # Parse event
        event = EpisodeSummarized(**event_data)
        
        # Bind correlation ID for tracking
        bind_correlation_id(event.event_id)
        logger.info("episode_summarized_event_received", 
                   event_id=event.event_id, 
                   episode_id=event.episode_id,
                   episode_title=event.episode_title,
                   podcast_name=event.podcast_name)
        
        # Report status (Async)
        manager = get_pipeline_status_manager()
        manager.update_service_status('rag', event.episode_id, "indexing", progress=0.1, additional_data={
            "episode_title": event.episode_title,
            "podcast_name": event.podcast_name
        })
        
        # === ATOMIC IDEMPOTENCY CHECK ===
        from podcast_transcriber_shared.idempotency import get_idempotency_manager
        
        idempotency_manager = get_idempotency_manager()
        idempotency_key = idempotency_manager.make_key("rag", "transcribed", event.episode_id)
        
        # Atomic check-and-set: returns True if this is the first time processing
        is_first_time = await idempotency_manager.check_and_set(idempotency_key, ttl=86400)
        
        if not is_first_time:
            logger.info("episode_already_processed_skipping", 
                       episode_id=event.episode_id, 
                       title=event.episode_title,
                       idempotency_key=idempotency_key)
            return True
        
        # Fetch transcript and summary from database (Async)
        from podcast_transcriber_shared.database import get_episode_by_id, get_summary_by_episode_id
        
        episode = await get_episode_by_id(event.episode_id, load_transcript=True)
        summary_record = await get_summary_by_episode_id(event.episode_id)
        
        if not episode or not episode.transcript_text:
            logger.error("no_transcript_text_for_episode", episode_id=event.episode_id)
            return True  # Acknowledge to remove invalid event
        
        summary_content = summary_record.content if summary_record else {}
        
        content = episode.transcript_text
        metadata = episode.meta_data or {}
        metadata["source_file"] = f"db://episodes/{event.episode_id}"
        metadata["episode_title"] = event.episode_title
        metadata["podcast_name"] = event.podcast_name
        metadata["episode_id"] = event.episode_id
        
        # Include summary fields in metadata for context
        if summary_content:
            metadata["summary_hook"] = summary_content.get("hook", "")
            metadata["key_takeaways"] = summary_content.get("key_takeaways", [])
        
        # Chunking
        transcript_lines = get_transcript_body(content)
        chunks = chunk_by_speaker_turns(transcript_lines)
        logger.info("transcript_chunked", episode_id=event.episode_id, chunk_count=len(chunks))
        
        # Generate embeddings (Async)
        embedding_service = get_embedding_service()
        chunk_texts = [chunk["text"] for chunk in chunks]
        
        embeddings = await embedding_service.embed_batch(chunk_texts)
        
        # Store in Qdrant (async)
        manager.update_service_status('rag', event.episode_id, "indexing", progress=0.7, log_message="Uploading embeddings to vector store...")
        num_inserted = await qdrant_service.insert_chunks(chunks, embeddings, metadata)
        logger.info("chunks_inserted_to_qdrant", episode_id=event.episode_id, chunk_count=num_inserted)
        
        # Update BM25 index (blocking)
        try:
            hybrid_service = get_hybrid_retriever_service(
                embeddings_service=embedding_service,
                qdrant_service=qdrant_service
            )
            
            new_documents = []
            for i, chunk in enumerate(chunks):
                doc = Document(
                    page_content=chunk["text"],
                    metadata={
                        "episode_title": event.episode_title,
                        "podcast_name": event.podcast_name,
                        "speaker": chunk.get("speaker", "UNKNOWN"),
                        "timestamp": chunk.get("timestamp", "00:00:00"),
                        "chunk_index": i,
                        "source_file": metadata.get("source_file", "")
                    }
                )
                new_documents.append(doc)
            
            hybrid_service.add_documents(new_documents)
            logger.info("bm25_index_updated", episode_id=event.episode_id, document_count=len(new_documents))
            
        except Exception as e:
            logger.warning("bm25_index_update_failed", episode_id=event.episode_id, error=str(e))
        
        # Clear individual status and increment completed count
        manager.clear_service_status('rag', event.episode_id)
        manager.redis.incr(f"{manager.SERVICE_STATS_PREFIX}rag:completed") if manager.redis else None
        
        logger.info("rag_processing_complete", episode_id=event.episode_id, title=event.episode_title)
        return True
        
    except Exception as e:
        logger.error("rag_event_processing_error", episode_id=event.episode_id, error=str(e), exc_info=True)
        return False


async def start_rag_event_subscriber():
    """Start the RAG event subscriber (Async)."""
    logger.info("rag_event_subscriber_starting", stream="STREAM_SUMMARIZED", group="rag_service_group")
    
    event_bus = get_event_bus()
    
    # Use Redis Streams with a consumer group for reliability
    await event_bus.subscribe(
        stream=event_bus.STREAM_SUMMARIZED,
        group_name="rag_service_group",
        consumer_name="rag_worker_1",
        callback=process_summary_event
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
