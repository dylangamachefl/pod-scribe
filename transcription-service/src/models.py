"""
Pydantic Models for Transcription Service
Provides type-safe data models for episode data and processing results.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class EpisodeData(BaseModel):
    """Model for episode data from RSS feed or queue."""
    
    # Core fields
    id: str = Field(..., description="Unique identifier (GUID or link)")
    episode_title: str = Field(..., description="Episode title")
    feed_title: str = Field(..., description="Podcast/feed name")
    audio_url: str = Field(..., description="URL to audio file or YouTube video")
    
    # Optional metadata
    link: Optional[str] = Field(None, description="Episode web link")
    published: Optional[str] = Field(None, description="Publication date")
    description: Optional[str] = Field(None, description="Episode description")
    duration: Optional[int] = Field(None, description="Duration in seconds")
    
    # Internal tracking
    from_queue: bool = Field(default=False, description="True if from pending queue")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "https://example.com/episode-123",
                "episode_title": "How to Build Great Software",
                "feed_title": "Tech Podcast",
                "audio_url": "https://example.com/audio.mp3",
                "from_queue": False
            }
        }


class TranscriptMetadata(BaseModel):
    """Model for transcript metadata."""
    
    episode_title: str
    podcast_name: str
    processed_date: datetime = Field(default_factory=datetime.now)
    transcript_path: str
    audio_url: Optional[str] = None
    duration: Optional[int] = None
    speakers: Optional[List[str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "episode_title": "Episode 1",
                "podcast_name": "My Podcast",
                "processed_date": "2025-12-10T12:00:00",
                "transcript_path": "/app/shared/output/episode1.txt",
                "audio_url": "https://example.com/audio.mp3"
            }
        }


class ProcessingResult(BaseModel):
    """Model for episode processing results."""
    
    success: bool
    episode_id: str
    episode_title: str
    transcript_path: Optional[str] = None
    error_message: Optional[str] = None
    rag_ingested: bool = Field(default=False, description="Successfully ingested to RAG")
    summary_created: bool = Field(default=False, description="Summary created")
    processing_time_seconds: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "episode_id": "ep-123",
                "episode_title": "Episode 1",
                "transcript_path": "/app/shared/output/episode1.txt",
                "rag_ingested": True,
                "summary_created": False,
                "processing_time_seconds": 245.5
            }
        }


class ServiceConfig(BaseModel):
    """Model for external service configuration."""
    
    name: str
    url: str
    timeout_seconds: int = Field(default=60)
    retry_attempts: int = Field(default=3)
    retry_delay_seconds: float = Field(default=2.0)
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "RAG Service",
                "url": "http://localhost:8000",
                "timeout_seconds": 60,
                "retry_attempts": 3
            }
        }
