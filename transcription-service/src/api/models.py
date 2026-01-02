"""
API Models for Transcription Service
Pydantic models for request/response validation.
"""
from typing import Optional, List
from pydantic import BaseModel, HttpUrl
from datetime import datetime


# Feed Models
class FeedCreate(BaseModel):
    url: str


class FeedUpdate(BaseModel):
    active: bool


class Feed(BaseModel):
    id: str
    url: str
    title: str
    active: bool


# Episode Models
class Episode(BaseModel):
    id: str
    episode_title: str
    feed_title: str
    published_date: str
    duration: Optional[str] = None
    audio_url: str
    selected: bool = False
    is_seen: bool = False
    is_favorite: bool = False
    status: str = "pending"  # pending, processing, completed, failed


class EpisodeSelect(BaseModel):
    selected: bool


class BulkSelectRequest(BaseModel):
    episode_ids: List[str]
    selected: bool


class EpisodeFetchRequest(BaseModel):
    """Request model for fetching episodes from feeds."""
    days: Optional[int] = None  # Number of days to look back, None = use default from env


class BulkSeenRequest(BaseModel):
    """Request model for marking episodes as seen/unseen."""
    episode_ids: List[str]
    seen: bool = True


class EpisodeFavoriteUpdate(BaseModel):
    """Request model for toggling an episode as favorite."""
    is_favorite: bool = True


# Transcription Models
class PipelineStage(BaseModel):
    active: bool
    completed: int
    total: int
    current: Optional[dict] = None

class PipelineStatus(BaseModel):
    is_running: bool
    stages: dict[str, PipelineStage]

class TranscriptionStatus(BaseModel):
    is_running: bool
    current_episode: Optional[str] = None
    current_podcast: Optional[str] = None
    stage: str = "idle"  # idle, preparing, downloading, transcribing, diarizing, saving
    progress: float = 0.0
    episodes_completed: int = 0
    episodes_total: int = 0
    gpu_name: Optional[str] = None
    gpu_usage: int = 0
    vram_used_gb: float = 0.0
    vram_total_gb: float = 0.0
    start_time: Optional[str] = None
    recent_logs: List[str] = []
    pipeline: Optional[PipelineStatus] = None


class TranscriptionStartRequest(BaseModel):
    episode_ids: Optional[List[str]] = None  # If None, process all selected


class TranscriptionStartResponse(BaseModel):
    status: str
    message: str
    episodes_count: int


# Transcript Models
class PodcastInfo(BaseModel):
    name: str
    episode_count: int


class EpisodeInfo(BaseModel):
    name: str
    file_path: str


class TranscriptResponse(BaseModel):
    podcast_name: str
    episode_name: str
    content: str


# Stats Models
class StatsResponse(BaseModel):
    active_feeds: int
    total_feeds: int
    total_podcasts: int
    total_episodes_processed: int
    pending_episodes: int
    selected_episodes: int


# Health Models
class HealthResponse(BaseModel):
    status: str
    api_version: str
    transcription_service_available: bool
