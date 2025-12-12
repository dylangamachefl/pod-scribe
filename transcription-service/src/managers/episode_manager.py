#!/usr/bin/env python3
"""
Episode Queue Manager - SQLite Version
Shared utilities for managing the pending episodes queue using SQLite.
"""

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from contextlib import contextmanager

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
EPISODES_DB_FILE = CONFIG_DIR / "episodes.db"
HISTORY_FILE = CONFIG_DIR / "history.json"


# ============================================================================
# Database Schema and Initialization
# ============================================================================

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    feed_url TEXT,
    feed_title TEXT,
    episode_title TEXT,
    audio_url TEXT,
    published_date TEXT,
    fetched_date TEXT,
    status TEXT DEFAULT 'PENDING',
    selected INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_status ON episodes(status);
CREATE INDEX IF NOT EXISTS idx_selected ON episodes(selected);
CREATE INDEX IF NOT EXISTS idx_url ON episodes(url);
"""


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Ensures proper connection management and transaction handling.
    """
    conn = sqlite3.connect(str(EPISODES_DB_FILE))
    conn.row_factory = sqlite3.Row  # Return rows as dict-like objects
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database() -> None:
    """Initialize the database schema if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    with get_db_connection() as conn:
        conn.executescript(DB_SCHEMA)


# Ensure database is initialized on module import
init_database()


# ============================================================================
# Core Episode Queue Operations
# ============================================================================

def add_episode_to_queue(episode: Dict) -> bool:
    """
    Add a new episode to the pending queue using SQLite.
    Returns True if added, False if already exists.
    
    Uses INSERT OR IGNORE for automatic deduplication by episode ID.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Prepare episode data
            cursor.execute("""
                INSERT OR IGNORE INTO episodes (
                    id, url, feed_url, feed_title, episode_title,
                    audio_url, published_date, fetched_date, status, selected
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0)
            """, (
                episode.get('id'),
                episode.get('url', episode.get('audio_url')),  # Fallback to audio_url for url
                episode.get('feed_url'),
                episode.get('feed_title'),
                episode.get('episode_title'),
                episode.get('audio_url'),
                episode.get('published_date'),
                episode.get('fetched_date'),
            ))
            
            # Return True if actually inserted
            return cursor.rowcount > 0
            
    except sqlite3.IntegrityError:
        # Unique constraint violation (duplicate URL)
        return False


def remove_episode_from_queue(episode_id: str) -> None:
    """Remove an episode from the pending queue."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))


def mark_episode_selected(episode_id: str, selected: bool) -> bool:
    """
    Mark episode as selected or unselected with atomic transaction.
    
    Returns:
        True if episode was found and updated, False otherwise.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE episodes SET selected = ? WHERE id = ?",
            (1 if selected else 0, episode_id)
        )
        return cursor.rowcount > 0


def get_selected_episodes() -> List[Dict]:
    """Get all episodes marked as selected."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, url, feed_url, feed_title, episode_title,
                   audio_url, published_date, fetched_date, status, selected
            FROM episodes
            WHERE selected = 1
            ORDER BY created_at DESC
        """)
        
        return [dict(row) for row in cursor.fetchall()]


def get_all_pending_episodes() -> List[Dict]:
    """Get all pending episodes regardless of selection status."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, url, feed_url, feed_title, episode_title,
                   audio_url, published_date, fetched_date, status, selected
            FROM episodes
            WHERE status = 'PENDING'
            ORDER BY created_at DESC
        """)
        
        return [dict(row) for row in cursor.fetchall()]


def clear_processed_episodes(episode_ids: List[str]) -> None:
    """Remove processed episodes from the queue."""
    if not episode_ids:
        return
    
    with get_db_connection() as conn:
        placeholders = ','.join('?' * len(episode_ids))
        conn.execute(
            f"DELETE FROM episodes WHERE id IN ({placeholders})",
            episode_ids
        )


def bulk_mark_selected(episode_ids: List[str], selected: bool) -> None:
    """Mark multiple episodes as selected/unselected."""
    if not episode_ids:
        return
    
    with get_db_connection() as conn:
        placeholders = ','.join('?' * len(episode_ids))
        conn.execute(
            f"UPDATE episodes SET selected = ? WHERE id IN ({placeholders})",
            [1 if selected else 0] + episode_ids
        )


def get_episode_by_id(episode_id: str) -> Optional[Dict]:
    """Get a specific episode by its ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, url, feed_url, feed_title, episode_title,
                   audio_url, published_date, fetched_date, status, selected
            FROM episodes
            WHERE id = ?
        """, (episode_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None


# ============================================================================
# History Management (Kept for compatibility)
# ============================================================================

def load_history() -> Dict:
    """Load processing history to avoid duplicates."""
    if not HISTORY_FILE.exists():
        return {"processed_episodes": []}
    
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


# ============================================================================
# RSS Feed Fetching (Unchanged)
# ============================================================================

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
        
        # Get pending IDs from database
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM episodes")
            pending_ids = set(row['id'] for row in cursor.fetchall())
        
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
