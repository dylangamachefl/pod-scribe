import asyncio
import os
import sys

# Add src and shared to path
sys.path.append(os.path.join(os.getcwd(), 'transcription-service', 'src'))
sys.path.append(os.path.join(os.getcwd(), 'shared'))

from podcast_transcriber_shared.status_monitor import get_pipeline_status_manager

def debug_status():
    manager = get_pipeline_status_manager()
    status = manager.get_pipeline_status()
    
    print("\n=== PIPELINE STATUS DEBUG ===")
    print(f"is_running: {status.get('is_running')}")
    print(f"active_episodes count: {len(status.get('active_episodes', []))}")
    print(f"episodes_total: {status.get('episodes_total')}")
    print(f"episodes_completed: {status.get('episodes_completed')}")
    print("\nActive Episodes Data:")
    for ep in status.get('active_episodes', []):
        print(f" - {ep['episode_id']}: {ep.get('title')} [{ep.get('stage')}]")
        
    print("\nFull JSON:")
    import json
    print(json.dumps(status, indent=2))

if __name__ == "__main__":
    debug_status()
