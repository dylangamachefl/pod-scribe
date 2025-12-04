"""
Pydantic models for API request/response schemas.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""
    question: str = Field(..., description="User's question about the podcasts")
    episode_title: Optional[str] = Field(
        default=None,
        description="Optional episode title for episode-scoped chat"
    )
    conversation_history: Optional[List[dict]] = Field(
        default=None, 
        description="Optional conversation history for context"
    )


class SourceCitation(BaseModel):
    """Source citation for answer."""
    podcast_name: str
    episode_title: str
    speaker: str
    timestamp: str
    text_snippet: str
    relevance_score: float


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""
    answer: str = Field(..., description="Generated answer from Gemini")
    sources: List[SourceCitation] = Field(
        default=[], 
        description="Source citations from transcripts"
    )
    processing_time_ms: float


class IngestRequest(BaseModel):
    """Request schema for manual file ingestion."""
    file_path: str = Field(..., description="Path to transcript file")


class IngestResponse(BaseModel):
    """Response schema for ingestion endpoint."""
    status: str
    message: str
    chunks_created: int
    episode_title: Optional[str] = None
    podcast_name: Optional[str] = None


class SummaryResponse(BaseModel):
    """Response schema for summary retrieval."""
    episode_title: str
    podcast_name: str
    summary: str
    key_topics: List[str]
    speakers: List[str]
    duration: Optional[str] = None
    created_at: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    qdrant_connected: bool
    embedding_model_loaded: bool
    gemini_api_configured: bool
