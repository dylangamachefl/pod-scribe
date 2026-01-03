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
            return {"is_running": False, "stages": {}, "active_episodes": []}

        active_episode_ids = list(self.redis.smembers(self.ACTIVE_EPISODES_KEY))
        
        stages = {}
        active_episodes_data = []
        
        # Track stats and active episodes per service
        for service in ['transcription', 'summarization', 'rag']:
            stats_raw = self.redis.get(self._get_stats_key(service))
            stats = json.loads(stats_raw) if stats_raw else {"completed": 0, "total": 0}
            
            # Find any active episodes for this service
            active_in_service = []
            for eid in active_episode_ids:
                status_raw = self.redis.get(self._get_status_key(service, eid))
                if status_raw:
                    status_data = json.loads(status_raw)
                    status_data['episode_id'] = eid
                    status_data['service'] = service
                    active_in_service.append(status_data)
            
            stages[service] = {
                "active": len(active_in_service) > 0 or (stats['completed'] < stats['total'] and stats['total'] > 0),
                "completed": stats['completed'],
                "total": stats['total'],
                "current": active_in_service[0] if active_in_service else None
            }
            
            # Accumulate all active episode data
            active_episodes_data.extend(active_in_service)

        # Group by episode_id for a cleaner view
        episodes_map = {}
        for entry in active_episodes_data:
            eid = entry['episode_id']
            if eid not in episodes_map:
                episodes_map[eid] = {
                    "episode_id": eid,
                    "title": entry.get('current_episode') or entry.get('episode_title') or "Unknown",
                    "podcast": entry.get('current_podcast') or entry.get('podcast_name') or "Unknown",
                    "stage": entry.get('stage', 'queued'),
                    "progress": entry.get('progress', 0.0),
                    "services": {}
                }
            episodes_map[eid]['services'][entry['service']] = entry

        # Cleanup: if an episode ID has no status in any service, it's stale
        for eid in active_episode_ids:
            if eid not in episodes_map and eid != "current":
                self.redis.srem(self.ACTIVE_EPISODES_KEY, eid)

        # Re-evaluating is_running:
        # 1. At least one episode is actively being processed in a service
        # 2. Transcription service is explicitly running (e.g. download, transcribe)
        # 3. GPU usage is high (optional, but good indicator)
        
        transcription_status_raw = self.redis.get("transcription:status")
        transcription_status = json.loads(transcription_status_raw) if transcription_status_raw else {}
        service_is_running = transcription_status.get('is_running', False)
        
        is_running = service_is_running or len(episodes_map) > 0
        
        # Cleanup: if all stages finished and no service is running, clear active episodes
        if not is_running and active_episode_ids:
             self.redis.delete(self.ACTIVE_EPISODES_KEY)
             # Also reset stats if they were "stuck"
             for service in ['transcription', 'summarization', 'rag']:
                 self.redis.delete(self._get_stats_key(service))

        return {
            "is_running": is_running,
            "stages": stages,
            "active_episodes": list(episodes_map.values()),
            "gpu_name": transcription_status.get('gpu_name'),
            "gpu_usage": transcription_status.get('gpu_usage', 0),
            "vram_used_gb": transcription_status.get('vram_used_gb', 0),
            "vram_total_gb": transcription_status.get('vram_total_gb', 0),
            "recent_logs": transcription_status.get('recent_logs', []),
            "episodes_completed": transcription_status.get('episodes_completed', 0),
            "episodes_total": transcription_status.get('episodes_total', 0)
        }

    def clear_all_status(self):
        """Force clear all pipeline status and stats from Redis."""
        if not self.redis: return
        
        # Clear active episodes set
        self.redis.delete(self.ACTIVE_EPISODES_KEY)
        
        # Clear all status and stats keys
        keys_to_delete = []
        keys_to_delete.extend(self.redis.keys(f"{self.SERVICE_STATUS_PREFIX}*"))
        keys_to_delete.extend(self.redis.keys(f"{self.SERVICE_STATS_PREFIX}*"))
        keys_to_delete.append("transcription:status")
        
        if keys_to_delete:
            self.redis.delete(*keys_to_delete)

_manager = None
def get_pipeline_status_manager() -> PipelineStatusManager:
    global _manager
    if _manager is None:
        _manager = PipelineStatusManager()
    return _manager
