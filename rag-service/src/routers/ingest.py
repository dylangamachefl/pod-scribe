"""
Ingest Router
Manual file ingestion endpoint (optional - file watcher handles auto-ingestion).
"""
from fastapi import APIRouter, HTTPException
from pathlib import Path

from models import IngestRequest, IngestResponse

from utils.chunking import (
    extract_metadata_from_transcript,
    get_transcript_body,
    chunk_by_speaker_turns
)
from services.embeddings import get_embedding_service
from services.qdrant_client import get_qdrant_service

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
async def ingest_file(request: IngestRequest):
    """
    Manually ingest a transcript file into the RAG system.
    
    This endpoint is optional since the file watcher handles auto-ingestion.
    Useful for re-processing files or manual triggers.
    """
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
        
        return IngestResponse(
            status="success",
            message=f"Successfully ingested {num_inserted} chunks",
            chunks_created=num_inserted,
            episode_title=metadata.get("episode_title"),
            podcast_name=metadata.get("podcast_name")
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting file: {str(e)}")


@router.get("/stats")
async def get_ingestion_stats():
    """
    Get statistics about ingested content.
    """
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
