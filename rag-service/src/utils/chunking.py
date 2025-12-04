"""
Text Chunking Utilities
Strategies for splitting transcripts into meaningful chunks for embedding.
"""
from typing import List, Dict
import re

from config import CHUNK_SIZE, CHUNK_OVERLAP


def parse_transcript_line(line: str) -> Dict:
    """
    Parse a transcript line in format: [SPEAKER] HH:MM:SS: text
    
    Args:
        line: Raw transcript line
        
    Returns:
        Dict with speaker, timestamp, and text
    """
    # Pattern: [SPEAKER] HH:MM:SS: text
    pattern = r'\[(.+?)\]\s+(\d{2}:\d{2}:\d{2}):\s+(.+)'
    match = re.match(pattern, line.strip())
    
    if match:
        return {
            "speaker": match.group(1),
            "timestamp": match.group(2),
            "text": match.group(3)
        }
    else:
        # Fallback for malformed lines
        return {
            "speaker": "UNKNOWN",
            "timestamp": "00:00:00",
            "text": line.strip()
        }


def chunk_by_speaker_turns(
    transcript_lines: List[str],
    max_chunk_size: int = CHUNK_SIZE
) -> List[Dict]:
    """
    Chunk transcript by speaker turns, combining consecutive turns from same speaker.
    
    Args:
        transcript_lines: List of transcript lines
        max_chunk_size: Maximum characters per chunk
        
    Returns:
        List of chunks with metadata
    """
    chunks = []
    current_chunk = {
        "speaker": None,
        "timestamp": None,
        "text": ""
    }
    
    for line in transcript_lines:
        parsed = parse_transcript_line(line)
        
        # Skip empty lines
        if not parsed["text"]:
            continue
        
        # If speaker changes or chunk too large, finalize current chunk
        if (current_chunk["speaker"] and 
            (parsed["speaker"] != current_chunk["speaker"] or 
             len(current_chunk["text"]) + len(parsed["text"]) > max_chunk_size)):
            
            if current_chunk["text"]:
                chunks.append(current_chunk.copy())
            
            current_chunk = {
                "speaker": parsed["speaker"],
                "timestamp": parsed["timestamp"],
                "text": parsed["text"]
            }
        else:
            # Extend current chunk
            if not current_chunk["speaker"]:
                current_chunk["speaker"] = parsed["speaker"]
                current_chunk["timestamp"] = parsed["timestamp"]
            
            current_chunk["text"] += " " + parsed["text"]
    
    # Add final chunk
    if current_chunk["text"]:
        chunks.append(current_chunk)
    
    return chunks


def chunk_by_fixed_size(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
) -> List[str]:
    """
    Simple fixed-size chunking with overlap (fallback strategy).
    
    Args:
        text: Input text
        chunk_size: Size of each chunk in characters
        overlap: Overlap between chunks
        
    Returns:
        List of text chunks
    """
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += (chunk_size - overlap)
    
    return chunks


def extract_metadata_from_transcript(transcript_content: str) -> Dict:
    """
    Extract metadata from transcript header.
    
    Expected format:
    Title: Episode Title
    Podcast: Podcast Name
    Processed: 2024-12-04 10:00:00
    ============
    [transcript content...]
    
    Args:
        transcript_content: Full transcript text
        
    Returns:
        Dict with episode_title, podcast_name, processed_date
    """
    lines = transcript_content.split('\n')
    metadata = {
        "episode_title": "Unknown Episode",
        "podcast_name": "Unknown Podcast",
        "processed_date": None
    }
    
    for line in lines[:10]:  # Check first 10 lines
        if line.startswith("Title:"):
            metadata["episode_title"] = line.replace("Title:", "").strip()
        elif line.startswith("Podcast:"):
            metadata["podcast_name"] = line.replace("Podcast:", "").strip()
        elif line.startswith("Processed:"):
            metadata["processed_date"] = line.replace("Processed:", "").strip()
        elif "========" in line:
            break  # End of header
    
    return metadata


def get_transcript_body(transcript_content: str) -> List[str]:
    """
    Extract transcript body (without metadata header).
    
    Args:
        transcript_content: Full transcript text
        
    Returns:
        List of transcript lines
    """
    lines = transcript_content.split('\n')
    
    # Find separator
    separator_index = 0
    for i, line in enumerate(lines):
        if "========" in line:
            separator_index = i + 1
            break
    
    # Return lines after separator
    return [line for line in lines[separator_index:] if line.strip()]
