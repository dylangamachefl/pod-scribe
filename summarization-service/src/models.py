"""
Pydantic models for the summarization service.
"""
from typing import List, Optional, Dict, Any
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
    
    # Core structured fields (matching StructuredSummaryV2)
    hook: str
    key_takeaways: List[Dict[str, str]]
    actionable_advice: List[str]
    quotes: List[str]
    concepts: List[Dict[str, str]]
    perspectives: str
    summary: str
    key_topics: List[str]
    
    # Legacy fields for backward compatibility
    insights: Optional[List[str]] = None  # Deprecated, mapped from key_takeaways
    
    # Metadata
    speakers: Optional[List[str]] = None
    duration: Optional[str] = None
    audio_url: Optional[str] = None
    processing_time_ms: Optional[float] = None  # Legacy: use total_processing_time_ms
    created_at: Optional[str] = None
    source_file: Optional[str] = None
    
    # Two-stage metadata
    stage1_processing_time_ms: Optional[float] = None
    stage2_processing_time_ms: Optional[float] = None
    total_processing_time_ms: Optional[float] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    gemini_api_configured: bool
    model_name: str
    event_subscriber_active: bool = True
