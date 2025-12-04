#!/usr/bin/env python3
"""
Episode Queue Manager
Shared utilities for managing the pending episodes queue.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

import feedparser

# Get absolute paths
# Navigate up from: transcription-service/src/managers/ -> transcription-service/ -> root/ -> shared/
SCRIPT_DIR = Path(__file__).parent.parent.parent.parent
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


def mark_episode_selected(episode_id: str, selected: bool):
    """Mark episode as selected or unselected."""
    data = load_pending_episodes()
    
    for episode in data['episodes']:
        if episode.get('id') == episode_id:
            episode['selected'] = selected
            break
    
    save_pending_episodes(data)


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


def fetch_episodes_from_feed(feed_url: str, feed_title: str = None) -> tuple[List[Dict], str]:
    """
    Fetch episodes from an RSS feed.
    Returns (episodes_list, feed_title).
    Episodes that are already processed or in the queue are filtered out.
    """
    try:
        feed = feedparser.parse(feed_url)
        
        if feed.bozo and not feed.entries:
            return [], f"Feed error: {feed.bozo_exception}"
        
        # Get feed title
        if not feed_title and feed.feed.get('title'):
            feed_title = feed.feed.get('title')
        elif not feed_title:
            feed_title = 'Unknown Podcast'
        
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
            
            # Find audio enclosure
            audio_url = None
            for enclosure in entry.get('enclosures', []):
                if enclosure.get('type', '').startswith('audio/'):
                    audio_url = enclosure.get('href')
                    break
            
            if not audio_url:
                continue
            
            # Extract published date
            published_date = entry.get('published', '')
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    published_date = datetime(*entry.published_parsed[:6]).isoformat()
                except:
                    pass
            
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
