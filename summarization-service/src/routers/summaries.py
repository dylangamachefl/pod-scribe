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
        
        # Generate summary
        result = gemini_service.summarize_transcript(
            request.transcript_text,
            request.episode_title,
            request.podcast_name
        )
        
        # Save summary
        # Create safe filename from episode title
        safe_filename = "".join(c for c in request.episode_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_filename = safe_filename.replace(' ', '_')
        summary_file = SUMMARY_OUTPUT_PATH / f"{safe_filename}_summary.json"
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                "episode_title": request.episode_title,
                "podcast_name": request.podcast_name,
                "summary": result.get("summary", ""),
                "key_topics": result.get("key_topics", []),
                "insights": result.get("insights", []),
                "quotes": result.get("quotes", []),
                "processing_time_ms": result.get("processing_time_ms", 0)
            }, f, indent=2)
        
        return SummaryResponse(
            episode_title=request.episode_title,
            podcast_name=request.podcast_name,
            summary=result.get("summary", ""),
            key_topics=result.get("key_topics", []),
            insights=result.get("insights", []),
            quotes=result.get("quotes", []),
            speakers=result.get("speakers", []),
            duration=result.get("duration"),
            audio_url=result.get("audio_url"),
            processing_time_ms=result.get("processing_time_ms", 0)
        )
    
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
                
                summaries.append(SummaryResponse(
                    episode_title=data.get("episode_title", "Unknown"),
                    podcast_name=data.get("podcast_name", "Unknown"),
                    summary=data.get("summary", "No summary available"),
                    key_topics=data.get("key_topics", []),
                    insights=data.get("insights", []),
                    quotes=data.get("quotes", []),
                    speakers=data.get("speakers", []),
                    duration=data.get("duration"),
                    audio_url=data.get("audio_url"),
                    processing_time_ms=data.get("processing_time_ms"),
                    created_at=data.get("processed_date", "Unknown")
                ))
        
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
                    return SummaryResponse(
                        episode_title=data.get("episode_title", "Unknown"),
                        podcast_name=data.get("podcast_name", "Unknown"),
                        summary=data.get("summary", "No summary available"),
                        key_topics=data.get("key_topics", []),
                        insights=data.get("insights", []),
                        quotes=data.get("quotes", []),
                        speakers=data.get("speakers", []),
                        duration=data.get("duration"),
                        audio_url=data.get("audio_url"),
                        processing_time_ms=data.get("processing_time_ms"),
                        created_at=data.get("processed_date", "Unknown")
                    )
        
        raise HTTPException(status_code=404, detail=f"Summary not found for episode: {episode_title}")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving summary: {str(e)}")
