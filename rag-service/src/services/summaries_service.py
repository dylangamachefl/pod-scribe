"""
Summary Service Helper
Provides helper functions for summary-related operations.
"""
import json
from pathlib import Path
from typing import Optional, Dict

from config import SUMMARY_OUTPUT_PATH


def get_summary_by_episode_title(episode_title: str) -> Optional[Dict]:
    """
    Get summary data for a specific episode by title.
    
    Args:
        episode_title: Episode title to search for
        
    Returns:
        Summary dict or None if not found
    """
    try:
        if not SUMMARY_OUTPUT_PATH.exists():
            return None
        
        for summary_file in SUMMARY_OUTPUT_PATH.glob("*_summary.json"):
            with open(summary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                if data.get("episode_title") == episode_title:
                    return data
        
        return None
    except Exception as e:
        print(f"Error loading summary: {e}")
        return None
