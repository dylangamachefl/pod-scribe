"""
Summaries Router
Handles summary generation and retrieval endpoints.
"""
from fastapi import APIRouter, HTTPException
from typing import List
import json
from pathlib import Path

from models import SummarizeRequest, SummaryResponse
from config import SUMMARY_OUTPUT_PATH
from services.gemini_service import get_gemini_service
from utils.transcript_parser import extract_metadata_from_transcript
from podcast_transcriber_shared.database import get_session_maker, Summary
from sqlalchemy import select

router = APIRouter(prefix="/summaries", tags=["summaries"])





@router.post("/generate", response_model=SummaryResponse)
async def generate_summary(request: SummarizeRequest):
    """
    Generate a summary for a transcript (manual trigger).
    """
    try:
        gemini_service = get_gemini_service()
        
        # Generate summary (returns StructuredSummary Pydantic model)
        result = gemini_service.summarize_transcript(
            request.transcript_text,
            request.episode_title,
            request.podcast_name
        )
        
        # Save summary with complete structured data
        # Create safe filename from episode title
        safe_filename = "".join(c for c in request.episode_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_filename = safe_filename.replace(' ', '_')
        summary_file = SUMMARY_OUTPUT_PATH / f"{safe_filename}_summary.json"
        
        # Combine request metadata with structured summary
        complete_summary_data = {
            "episode_title": request.episode_title,
            "podcast_name": request.podcast_name,
            # Unpack all structured summary fields from Pydantic model
            **result.model_dump()
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(complete_summary_data, f, indent=2)
        
        # Return the structured data as SummaryResponse
        return SummaryResponse(**complete_summary_data)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")


@router.get("", response_model=List[SummaryResponse])
async def list_summaries():
    """
    List all available episode summaries from the database.
    """
    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            # Query summaries from DB, newest first
            query = select(Summary).order_by(Summary.created_at.desc())
            result = await session.execute(query)
            db_summaries = result.scalars().all()
            
            response = []
            for s in db_summaries:
                try:
                    # Content is already a dict matching SummaryResponse structure
                    response.append(SummaryResponse(**s.content))
                except Exception as e:
                    print(f"⚠️ Error parsing summary {s.id}: {e}")
                    continue
            
            return response
    
    except Exception as e:
        print(f"❌ Error listing summaries: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing summaries: {str(e)}")


@router.get("/{episode_title}", response_model=SummaryResponse)
async def get_summary(episode_title: str):
    """
    Get summary for a specific episode by title from database.
    """
    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            # Search within the JSONB content for episode_title
            # Note: Postgres JSONB operator ->> returns text
            query = select(Summary).where(
                Summary.content["episode_title"].astext == episode_title
            )
            result = await session.execute(query)
            summary = result.scalar_one_or_none()
            
            if not summary:
                raise HTTPException(status_code=404, detail=f"Summary not found for episode: {episode_title}")
                
            return SummaryResponse(**summary.content)
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error retrieving summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving summary: {str(e)}")
