"""
RAG Event Subscriber
Listens for EpisodeTranscribed events and processes transcripts for RAG.
"""
import asyncio
from pathlib import Path

from podcast_transcriber_shared.events import get_event_bus, EpisodeTranscribed
from services.embeddings import get_embedding_service
from services.qdrant_client import get_qdrant_service
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
    
    Args:
        episode_id: Unique episode identifier
        qdrant_service: Qdrant service instance
        
    Returns:
        True if episode exists in Qdrant, False otherwise
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
        # If check fails, proceed with ingestion (fail-open)
        return False


async def process_transcription_event(event_data: dict):
    """
    Process an EpisodeTranscribed event asynchronously.
    
    Called when a new transcript is available.
    Chunks the transcript and ingests into Qdrant + BM25 index.
    
    Args:
        event_data: Event data dictionary from Redis
    """
    try:
        # Parse event
        event = EpisodeTranscribed(**event_data)
        
        print(f"\n{'='*60}")
        print(f"📥 Received EpisodeTranscribed event")
        print(f"   Event ID: {event.event_id}")
        print(f"   Episode ID: {event.episode_id}")
        print(f"   Episode: {event.episode_title}")
        print(f"   Podcast: {event.podcast_name}")
        print(f"{'='*60}")
        
        # === IDEMPOTENCY CHECK ===
        # Check if this episode has already been ingested
        qdrant_service = get_qdrant_service()
        
        # Run blocking check in executor
        loop = asyncio.get_running_loop()
        already_ingested = await loop.run_in_executor(
            None, _episode_already_ingested, event.episode_id, qdrant_service
        )
        
        if already_ingested:
            print(f"⏭️  Episode already ingested, skipping: {event.episode_title}")
            print(f"   Episode ID: {event.episode_id}")
            print(f"{'='*60}\n")
            return
        
        # Fetch transcript from database
        from podcast_transcriber_shared.database import get_episode_by_id
        
        episode = await loop.run_in_executor(
            None, 
            lambda: asyncio.run(get_episode_by_id(event.episode_id, load_transcript=True))
        )
        
        if not episode:
            print(f"❌ Episode not found in database: {event.episode_id}")
            return
        
        if not episode.transcript_text:
            print(f"❌ No transcript text for episode: {event.episode_id}")
            return
        
        content = episode.transcript_text
        
        # Extract metadata from DB fields
        metadata = episode.meta_data or {}
        metadata["source_file"] = f"db://episodes/{event.episode_id}"  # Virtual path for reference
        metadata["episode_title"] = event.episode_title
        metadata["podcast_name"] = event.podcast_name
        
        # Extract transcript body
        transcript_lines = get_transcript_body(content)
        
        # Chunk by speaker turns
        chunks = chunk_by_speaker_turns(transcript_lines)
        
        print(f"📄 Extracted {len(chunks)} chunks from transcript")
        
        # Generate embeddings (blocking API call - run in executor)
        embedding_service = get_embedding_service()
        chunk_texts = [chunk["text"] for chunk in chunks]
        
        embeddings = await loop.run_in_executor(
            None, embedding_service.embed_batch, chunk_texts
        )
        
        print(f"🔢 Generated embeddings for {len(chunks)} chunks")
        
        # Store in Qdrant with episode_id for idempotency (blocking I/O)
        metadata["episode_id"] = event.episode_id
        
        num_inserted = await loop.run_in_executor(
            None, qdrant_service.insert_chunks, chunks, embeddings, metadata
        )
        
        print(f"✅ Inserted {num_inserted} chunks into Qdrant")
        
        # Update BM25 index incrementally (blocking pickle I/O)
        try:
            # Get or initialize hybrid service
            try:
                hybrid_service = get_hybrid_retriever_service()
            except ValueError:
                hybrid_service = get_hybrid_retriever_service(
                    embeddings_service=embedding_service,
                    qdrant_service=qdrant_service
                )
            
            # Convert chunks to Documents for BM25
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
            
            # Add incrementally to BM25 index (blocking pickle I/O)
            await loop.run_in_executor(
                None, hybrid_service.add_documents, new_documents
            )
            print(f"✅ Updated BM25 index with {len(new_documents)} documents")
            
        except Exception as e:
            print(f"⚠️  Warning: Failed to update BM25 index: {e}")
        
        print(f"{'='*60}")
        print(f"✅ Event processing complete: {event.episode_title}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ Error processing transcription event: {e}")
        import traceback
        traceback.print_exc()


def start_rag_event_subscriber():
    """Start the RAG event subscriber (blocking)."""
    print("\n" + "="*60)
    print("🚀 Starting RAG Event Subscriber")
    print("="*60)
    print("   Listening for: EpisodeTranscribed events")
    print("   Channel: episodes:transcribed")
    print("="*60 + "\n")
    
    # Get event bus and subscribe
    event_bus = get_event_bus()
    
    # This is a blocking call
    event_bus.subscribe(
        channel=event_bus.CHANNEL_TRANSCRIBED,
        callback=process_transcription_event
    )


async def start_subscriber_async():
    """
    Async wrapper for the event subscriber.
    
    Runs the blocking subscriber in a thread executor so it can be
    started as a background task from FastAPI lifespan without blocking
    the API server.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, start_rag_event_subscriber)


if __name__ == "__main__":
    # Initialize services before subscribing
    print("📦 Initializing RAG services...")
    get_embedding_service()
    get_qdrant_service()
    print("✅ Services initialized\n")
    
    # Start subscriber (blocking)
    start_rag_event_subscriber()
