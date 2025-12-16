"""
RSS Feed Utilities
Pure functions for parsing RSS/Atom feeds without database dependencies.
"""
import os
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple


def fetch_episodes_from_rss(
    feed_url: str, 
    feed_title: str = None,
    days_limit: Optional[int] = None
) -> Tuple[List[Dict], str]:
    """
    Fetch episodes from an RSS or Atom feed.
    
    Args:
        feed_url: The RSS/Atom feed URL to parse
        feed_title: Optional feed title override
        days_limit: Number of days to look back for episodes.
                   If None, uses EPISODE_DEFAULT_DAYS env var (default 7).
                   If 0, fetches all episodes.
    
    Returns:
        Tuple of (episodes_list, feed_title)
        Each episode dict contains: id, feed_url, feed_title, episode_title,
                                    audio_url, published_date, fetched_date
    
    Note:
        This function does NOT check for duplicates or interact with the database.
        Duplicate checking should be done by the caller.
    """
    try:
        # Get default days limit from environment if not specified
        if days_limit is None:
            days_limit = int(os.getenv('EPISODE_DEFAULT_DAYS', '7'))
        
        # Parse feed
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
        
        episodes = []
        for entry in feed.get('entries', []):
            episode_id = entry.get('id', entry.get('link', ''))
            
            if not episode_id:
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
            
            episode = {
                'id': episode_id,
                'feed_url': feed_url,
                'feed_title': feed_title,
                'episode_title': entry.get('title', 'Untitled Episode'),
                'audio_url': audio_url,
                'published_date': published_date,
                'fetched_date': datetime.now().isoformat()
            }
            
            episodes.append(episode)
        
        return episodes, feed_title
    
    except Exception as e:
        return [], f"Error: {str(e)}"
