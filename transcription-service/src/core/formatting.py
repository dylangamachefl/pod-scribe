"""
Text Formatting Utilities
Functions for formatting transcripts and sanitizing filenames.
"""
import re
from typing import Dict


def sanitize_filename(filename: str) -> str:
    """Remove invalid characters from filename.
    
    Args:
        filename: Original filename string
        
    Returns:
        Sanitized filename safe for use on filesystem
    """
    # Replace invalid chars with underscore
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limit length
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    return sanitized.strip()


def format_transcript(result: Dict) -> str:
    """Format transcript with speaker labels and timestamps.
    
    Args:
        result: Transcript result dict with segments
        
    Returns:
        Formatted transcript string with timestamps and speaker labels
    """
    lines = []
    
    for segment in result.get("segments", []):
        start_time = segment.get("start", 0)
        text = segment.get("text", "").strip()
        speaker = segment.get("speaker", "UNKNOWN")
        
        # Format timestamp as HH:MM:SS
        hours = int(start_time // 3600)
        minutes = int((start_time % 3600) // 60)
        seconds = int(start_time % 60)
        timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        lines.append(f"[{speaker}] {timestamp}: {text}")
    
    return "\n".join(lines)


def format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS timestamp.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
