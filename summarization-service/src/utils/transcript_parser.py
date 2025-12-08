"""
Transcript parsing utilities.
Extracts metadata from transcript files.
"""
from typing import Dict
import re
from datetime import datetime


def extract_metadata_from_transcript(content: str) -> Dict:
    """
    Extract metadata from transcript file header.
    
    Args:
        content: Full transcript content
        
    Returns:
        Dictionary with episode_title, podcast_name, processed_date, speakers, duration, and audio_url
    """
    metadata = {
        "episode_title": "Unknown Episode",
        "podcast_name": "Unknown Podcast",
        "processed_date": datetime.now().isoformat(),
        "speakers": [],
        "duration": None,
        "audio_url": None
    }
    
    lines = content.split('\n')
    
    for line in lines[:30]:  # Check first 30 lines for metadata
        if line.startswith("Episode:"):
            metadata["episode_title"] = line.replace("Episode:", "").strip()
        elif line.startswith("Podcast:"):
            metadata["podcast_name"] = line.replace("Podcast:", "").strip()
        elif line.startswith("Processed:"):
            metadata["processed_date"] = line.replace("Processed:", "").strip()
        elif line.startswith("Duration:"):
            metadata["duration"] = line.replace("Duration:", "").strip()
        elif line.startswith("Audio URL:"):
            metadata["audio_url"] = line.replace("Audio URL:", "").strip()
        elif line.startswith("Speakers:"):
            # Parse comma-separated speaker list
            speakers_str = line.replace("Speakers:", "").strip()
            if speakers_str:
                metadata["speakers"] = [s.strip() for s in speakers_str.split(",")]
    
    return metadata
