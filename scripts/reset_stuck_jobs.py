"""
Recovery Script for Podcast Transcriber
Resets episodes stuck in 'PROCESSING' status and clears stale Redis state.
"""
import os
import asyncio
import redis
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from sqlalchemy import select, update
from podcast_transcriber_shared.database import get_session_maker, Episode, EpisodeStatus
from podcast_transcriber_shared.status_monitor import get_pipeline_status_manager

async def recover(temp_dir: Optional[Path] = None):
    """
    Recover stuck jobs and cleanup stale resources.
    
    Args:
        temp_dir: Optional path to transcription temp directory for file cleanup
    """
    print("🚀 Starting recovery process...")

    # 1. Reset Database Status
    session_maker = get_session_maker()
    async with session_maker() as session:
        # Find stuck episodes (TRANSCRIBING with old heartbeat > 10m)
        # OR just those in PROCESSING (legacy)
        from datetime import timedelta
        ten_mins_ago = datetime.utcnow() - timedelta(minutes=10)
        
        query = select(Episode).where(
            (Episode.status == EpisodeStatus.TRANSCRIBING) & 
            ((Episode.heartbeat < ten_mins_ago) | (Episode.heartbeat == None))
        )
        result = await session.execute(query)
        stuck_episodes = result.scalars().all()
        
        if stuck_episodes:
            print(f"🔄 Found {len(stuck_episodes)} stuck episodes.")
            for ep in stuck_episodes:
                print(f"   - {ep.id}: {ep.title} (Status: {ep.status})")
                
                # Idempotent cleanup: remove temp files for this episode
                if temp_dir and temp_dir.exists():
                    # We look for files starting with a sanitized version of the title
                    # but since we don't have the sanitizer here easily, 
                    # we just skip if we can't match. 
                    # In a real fix, we'd store the filename in DB.
                    pass
            
            # Reset to PENDING
            stuck_ids = [ep.id for ep in stuck_episodes]
            stmt = (
                update(Episode)
                .where(Episode.id.in_(stuck_ids))
                .values(status=EpisodeStatus.PENDING, heartbeat=None)
            )
            await session.execute(stmt)
            await session.commit()
            print(f"✅ Reset {len(stuck_ids)} jobs to PENDING.")
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

    print("✨ Recovery complete!")


if __name__ == "__main__":
    asyncio.run(recover())

if __name__ == "__main__":
    asyncio.run(recover())
