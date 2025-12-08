"""
Transcription Service API
FastAPI backend for podcast transcription management.
"""
import os
import sys
import json
import uuid
import subprocess
import threading
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import feedparser

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.models import (
    Feed, FeedCreate, FeedUpdate,
    Episode, EpisodeSelect, BulkSelectRequest, EpisodeFetchRequest,
    TranscriptionStatus, TranscriptionStartRequest, TranscriptionStartResponse,
    PodcastInfo, EpisodeInfo, TranscriptResponse,
    StatsResponse, HealthResponse
)
from managers.episode_manager import (
    load_pending_episodes,
    save_pending_episodes,
    mark_episode_selected,
    fetch_episodes_from_feed,
    add_episode_to_queue,
    bulk_mark_selected,
    clear_processed_episodes
)
from managers.status_monitor import read_status

# Get absolute paths
SCRIPT_DIR = Path(os.path.abspath(__file__)).parent.parent.parent.parent
CONFIG_DIR = SCRIPT_DIR / "shared" / "config"
OUTPUT_DIR = SCRIPT_DIR / "shared" / "output"
CLI_SCRIPT = SCRIPT_DIR / "transcription-service" / "src" / "cli.py"

SUBSCRIPTIONS_FILE = CONFIG_DIR / "subscriptions.json"
HISTORY_FILE = CONFIG_DIR / "history.json"

# Ensure directories exist
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Create FastAPI app
app = FastAPI(
    title="Podcast Transcription API",
    description="RESTful API for managing podcast transcription",
    version="1.0.0"
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background transcription process
transcription_process = None


# ============================================================================
# Helper Functions
# ============================================================================

def load_subscriptions() -> List[dict]:
    """Load RSS feed subscriptions."""
    if not SUBSCRIPTIONS_FILE.exists():
        return []
    with open(SUBSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_subscriptions(subscriptions: List[dict]):
    """Save RSS feed subscriptions."""
    with open(SUBSCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(subscriptions, f, indent=2)


def load_history() -> dict:
    """Load processing history."""
    if not HISTORY_FILE.exists():
        return {"processed_episodes": []}
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_rss_feed(url: str) -> tuple[bool, str]:
    """Validate RSS feed URL and return (is_valid, title_or_error)."""
    try:
        feed = feedparser.parse(url)
        
        if feed.bozo and not feed.entries:
            return False, f"Invalid feed: {feed.bozo_exception}"
        
        if not feed.entries:
            return False, "Feed contains no episodes"
        
        feed_title = feed.feed.get('title', 'Unknown Podcast')
        return True, feed_title
    
    except Exception as e:
        return False, str(e)


def get_available_podcasts() -> List[dict]:
    """Get list of podcasts with transcripts."""
    if not OUTPUT_DIR.exists():
        return []
    
    podcasts = []
    for d in OUTPUT_DIR.iterdir():
        if d.is_dir():
            episode_count = len(list(d.glob("*.txt")))
            podcasts.append({
                "name": d.name,
                "episode_count": episode_count
            })
    
    return sorted(podcasts, key=lambda x: x["name"])


def get_podcast_episodes(podcast_name: str) -> List[str]:
    """Get list of episodes for a podcast."""
    podcast_dir = OUTPUT_DIR / podcast_name
    if not podcast_dir.exists():
        return []
    
    episodes = [f.stem for f in podcast_dir.glob("*.txt")]
    return sorted(episodes, reverse=True)  # Newest first


def read_transcript(podcast_name: str, episode_name: str) -> Optional[str]:
    """Read transcript file."""
    transcript_file = OUTPUT_DIR / podcast_name / f"{episode_name}.txt"
    
    if not transcript_file.exists():
        return None
    
    with open(transcript_file, 'r', encoding='utf-8') as f:
        return f.read()


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Podcast Transcription API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        api_version="1.0.0",
        transcription_service_available=CLI_SCRIPT.exists()
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get overall statistics."""
    subscriptions = load_subscriptions()
    history = load_history()
    podcasts = get_available_podcasts()
    pending_data = load_pending_episodes()
    pending_episodes = pending_data.get('episodes', [])
    
    return StatsResponse(
        active_feeds=sum(1 for s in subscriptions if s.get('active', True)),
        total_feeds=len(subscriptions),
        total_podcasts=len(podcasts),
        total_episodes_processed=len(history.get('processed_episodes', [])),
        pending_episodes=len(pending_episodes),
        selected_episodes=sum(1 for ep in pending_episodes if ep.get('selected', False))
    )


# ============================================================================
# Feed Management Endpoints
# ============================================================================

@app.get("/feeds", response_model=List[Feed])
async def list_feeds():
    """List all RSS feed subscriptions."""
    subscriptions = load_subscriptions()
    
    # Add IDs if not present
    for i, sub in enumerate(subscriptions):
        if 'id' not in sub:
            sub['id'] = str(uuid.uuid4())
    
    save_subscriptions(subscriptions)
    
    return [
        Feed(
            id=sub.get('id', str(i)),
            url=sub['url'],
            title=sub.get('title', 'Unknown Podcast'),
            active=sub.get('active', True)
        )
        for i, sub in enumerate(subscriptions)
    ]


@app.post("/feeds", response_model=Feed)
async def add_feed(feed_create: FeedCreate):
    """Add new RSS feed."""
    subscriptions = load_subscriptions()
    
    # Check if already exists
    if any(s['url'] == feed_create.url for s in subscriptions):
        raise HTTPException(status_code=400, detail="Feed already exists")
    
    # Validate feed
    is_valid, result = validate_rss_feed(feed_create.url)
    
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid feed: {result}")
    
    feed_title = result
    feed_id = str(uuid.uuid4())
    
    new_feed = {
        "id": feed_id,
        "url": feed_create.url,
        "title": feed_title,
        "active": True
    }
    
    subscriptions.append(new_feed)
    save_subscriptions(subscriptions)
    
    return Feed(**new_feed)


@app.put("/feeds/{feed_id}", response_model=Feed)
async def update_feed(feed_id: str, feed_update: FeedUpdate):
    """Update feed (toggle active state)."""
    subscriptions = load_subscriptions()
    
    # Find feed
    feed_index = None
    for i, sub in enumerate(subscriptions):
        if sub.get('id') == feed_id:
            feed_index = i
            break
    
    if feed_index is None:
        raise HTTPException(status_code=404, detail="Feed not found")
    
    subscriptions[feed_index]['active'] = feed_update.active
    save_subscriptions(subscriptions)
    
    return Feed(**subscriptions[feed_index])


@app.delete("/feeds/{feed_id}")
async def delete_feed(feed_id: str):
    """Delete RSS feed."""
    subscriptions = load_subscriptions()
    
    # Find and remove feed
    original_length = len(subscriptions)
    subscriptions = [s for s in subscriptions if s.get('id') != feed_id]
    
    if len(subscriptions) == original_length:
        raise HTTPException(status_code=404, detail="Feed not found")
    
    save_subscriptions(subscriptions)
    
    return {"status": "deleted", "feed_id": feed_id}


# ============================================================================
# Episode Queue Endpoints
# ============================================================================

@app.get("/episodes/queue", response_model=List[Episode])
async def get_episode_queue():
    """Get all pending episodes."""
    pending_data = load_pending_episodes()
    episodes = pending_data.get('episodes', [])
    
    return [Episode(**ep) for ep in episodes]


@app.post("/episodes/fetch")
async def fetch_episodes(request: EpisodeFetchRequest = None):
    """
    Fetch new episodes from active feeds.
    
    Args:
        request: Optional request body with 'days' parameter to specify
                how many days back to fetch episodes (default: from env EPISODE_DEFAULT_DAYS)
    """
    subscriptions = load_subscriptions()
    active_subs = [sub for sub in subscriptions if sub.get('active', True)]
    
    if not active_subs:
        raise HTTPException(status_code=400, detail="No active feeds found")
    
    # Get days limit from request or use None to apply default from env
    days_limit = request.days if request else None
    
    total_new = 0
    for sub in active_subs:
        episodes, feed_title = fetch_episodes_from_feed(
            sub.get('url'),
            sub.get('title'),
            days_limit=days_limit
        )
        
        for episode in episodes:
            if add_episode_to_queue(episode):
                total_new += 1
    
    return {
        "status": "completed",
        "new_episodes": total_new,
        "days_filter": days_limit if days_limit is not None else int(os.getenv('EPISODE_DEFAULT_DAYS', '7'))
    }


@app.put("/episodes/{episode_id}/select")
async def select_episode(episode_id: str, selection: EpisodeSelect):
    """Mark episode as selected/unselected."""
    success = mark_episode_selected(episode_id, selection.selected)
    
    if not success:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    return {"status": "updated", "episode_id": episode_id, "selected": selection.selected}


@app.post("/episodes/bulk-select")
async def bulk_select_episodes(request: BulkSelectRequest):
    """Bulk select/deselect episodes."""
    bulk_mark_selected(request.episode_ids, request.selected)
    
    return {
        "status": "updated",
        "count": len(request.episode_ids),
        "selected": request.selected
    }


@app.delete("/episodes/processed")
async def clear_processed():
    """Clear processed episodes from queue."""
    count = clear_processed_episodes()
    
    return {
        "status": "cleared",
        "count": count
    }


# ============================================================================
# Transcription Control Endpoints
# ============================================================================

@app.get("/transcription/status", response_model=TranscriptionStatus)
async def get_transcription_status():
    """Get current transcription status."""
    status = read_status()
    
    if status:
        return TranscriptionStatus(**status)
    else:
        return TranscriptionStatus(is_running=False, stage="idle")


@app.post("/transcription/start", response_model=TranscriptionStartResponse)
async def start_transcription(
    request: TranscriptionStartRequest,
    background_tasks: BackgroundTasks
):
    """Start transcription process for selected episodes."""
    # Check if already running (via status file)
    status = read_status()
    if status and status.get('is_running'):
        raise HTTPException(status_code=400, detail="Transcription already in progress")
    
    # Get selected episodes
    pending_data = load_pending_episodes()
    episodes = pending_data.get('episodes', [])
    selected_episodes = [ep for ep in episodes if ep.get('selected', False)]
    
    if not selected_episodes:
        raise HTTPException(status_code=400, detail="No episodes selected")
    
    # Trigger host-side listener
    import requests
    
    def trigger_host_listener():
        try:
            # Try host.docker.internal first (Docker Desktop)
            # If that fails, try localhost (for local dev)
            endpoints = [
                "http://host.docker.internal:8080/start",
                "http://localhost:8080/start"
            ]
            
            success = False
            for endpoint in endpoints:
                try:
                    print(f"Attempting to trigger listener at {endpoint}...")
                    response = requests.post(endpoint, timeout=2)
                    if response.status_code == 200:
                        print(f"Successfully triggered listener at {endpoint}")
                        success = True
                        break
                except requests.RequestException:
                    continue
            
            if not success:
                print("Failed to contact host listener on any known endpoint")
                
        except Exception as e:
            print(f"Error triggering host listener: {e}")

    background_tasks.add_task(trigger_host_listener)
    
    return TranscriptionStartResponse(
        status="started",
        message=f"Transcription signal sent for {len(selected_episodes)} episode(s)",
        episodes_count=len(selected_episodes)
    )


# ============================================================================
# Transcript Browsing Endpoints
# ============================================================================

@app.get("/transcripts", response_model=List[PodcastInfo])
async def list_podcasts():
    """List all available podcasts."""
    podcasts = get_available_podcasts()
    return [PodcastInfo(**p) for p in podcasts]


@app.get("/transcripts/{podcast_name}", response_model=List[EpisodeInfo])
async def list_episodes(podcast_name: str):
    """List episodes for a podcast."""
    episodes = get_podcast_episodes(podcast_name)
    
    if not episodes:
        raise HTTPException(status_code=404, detail="Podcast not found or has no episodes")
    
    podcast_dir = OUTPUT_DIR / podcast_name
    
    return [
        EpisodeInfo(
            name=ep,
            file_path=str(podcast_dir / f"{ep}.txt")
        )
        for ep in episodes
    ]


@app.get("/transcripts/{podcast_name}/{episode_name}", response_model=TranscriptResponse)
async def get_transcript(podcast_name: str, episode_name: str):
    """Get specific transcript content."""
    content = read_transcript(podcast_name, episode_name)
    
    if content is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    return TranscriptResponse(
        podcast_name=podcast_name,
        episode_name=episode_name,
        content=content
    )


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "transcription_api:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
