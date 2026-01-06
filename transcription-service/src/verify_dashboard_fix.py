import json
import os
import sys
from pathlib import Path

# In container, src is in PYTHONPATH or we add it
sys.path.insert(0, "/app/src")
sys.path.insert(0, "/app/shared")

from podcast_transcriber_shared.status_monitor import get_pipeline_status_manager
from managers.status_monitor import write_status, clear_status

def test_dashboard_aggregation():
    manager = get_pipeline_status_manager()
    
    print("Testing dashboard aggregation fixes inside container...")
    
    # 1. Clear status
    print("Step 1: Clearing all status...")
    manager.clear_all_status()
    
    # 2. Write "current" status (placeholder used by worker)
    print("Step 2: Writing 'current' status placeholder...")
    write_status(
        is_running=True,
        episode_id="current",
        current_episode="Test Episode Name",
        current_podcast="Test Podcast",
        stage="transcribing",
        progress=0.5,
        episodes_completed=1,
        episodes_total=5
    )
    
    # 3. Write a real episode status
    print("Step 3: Writing real episode status...")
    write_status(
        is_running=True,
        episode_id="real_ep_123",
        current_episode="Real Episode 123",
        current_podcast="Real Podcast",
        stage="transcribing",
        progress=0.4
    )
    
    # 4. Get aggregated status
    print("Step 4: Getting aggregated status...")
    status = manager.get_pipeline_status()
    
    # VERIFICATION
    active_episodes = status.get('active_episodes', [])
    active_ids = [ep['episode_id'] for ep in active_episodes]
    
    print(f"\nAggregated active episodes: {active_ids}")
    
    # Verify "current" is NOT in active_episodes
    if "current" in active_ids:
        print("❌ FAIL: 'current' found in active_episodes list!")
        return False
    else:
        print("✅ PASS: 'current' NOT in active_episodes list.")
        
    # Verify the real episode is there
    if "real_ep_123" not in active_ids:
        print("❌ FAIL: Real episode 'real_ep_123' NOT found in active_episodes list!")
        return False
    else:
        print("✅ PASS: Real episode 'real_ep_123' found.")

    # Verify GPU/Stats fallback
    print(f"GPU Name: {status.get('gpu_name')}")
    print(f"Batch Progress: {status.get('episodes_completed')} / {status.get('episodes_total')}")
    
    if status.get('episodes_total') == 5:
        print("✅ PASS: Batch progress correctly reported.")
    else:
        print(f"❌ FAIL: Expected 5 total episodes, got {status.get('episodes_total')}")
        return False
        
    print("\nAll verification checks passed!")
    return True

if __name__ == "__main__":
    try:
        success = test_dashboard_aggregation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
