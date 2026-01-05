from fastapi import APIRouter, HTTPException
from pathlib import Path

from models import IngestRequest, IngestDBRequest, IngestResponse

from utils.chunking import (
    extract_metadata_from_transcript,
    get_transcript_body,
    chunk_by_speaker_turns
)
from services.embeddings import get_embedding_service
from services.qdrant_service import get_qdrant_service
from podcast_transcriber_shared.database import get_episode_by_id
from langchain_core.documents import Document

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
async def ingest_file(request: IngestRequest):
    # ... existing code (unchanged) ...
    try:
        file_path = Path(request.file_path)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")
        
        if file_path.suffix.lower() != '.txt':
            raise HTTPException(status_code=400, detail="Only .txt transcript files are supported")
        
        # Read transcript
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract metadata
        metadata = extract_metadata_from_transcript(content)
        metadata["source_file"] = str(file_path)
        
        return await _process_ingestion(content, metadata)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting file: {str(e)}")


@router.post("/db", response_model=IngestResponse)
async def ingest_from_db(request: IngestDBRequest):
    """
    Ingest a transcript directly from the database by episode_id.
    Useful for repairing failed RAG indexing for already-transcribed episodes.
    """
    try:
        episode = await get_episode_by_id(request.episode_id, load_transcript=True)
        
        if not episode or not episode.transcript_text:
            raise HTTPException(
                status_code=404, 
                detail=f"Episode or transcript not found in DB: {request.episode_id}"
            )
        
        # Extract metadata
        metadata = episode.meta_data or {}
        metadata["source_file"] = f"db://episodes/{request.episode_id}"
        metadata["episode_id"] = request.episode_id
        metadata["episode_title"] = episode.title
        metadata["podcast_name"] = episode.podcast_name
        
        return await _process_ingestion(episode.transcript_text, metadata)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting from DB: {str(e)}")


async def _process_ingestion(content: str, metadata: dict) -> IngestResponse:
    """Helper to process transcript content into Qdrant and Hybrid Index."""
    # Extract transcript body
    transcript_lines = get_transcript_body(content)
    
    # Chunk by speaker turns
    chunks = chunk_by_speaker_turns(transcript_lines)
    
    # Generate embeddings
    embedding_service = get_embedding_service()
    chunk_texts = [chunk["text"] for chunk in chunks]
    embeddings = embedding_service.embed_batch(chunk_texts)
    
    # Store in Qdrant
    qdrant_service = get_qdrant_service()
    num_inserted = qdrant_service.insert_chunks(chunks, embeddings, metadata)
    
    # Update hybrid search indexes incrementally
    try:
        from services.hybrid_retriever import get_hybrid_retriever_service
        
        try:
            hybrid_service = get_hybrid_retriever_service()
        except ValueError:
            # First time initialization
            hybrid_service = get_hybrid_retriever_service(
                embeddings_service=embedding_service,
                qdrant_service=qdrant_service
            )
        
        # Convert chunks to Documents for BM25 indexing
        new_documents = []
        for i, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk["text"],
                metadata={
                    "episode_title": metadata.get("episode_title", "Unknown"),
                    "podcast_name": metadata.get("podcast_name", "Unknown"),
                    "speaker": chunk.get("speaker", "UNKNOWN"),
                    "timestamp": chunk.get("timestamp", "00:00:00"),
                    "chunk_index": i,
                    "source_file": metadata.get("source_file", ""),
                    "episode_id": metadata.get("episode_id", "")
                }
            )
            new_documents.append(doc)
        
        # Incrementally add to BM25 index
        print(f"Adding {len(new_documents)} documents to BM25 index...")
        hybrid_service.add_documents(new_documents)
        print(f"✅ BM25 index updated incrementally")
    except Exception as e:
        print(f"⚠️ Warning: Failed to update hybrid indexes: {str(e)}")
    
    return IngestResponse(
        status="success",
        message=f"Successfully ingested {num_inserted} chunks",
        chunks_created=num_inserted,
        episode_title=metadata.get("episode_title"),
        podcast_name=metadata.get("podcast_name")
    )


@router.get("/stats")
async def get_ingestion_stats():
    # ... stats code ...
    try:
        qdrant_service = get_qdrant_service()
        stats = qdrant_service.get_collection_stats()
        
        return {
            "total_chunks": stats["total_points"],
            "collection_name": stats["collection_name"],
            "embedding_dimension": stats["vector_dimension"]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving stats: {str(e)}")
