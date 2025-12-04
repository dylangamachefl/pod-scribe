"""
Summaries Router
Retrieves generated summaries for episodes.
"""
from fastapi import APIRouter, HTTPException
from typing import List
import json
from pathlib import Path

from models import SummaryResponse
from config import SUMMARY_OUTPUT_PATH

router = APIRouter(prefix="/summaries", tags=["summaries"])


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
                
                # Extract speakers from summary if available
                speakers = data.get("speakers", [])
                if not speakers:
                    # Try to infer from source file (basic heuristic)
                    speakers = ["Multiple Speakers"]
                
                summaries.append(SummaryResponse(
                    episode_title=data.get("episode_title", "Unknown"),
                    podcast_name=data.get("podcast_name", "Unknown"),
                    summary=data.get("summary", "No summary available"),
                    key_topics=data.get("key_topics", []),
                    speakers=speakers,
                    duration=None,  # Could extract from transcript if needed
                    created_at=data.get("processed_date", "Unknown")
                ))
        
        # Sort by created_at (most recent first)
        summaries.sort(key=lambda x: x.created_at, reverse=True)
        
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
                    speakers = data.get("speakers", ["Multiple Speakers"])
                    
                    return SummaryResponse(
                        episode_title=data.get("episode_title", "Unknown"),
                        podcast_name=data.get("podcast_name", "Unknown"),
                        summary=data.get("summary", "No summary available"),
                        key_topics=data.get("key_topics", []),
                        speakers=speakers,
                        duration=None,
                        created_at=data.get("processed_date", "Unknown")
                    )
        
        raise HTTPException(status_code=404, detail=f"Summary not found for episode: {episode_title}")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving summary: {str(e)}")
