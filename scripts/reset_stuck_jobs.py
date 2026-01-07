"""
Recovery Script for Podcast Transcriber
Resets episodes stuck in 'PROCESSING' status and clears stale Redis state.
"""
import os
import asyncio
import redis
import json
from sqlalchemy import select, update
from podcast_transcriber_shared.database import get_session_maker, Episode, EpisodeStatus
from podcast_transcriber_shared.status_monitor import get_pipeline_status_manager

async def recover():
    print("🚀 Starting recovery process...")

    # 1. Reset Database Status
    session_maker = get_session_maker()
    async with session_maker() as session:
        # Find stuck episodes
        query = select(Episode).where(Episode.status == EpisodeStatus.PROCESSING)
        result = await session.execute(query)
        stuck_episodes = result.scalars().all()
        
        if stuck_episodes:
            print(f"🔄 Found {len(stuck_episodes)} episodes stuck in PROCESSING.")
            for ep in stuck_episodes:
                print(f"   - {ep.id}: {ep.title}")
            
            # Reset to PENDING
            stmt = (
                update(Episode)
                .where(Episode.status == EpisodeStatus.PROCESSING)
                .values(status=EpisodeStatus.PENDING)
            )
            await session.execute(stmt)
            await session.commit()
            print("✅ Database statuses reset to PENDING.")
        else:
            print("✅ No stuck episodes found in database.")

    # 2. Clear Redis Stale State
    manager = get_pipeline_status_manager()
    if manager.redis:
        print("🧹 Clearing stale Redis keys...")
        # Clear legacy status
        manager.redis.delete("transcription:status")
        # Clear active episodes set
        manager.redis.delete("pipeline:active_episodes")
        # Clear GPU lock
        manager.redis.delete("gpu_resource_lock")
        
        # Clear any status:transcription:* keys
        keys = manager.redis.keys("status:transcription:*")
        if keys:
            manager.redis.delete(*keys)
            print(f"✅ Cleared {len(keys)} individual status keys.")
            
        print("✅ Redis state cleaned.")
    else:
        print("⚠️  Redis not available.")

    print("✨ Recovery complete! You can now restart transcription.")

if __name__ == "__main__":
    asyncio.run(recover())
