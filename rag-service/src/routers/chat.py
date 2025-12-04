"""
Chat Router
Handles Q&A queries with episode-scoped context stuffing or vector search.
"""
from fastapi import APIRouter, HTTPException
import time
import os
from pathlib import Path

from models import ChatRequest, ChatResponse, SourceCitation
from services.gemini_client import get_chat_client
from utils.chunking import extract_metadata_from_transcript

router = APIRouter(prefix="/chat", tags=["chat"])


def load_transcript_file(podcast_name: str, episode_title: str) -> str:
    """
    Load full transcript from filesystem.
    
    Args:
        podcast_name: Podcast name
        episode_title: Episode title
        
    Returns:
        Full transcript text
    """
    # Look in shared/output directory
    base_path = Path("../shared/output") / podcast_name
    
    if not base_path.exists():
        raise FileNotFoundError(f"Podcast directory not found: {podcast_name}")
    
    # Find transcript file matching episode title
    for file in base_path.glob("*.txt"):
        content = file.read_text(encoding='utf-8')
        metadata = extract_metadata_from_transcript(content)
        
        if metadata["episode_title"] == episode_title:
            return content
    
    raise FileNotFoundError(f"Transcript not found for episode: {episode_title}")


@router.post("", response_model=ChatResponse)
async def ask_question(request: ChatRequest):
    """
    Answer a question using episode-scoped full transcript context or legacy vector search.
    
    If episode_title is provided, uses context stuffing with full transcript.
    Otherwise, falls back to vector search (deprecated).
    """
    try:
        start_time = time.time()
        
        # Episode-scoped mode with full context stuffing
        if hasattr(request, 'episode_title') and request.episode_title:
            try:
                # Load full transcript
                # Extract podcast name from existing summaries/metadata
                # For now, we'll need to search for it
                from services.summaries_service import get_summary_by_episode_title
                summary = get_summary_by_episode_title(request.episode_title)
                
                if not summary:
                    raise ValueError(f"Episode not found: {request.episode_title}")
                
                transcript_text = load_transcript_file(
                    summary["podcast_name"],
                    request.episode_title
                )
                
                # Use chat client with full transcript
                chat_client = get_chat_client()
                response = chat_client.answer_with_full_transcript(
                    question=request.question,
                    transcript_text=transcript_text,
                    episode_title=request.episode_title,
                    podcast_name=summary["podcast_name"],
                    conversation_history=request.conversation_history
                )
                
                processing_time = (time.time() - start_time) * 1000
                
                return ChatResponse(
                    answer=response["answer"],
                    sources=[],  # No source citations needed for full context
                    processing_time_ms=processing_time
                )
                
            except Exception as e:
                raise HTTPException(
                    status_code=404,
                    detail=f"Error loading transcript: {str(e)}"
                )
        
        # Legacy mode: vector search (deprecated for new usage)
        else:
            # This path is kept for backwards compatibility
            # but should be phased out
            return ChatResponse(
                answer="Please specify an episode_title for episode-scoped chat. Cross-episode search has been deprecated.",
                sources=[],
                processing_time_ms=(time.time() - start_time) * 1000
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing question: {str(e)}")
