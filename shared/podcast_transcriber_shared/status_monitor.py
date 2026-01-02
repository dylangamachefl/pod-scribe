import json
import os
from datetime import datetime
from typing import Optional, Dict, List, Any
import redis

class PipelineStatusManager:
    """
    Manages and aggregates status information across the entire podcast processing pipeline.
    Transcription -> Summarization -> RAG Indexing.
    """
    
    # Redis Keys
    ACTIVE_EPISODES_KEY = "pipeline:active_episodes"
    SERVICE_STATUS_PREFIX = "status:" # status:{service}:{episode_id}
    SERVICE_STATS_PREFIX = "stats:"   # stats:{service}
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://redis:6379')
        try:
            self.redis = redis.from_url(self.redis_url, decode_responses=True)
        except Exception as e:
            print(f"Warning: Failed to initialize Redis in PipelineStatusManager: {e}")
            self.redis = None

    def _get_status_key(self, service: str, episode_id: str) -> str:
        return f"{self.SERVICE_STATUS_PREFIX}{service}:{episode_id}"

    def _get_stats_key(self, service: str) -> str:
        return f"{self.SERVICE_STATS_PREFIX}{service}"

    def set_service_status(self, service: str, episode_id: str, status_data: Dict[str, Any]):
        """Set the status for a specific episode in a specific service."""
        if not self.redis: return
        
        key = self._get_status_key(service, episode_id)
        status_data['last_updated'] = datetime.now().isoformat()
        
        # Add to active episodes set
        self.redis.sadd(self.ACTIVE_EPISODES_KEY, episode_id)
        # Set detailed status with 1 hour expiration (safety)
        self.redis.setex(key, 3600, json.dumps(status_data))

    def clear_service_status(self, service: str, episode_id: str):
        """Clear the status for an episode in a service when done."""
        if not self.redis: return
        
        # Delete detailed status
        self.redis.delete(self._get_status_key(service, episode_id))
        
        # Check if other services are still working on this episode
        # This is a bit tricky, but for now we'll rely on the API aggregator
        # to clean up ACTIVE_EPISODES_KEY when appropriate or use a TTL.

    def update_stats(self, service: str, completed: int, total: int):
        """Update overall stats for a service (e.g., 2/5 episodes completed)."""
        if not self.redis: return
        
        key = self._get_stats_key(service)
        data = {
            "completed": completed,
            "total": total,
            "last_updated": datetime.now().isoformat()
        }
        self.redis.set(key, json.dumps(data))

    def initialize_batch(self, episode_ids: List[str], total_count: int):
        """Initialize a new batch run across all services."""
        if not self.redis: return
        
        # Clear old stats (optional, depending on desired persistence)
        for service in ['transcription', 'summarization', 'rag']:
            self.redis.delete(self._get_stats_key(service))
            # Also clear individual episode statuses for these IDs to be safe
            for eid in episode_ids:
                self.redis.delete(self._get_status_key(service, eid))
        
        # Add all to active set
        if episode_ids:
            self.redis.sadd(self.ACTIVE_EPISODES_KEY, *episode_ids)
            
        # Initialize transcription stats
        self.update_stats('transcription', 0, total_count)
        self.update_stats('summarization', 0, total_count)
        self.update_stats('rag', 0, total_count)

    def get_pipeline_status(self) -> Dict[str, Any]:
        """Aggregate all status info into a single pipeline view."""
        if not self.redis:
            return {"is_running": False, "stages": {}}

        active_episode_ids = self.redis.smembers(self.ACTIVE_EPISODES_KEY)
        
        stages = {}
        for service in ['transcription', 'summarization', 'rag']:
            stats_raw = self.redis.get(self._get_stats_key(service))
            stats = json.loads(stats_raw) if stats_raw else {"completed": 0, "total": 0}
            
            # Find any active episodes for this service
            active_in_service = []
            for eid in active_episode_ids:
                status_raw = self.redis.get(self._get_status_key(service, eid))
                if status_raw:
                    active_in_service.append(json.loads(status_raw))
            
            stages[service] = {
                "active": len(active_in_service) > 0 or (stats['completed'] < stats['total'] and stats['total'] > 0),
                "completed": stats['completed'],
                "total": stats['total'],
                "current": active_in_service[0] if active_in_service else None
            }

        # Cleanup: if all stages finished, clear active episodes
        is_running = any(s['active'] for s in stages.values())
        if not is_running and active_episode_ids:
             self.redis.delete(self.ACTIVE_EPISODES_KEY)

        return {
            "is_running": is_running,
            "stages": stages
        }

_manager = None
def get_pipeline_status_manager() -> PipelineStatusManager:
    global _manager
    if _manager is None:
        _manager = PipelineStatusManager()
    return _manager
