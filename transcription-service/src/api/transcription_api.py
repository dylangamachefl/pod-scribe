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
import asyncio
import redis
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select, func
import feedparser

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.models import (
    Feed, FeedCreate, FeedUpdate,
    Episode, EpisodeSelect, BulkSelectRequest, BulkSeenRequest, EpisodeFetchRequest,
    EpisodeFavoriteUpdate,
    TranscriptionStatus, TranscriptionStartRequest, TranscriptionStartResponse,
    BatchProgressResponse, BatchEpisodeStatus,
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
    bulk_update_episodes_batch,
    get_session_maker,
    EpisodeStatus,
    Summary as SummaryModel
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

# LEGACY JSON HANDLERS REMOVED - Using PostgreSQL


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

@app.on_event("startup")
async def startup_event():
    """Startup tasks: start the stale job monitor."""
    # Start stale job monitor in a separate thread
    threading.Thread(target=stale_job_monitor_wrapper, daemon=True).start()
    logger.info("⏱️ Stale job monitor started")

def stale_job_monitor_wrapper():
    """Wrapper to run the async monitor in a thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(monitor_stale_jobs())

async def monitor_stale_jobs():
    """Periodically check for episodes stuck in PROCESSING."""
    while True:
        try:
            from podcast_transcriber_shared.database import get_session_maker, Episode, EpisodeStatus
            from sqlalchemy import select, update
            from datetime import datetime, timedelta
            
            # Check every 30 minutes
            await asyncio.sleep(1800)
            
            logger.info("🔍 Checking for stale processing episodes...")
            session_maker = get_session_maker()
            async with session_maker() as session:
                # Any episode in PROCESSING for > 2 hours is considered stale
                stale_threshold = datetime.utcnow() - timedelta(hours=2)
                
                query = select(Episode).where(
                    Episode.status == EpisodeStatus.PROCESSING,
                    Episode.processed_at < stale_threshold
                )
                result = await session.execute(query)
                stale_episodes = result.scalars().all()
                
                if stale_episodes:
                    logger.warning(f"🔄 Found {len(stale_episodes)} stale episodes. Resetting to PENDING.")
                    for ep in stale_episodes:
                        logger.info(f"   - Stale: {ep.id}")
                    
                    stmt = (
                        update(Episode)
                        .where(Episode.id.in_([ep.id for ep in stale_episodes]))
                        .values(status=EpisodeStatus.PENDING)
                    )
                    await session.execute(stmt)
                    await session.commit()
        except Exception as e:
            logger.error(f"Error in stale job monitor: {e}")
            await asyncio.sleep(60) # Retry sooner on error

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
    """Get overall statistics from PostgreSQL."""
    from podcast_transcriber_shared.database import get_session_maker, Episode as EpisodeModel, Feed as FeedModel, Summary as SummaryModel
    from sqlalchemy import select, func
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        # Feed counts
        total_feeds_query = select(func.count()).select_from(FeedModel)
        active_feeds_query = select(func.count()).select_from(FeedModel).where(FeedModel.is_active == True)
        
        # Episode counts
        pending_episodes_query = select(func.count()).select_from(EpisodeModel).where(EpisodeModel.status == EpisodeStatus.PENDING)
        selected_episodes_query = select(func.count()).select_from(EpisodeModel).where(EpisodeModel.is_selected == True)
        processed_episodes_query = select(func.count()).select_from(SummaryModel)
        
        # Podcast count (distinct podcast_name from episodes)
        total_podcasts_query = select(func.count(func.distinct(EpisodeModel.podcast_name)))
        
        total_feeds = (await session.execute(total_feeds_query)).scalar() or 0
        active_feeds = (await session.execute(active_feeds_query)).scalar() or 0
        pending_count = (await session.execute(pending_episodes_query)).scalar() or 0
        selected_count = (await session.execute(selected_episodes_query)).scalar() or 0
        processed_count = (await session.execute(processed_episodes_query)).scalar() or 0
        podcasts_count = (await session.execute(total_podcasts_query)).scalar() or 0
    
    return StatsResponse(
        active_feeds=active_feeds,
        total_feeds=total_feeds,
        total_podcasts=podcasts_count,
        total_episodes_processed=processed_count,
        pending_episodes=pending_count,
        selected_episodes=selected_count
    )


# ============================================================================
# Feed Management Endpoints
# ============================================================================

@app.get("/feeds", response_model=List[Feed])
async def list_feeds():
    """List all RSS feed subscriptions from PostgreSQL."""
    from podcast_transcriber_shared.database import get_session_maker, Feed as FeedModel
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(select(FeedModel).order_by(FeedModel.title))
        feeds = result.scalars().all()
        
        return [
            Feed(
                id=f.id,
                url=f.url,
                title=f.title,
                is_active=f.is_active,
                last_fetched_at=f.last_fetched_at
            )
            for f in feeds
        ]


@app.post("/feeds", response_model=Feed)
async def add_feed(feed_create: FeedCreate):
    """Add new RSS feed to PostgreSQL."""
    from podcast_transcriber_shared.database import get_session_maker, Feed as FeedModel
    
    # Validate feed
    is_valid, result = validate_rss_feed(feed_create.url)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid feed: {result}")
    
    feed_title = result
    feed_id = str(uuid.uuid4())
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        # Check if already exists
        existing = await session.execute(select(FeedModel).where(FeedModel.url == feed_create.url))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Feed already exists")
            
        new_feed = FeedModel(
            id=feed_id,
            url=feed_create.url,
            title=feed_title,
            is_active=True
        )
        session.add(new_feed)
        await session.commit()
        await session.refresh(new_feed)
        
        return Feed(
            id=new_feed.id,
            url=new_feed.url,
            title=new_feed.title,
            is_active=new_feed.is_active,
            last_fetched_at=new_feed.last_fetched_at
        )


@app.put("/feeds/{feed_id}", response_model=Feed)
async def update_feed(feed_id: str, feed_update: FeedUpdate):
    """Update feed in PostgreSQL (toggle active state)."""
    from podcast_transcriber_shared.database import get_session_maker, Feed as FeedModel
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        feed = await session.get(FeedModel, feed_id)
        if not feed:
            raise HTTPException(status_code=404, detail="Feed not found")
            
        feed.is_active = feed_update.is_active
        await session.commit()
        await session.refresh(feed)
        
        return Feed(
            id=feed.id,
            url=feed.url,
            title=feed.title,
            is_active=feed.is_active,
            last_fetched_at=feed.last_fetched_at
        )


@app.delete("/feeds/{feed_id}")
async def delete_feed(feed_id: str):
    """Delete RSS feed from PostgreSQL."""
    from podcast_transcriber_shared.database import get_session_maker, Feed as FeedModel
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        feed = await session.get(FeedModel, feed_id)
        if not feed:
            raise HTTPException(status_code=404, detail="Feed not found")
            
        await session.delete(feed)
        await session.commit()
        
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
            selected=ep.is_selected,  # Use robust column
            fetched_date=ep.created_at.isoformat() if ep.created_at else '',
            is_seen=ep.is_seen,
            is_favorite=ep.is_favorite,
            is_selected=ep.is_selected,
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
    Fetch new episodes from active feeds in PostgreSQL and store them.
    
    Args:
        request: Optional request body with 'days' parameter to specify
                how many days back to fetch episodes
    """
    from podcast_transcriber_shared.database import get_session_maker, Feed as FeedModel, Episode as EpisodeModel
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        # 1. Query active feeds from PostgreSQL
        result = await session.execute(select(FeedModel).where(FeedModel.is_active == True))
        active_feeds = result.scalars().all()
        
        if not active_feeds:
            raise HTTPException(status_code=400, detail="No active feeds found in database")
        
        # Get days limit from request or use None (falls back to RSS util default)
        days_limit = request.days if request else None
        
        total_new = 0
        
        # 2. Iterate through feeds and fetch episodes
        for feed in active_feeds:
            logger.info(f"🔄 Fetching episodes for: {feed.title} ({feed.url})")
            
            # Fetch episodes from RSS/Atom
            episodes_data, feed_title = fetch_episodes_from_rss(
                feed.url,
                feed.title,
                days_limit=days_limit
            )
            
            # 3. Create episodes in PostgreSQL linked to this feed
            # We do this in the same session to ensure atomicity
            new_feed_episodes = 0
            for ep_data in episodes_data:
                episode_id = ep_data.get('id')
                
                # Check if episode already exists (by ID)
                # We use session.execute with select to check existence before insert
                # or rely on the create_episode logic if we update it to handle feed_id
                
                # For this refactor, we'll implement a clean UPSERT logic here
                from sqlalchemy.dialects.postgresql import insert
                
                stmt = insert(EpisodeModel).values(
                    id=episode_id,
                    url=ep_data.get('audio_url', ''),
                    title=ep_data.get('episode_title', 'Unknown'),
                    podcast_name=feed.title,
                    feed_id=feed.id,
                    status=EpisodeStatus.PENDING,
                    meta_data={
                        'feed_url': ep_data.get('feed_url'),
                        'audio_url': ep_data.get('audio_url'),
                        'published_date': ep_data.get('published_date'),
                        'selected': False # Legacy field in meta_data
                    },
                    is_selected=False,
                    is_seen=False,
                    is_favorite=False
                ).on_conflict_do_nothing(index_elements=['id'])
                
                res = await session.execute(stmt)
                if res.rowcount > 0:
                    new_feed_episodes += 1
                    total_new += 1
            
            # 4. Update last_fetched_at for the feed
            feed.last_fetched_at = datetime.utcnow()
            logger.info(f"✅ {feed.title}: {new_feed_episodes} new episodes found.")
            
        # 5. Commit all changes (episodes + feed timestamps) in one transaction
        await session.commit()
    
    return {
        "status": "completed",
        "new_episodes": total_new,
        "days_filter": days_limit if days_limit is not None else "all"
    }


@app.put("/episodes/{episode_id}/select")
async def select_episode(episode_id: str, selection: EpisodeSelect):
    """Mark episode as selected/unselected in PostgreSQL."""
    from podcast_transcriber_shared.database import get_session_maker, Episode as EpisodeModel
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        episode = await session.get(EpisodeModel, episode_id)
        if not episode:
            raise HTTPException(status_code=404, detail="Episode not found")
        
        episode.is_selected = selection.selected
        
        # Keep legacy meta_data in sync for now if needed, though column is SSOT
        if episode.meta_data is None:
            episode.meta_data = {}
        updated_meta = episode.meta_data.copy()
        updated_meta['selected'] = selection.selected
        episode.meta_data = updated_meta
        
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
    from podcast_transcriber_shared.database import get_session_maker, Episode as EpisodeModel
    from sqlalchemy import update
    
    if not request.episode_ids:
        return {"status": "updated", "count": 0, "selected": request.selected}
        
    session_maker = get_session_maker()
    async with session_maker() as session:
        # Update is_selected column directly
        stmt = (
            update(EpisodeModel)
            .where(EpisodeModel.id.in_(request.episode_ids))
            .values(is_selected=request.selected)
        )
        result = await session.execute(stmt)
        await session.commit()
        
    return {
        "status": "updated",
        "count": result.rowcount,
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

from podcast_transcriber_shared.status_monitor import get_pipeline_status_manager

@app.get("/transcription/status", response_model=TranscriptionStatus)
async def get_transcription_status():
    """Get current transcription status including full pipeline status and active episodes."""
    manager = get_pipeline_status_manager()
    status = read_status()
    pipeline_status = manager.get_pipeline_status()
    
    active_episodes = pipeline_status.get('active_episodes', [])
    
    # Base response derived from pipeline manager
    response_data = {
        "is_running": pipeline_status['is_running'],
        "is_stopped": pipeline_status.get('is_stopped', False),
        "current_batch_id": pipeline_status.get('current_batch_id'),
        "pipeline": pipeline_status,
        "active_episodes": active_episodes,
        "gpu_name": pipeline_status.get('gpu_name'),
        "gpu_usage": pipeline_status.get('gpu_usage', 0),
        "vram_used_gb": pipeline_status.get('vram_used_gb', 0.0),
        "vram_total_gb": pipeline_status.get('vram_total_gb', 0.0),
        "recent_logs": pipeline_status.get('recent_logs', []),
        "episodes_completed": pipeline_status.get('episodes_completed', 0),
        "episodes_total": pipeline_status.get('episodes_total', 0)
    }
    
    if status:
        # Overlay episode-specific status
        response_data.update({
            "stage": status.get('stage', 'idle'),
            "progress": status.get('progress', 0.0),
            "current_episode": status.get('current_episode'),
            "current_podcast": status.get('current_podcast'),
        })
    else:
        response_data.update({
            "stage": "idle",
            "progress": 0.0
        })

    return TranscriptionStatus(**response_data)


@app.post("/transcription/stop")
async def stop_transcription():
    """Stop the transcription pipeline, clear pending job queues, and reset status."""
    manager = get_pipeline_status_manager()
    manager.set_stop_signal(True)
    
    # Purge pending job streams from Redis
    from podcast_transcriber_shared.events import get_event_bus, EventBus
    eb = get_event_bus()
    await eb.purge_stream(EventBus.STREAM_TRANSCRIPTION_JOBS)
    await eb.purge_stream(EventBus.STREAM_BATCH_TRANSCRIBED)
    await eb.purge_stream(EventBus.STREAM_BATCH_SUMMARIZED)
    
    # Clear all status and stats to return to idle state
    manager.clear_all_status()
    
    return {"status": "reset", "message": "Pipeline reset to idle state and pending job queues cleared. Busy workers will abort shortly."}


# Removed resume_transcription as per user request for simpler "reset to idle" flow.


@app.get("/batches/{batch_id}/progress", response_model=BatchProgressResponse)
async def get_batch_progress(batch_id: str):
    """
    Get detailed progress for all episodes in a batch.
    """
    from podcast_transcriber_shared.database import get_session_maker, Episode as EpisodeModel
    from sqlalchemy import select, func
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        # Fetch all episodes in this batch
        query = select(EpisodeModel).where(EpisodeModel.batch_id == batch_id)
        result = await session.execute(query)
        episodes = result.scalars().all()
        
        if not episodes:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
        
        total = len(episodes)
        transcribed_count = 0
        summarized_count = 0
        indexed_count = 0
        completed_count = 0
        
        batch_episodes = []
        for ep in episodes:
            status = ep.status
            
            # Count phases (cumulative logic)
            if status in (EpisodeStatus.TRANSCRIBED, EpisodeStatus.SUMMARIZING, 
                         EpisodeStatus.SUMMARIZED, EpisodeStatus.INDEXING, 
                         EpisodeStatus.INDEXED, EpisodeStatus.COMPLETED):
                transcribed_count += 1
                
            if status in (EpisodeStatus.SUMMARIZED, EpisodeStatus.INDEXING, 
                         EpisodeStatus.INDEXED, EpisodeStatus.COMPLETED):
                summarized_count += 1
                
            if status in (EpisodeStatus.INDEXED, EpisodeStatus.COMPLETED):
                indexed_count += 1
                
            if status == EpisodeStatus.COMPLETED:
                completed_count += 1
                
            batch_episodes.append(BatchEpisodeStatus(
                id=ep.id,
                title=ep.title,
                status=status.value
            ))
            
        # Determine overall batch status
        overall_status = "processing"
        if completed_count == total:
            overall_status = "completed"
        elif any(ep.status == EpisodeStatus.FAILED for ep in episodes):
            overall_status = "failed"
            
        return BatchProgressResponse(
            batch_id=batch_id,
            total_episodes=total,
            completed_episodes=completed_count,
            transcribed_count=transcribed_count,
            summarized_count=summarized_count,
            indexed_count=indexed_count,
            episodes=batch_episodes,
            status=overall_status,
            updated_at=datetime.utcnow()
        )


@app.post("/transcription/status/clear")
async def clear_transcription_status():
    """Manually clear all stale pipeline status and stats."""
    manager = get_pipeline_status_manager()
    manager.clear_all_status()
    return {"status": "cleared", "message": "All pipeline status and stats have been reset."}


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
    from podcast_transcriber_shared.status_monitor import get_pipeline_status_manager
    
    # Reset stop signal at start
    manager = get_pipeline_status_manager()
    manager.set_stop_signal(False)
    
    # Check if already running
    pipeline_status = manager.get_pipeline_status()
    if pipeline_status and pipeline_status.get('is_running'):
        raise HTTPException(status_code=400, detail="Transcription pipeline already in progress")
    
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
        # Case 2: Fallback to "selected" episodes in database (any status)
        all_episodes = await list_episodes()
        target_episodes = [
            {'id': ep.id, 'audio_url': ep.meta_data.get('audio_url', ep.url),
             'episode_title': ep.title, 'feed_title': ep.podcast_name}
            for ep in all_episodes if ep.meta_data and ep.meta_data.get('selected')
        ]
    
    if not target_episodes:
        raise HTTPException(status_code=400, detail="No episodes selected for transcription")
        
    # Initialize pipeline batch
    batch_id = f"batch_{uuid.uuid4().hex[:8]}"
    episode_ids = [ep['id'] for ep in target_episodes]
    manager.initialize_batch(episode_ids, len(episode_ids), batch_id)
    
    # Associate episodes with batch in database and mark as QUEUED
    await bulk_update_episodes_batch(episode_ids, batch_id, EpisodeStatus.QUEUED)
    
    # Store batch_id in manager for tracking if needed
    # (The manager already tracks active_episodes but batch_id helps for staged signaling)
    
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
                # Update metadata to set selected=False as we are now processing
                episode = await get_episode_by_id(episode_id, load_transcript=False)
                if episode:
                    updated_meta = (episode.meta_data or {}).copy()
                    updated_meta['selected'] = False
                    
                    from sqlalchemy import update
                    from podcast_transcriber_shared.database import Episode as EpisodeModel
                    session_maker = get_session_maker()
                    async with session_maker() as session:
                        stmt = (
                            update(EpisodeModel)
                            .where(EpisodeModel.id == episode_id)
                            .values(meta_data=updated_meta)
                        )
                        await session.execute(stmt)
                        await session.commit()

                # Publish to Redis Stream via EventBus
                # We do this manually here because we want to use the raw redis connection we already have
                # But to follow the pattern, we should construct the event properly

                job_data = {
                    'event_id': str(uuid.uuid4()),
                    'timestamp': datetime.now().isoformat(),
                    'service': 'transcription-api',
                    'episode_id': episode_id,
                    'audio_url': ep.get('audio_url', ''),
                    'batch_id': batch_id
                }
                
                # Sanitize None values
                if job_data['audio_url'] is None:
                    job_data['audio_url'] = ""

                # Publish to stream: stream:transcription:jobs
                r.xadd('stream:transcription:jobs', job_data, id='*')
                enqueued_count += 1
                
                logger.info(f"📤 Published transcription job for {episode_id} to stream")
                
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
            episodes_count=enqueued_count,
            batch_id=batch_id
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
