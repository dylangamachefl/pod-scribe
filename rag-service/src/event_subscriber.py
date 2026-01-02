"""
RAG Event Subscriber
Listens for EpisodeTranscribed events and processes transcripts for RAG.
"""
import asyncio
from pathlib import Path

from podcast_transcriber_shared.events import get_event_bus, EpisodeTranscribed
from podcast_transcriber_shared.status_monitor import get_pipeline_status_manager
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


def _episode_already_ingested(episode_id: str, qdrant_service) -> bool:
    """
    Check if episode has already been ingested into Qdrant.
    """
    try:
        # Query Qdrant for any chunks with this episode_id
        results, _ = qdrant_service.client.scroll(
            collection_name=qdrant_service.collection_name,
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
        print(f"⚠️  Warning: Could not check for duplicates: {e}")
        # Fail-open: proceed with ingestion if check fails
        return False


async def process_transcription_event(event_data: dict):
    """
    Process an EpisodeTranscribed event asynchronously.
    """
    try:
        # Parse event
        event = EpisodeTranscribed(**event_data)
        
        print(f"\n{'='*60}")
        print(f"📥 Received EpisodeTranscribed event")
        print(f"   Event ID: {event.event_id}")
        print(f"   Episode: {event.episode_title}")
        print(f"{'='*60}")
        
        # Report status
        manager = get_pipeline_status_manager()
        manager.set_service_status('rag', event.episode_id, {
            "episode_title": event.episode_title,
            "podcast_name": event.podcast_name,
            "stage": "indexing"
        })
        
        # === IDEMPOTENCY CHECK ===
        qdrant_service = get_qdrant_service()
        
        loop = asyncio.get_running_loop()
        already_ingested = await loop.run_in_executor(
            None, _episode_already_ingested, event.episode_id, qdrant_service
        )
        
        if already_ingested:
            print(f"⏭️  Episode already ingested, skipping: {event.episode_title}")
            return
        
        # Fetch transcript from database (Async)
        from podcast_transcriber_shared.database import get_episode_by_id
        
        episode = await get_episode_by_id(event.episode_id, load_transcript=True)
        
        if not episode or not episode.transcript_text:
            print(f"❌ No transcript text for episode: {event.episode_id}")
            return
        
        content = episode.transcript_text
        metadata = episode.meta_data or {}
        metadata["source_file"] = f"db://episodes/{event.episode_id}"
        metadata["episode_title"] = event.episode_title
        metadata["podcast_name"] = event.podcast_name
        metadata["episode_id"] = event.episode_id
        
        # Chunking
        transcript_lines = get_transcript_body(content)
        chunks = chunk_by_speaker_turns(transcript_lines)
        print(f"📄 Extracted {len(chunks)} chunks")
        
        # Generate embeddings (blocking)
        embedding_service = get_embedding_service()
        chunk_texts = [chunk["text"] for chunk in chunks]
        
        embeddings = await loop.run_in_executor(
            None, embedding_service.embed_batch, chunk_texts
        )
        
        # Store in Qdrant (blocking)
        num_inserted = await loop.run_in_executor(
            None, qdrant_service.insert_chunks, chunks, embeddings, metadata
        )
        print(f"✅ Inserted {num_inserted} chunks into Qdrant")
        
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
            
            await loop.run_in_executor(
                None, hybrid_service.add_documents, new_documents
            )
            print(f"✅ Updated BM25 index")
            
        except Exception as e:
            print(f"⚠️  Failed to update BM25 index: {e}")
        
        # Clear individual status and increment completed count
        manager.clear_service_status('rag', event.episode_id)
        manager.redis.incr(f"{manager.SERVICE_STATS_PREFIX}rag:completed") if manager.redis else None
        
        print(f"✅ Processing complete: {event.episode_title}\n")
        
    except Exception as e:
        print(f"❌ Error processing event: {e}")
        import traceback
        traceback.print_exc()


async def start_rag_event_subscriber():
    """Start the RAG event subscriber (Async)."""
    print("\n" + "="*60)
    print("🚀 Starting RAG Event Subscriber")
    print("="*60)
    
    event_bus = get_event_bus()
    
    # This is now an awaitable call that runs indefinitely
    await event_bus.subscribe(
        channel=event_bus.CHANNEL_TRANSCRIBED,
        callback=process_transcription_event
    )


if __name__ == "__main__":
    # Initialize services
    print("📦 Initializing RAG services...")
    get_embedding_service()
    get_qdrant_service()
    
    # Run async subscriber
    try:
        asyncio.run(start_rag_event_subscriber())
    except KeyboardInterrupt:
        pass
