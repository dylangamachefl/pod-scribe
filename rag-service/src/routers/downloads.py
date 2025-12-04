"""
Downloads Router
Provides endpoints for downloading transcripts and summaries.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pathlib import Path
import json

from config import SUMMARY_OUTPUT_PATH

router = APIRouter(prefix="/download", tags=["downloads"])


@router.get("/transcript/{podcast_name}/{episode_name}", response_class=PlainTextResponse)
async def download_transcript(podcast_name: str, episode_name: str):
    """
    Download full transcript for an episode.
    
    Args:
        podcast_name: Podcast name
        episode_name: Episode name/title
        
    Returns:
        Plain text transcript content
    """
    try:
        # Look in shared/output directory
        base_path = Path("../shared/output") / podcast_name
        
        if not base_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Podcast directory not found: {podcast_name}"
            )
        
        # Find transcript file matching episode
        for file in base_path.glob("*.txt"):
            # Simple matching by episode name in filename or content
            if episode_name.lower() in file.stem.lower():
                return file.read_text(encoding='utf-8')
        
        raise HTTPException(
            status_code=404,
            detail=f"Transcript not found for episode: {episode_name}"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading transcript: {str(e)}"
        )


@router.get("/summary/{episode_title}", response_class=PlainTextResponse)
async def download_summary(episode_title: str):
    """
    Download formatted summary for an episode.
    
    Args:
        episode_title: Episode title
        
    Returns:
        Formatted summary as plain text
    """
    try:
        if not SUMMARY_OUTPUT_PATH.exists():
            raise HTTPException(
                status_code=404,
                detail="Summary directory not found"
            )
        
        # Search for matching summary file
        for summary_file in SUMMARY_OUTPUT_PATH.glob("*_summary.json"):
            with open(summary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                if data.get("episode_title") == episode_title:
                    # Format summary as readable text
                    formatted = f"""Episode: {data.get('episode_title', 'Unknown')}
Podcast: {data.get('podcast_name', 'Unknown')}
Date: {data.get('processed_date', 'Unknown')}

SUMMARY
=======
{data.get('summary', 'No summary available')}

KEY TOPICS
==========
{chr(10).join(f"- {topic}" for topic in data.get('key_topics', []))}

INSIGHTS
========
{chr(10).join(f"- {insight}" for insight in data.get('insights', []))}

NOTABLE QUOTES
==============
{chr(10).join(f'- "{quote}"' for quote in data.get('quotes', []))}
"""
                    return formatted
        
        raise HTTPException(
            status_code=404,
            detail=f"Summary not found for episode: {episode_title}"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving summary: {str(e)}"
        )
