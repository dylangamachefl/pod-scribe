"""
Distributed GPU Lock using Redis
Prevents VRAM collision between Transcription (Whisper) and RAG (Ollama)
"""
import os
import asyncio
import redis.asyncio as redis
from contextlib import asynccontextmanager

class GPULock:
    LOCK_NAME = "gpu_resource_lock"

    def __init__(self, redis_url: str = None, timeout: int = 600):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.timeout = timeout
        self.client = None
        self.lock = None

    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a distributed lock for GPU usage.
        Waits until the lock is available.
        """
        if not self.client:
            self.client = redis.from_url(self.redis_url, decode_responses=True)

        # Redis Lock object
        # Using a lock name that is shared across all services connecting to the same Redis
        self.lock = self.client.lock(self.LOCK_NAME, timeout=self.timeout)

        # Blocking acquire
        # Ideally, we should loop with a check to allow for interruptions/logging
        # but redis-py's lock.acquire(blocking=True) is simple and effective.
        print(f"🔒 Requesting GPU lock ({self.LOCK_NAME})...")
        try:
            acquired = await self.lock.acquire(blocking=True)
            if not acquired:
                raise Exception("Failed to acquire GPU lock")

            print(f"🔓 GPU lock acquired")
            yield
        finally:
            if self.lock and await self.lock.owned():
                await self.lock.release()
                print(f"🔓 GPU lock released")

            if self.client:
                await self.client.close()
                self.client = None

# Singleton-like usage helper
_gpu_lock = None

def get_gpu_lock() -> GPULock:
    global _gpu_lock
    if _gpu_lock is None:
        _gpu_lock = GPULock()
    return _gpu_lock
