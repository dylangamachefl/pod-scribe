"""
Transcript parsing utilities.
Extracts metadata from transcript files.
"""
from typing import Dict
import re
from datetime import datetime


def extract_metadata_from_transcript(content: str, filename: str = None) -> Dict:
    """
    Extract metadata from transcript file header.
    
    Args:
        content: Full transcript content
        filename: Optional filename to use as fallback for episode title
        
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
    
    # Extract metadata from header (first 30 lines)
    for line in lines[:30]:
        # Handle both "Title:" and "Episode:" prefixes
        if line.startswith("Title:") or line.startswith("Episode:"):
            title = line.replace("Title:", "").replace("Episode:", "").strip()
            if title:
                metadata["episode_title"] = title
        elif line.startswith("Podcast:"):
            podcast = line.replace("Podcast:", "").strip()
            if podcast:
                metadata["podcast_name"] = podcast
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
    
    # Fallback: Use filename if episode title is still unknown
    if metadata["episode_title"] == "Unknown Episode" and filename:
        # Remove .txt extension and use filename as title
        title_from_filename = filename.replace(".txt", "").strip()
        if title_from_filename:
            metadata["episode_title"] = title_from_filename
    
    # Extract unique speakers from transcript content if not found in metadata
    if not metadata["speakers"]:
        speaker_pattern = re.compile(r'\[SPEAKER_(\d+)\]')
        speaker_matches = speaker_pattern.findall(content)
        if speaker_matches:
            # Get unique speaker IDs and format them
            unique_speakers = sorted(set(speaker_matches))
            metadata["speakers"] = [f"Speaker {s}" for s in unique_speakers]
    
    return metadata
