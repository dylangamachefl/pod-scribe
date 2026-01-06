"""
Redis-based Idempotency Manager
Provides atomic idempotency checks for event processing to prevent duplicate work.
"""
import os
from typing import Optional
import redis.asyncio as redis


class IdempotencyManager:
    """
    Manages idempotency keys in Redis with atomic operations.
    Prevents duplicate event processing across distributed workers.
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, redis_url: Optional[str] = None):
        """
        Initialize idempotency manager.
        
        Args:
            redis_client: Existing Redis client (optional)
            redis_url: Redis connection URL (optional, defaults to REDIS_URL env var)
        """
        self.redis_client = redis_client
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._own_client = redis_client is None
    
    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                health_check_interval=30
            )
        return self.redis_client
    
    async def check_and_set(
        self, 
        key: str, 
        ttl: int = 86400,
        value: str = "1"
    ) -> bool:
        """
        Atomically check if a key exists and set it if not.
        
        This is the core idempotency operation. If the key doesn't exist,
        it's created with the given TTL. If it already exists, nothing happens.
        
        Args:
            key: Idempotency key (e.g., "idempotency:rag:episode_123")
            ttl: Time-to-live in seconds (default: 24 hours)
            value: Value to store (default: "1")
        
        Returns:
            True if this is the first time seeing this key (proceed with processing)
            False if the key already exists (skip duplicate processing)
        """
        client = await self._get_client()
        
        # SET with NX (only if not exists) and EX (expiration)
        # Returns True if key was set, None if key already existed
        result = await client.set(key, value, nx=True, ex=ttl)
        
        return result is not None
    
    async def is_processed(self, key: str) -> bool:
        """
        Check if a key has been processed (exists in Redis).
        
        Args:
            key: Idempotency key
        
        Returns:
            True if already processed, False otherwise
        """
        client = await self._get_client()
        return await client.exists(key) > 0
    
    async def mark_processed(self, key: str, ttl: int = 86400, value: str = "1") -> bool:
        """
        Mark a key as processed (non-atomic, use check_and_set for atomicity).
        
        Args:
            key: Idempotency key
            ttl: Time-to-live in seconds
            value: Value to store
        
        Returns:
            True if successfully marked
        """
        client = await self._get_client()
        await client.set(key, value, ex=ttl)
        return True
    
    async def clear(self, key: str) -> bool:
        """
        Clear an idempotency key (for testing or manual reprocessing).
        
        Args:
            key: Idempotency key to clear
        
        Returns:
            True if key was deleted, False if it didn't exist
        """
        client = await self._get_client()
        result = await client.delete(key)
        return result > 0
    
    async def close(self):
        """Close Redis connection if we own it."""
        if self._own_client and self.redis_client:
            await self.redis_client.close()
    
    @staticmethod
    def make_key(service: str, event_type: str, episode_id: str) -> str:
        """
        Generate a standardized idempotency key.
        
        Args:
            service: Service name (e.g., "rag", "summarization")
            event_type: Event type (e.g., "transcribed", "summarized")
            episode_id: Episode identifier
        
        Returns:
            Formatted idempotency key
        
        Example:
            >>> IdempotencyManager.make_key("rag", "transcribed", "ep_123")
            "idempotency:rag:transcribed:ep_123"
        """
        return f"idempotency:{service}:{event_type}:{episode_id}"


# Singleton instance
_idempotency_manager = None

def get_idempotency_manager(redis_client: Optional[redis.Redis] = None) -> IdempotencyManager:
    """
    Get or create the global IdempotencyManager instance.
    
    Args:
        redis_client: Optional Redis client to use (for sharing connections)
    
    Returns:
        IdempotencyManager singleton
    """
    global _idempotency_manager
    if _idempotency_manager is None:
        _idempotency_manager = IdempotencyManager(redis_client=redis_client)
    return _idempotency_manager
