"""
Event Schemas and Redis Pub/Sub Infrastructure
Provides event-driven communication between services.
"""
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor
import redis
import json
import os
import time
import traceback
import signal
import sys


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
    diarization_failed: bool = False  # True if speaker identification failed
    
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
                "docker_transcript_path": "/app/shared/output/transcript.txt",
                "diarization_failed": False
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
    
    def __init__(self, redis_url: Optional[str] = None, max_workers: int = 4):
        """
        Initialize event bus connection.
        
        Args:
            redis_url: Redis connection URL (defaults to REDIS_URL env var)
            max_workers: Maximum number of concurrent callback threads
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client = None
        self.pubsub = None
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="EventBus")
        self._shutdown = False
        self._connect()
        
        # Register graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
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
    
    def subscribe(self, channel: str, callback: Callable[[Dict], None]):
        """
        Subscribe to a channel and process events with callback.
        Automatically reconnects on connection failures with exponential backoff.
        Callbacks are executed in background threads to prevent blocking.
        
        This is a blocking call that runs indefinitely until shutdown.
        
        Args:
            channel: Channel name to subscribe to
            callback: Function to call for each event (receives event dict)
        """
        retry_delay = 1  # Start at 1 second
        max_retry_delay = 60  # Cap at 60 seconds
        
        print(f"🔄 Starting resilient subscriber for channel: {channel}")
        print(f"   Max concurrent workers: {self.executor._max_workers}")
        
        while not self._shutdown:
            try:
                # Ensure we have a connection
                if not self.client:
                    print(f"⚠️  No Redis connection, reconnecting...")
                    self._connect()
                    if not self.client:
                        raise redis.ConnectionError("Failed to establish connection")
                
                # Subscribe to channel
                self.pubsub = self.client.pubsub()
                self.pubsub.subscribe(channel)
                
                print(f"📥 Subscribed to channel: {channel}")
                print(f"   Waiting for events...")
                
                # Reset retry delay on successful connection
                retry_delay = 1
                
                # Listen for messages (blocking loop)
                for message in self.pubsub.listen():
                    if self._shutdown:
                        print(f"\n🛑 Shutdown signal received, stopping subscriber")
                        break
                    
                    if message['type'] == 'message':
                        # Process event in background thread (non-blocking)
                        self.executor.submit(self._process_message, message['data'], callback)
                
            except redis.ConnectionError as e:
                print(f"\n❌ Lost connection to Redis: {e}")
                print(f"   Reconnecting in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)  # Exponential backoff
                
                # Clean up broken connection
                if self.pubsub:
                    try:
                        self.pubsub.close()
                    except:
                        pass
                    self.pubsub = None
                
                self.client = None
                self._connect()  # Attempt to reconnect
                
            except Exception as e:
                print(f"\n❌ Unexpected subscription error on {channel}: {e}")
                traceback.print_exc()
                print(f"   Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
        
        print(f"✅ Subscriber stopped for channel: {channel}")
    
    def _process_message(self, message_data: str, callback: Callable[[Dict], None]):
        """
        Process a single message in a background thread.
        Supports both sync and async callbacks.
        
        Args:
            message_data: JSON string from Redis
            callback: Callback function to invoke (sync or async)
        """
        try:
            # Parse event JSON
            event_data = json.loads(message_data)
            
            # Check if callback is async
            import asyncio
            import inspect
            
            if inspect.iscoroutinefunction(callback):
                # Run async callback in executor thread
                asyncio.run(callback(event_data))
            else:
                # Call sync callback directly
                callback(event_data)
            
        except Exception as e:
            print(f"❌ Error processing event: {e}")
            traceback.print_exc()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n⚠️  Received signal {signum}, shutting down EventBus...")
        self._shutdown = True
        self.close()
        sys.exit(0)
    
    def close(self):
        """Close Redis connections and shutdown thread pool."""
        print("🛑 Closing EventBus connections...")
        self._shutdown = True
        
        # Shutdown thread pool
        print("   Waiting for background tasks to complete...")
        self.executor.shutdown(wait=True, cancel_futures=False)
        
        # Close Redis connections
        if self.pubsub:
            try:
                self.pubsub.close()
            except:
                pass
        if self.client:
            try:
                self.client.close()
            except:
                pass
        
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
