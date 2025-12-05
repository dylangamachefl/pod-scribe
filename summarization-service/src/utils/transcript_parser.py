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
        Dictionary with episode_title, podcast_name, and processed_date
    """
    metadata = {
        "episode_title": "Unknown Episode",
        "podcast_name": "Unknown Podcast",
        "processed_date": datetime.now().isoformat()
    }
    
    lines = content.split('\n')
    
    for line in lines[:20]:  # Check first 20 lines for metadata
        if line.startswith("Episode:"):
            metadata["episode_title"] = line.replace("Episode:", "").strip()
        elif line.startswith("Podcast:"):
            metadata["podcast_name"] = line.replace("Podcast:", "").strip()
        elif line.startswith("Processed:"):
            metadata["processed_date"] = line.replace("Processed:", "").strip()
    
    return metadata
