"""
Event Schemas and Redis Pub/Sub Infrastructure
Provides event-driven communication between services.
"""
from typing import Optional, Dict, Any, Callable, Awaitable
from datetime import datetime
from pydantic import BaseModel, Field
import redis.asyncio as redis
import json
import os
import time
import traceback
import signal
import sys
import asyncio
import inspect


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
    Uses redis.asyncio for non-blocking I/O.
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
        self._shutdown = False
    
    async def _connect(self):
        """Establish Redis connection with retry logic."""
        if self.client:
            return

        try:
            self.client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            await self.client.ping()
            print(f"✅ Redis EventBus connected: {self.redis_url}")
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")
            print(f"   Redis URL: {self.redis_url}")
            print(f"   Events will not be published/received")
            self.client = None
    
    async def publish(self, channel: str, event: BaseEvent) -> bool:
        """
        Publish an event to a channel asynchronously.
        
        Args:
            channel: Channel name (use CHANNEL_* constants)
            event: Event object to publish
            
        Returns:
            True if published successfully, False otherwise
        """
        if not self.client:
            await self._connect()

        if not self.client:
            print(f"⚠️  EventBus not connected, cannot publish to {channel}")
            return False
        
        try:
            # Serialize event to JSON
            event_json = event.model_dump_json()
            
            # Publish to Redis channel
            num_subscribers = await self.client.publish(channel, event_json)
            
            print(f"📤 Published event to {channel}: {event.event_id} ({num_subscribers} subscribers)")
            return True
            
        except Exception as e:
            print(f"❌ Failed to publish event to {channel}: {e}")
            # Try to reconnect for next time
            self.client = None
            return False
    
    async def subscribe(self, channel: str, callback: Callable[[Dict], Awaitable[None]]):
        """
        Subscribe to a channel and process events with callback.
        Automatically reconnects on connection failures with exponential backoff.
        
        This is a blocking call (awaitable) that runs indefinitely until shutdown.
        
        Args:
            channel: Channel name to subscribe to
            callback: Async function to call for each event (receives event dict)
        """
        retry_delay = 1  # Start at 1 second
        max_retry_delay = 60  # Cap at 60 seconds
        
        print(f"🔄 Starting async subscriber for channel: {channel}")
        
        while not self._shutdown:
            pubsub = None
            try:
                # Ensure we have a connection
                await self._connect()
                if not self.client:
                    raise redis.ConnectionError("Failed to establish connection")
                
                # Subscribe to channel
                pubsub = self.client.pubsub()
                await pubsub.subscribe(channel)
                
                print(f"📥 Subscribed to channel: {channel}")
                print(f"   Waiting for events...")
                
                # Reset retry delay on successful connection
                retry_delay = 1
                
                # Listen for messages (async generator)
                async for message in pubsub.listen():
                    if self._shutdown:
                        print(f"\n🛑 Shutdown signal received, stopping subscriber")
                        break
                    
                    if message['type'] == 'message':
                        # Process event in background task (fire and forget)
                        # This ensures one slow callback doesn't block receiving other messages
                        asyncio.create_task(self._process_message(message['data'], callback))
                
            except (redis.ConnectionError, OSError) as e:
                print(f"\n❌ Lost connection to Redis: {e}")
                print(f"   Reconnecting in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)  # Exponential backoff
                
                self.client = None # Force reconnect
                
            except asyncio.CancelledError:
                print("🛑 Subscriber task cancelled")
                break
                
            except Exception as e:
                print(f"\n❌ Unexpected subscription error on {channel}: {e}")
                traceback.print_exc()
                print(f"   Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)

            finally:
                if pubsub:
                    try:
                        await pubsub.close()
                    except:
                        pass
        
        print(f"✅ Subscriber stopped for channel: {channel}")
    
    async def _process_message(self, message_data: str, callback: Callable[[Dict], Awaitable[None]]):
        """
        Process a single message.
        """
        try:
            # Parse event JSON
            event_data = json.loads(message_data)
            
            # Check if callback is async
            if inspect.iscoroutinefunction(callback):
                await callback(event_data)
            else:
                # If sync, run in thread pool to avoid blocking the loop
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, callback, event_data)
            
        except Exception as e:
            print(f"❌ Error processing event: {e}")
            traceback.print_exc()
    
    def register_signal_handlers(self):
        """
        Register signal handlers for graceful shutdown.
        MUST be called from the main thread only.
        """
        import threading
        if threading.current_thread() is not threading.main_thread():
             # We can't register signals in background threads, so we just ignore/log
             # This is common in dev servers with reloaders
             print("⚠️  Not registering signal handlers (not main thread)")
             return
        
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            print("✅ Signal handlers registered for graceful shutdown")
        except ValueError:
            print("⚠️  Failed to register signal handlers")

    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n⚠️  Received signal {signum}, shutting down EventBus...")
        self._shutdown = True
        # Note: We can't await close() here easily because this is a sync signal handler
        # But setting _shutdown = True will stop the loops
    
    async def close(self):
        """Close Redis connections."""
        print("🛑 Closing EventBus connections...")
        self._shutdown = True
        
        if self.client:
            try:
                await self.client.close()
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
