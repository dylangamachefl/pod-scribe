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
    List all available episode summaries.
    """
    try:
        summaries = []
        
        if not SUMMARY_OUTPUT_PATH.exists():
            return summaries
        
        for summary_file in SUMMARY_OUTPUT_PATH.glob("*_summary.json"):
            with open(summary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Data is now properly structured - directly create response model
                # Handle both old format (with nested JSON) and new format
                try:
                    summaries.append(SummaryResponse(**data))
                except Exception as e:
                    print(f"⚠️ Error loading summary {summary_file.name}: {e}")
                    # Skip malformed summaries
                    continue
        
        # Sort by created_at (most recent first)
        summaries.sort(key=lambda x: x.created_at or "", reverse=True)
        
        return summaries
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing summaries: {str(e)}")


@router.get("/{episode_title}", response_model=SummaryResponse)
async def get_summary(episode_title: str):
    """
    Get summary for a specific episode by title.
    """
    try:
        # Search for matching summary file
        for summary_file in SUMMARY_OUTPUT_PATH.glob("*_summary.json"):
            with open(summary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                if data.get("episode_title") == episode_title:
                    # Data is now properly structured - directly create response model
                    try:
                        return SummaryResponse(**data)
                    except Exception as e:
                        print(f"⚠️ Error parsing summary for {episode_title}: {e}")
                        raise HTTPException(
                            status_code=500, 
                            detail=f"Error parsing summary data: {str(e)}"
                        )
        
        raise HTTPException(status_code=404, detail=f"Summary not found for episode: {episode_title}")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving summary: {str(e)}")
