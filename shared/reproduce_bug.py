import os
import sys
import json
import redis
import time
from pathlib import Path

# In container, shared is likely at /app/shared or equivalent
# But we can just import from podcast_transcriber_shared if it's in the path
sys.path.insert(0, "/app/shared")

try:
    from podcast_transcriber_shared.status_monitor import get_pipeline_status_manager
except ImportError:
    # Try alternate path
    sys.path.insert(0, "/app")
    from shared.podcast_transcriber_shared.status_monitor import get_pipeline_status_manager

def test_status_race_condition():
    print("Testing PipelineStatusManager race condition...")
    manager = get_pipeline_status_manager()
    
    # 1. Initialize a batch (simulate API start)
    episode_ids = ["test_ep_1", "test_ep_2"]
    print(f"Initializing batch for {episode_ids}...")
    manager.initialize_batch(episode_ids, 2)
    
    # Verify they are in Redis
    active_ids = manager.redis.smembers(manager.ACTIVE_EPISODES_KEY)
    print(f"Active IDs in Redis: {active_ids}")
    
    # 2. Get status (Simulate first frontend poll BEFORE worker starts)
    print("Getting pipeline status (poll 1)...")
    status = manager.get_pipeline_status()
    print(f"Is running: {status['is_running']}")
    print(f"Active episodes count: {len(status['active_episodes'])}")
    
    # 3. Check Redis again
    active_ids_after = manager.redis.smembers(manager.ACTIVE_EPISODES_KEY)
    print(f"Active IDs in Redis after poll 1: {active_ids_after}")
    
    if len(active_ids_after) == 0 and len(episode_ids) > 0:
        print("❌ BUG CONFIRMED: Active episodes were cleared because no service reported status yet!")
    else:
        print("✅ Bug not reproduced or IDs preserved.")

if __name__ == "__main__":
    test_status_race_condition()
