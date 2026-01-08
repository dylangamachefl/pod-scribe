"""
Event Schemas and Redis Pub/Sub Infrastructure
Provides event-driven communication between services.
"""
from typing import Optional, Dict, Any, Callable, Awaitable
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
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
    # Enriched fields to reduce downstream database queries
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    speaker_count: Optional[int] = None


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


class TranscriptionJob(BaseEvent):
    """Event published to queue a transcription job."""
    episode_id: str
    audio_url: Optional[str] = None
    batch_id: Optional[str] = None  # Optional batch association


class BatchTranscribed(BaseEvent):
    """Event published when a batch of transcriptions is complete."""
    batch_id: str
    episode_ids: list[str]

    @field_validator('episode_ids', mode='before')
    @classmethod
    def parse_episode_ids(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v


class BatchSummarized(BaseEvent):
    """Event published when a batch of summaries is complete."""
    batch_id: str
    episode_ids: list[str]

    @field_validator('episode_ids', mode='before')
    @classmethod
    def parse_episode_ids(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v


class BatchIngested(BaseEvent):
    """Event published when a batch of episodes is ingested into RAG."""
    batch_id: str
    episode_ids: list[str]

    @field_validator('episode_ids', mode='before')
    @classmethod
    def parse_episode_ids(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v


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
    STREAM_TRANSCRIPTION_JOBS = "stream:transcription:jobs"
    STREAM_BATCH_TRANSCRIBED = "stream:batch:transcribed"
    STREAM_BATCH_SUMMARIZED = "stream:batch:summarized"
    STREAM_DLQ = "stream:dlq"
    
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
            # Serialize event to dict for Redis Stream, excluding None values
            event_data = event.model_dump(mode='json', exclude_none=True)
            
            # Sanitize types for Redis Stream
            for key, value in event_data.items():
                if isinstance(value, bool):
                    event_data[key] = 1 if value else 0
                elif isinstance(value, list):
                    event_data[key] = json.dumps(value)
            
            # XADD to stream
            await self.client.xadd(stream, event_data, id='*')
            
            print(f"📤 Published event to {stream}: {event.event_id}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to publish event to {stream}: {e}")
            # Don't set self.client = None immediately unless it's a connection error
            if isinstance(e, (redis.ConnectionError, redis.TimeoutError)):
                self.client = None
            return False

    async def purge_stream(self, stream: str):
        """
        Purge all messages from a Redis Stream.
        Useful for stopping/clearing the pipeline.
        """
        if not self.client:
            await self._connect()
        
        if not self.client:
            return
            
        try:
            # XTRIM with MAXLEN 0 effectively deletes all messages
            await self.client.xtrim(stream, maxlen=0)
            print(f"🗑️ Purged stream: {stream}")
        except Exception as e:
            print(f"❌ Failed to purge stream {stream}: {e}")
    
    async def subscribe(
        self, 
        stream: str, 
        group_name: str, 
        consumer_name: str, 
        callback: Callable[[Dict], Awaitable[bool]]
    ):
        """
        Subscribe to a Redis Stream using a consumer group.
        Provides reliability and persistence.
        """
        if not self.client:
            await self._connect()
        
        # Create consumer group if it doesn't exist
        try:
            await self.client.xgroup_create(stream, group_name, id='0', mkstream=True)
            print(f"✅ Created consumer group '{group_name}' for stream '{stream}'")
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                print(f"⚠️  Error creating consumer group: {e}")
        
        print(f"📥 Subscribed to {stream} as {consumer_name} (Group: {group_name})")
        
        while not self._shutdown:
            try:
                if not self.client:
                    await self._connect()
                    if not self.client:
                        await asyncio.sleep(5)
                        continue
                # 1. Process pending messages (recover from crashes)
                # Instead of simple XREADGROUP '0', we use XPENDING + XCLAIM to ensure
                # delivery count increments and we can handle retries/DLQ logic.

                # Get info on pending messages for this consumer
                pending_info = await self.client.xpending_range(
                    stream, group_name, min='-', max='+', count=20, consumername=consumer_name
                )
                
                if pending_info:
                    for message_info in pending_info:
                        # message_info is a dict with keys: message_id, consumer, time_since_delivered, times_delivered
                        entry_id = message_info.get('message_id')
                        delivery_count = message_info.get('times_delivered', 1)  # Use 'times_delivered' not 'delivery_count'

                        # Check DLQ threshold
                        if delivery_count > 5:
                            print(f"💀 Moving pending message {entry_id} to DLQ (count: {delivery_count})")
                            await self._move_to_dlq(stream, group_name, entry_id)
                            continue

                        # Fetch message data using XCLAIM (re-claim from self to fetch data + ensure ownership)
                        # Note: XCLAIM usually claims from *others*, but claiming from self works to get data.
                        # However, to be efficient, we can just use XREADGROUP with ID '0' but we want to know *which* failed.

                        # Force increment delivery count by claiming it again (even from self)
                        claimed_messages = await self.client.xclaim(
                            stream, group_name, consumer_name,
                            min_idle_time=0,
                            message_ids=[entry_id]
                        )

                        if claimed_messages:
                            for _, entry_data in claimed_messages:
                                print(f"🔄 Resuming pending event {entry_id} (Attempt {delivery_count})")
                                success = await self._process_entry_safe(entry_id, entry_data, callback)

                                if success and self.client:
                                    await self.client.xack(stream, group_name, entry_id)
                                else:
                                    # Failed again or connection lost.
                                    await asyncio.sleep(1)

                # 2. Read only new messages (ID '>')
                messages = await self.client.xreadgroup(
                    groupname=group_name,
                    consumername=consumer_name,
                    streams={stream: '>'},
                    count=1,
                    block=5000
                )
                
                if messages:
                    for stream_name, entries in messages:
                        for entry_id, entry_data in entries:
                            success = await self._process_entry_safe(entry_id, entry_data, callback)

                            if success and self.client:
                                await self.client.xack(stream, group_name, entry_id)
                            # If failed, it stays in PEL and will be picked up by pending loop above
                            # with incremented delivery count next time.
                            
            except (redis.ConnectionError, OSError) as e:
                print(f"❌ Redis connection error: {e}")
                await asyncio.sleep(5)
                self.client = None
                await self._connect()
            except Exception as e:
                print(f"❌ Error in stream consumer: {e}")
                await asyncio.sleep(1)

    async def _process_entry_safe(self, entry_id: str, entry_data: dict, callback: Callable[[Dict], Awaitable[bool]]) -> bool:
        """
        Process a single stream entry with error handling.
        Returns True if successful, False otherwise.
        """
        try:
            result = False
            if inspect.iscoroutinefunction(callback):
                result = await callback(entry_data)
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, callback, entry_data)

            return result is True

        except Exception as e:
            print(f"❌ Error processing event {entry_id}: {e}")
            traceback.print_exc()
            return False

    async def _move_to_dlq(self, stream: str, group_name: str, entry_id: str):
        """
        Move a message to the Dead Letter Queue with monitoring and alerting.
        Increments DLQ counters and logs warnings for operational visibility.
        """
        try:
            # Fetch data using XRANGE
            messages = await self.client.xrange(stream, min=entry_id, max=entry_id, count=1)
            
            if messages:
                _, entry_data = messages[0]

                dlq_entry = entry_data.copy()
                dlq_entry['original_stream'] = stream
                dlq_entry['original_id'] = entry_id
                dlq_entry['failed_at'] = datetime.now().isoformat()

                # Add to DLQ
                await self.client.xadd(self.STREAM_DLQ, dlq_entry)
                
                # Increment DLQ counters for monitoring
                dlq_counter_key = f"dlq:counter:{stream}"
                dlq_total_key = "dlq:counter:total"
                
                await self.client.incr(dlq_counter_key)
                total_dlq = await self.client.incr(dlq_total_key)
                
                # Structured logging for DLQ events
                print(f"⚠️  DLQ: Message moved | stream={stream} | entry_id={entry_id} | total_dlq={total_dlq}")
                
                # Alert if DLQ threshold exceeded (configurable via env var)
                dlq_threshold = int(os.getenv("DLQ_ALERT_THRESHOLD", "100"))
                if total_dlq >= dlq_threshold and total_dlq % 10 == 0:  # Alert every 10 messages after threshold
                    print(f"🚨 DLQ ALERT: Total DLQ messages ({total_dlq}) exceeds threshold ({dlq_threshold})")
                    # TODO: Integrate with alerting system (email, Slack, PagerDuty, etc.)

            # Ack in original stream so it's removed from PEL
            await self.client.xack(stream, group_name, entry_id)
            print(f"✅ Message {entry_id} moved to DLQ and ACKed")
            
        except Exception as e:
            print(f"❌ Error moving {entry_id} to DLQ: {e}")

    def register_signal_handlers(self):
        """
        Register signal handlers for graceful shutdown.
        MUST be called from the main thread only.
        """
        import threading
        if threading.current_thread() is not threading.main_thread():
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
