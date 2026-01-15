import re
from typing import List

def chunk_transcript(text: str, chunk_size: int = 30000, overlap: int = 4500) -> List[str]:
    """
    Splits transcript into chunks with a sliding window overlap.
    Ensures cuts happen at speaker labels [SPEAKER_XX] to maintain context.
    """
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        if end >= text_len:
            chunks.append(text[start:])
            break

        # Look for a speaker label near the desired end to avoid mid-thought cuts
        # search backwards from the end for the nearest [SPEAKER_
        search_range = text[end-500:end+100]
        match = re.search(r'\[SPEAKER_\d+\]', search_range)
        
        if match:
            actual_end = (end - 500) + match.start()
        else:
            # Fallback to nearest newline if no speaker label is found
            actual_end = text.rfind('\n', start + chunk_size - 1000, end)
            if actual_end == -1: actual_end = end

        chunks.append(text[start:actual_end])
        # Move start back by overlap for the next window
        # Ensure start moves forward to avoid infinite loops
        new_start = actual_end - overlap
        if new_start <= start:
            start = actual_end # Force forward progress if overlap is too large
        else:
            start = new_start
        
    return chunks
