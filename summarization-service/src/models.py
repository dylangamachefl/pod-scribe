"""
Pydantic models for the summarization service.
"""
from typing import List, Optional
from pydantic import BaseModel


class SummarizeRequest(BaseModel):
    """Request model for manual summarization."""
    podcast_name: str
    episode_title: str
    transcript_text: str


class SummaryResponse(BaseModel):
    """Response model for summary data."""
    episode_title: str
    podcast_name: str
    summary: str
    key_topics: List[str]
    insights: List[str]
    quotes: List[str]
    speakers: Optional[List[str]] = None
    duration: Optional[str] = None
    audio_url: Optional[str] = None
    processing_time_ms: Optional[float] = None
    created_at: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    gemini_api_configured: bool
    model_name: str
    file_watcher_active: bool
