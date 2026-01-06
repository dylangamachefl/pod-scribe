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
# Event Schemas (Lightweight)
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
    diarization_failed: bool = False


class EpisodeSummarized(BaseEvent):
    """Event published when an episode summary is generated."""
    episode_id: str
    episode_title: str
    podcast_name: str


class EpisodeIngested(BaseEvent):
    """Event published when an episode is ingested into RAG."""
    episode_id: str
    episode_title: str
    podcast_name: str
    chunks_created: int


# =================================================================
# Redis Streams Client
# =================================================================

class EventBus:
    """
    Redis-based event bus using Redis Streams for reliable messaging.
    Handles event publishing, persistent subscription, and consumer groups.
    """
    
    # Stream names
    STREAM_TRANSCRIBED = "stream:episodes:transcribed"
    STREAM_SUMMARIZED = "stream:episodes:summarized"
    STREAM_INGESTED = "stream:episodes:ingested"
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize event bus connection.
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client = None
        self._shutdown = False
    
    async def _connect(self):
        """Establish Redis connection."""
        if self.client:
            return

        try:
            self.client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                health_check_interval=30
            )
            await self.client.ping()
            print(f"✅ Redis EventBus (Streams) connected: {self.redis_url}")
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")
            self.client = None
    
    async def publish(self, stream: str, event: BaseEvent) -> bool:
        """
        Publish an event to a Redis Stream asynchronously.
        """
        if not self.client:
            await self._connect()

        if not self.client:
            return False
        
        try:
            # Serialize event to dict for Redis Stream
            event_data = event.model_dump(mode='json')
            
            # Sanitize booleans for Redis (Redis Streams don't accept bools with decode_responses=True)
            for key, value in event_data.items():
                if isinstance(value, bool):
                    event_data[key] = 1 if value else 0
            
            # XADD to stream
            # * means auto-generate entry ID
            await self.client.xadd(stream, event_data, id='*')
            
            print(f"📤 Published event to {stream}: {event.event_id}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to publish event to {stream}: {e}")
            self.client = None
            return False
    
    async def subscribe(
        self, 
        stream: str, 
        group_name: str, 
        consumer_name: str, 
        callback: Callable[[Dict], Awaitable[None]]
    ):
        """
        Subscribe to a Redis Stream using a consumer group.
        Provides reliability and persistence: if the service is down,
        it will pick up missed events when it resumes.
        """
        if not self.client:
            await self._connect()
        
        # Create consumer group if it doesn't exist
        try:
            # Attempt to create group starting from the beginning of the stream ($ for only new events, 0 for all)
            await self.client.xgroup_create(stream, group_name, id='0', mkstream=True)
            print(f"✅ Created consumer group '{group_name}' for stream '{stream}'")
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                print(f"⚠️  Error creating consumer group: {e}")
        
        print(f"📥 Subscribed to {stream} as {consumer_name} (Group: {group_name})")
        
        while not self._shutdown:
            try:
                # Read from stream in consumer group
                # > means read only new messages not delivered to other consumers in the group
                messages = await self.client.xreadgroup(
                    groupname=group_name,
                    consumername=consumer_name,
                    streams={stream: '>'},
                    count=1,
                    block=5000  # Block for 5 seconds
                )
                
                if messages:
                    for stream_name, entries in messages:
                        for entry_id, entry_data in entries:
                            # Process the entry
                            await self._process_entry(entry_id, entry_data, callback)
                            # Acknowledge the message
                            await self.client.xack(stream, group_name, entry_id)
                            
            except (redis.ConnectionError, OSError) as e:
                print(f"❌ Redis connection error: {e}")
                await asyncio.sleep(5)
                self.client = None
                await self._connect()
            except Exception as e:
                print(f"❌ Error in stream consumer: {e}")
                await asyncio.sleep(1)

    async def _process_entry(self, entry_id: str, entry_data: dict, callback: Callable[[Dict], Awaitable[None]]):
        """Process a single stream entry."""
        try:
            if inspect.iscoroutinefunction(callback):
                await callback(entry_data)
            else:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, callback, entry_data)
        except Exception as e:
            print(f"❌ Error processing event {entry_id}: {e}")
            traceback.print_exc()
    
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
