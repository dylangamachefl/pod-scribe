"""
Database Layer for Podcast Transcriber
Centralized PostgreSQL database for episodes, transcripts, and summaries.
"""
import os
from datetime import datetime
from typing import Optional, List
from enum import Enum

from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Boolean, Enum as SQLEnum,
    ForeignKey, create_engine, select, update
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship, defer
from sqlalchemy.sql import func


# Base class for all models
Base = declarative_base()


class EpisodeStatus(str, Enum):
    """Episode processing status"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Episode(Base):
    """
    Episode model - stores podcast episodes and transcripts.
    
    The transcript_text column can be large (50-100KB per episode).
    Use deferred loading when listing episodes to avoid memory issues.
    """
    __tablename__ = "episodes"
    
    # Primary identifier (GUID from RSS feed)
    id = Column(String(255), primary_key=True, index=True)
    
    # Episode metadata
    url = Column(String(2048), unique=True, nullable=False, index=True)
    title = Column(String(512), nullable=False)
    podcast_name = Column(String(255), nullable=False, index=True)
    
    # Processing status
    status = Column(
        SQLEnum(EpisodeStatus, name="episode_status", native_enum=False),
        nullable=False,
        default=EpisodeStatus.PENDING,
        index=True
    )
    
    # Full transcript text (can be large - use deferred loading)
    transcript_text = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    #灵活元数据（扬声器、持续时间、audio_url等）
    meta_data = Column(JSONB, nullable=True, default={})
    
    # Seen status for inbox management
    is_seen = Column(Boolean, default=False, nullable=False, index=True)
    
    # Relationship to summaries
    summaries = relationship("Summary", back_populates="episode", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Episode(id={self.id}, title={self.title}, status={self.status})>"


class Summary(Base):
    """
    Summary model - stores structured summaries for episodes.
    """
    __tablename__ = "summaries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    episode_id = Column(String(255), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Structured summary data (hook, key_takeaways, quotes, etc.)
    content = Column(JSONB, nullable=False)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationship to episode
    episode = relationship("Episode", back_populates="summaries")
    
    def __repr__(self):
        return f"<Summary(id={self.id}, episode_id={self.episode_id})>"


# Database connection
_engine = None
_async_session_maker = None


def get_engine():
    """Get or create async SQLAlchemy engine from DATABASE_URL."""
    global _engine
    if _engine is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")
        
        # Ensure we're using asyncpg driver
        if not database_url.startswith("postgresql+asyncpg://"):
            if database_url.startswith("postgresql://"):
                database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            else:
                raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        
        _engine = create_async_engine(
            database_url,
            echo=False,  # Set to True for SQL query logging
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Verify connections before using
        )
    return _engine


def get_session_maker():
    """Get or create async session maker."""
    global _async_session_maker
    if _async_session_maker is None:
        engine = get_engine()
        _async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_maker


async def get_session() -> AsyncSession:
    """Get an async database session."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session


async def init_db():
    """Initialize database - create tables if they don't exist."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables initialized")


# ============================================================================
# Episode CRUD Operations
# ============================================================================

async def get_episode_by_id(episode_id: str, load_transcript: bool = True) -> Optional[Episode]:
    """
    Fetch episode by ID.
    
    Args:
        episode_id: Unique episode identifier
        load_transcript: If False, defers loading transcript_text column (more efficient)
    
    Returns:
        Episode object or None if not found
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        query = select(Episode).where(Episode.id == episode_id)
        
        if not load_transcript:
            query = query.options(defer(Episode.transcript_text))
        
        result = await session.execute(query)
        return result.scalar_one_or_none()


async def list_episodes(
    podcast_name: Optional[str] = None,
    status: Optional[EpisodeStatus] = None,
    is_seen: Optional[bool] = None,
    limit: Optional[int] = None
) -> List[Episode]:
    """
    List episodes without loading full transcript text (uses deferred loading).
    
    Args:
        podcast_name: Filter by podcast name (optional)
        status: Filter by status (optional)
        is_seen: Filter by seen status (optional)
        limit: Maximum number of episodes to return (None for all)
    
    Returns:
        List of Episode objects (transcript_text not loaded)
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        query = select(Episode).options(defer(Episode.transcript_text))
        
        if podcast_name:
            query = query.where(Episode.podcast_name == podcast_name)
        
        if status:
            query = query.where(Episode.status == status)
            
        if is_seen is not None:
            query = query.where(Episode.is_seen == is_seen)
        
        query = query.order_by(Episode.created_at.desc())
        
        if limit is not None:
            query = query.limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()


async def mark_episodes_as_seen(
    episode_ids: List[str],
    seen: bool = True
) -> int:
    """
    Bulk update episodes' seen status.
    
    Args:
        episode_ids: List of episode IDs to update
        seen: Whether to mark as seen or unseen
    
    Returns:
        Number of updated rows
    """
    if not episode_ids:
        return 0
        
    session_maker = get_session_maker()
    async with session_maker() as session:
        query = (
            update(Episode)
            .where(Episode.id.in_(episode_ids))
            .values(is_seen=seen)
        )
        result = await session.execute(query)
        await session.commit()
        return result.rowcount


async def create_episode(
    episode_id: str,
    url: str,
    title: str,
    podcast_name: str,
    status: EpisodeStatus = EpisodeStatus.PENDING,
    meta_data: Optional[dict] = None
) -> Episode:
    """
    Create a new episode.
    
    Args:
        episode_id: Unique episode identifier (GUID from RSS)
        url: Audio URL
        title: Episode title
        podcast_name: Podcast name
        status: Initial status (default: PENDING)
        meta_data: Optional metadata dict
    
    Returns:
        Created Episode object
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        episode = Episode(
            id=episode_id,
            url=url,
            title=title,
            podcast_name=podcast_name,
            status=status,
            meta_data=meta_data or {}
        )
        session.add(episode)
        await session.commit()
        await session.refresh(episode)
        return episode


async def update_episode_status(
    episode_id: str,
    status: EpisodeStatus,
    processed_at: Optional[datetime] = None
) -> Optional[Episode]:
    """
    Update episode status.
    
    Args:
        episode_id: Episode identifier
        status: New status
        processed_at: Optional timestamp (defaults to now if status is COMPLETED or FAILED)
    
    Returns:
        Updated Episode or None if not found
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        episode = await session.get(Episode, episode_id)
        if not episode:
            return None
        
        episode.status = status
        
        if processed_at:
            episode.processed_at = processed_at
        elif status in (EpisodeStatus.COMPLETED, EpisodeStatus.FAILED):
            episode.processed_at = datetime.utcnow()
        
        await session.commit()
        await session.refresh(episode)
        return episode


async def save_transcript(
    episode_id: str,
    transcript_text: str,
    metadata: Optional[dict] = None
) -> Optional[Episode]:
    """
    Save transcript text to episode.
    
    Args:
        episode_id: Episode identifier
        transcript_text: Full transcript text
        metadata: Optional metadata to merge with existing
    
    Returns:
        Updated Episode or None if not found
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        episode = await session.get(Episode, episode_id)
        if not episode:
            return None
        
        episode.transcript_text = transcript_text
        episode.status = EpisodeStatus.COMPLETED
        episode.processed_at = datetime.utcnow()
        
        if metadata:
            # Merge new metadata with existing
            episode.meta_data = {**(episode.meta_data or {}), **metadata}
        
        await session.commit()
        await session.refresh(episode)
        return episode


# ============================================================================
# Summary CRUD Operations
# ============================================================================

async def get_summary_by_episode_id(episode_id: str) -> Optional[Summary]:
    """
    Get summary for an episode.
    
    Args:
        episode_id: Episode identifier
    
    Returns:
        Summary object or None if not found
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        query = select(Summary).where(Summary.episode_id == episode_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()


async def save_summary(episode_id: str, content: dict) -> Summary:
    """
    Save summary for an episode.
    
    Args:
        episode_id: Episode identifier
        content: Summary content (JSONB)
    
    Returns:
        Created Summary object
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        summary = Summary(
            episode_id=episode_id,
            content=content
        )
        session.add(summary)
        await session.commit()
        await session.refresh(summary)
        return summary
