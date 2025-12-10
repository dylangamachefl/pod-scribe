"""
Event Schemas and Redis Pub/Sub Infrastructure
Provides event-driven communication between services.
"""
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import redis
import json
import os


# =================================================================
# Event Schemas
# =================================================================

class BaseEvent(BaseModel):
    """Base class for all events."""
    event_id: str = Field(..., description="Unique event identifier")
    timestamp: datetime = Field(default_factory=datetime.now)
    service: str = Field(..., description="Service that published the event")


class EpisodeTranscribed(BaseEvent):
    """Event published when an episode is successfully transcribed."""
    episode_id: str
    episode_title: str
    podcast_name: str
    transcript_path: str  # Absolute path on host
    docker_transcript_path: str  # Docker container path
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "evt_123",
                "timestamp": "2025-12-10T12:00:00",
                "service": "transcription",
                "episode_id": "ep_456",
                "episode_title": "How to Build Great Software",
                "podcast_name": "Tech Podcast",
                "transcript_path": "C:/path/to/transcript.txt",
                "docker_transcript_path": "/app/shared/output/transcript.txt"
            }
        }


class EpisodeSummarized(BaseEvent):
    """Event published when an episode summary is generated."""
    episode_id: str
    episode_title: str
    podcast_name: str
    summary_path: str  # Path to summary JSON file
    summary_data: Dict[str, Any]  # Summary content
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "evt_789",
                "timestamp": "2025-12-10T12:05:00",
                "service": "summarization",
                "episode_id": "ep_456",
                "episode_title": "How to Build Great Software",
                "podcast_name": "Tech Podcast",
                "summary_path": "/app/shared/summaries/episode_summary.json",
                "summary_data": {"hook": "...", "key_takeaways": [...]}
            }
        }


class EpisodeIngested(BaseEvent):
    """Event published when an episode is ingested into RAG."""
    episode_id: str
    episode_title: str
    podcast_name: str
    chunks_created: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "evt_012",
                "timestamp": "2025-12-10T12:10:00",
                "service": "rag",
                "episode_id": "ep_456",
                "episode_title": "How to Build Great Software",
                "podcast_name": "Tech Podcast",
                "chunks_created": 50
            }
        }


# =================================================================
# Redis Pub/Sub Client
# =================================================================

class EventBus:
    """
    Redis-based event bus for pub/sub messaging between services.
    Handles event publishing, subscription, and automatic reconnection.
    """
    
    # Event channel names
    CHANNEL_TRANSCRIBED = "episodes:transcribed"
    CHANNEL_SUMMARIZED = "episodes:summarized"
    CHANNEL_INGESTED = "episodes:ingested"
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize event bus connection.
        
        Args:
            redis_url: Redis connection URL (defaults to REDIS_URL env var)
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client = None
        self.pubsub = None
        self._connect()
    
    def _connect(self):
        """Establish Redis connection with retry logic."""
        try:
            self.client = redis.from_url(
                self.redis_url,
                decode_responses=True,  # Auto-decode bytes to strings
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.client.ping()
            print(f"✅ Redis EventBus connected: {self.redis_url}")
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")
            print(f"   Redis URL: {self.redis_url}")
            print(f"   Events will not be published/received")
            self.client = None
    
    def publish(self, channel: str, event: BaseEvent) -> bool:
        """
        Publish an event to a channel.
        
        Args:
            channel: Channel name (use CHANNEL_* constants)
            event: Event object to publish
            
        Returns:
            True if published successfully, False otherwise
        """
        if not self.client:
            print(f"⚠️  EventBus not connected, cannot publish to {channel}")
            return False
        
        try:
            # Serialize event to JSON
            event_json = event.model_dump_json()
            
            # Publish to Redis channel
            num_subscribers = self.client.publish(channel, event_json)
            
            print(f"📤 Published event to {channel}: {event.event_id} ({num_subscribers} subscribers)")
            return True
            
        except Exception as e:
            print(f"❌ Failed to publish event to {channel}: {e}")
            return False
    
    def subscribe(self, channel: str, callback):
        """
        Subscribe to a channel and process events with callback.
        This is a blocking call that runs in a loop.
        
        Args:
            channel: Channel name to subscribe to
            callback: Function to call for each event (receives event dict)
        """
        if not self.client:
            print(f"❌ EventBus not connected, cannot subscribe to {channel}")
            return
        
        try:
            # Create pubsub instance
            self.pubsub = self.client.pubsub()
            self.pubsub.subscribe(channel)
            
            print(f"📥 Subscribed to channel: {channel}")
            print(f"   Waiting for events...")
            
            # Listen for messages (blocking loop)
            for message in self.pubsub.listen():
                if message['type'] == 'message':
                    try:
                        # Parse event JSON
                        event_data = json.loads(message['data'])
                        
                        # Call callback with event data
                        callback(event_data)
                        
                    except Exception as e:
                        print(f"❌ Error processing event: {e}")
                        import traceback
                        traceback.print_exc()
                        
        except Exception as e:
            print(f"❌ Subscription error on {channel}: {e}")
        finally:
            if self.pubsub:
                self.pubsub.close()
    
    def close(self):
        """Close Redis connections."""
        if self.pubsub:
            self.pubsub.close()
        if self.client:
            self.client.close()
        print("✅ EventBus connections closed")


# =================================================================
# Singleton Instance
# =================================================================

_event_bus = None

def get_event_bus() -> EventBus:
    """Get or create the global EventBus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
