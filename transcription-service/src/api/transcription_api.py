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
import logging
import redis
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select
import feedparser

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.models import (
    Feed, FeedCreate, FeedUpdate,
    Episode, EpisodeSelect, BulkSelectRequest, BulkSeenRequest, EpisodeFetchRequest,
    EpisodeFavoriteUpdate,
    TranscriptionStatus, TranscriptionStartRequest, TranscriptionStartResponse,
    PodcastInfo, EpisodeInfo, TranscriptResponse,
    StatsResponse, HealthResponse
)
# Setup logging
logger = logging.getLogger(__name__)

# PostgreSQL database imports
from podcast_transcriber_shared.database import (
    create_episode,
    list_episodes,
    get_episode_by_id,
    update_episode_status,
    mark_episodes_as_seen,
    EpisodeStatus
)

# RSS feed parsing utility
from utils.rss_utils import fetch_episodes_from_rss
from managers.status_monitor import read_status

# Get absolute paths
# In Docker: /app/src/api/transcription_api.py → /app/src/api → /app/src → /app
SCRIPT_DIR = Path(os.path.abspath(__file__)).parent.parent.parent
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

# Static file serving removed - all transcripts served from database

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


async def get_available_podcasts() -> List[dict]:
    """Get list of podcasts with transcripts from database."""
    from podcast_transcriber_shared.database import get_session_maker, Episode, EpisodeStatus
    from sqlalchemy import select, func
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        # Group by podcast_name and count completed episodes
        query = select(
            Episode.podcast_name,
            func.count(Episode.id).label('episode_count')
        ).where(
            Episode.status == EpisodeStatus.COMPLETED
        ).group_by(Episode.podcast_name)
        
        result = await session.execute(query)
        podcasts = [
            {"name": row.podcast_name, "episode_count": row.episode_count}
            for row in result
        ]
    
    return sorted(podcasts, key=lambda x: x["name"])


async def get_podcast_episodes(podcast_name: str) -> List[dict]:
    """Get list of episodes for a podcast from database."""
    from podcast_transcriber_shared.database import list_episodes, EpisodeStatus
    
    episodes = await list_episodes(
        podcast_name=podcast_name,
        status=EpisodeStatus.COMPLETED,
        limit=None
    )
    
    return [
        {
            "id": ep.id,
            "name": ep.title,
            "created_at": ep.created_at.isoformat() if ep.created_at else None
        }
        for ep in episodes
    ]


async def read_transcript(episode_id: str) -> Optional[str]:
    """Read transcript from database."""
    from podcast_transcriber_shared.database import get_episode_by_id
    
    episode = await get_episode_by_id(episode_id, load_transcript=True)
    return episode.transcript_text if episode else None


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
    podcasts = await get_available_podcasts()
    
    # Get pending and completed episode counts from PostgreSQL
    pending_episodes = await list_episodes(status=EpisodeStatus.PENDING)
    completed_episodes = await list_episodes(status=EpisodeStatus.COMPLETED)
    
    # Count selected episodes (stored in meta_data)
    selected_count = sum(1 for ep in pending_episodes if ep.meta_data and ep.meta_data.get('selected'))
    
    return StatsResponse(
        active_feeds=sum(1 for s in subscriptions if s.get('active', True)),
        total_feeds=len(subscriptions),
        total_podcasts=len(podcasts),
        total_episodes_processed=len(completed_episodes),
        pending_episodes=len(pending_episodes),
        selected_episodes=selected_count
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

@app.get("/episodes", response_model=List[Episode])
async def list_all_episodes(
    status: Optional[str] = None,
    feed_title: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0
):
    """
    Get episodes with optional filtering.
    """
    from podcast_transcriber_shared.database import list_episodes, EpisodeStatus
    
    # Convert string status to enum if provided
    status_enum = None
    if status:
        try:
            status_enum = EpisodeStatus(status)
        except ValueError:
            pass # Ignore invalid status or handle error
            
    episodes = await list_episodes(
        status=status_enum,
        podcast_name=feed_title,
        limit=limit
    )
    
    return [
        Episode(
            id=ep.id,
            feed_url=ep.meta_data.get('feed_url', '') if ep.meta_data else '',
            feed_title=ep.podcast_name,
            episode_title=ep.title,
            audio_url=ep.meta_data.get('audio_url', ep.url) if ep.meta_data else ep.url,
            published_date=ep.meta_data.get('published_date', '') if ep.meta_data else '',
            selected=ep.meta_data.get('selected', False) if ep.meta_data else False,
            fetched_date=ep.created_at.isoformat() if ep.created_at else '',
            is_seen=ep.is_seen,
            is_favorite=ep.is_favorite,
            status=ep.status.value
        )
        for ep in episodes
    ]


@app.get("/episodes/queue", response_model=List[Episode])
async def get_episode_queue():
    """Get all pending episodes from PostgreSQL."""
    episodes = await list_episodes(status=EpisodeStatus.PENDING)
    
    return [
        Episode(
            id=ep.id,
            feed_url=ep.meta_data.get('feed_url', '') if ep.meta_data else '',
            feed_title=ep.podcast_name,
            episode_title=ep.title,
            audio_url=ep.meta_data.get('audio_url', ep.url) if ep.meta_data else ep.url,
            published_date=ep.meta_data.get('published_date', '') if ep.meta_data else '',
            selected=ep.meta_data.get('selected', False) if ep.meta_data else False,
            fetched_date=ep.created_at.isoformat() if ep.created_at else '',
            is_seen=ep.is_seen,
            is_favorite=ep.is_favorite,
            status=ep.status.value
        )
        for ep in episodes
    ]


@app.post("/episodes/fetch")
async def fetch_episodes(request: EpisodeFetchRequest = None):
    """
    Fetch new episodes from active feeds and store in PostgreSQL.
    
    Args:
        request: Optional request body with 'days' parameter to specify
                how many days back to fetch episodes (default: all episodes from feed)
    """
    subscriptions = load_subscriptions()
    active_subs = [sub for sub in subscriptions if sub.get('active', True)]
    
    if not active_subs:
        raise HTTPException(status_code=400, detail="No active feeds found")
    
    # Get days limit from request or use None to apply default from env
    days_limit = request.days if request else None
    
    # Get existing episode IDs to avoid duplicates
    existing_episodes = await list_episodes()
    existing_ids = {ep.id for ep in existing_episodes}
    
    total_new = 0
    for sub in active_subs:
        # Fetch episodes from RSS feed
        episodes, feed_title = fetch_episodes_from_rss(
            sub.get('url'),
            sub.get('title'),
            days_limit=days_limit
        )
        
        # Create episodes in PostgreSQL (skip duplicates)
        for episode in episodes:
            episode_id = episode.get('id')
            if episode_id in existing_ids:
                continue  # Skip duplicates
                
            try:
                await create_episode(
                    episode_id=episode_id,
                    url=episode.get('audio_url', ''),
                    title=episode.get('episode_title', 'Unknown'),
                    podcast_name=episode.get('feed_title', 'Unknown'),
                    status=EpisodeStatus.PENDING,
                    meta_data={
                        'feed_url': episode.get('feed_url'),
                        'audio_url': episode.get('audio_url'),
                        'published_date': episode.get('published_date'),
                        'selected': False
                    }
                )
                total_new += 1
                existing_ids.add(episode_id)  # Track to avoid duplicates in same batch
            except Exception as e:
                logger.error(f"Failed to create episode {episode_id}: {e}")
                continue
    
    return {
        "status": "completed",
        "new_episodes": total_new,
        "days_filter": days_limit if days_limit is not None else "all"
    }


@app.put("/episodes/{episode_id}/select")
async def select_episode(episode_id: str, selection: EpisodeSelect):
    """Mark episode as selected/unselected in PostgreSQL metadata."""
    # Get episode without loading transcript
    episode = await get_episode_by_id(episode_id, load_transcript=False)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    # Update metadata with selected status
    updated_meta = episode.meta_data.copy() if episode.meta_data else {}
    updated_meta['selected'] = selection.selected
    
    # Update episode directly using database session
    from podcast_transcriber_shared.database import get_session_maker
    session_maker = get_session_maker()
    async with session_maker() as session:
        from podcast_transcriber_shared.database import Episode as EpisodeModel
        result = await session.execute(
            select(EpisodeModel).where(EpisodeModel.id == episode_id)
        )
        db_episode = result.scalar_one_or_none()
        if db_episode:
            db_episode.meta_data = updated_meta
            await session.commit()
    
    return {"status": "updated", "episode_id": episode_id, "selected": selection.selected}


@app.put("/episodes/{episode_id}/favorite")
async def toggle_favorite(episode_id: str, favorite_update: EpisodeFavoriteUpdate):
    """Toggle episode favorite status in PostgreSQL."""
    from podcast_transcriber_shared.database import get_session_maker
    session_maker = get_session_maker()
    async with session_maker() as session:
        from podcast_transcriber_shared.database import Episode as EpisodeModel
        result = await session.execute(
            select(EpisodeModel).where(EpisodeModel.id == episode_id)
        )
        db_episode = result.scalar_one_or_none()
        if not db_episode:
            raise HTTPException(status_code=404, detail="Episode not found")
        
        db_episode.is_favorite = favorite_update.is_favorite
        await session.commit()
    
    return {"status": "updated", "episode_id": episode_id, "is_favorite": favorite_update.is_favorite}


@app.post("/episodes/bulk-select")
async def bulk_select_episodes(request: BulkSelectRequest):
    """Bulk select/deselect episodes in PostgreSQL."""
    from podcast_transcriber_shared.database import save_transcript
    
    for episode_id in request.episode_ids:
        episode = await get_episode_by_id(episode_id, load_transcript=False)
        if episode:
            updated_meta = episode.meta_data or {}
            updated_meta['selected'] = request.selected
            await save_transcript(episode_id, episode.transcript_text or '', metadata=updated_meta)
    
    return {
        "status": "updated",
        "count": len(request.episode_ids),
        "selected": request.selected
    }


@app.post("/episodes/bulk-seen")
async def bulk_seen_episodes(request: BulkSeenRequest):
    """Bulk mark episodes as seen/unseen in PostgreSQL."""
    count = await mark_episodes_as_seen(request.episode_ids, request.seen)
    
    return {
        "status": "updated",
        "count": count,
        "seen": request.seen
    }


@app.delete("/episodes/processed")
async def clear_processed():
    """Delete completed episodes from PostgreSQL."""
    from podcast_transcriber_shared.database import get_session_maker
    from sqlalchemy import delete
    from podcast_transcriber_shared.database import Episode as EpisodeModel
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            delete(EpisodeModel).where(EpisodeModel.status == EpisodeStatus.COMPLETED)
        )
        await session.commit()
        count = result.rowcount
    
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
    """
    Create episodes in PostgreSQL and enqueue transcription jobs to Redis queue.
    
    The transcription worker daemon polls Redis and processes jobs.
    This provides immediate response and production-ready architecture.
    """
    import redis
    from datetime import datetime
    from podcast_transcriber_shared.database import create_episode, EpisodeStatus
    
    # Check if already running (via status file)
    status = read_status()
    if status and status.get('is_running'):
        raise HTTPException(status_code=400, detail="Transcription already in progress")
    
    # Identify target episodes
    target_episodes = []
    
    if request.episode_ids and len(request.episode_ids) > 0:
        # Case 1: Specific episodes requested via API
        from podcast_transcriber_shared.database import get_session_maker, Episode as EpisodeModel
        
        session_maker = get_session_maker()
        async with session_maker() as session:
            query = select(EpisodeModel).where(EpisodeModel.id.in_(request.episode_ids))
            result = await session.execute(query)
            episodes = result.scalars().all()
            
            target_episodes = [
                {'id': ep.id, 'audio_url': ep.meta_data.get('audio_url', ep.url),
                 'episode_title': ep.title, 'feed_title': ep.podcast_name}
                for ep in episodes
            ]
    else:
        # Case 2: Fallback to "selected" episodes in database (Legacy/Queue Page)
        all_pending = await list_episodes(status=EpisodeStatus.PENDING)
        target_episodes = [
            {'id': ep.id, 'audio_url': ep.meta_data.get('audio_url', ep.url),
             'episode_title': ep.title, 'feed_title': ep.podcast_name}
            for ep in all_pending if ep.meta_data and ep.meta_data.get('selected')
        ]
    
    if not target_episodes:
        raise HTTPException(status_code=400, detail="No episodes selected for transcription")
        
    # Alias for consistency with rest of function
    selected_episodes = target_episodes
    
    try:
        # Connect to Redis
        redis_url = os.getenv('REDIS_URL', 'redis://redis:6379')
        r = redis.from_url(redis_url, decode_responses=True)
        
        # Create episodes in PostgreSQL and enqueue to Redis
        enqueued_count = 0
        for ep in selected_episodes:
            episode_id = ep.get('id')
            
            try:
                # Episode already exists in PostgreSQL (created during fetch)
                # Just enqueue to Redis - worker will update status to PROCESSING
                
                # Create simplified job payload (just episode_id)
                job = {
                    'episode_id': episode_id,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Enqueue job to Redis
                r.lpush('transcription_queue', json.dumps(job))
                enqueued_count += 1
                
                logger.info(f"📤 Enqueued episode {episode_id} to transcription queue")
                
            except Exception as e:
                logger.error(f"Failed to create/enqueue episode {episode_id}: {e}")
                # Continue with other episodes even if one fails
                continue
        
        if enqueued_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to enqueue any episodes. Check logs for details."
            )
        
        logger.info(f"📤 Enqueued {enqueued_count} transcription job(s)")
        
        return TranscriptionStartResponse(
            status="queued",
            message=f"Transcription queued for {enqueued_count} episode(s). Worker will process shortly.",
            episodes_count=enqueued_count
        )
        
    except redis.ConnectionError as e:
        logger.error(f"Redis connection error: {e}")
        raise HTTPException(
            status_code=503,
            detail="Unable to connect to job queue. Please ensure Redis is running."
        )
    except Exception as e:
        logger.error(f"Error enqueueing job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to queue job: {str(e)}")


# ============================================================================
# Transcript Browsing Endpoints
# ============================================================================

@app.get("/transcripts", response_model=List[PodcastInfo])
async def list_podcasts():
    """List all available podcasts."""
    podcasts = await get_available_podcasts()
    return [PodcastInfo(**p) for p in podcasts]


@app.get("/transcripts/{podcast_name}", response_model=List[EpisodeInfo])
async def list_podcast_episodes(podcast_name: str):
    """List episodes for a podcast."""
    episodes = await get_podcast_episodes(podcast_name)
    
    if not episodes:
        raise HTTPException(status_code=404, detail="Podcast not found or has no episodes")
    
    return [
        EpisodeInfo(
            name=ep["name"],
            file_path=ep["id"]  # Use episode_id as file_path for backward compatibility
        )
        for ep in episodes
    ]


@app.get("/transcripts/{podcast_name}/{episode_id}", response_model=TranscriptResponse)
async def get_transcript(podcast_name: str, episode_id: str):
    """
    Get transcript content for a specific episode from database.
    """
    # Read transcript from database
    content = await read_transcript(episode_id)
    
    if content is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    return TranscriptResponse(
        podcast_name=podcast_name,
        episode_name=episode_id,
        content=content
    )


@app.get("/transcripts/{podcast_name}/{episode_id}/download")
async def download_transcript_raw(podcast_name: str, episode_id: str):
    """
    Download raw transcript content as a .txt file.
    """
    # Read transcript from database
    content = await read_transcript(episode_id)
    
    if content is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    from fastapi.responses import Response
    
    # Return as a downloadable text file
    return Response(
        content=content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{episode_id}.txt"'
        }
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
