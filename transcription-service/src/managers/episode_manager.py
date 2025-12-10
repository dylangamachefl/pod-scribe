#!/usr/bin/env python3
"""
Episode Queue Manager
Shared utilities for managing the pending episodes queue.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import feedparser

# Get absolute paths
# In Docker: /app/src/managers/episode_manager.py → /app/src/managers → /app/src → /app
# On Host: transcription-service/src/managers/episode_manager.py → transcription-service/src/managers → transcription-service/src → transcription-service → root
# We need different logic for container vs host!
import os

if os.path.exists('/app/src'):  # Running in Docker container
    SCRIPT_DIR = Path(__file__).parent.parent.parent  # Go to /app
else:  # Running on host
    SCRIPT_DIR = Path(__file__).parent.parent.parent.parent  # Go to project root

CONFIG_DIR = SCRIPT_DIR / "shared" / "config"
PENDING_EPISODES_FILE = CONFIG_DIR / "pending_episodes.json"
HISTORY_FILE = CONFIG_DIR / "history.json"



def load_pending_episodes() -> Dict:
    """Load pending episodes from config."""
    if not PENDING_EPISODES_FILE.exists():
        return {"episodes": []}
    
    with open(PENDING_EPISODES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_pending_episodes(data: Dict):
    """Save pending episodes to config."""
    with open(PENDING_EPISODES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def load_history() -> Dict:
    """Load processing history to avoid duplicates."""
    if not HISTORY_FILE.exists():
        return {"processed_episodes": []}
    
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def add_episode_to_queue(episode: Dict) -> bool:
    """
    Add a new episode to the pending queue.
    Returns True if added, False if already exists.
    """
    data = load_pending_episodes()
    
    # Check if episode already exists
    episode_id = episode.get('id')
    if any(ep.get('id') == episode_id for ep in data['episodes']):
        return False
    
    data['episodes'].append(episode)
    save_pending_episodes(data)
    return True


def remove_episode_from_queue(episode_id: str):
    """Remove an episode from the pending queue."""
    data = load_pending_episodes()
    data['episodes'] = [ep for ep in data['episodes'] if ep.get('id') != episode_id]
    save_pending_episodes(data)


def mark_episode_selected(episode_id: str, selected: bool) -> bool:
    """Mark episode as selected or unselected.
    
    Returns:
        True if episode was found and updated, False otherwise.
    """
    data = load_pending_episodes()
    
    found = False
    for episode in data['episodes']:
        if episode.get('id') == episode_id:
            episode['selected'] = selected
            found = True
            break
    
    if found:
        save_pending_episodes(data)
    
    return found


def get_selected_episodes() -> List[Dict]:
    """Get all episodes marked as selected."""
    data = load_pending_episodes()
    return [ep for ep in data['episodes'] if ep.get('selected', False)]


def get_all_pending_episodes() -> List[Dict]:
    """Get all pending episodes regardless of selection status."""
    data = load_pending_episodes()
    return data.get('episodes', [])


def clear_processed_episodes(episode_ids: List[str]):
    """Remove processed episodes from the queue."""
    data = load_pending_episodes()
    data['episodes'] = [ep for ep in data['episodes'] if ep.get('id') not in episode_ids]
    save_pending_episodes(data)


def fetch_episodes_from_feed(feed_url: str, feed_title: str = None, days_limit: Optional[int] = None) -> tuple[List[Dict], str]:
    """
    Fetch episodes from an RSS feed.
    Returns (episodes_list, feed_title).
    Episodes that are already processed or in the queue are filtered out.
    
    Args:
        feed_url: The RSS feed URL to fetch from
        feed_title: Optional feed title override
        days_limit: Number of days to look back for episodes. 
                   If None, fetches all episodes.
                   Defaults to EPISODE_DEFAULT_DAYS env var (7).
    """
    try:
        # Get default days limit from environment if not specified
        if days_limit is None:
            days_limit = int(os.getenv('EPISODE_DEFAULT_DAYS', '7'))
        
        feed = feedparser.parse(feed_url)
        
        if feed.bozo and not feed.entries:
            return [], f"Feed error: {feed.bozo_exception}"
        
        # Get feed title
        if not feed_title and feed.feed.get('title'):
            feed_title = feed.feed.get('title')
        elif not feed_title:
            feed_title = 'Unknown Podcast'
        
        # Calculate cutoff date for filtering (if days_limit > 0)
        cutoff_date = None
        if days_limit and days_limit > 0:
            cutoff_date = datetime.now() - timedelta(days=days_limit)
        
        # Load history and pending to avoid duplicates
        history = load_history()
        processed_ids = set(history.get('processed_episodes', []))
        pending_ids = set(ep.get('id') for ep in get_all_pending_episodes())
        
        episodes = []
        for entry in feed.get('entries', []):
            episode_id = entry.get('id', entry.get('link', ''))
            
            # Skip if already processed or pending
            if episode_id in processed_ids or episode_id in pending_ids:
                continue
            
            # Find audio/video URL
            audio_url = None
            
            # Method 1: Check for audio enclosures (standard podcast RSS)
            for enclosure in entry.get('enclosures', []):
                if enclosure.get('type', '').startswith('audio/'):
                    audio_url = enclosure.get('href')
                    break
            
            # Method 2: Check direct link attribute (Atom feeds like YouTube)
            if not audio_url and hasattr(entry, 'link'):
                audio_url = entry.link
            
            # Method 3: Check links array for alternate link (Atom feeds)
            if not audio_url and hasattr(entry, 'links'):
                for link_item in entry.links:
                    if link_item.get('rel') == 'alternate':
                        audio_url = link_item.get('href')
                        break
            
            # Method 4: Fallback to dict access
            if not audio_url:
                audio_url = entry.get('link', '')
            
            # Skip entries without valid URLs
            if not audio_url:
                continue
            
            # Extract published date
            published_date = entry.get('published', '')
            episode_datetime = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    episode_datetime = datetime(*entry.published_parsed[:6])
                    published_date = episode_datetime.isoformat()
                except:
                    pass
            
            # Apply time-based filter if cutoff_date is set
            if cutoff_date and episode_datetime:
                # Skip episodes older than cutoff date
                if episode_datetime < cutoff_date:
                    continue
            # Note: Episodes without valid published dates are included by default
            # This prevents accidentally filtering out episodes that don't have proper dates
            
            episode = {
                'id': episode_id,
                'feed_url': feed_url,
                'feed_title': feed_title,
                'episode_title': entry.get('title', 'Untitled Episode'),
                'audio_url': audio_url,
                'published_date': published_date,
                'selected': False,
                'fetched_date': datetime.now().isoformat()
            }
            
            episodes.append(episode)
        
        return episodes, feed_title
    
    except Exception as e:
        return [], f"Error: {str(e)}"


def bulk_mark_selected(episode_ids: List[str], selected: bool):
    """Mark multiple episodes as selected/unselected."""
    data = load_pending_episodes()
    
    for episode in data['episodes']:
        if episode.get('id') in episode_ids:
            episode['selected'] = selected
    
    save_pending_episodes(data)


def get_episode_by_id(episode_id: str) -> Optional[Dict]:
    """Get a specific episode by its ID."""
    data = load_pending_episodes()
    
    for episode in data['episodes']:
        if episode.get('id') == episode_id:
            return episode
    
    return None
