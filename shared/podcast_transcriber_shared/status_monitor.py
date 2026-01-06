import json
import os
from datetime import datetime
from typing import Optional, Dict, List, Any
import redis

class PipelineStatusManager:
    """
    Manages and aggregates status information across the entire podcast processing pipeline.
    Uses Redis Lua scripts for atomic status updates to prevent race conditions.
    """
    
    # Redis Keys
    ACTIVE_EPISODES_KEY = "pipeline:active_episodes"
    SERVICE_STATUS_PREFIX = "status:" # status:{service}:{episode_id}
    SERVICE_STATS_PREFIX = "stats:"   # stats:{service}
    
    # Lua Scripts for Atomic Operations
    SET_STATUS_LUA = """
    -- KEYS[1]: pipeline:active_episodes
    -- KEYS[2]: status:{service}:{episode_id}
    -- ARGV[1]: episode_id
    -- ARGV[2]: status_data_json
    -- ARGV[3]: ttl
    
    redis.call('SADD', KEYS[1], ARGV[1])
    redis.call('SETEX', KEYS[2], ARGV[3], ARGV[2])
    return 1
    """
    
    CLEAR_STATUS_LUA = """
    -- KEYS[1]: pipeline:active_episodes
    -- KEYS[2]: status:{service}:{episode_id}
    -- ARGV[1]: episode_id
    -- ARGV[2]: status_prefix
    
    redis.call('DEL', KEYS[2])
    
    -- Check if any other service still has status for this episode
    -- status:transcription:eid, status:summarization:eid, status:rag:eid
    local services = {'transcription', 'summarization', 'rag'}
    local active = false
    for _, svc in ipairs(services) do
        if redis.call('EXISTS', ARGV[2] .. svc .. ':' .. ARGV[1]) == 1 then
            active = true
            break
        end
    end
    
    if not active then
        redis.call('SREM', KEYS[1], ARGV[1])
    end
    return 1
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://redis:6379')
        try:
            self.redis = redis.from_url(self.redis_url, decode_responses=True)
            # Register Lua scripts
            self._set_status_script = self.redis.register_script(self.SET_STATUS_LUA)
            self._clear_status_script = self.redis.register_script(self.CLEAR_STATUS_LUA)
        except Exception as e:
            print(f"Warning: Failed to initialize Redis in PipelineStatusManager: {e}")
            self.redis = None

    def _get_status_key(self, service: str, episode_id: str) -> str:
        return f"{self.SERVICE_STATUS_PREFIX}{service}:{episode_id}"

    def _get_stats_key(self, service: str) -> str:
        return f"{self.SERVICE_STATS_PREFIX}{service}"

    def set_service_status(self, service: str, episode_id: str, status_data: Dict[str, Any]):
        """Set the status for a specific episode in a specific service atomically."""
        if not self.redis: return
        
        key = self._get_status_key(service, episode_id)
        status_data['last_updated'] = datetime.now().isoformat()
        
        try:
            self._set_status_script(
                keys=[self.ACTIVE_EPISODES_KEY, key],
                args=[episode_id, json.dumps(status_data), 3600]
            )
        except Exception as e:
            print(f"Error setting status via Lua: {e}")
            # Fallback simple set
            self.redis.sadd(self.ACTIVE_EPISODES_KEY, episode_id)
            self.redis.setex(key, 3600, json.dumps(status_data))

    def update_service_status(
        self,
        service: str,
        episode_id: str,
        stage: str,
        progress: float = 0.0,
        log_message: Optional[str] = None,
        additional_data: Optional[Dict] = None
    ):
        """
        Update service status with common fields (stage, progress, logs).
        This is the preferred way to report progress in a DRY manner.
        """
        # Get existing status for logs/history
        existing_status_raw = self.redis.get(self._get_status_key(service, episode_id)) if self.redis else None
        existing_status = json.loads(existing_status_raw) if existing_status_raw else {}
        
        recent_logs = existing_status.get('recent_logs', [])
        if log_message:
            timestamp = datetime.now().strftime("%H:%M:%S")
            recent_logs.insert(0, f"[{timestamp}] {log_message}")
            recent_logs = recent_logs[:50] # Keep last 50 logs
            
        status = {
            **existing_status,
            "stage": stage,
            "progress": progress,
            "recent_logs": recent_logs
        }
        
        if additional_data:
            status.update(additional_data)
            
        self.set_service_status(service, episode_id, status)

    def clear_service_status(self, service: str, episode_id: str):
        """Clear the status for an episode in a service atomically."""
        if not self.redis: return
        
        key = self._get_status_key(service, episode_id)
        try:
            self._clear_status_script(
                keys=[self.ACTIVE_EPISODES_KEY, key],
                args=[episode_id, self.SERVICE_STATUS_PREFIX]
            )
        except Exception as e:
            print(f"Error clearing status via Lua: {e}")
            self.redis.delete(key)

    def update_stats(self, service: str, completed: int, total: int):
        """Update overall stats for a service."""
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
        
        pipeline = self.redis.pipeline()
        for service in ['transcription', 'summarization', 'rag']:
            pipeline.delete(self._get_stats_key(service))
            for eid in episode_ids:
                pipeline.delete(self._get_status_key(service, eid))
        
        if episode_ids:
            pipeline.sadd(self.ACTIVE_EPISODES_KEY, *episode_ids)
        pipeline.execute()
            
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
        
        for service in ['transcription', 'summarization', 'rag']:
            stats_raw = self.redis.get(self._get_stats_key(service))
            stats = json.loads(stats_raw) if stats_raw else {"completed": 0, "total": 0}
            
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
            active_episodes_data.extend(active_in_service)

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

        transcription_status_raw = self.redis.get("transcription:status")
        transcription_status = json.loads(transcription_status_raw) if transcription_status_raw else {}
        service_is_running = transcription_status.get('is_running', False)
        
        is_running = service_is_running or len(episodes_map) > 0 or len(active_episode_ids) > 0
        
        # Cleanup stale IDs if nothing is running
        if not is_running and active_episode_ids:
             self.redis.delete(self.ACTIVE_EPISODES_KEY)
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
        
        self.redis.delete(self.ACTIVE_EPISODES_KEY)
        
        keys_to_delete = []
        keys_to_delete.extend(self.redis.keys(f"{self.SERVICE_STATUS_PREFIX}*"))
        keys_to_delete.extend(self.redis.keys(f"{self.SERVICE_STATS_PREFIX}*"))
        keys_to_delete.append("transcription:status")
        
        if keys_to_delete:
            self.redis.delete(*keys_to_delete)

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
