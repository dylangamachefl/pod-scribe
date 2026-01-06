#!/usr/bin/env python3
"""
Status Monitor Module
Tracks transcription status and GPU metrics for dashboard display.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import redis

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# Redis Configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
STATUS_KEY = "transcription:status"

# Initialize Redis client
# We use a synchronous client here to avoid breaking existing synchronous call sites
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
except Exception as e:
    print(f"Warning: Failed to initialize Redis client in status_monitor: {e}")
    redis_client = None


def get_gpu_stats() -> Dict:
    """Get current GPU usage and VRAM statistics.
    
    Returns:
        Dict with gpu_name, gpu_usage, vram_used_gb, vram_total_gb
    """
    if not TORCH_AVAILABLE or not torch.cuda.is_available():
        return {
            "gpu_name": "N/A",
            "gpu_usage": 0,
            "vram_used_gb": 0.0,
            "vram_total_gb": 0.0
        }
    
    try:
        gpu_name = torch.cuda.get_device_name(0)
        
        # Get VRAM stats
        vram_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        vram_allocated = torch.cuda.memory_allocated(0) / (1024**3)
        vram_reserved = torch.cuda.memory_reserved(0) / (1024**3)
        
        # Use reserved memory as it's more accurate for actual usage
        vram_used = vram_reserved
        
        # Try to get GPU utilization using nvidia-ml-py3 if available
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_usage = utilization.gpu
            pynvml.nvmlShutdown()
        except:
            # Estimate based on memory usage if pynvml not available
            gpu_usage = int((vram_used / vram_total) * 100) if vram_total > 0 else 0
        
        return {
            "gpu_name": gpu_name,
            "gpu_usage": gpu_usage,
            "vram_used_gb": round(vram_used, 2),
            "vram_total_gb": round(vram_total, 2)
        }
    except Exception as e:
        print(f"Warning: Could not get GPU stats: {e}")
        return {
            "gpu_name": "Unknown",
            "gpu_usage": 0,
            "vram_used_gb": 0.0,
            "vram_total_gb": 0.0
        }


from podcast_transcriber_shared.status_monitor import get_pipeline_status_manager

def write_status(
    is_running: bool,
    episode_id: str = "current",
    current_episode: str = "",
    current_podcast: str = "",
    stage: str = "idle",
    progress: float = 0.0,
    episodes_completed: int = 0,
    episodes_total: int = 0,
    start_time: Optional[str] = None,
    log_message: Optional[str] = None
):
    """Write current transcription status to shared PipelineStatusManager."""
    manager = get_pipeline_status_manager()
    gpu_stats = get_gpu_stats()
    
    additional_data = {
        "is_running": is_running,
        "current_episode": current_episode,
        "current_podcast": current_podcast,
        **gpu_stats
    }
    
    if start_time:
        additional_data["start_time"] = start_time
    if episodes_total > 0:
        additional_data["episodes_completed"] = episodes_completed
        additional_data["episodes_total"] = episodes_total
        manager.update_stats('transcription', episodes_completed, episodes_total)
        
    manager.update_service_status(
        service='transcription',
        episode_id=episode_id,
        stage=stage,
        progress=progress,
        log_message=log_message,
        additional_data=additional_data
    )


def read_status(episode_id: str = "current") -> Optional[Dict]:
    """Read transcription status for a specific episode from shared PipelineStatusManager."""
    manager = get_pipeline_status_manager()
    try:
        data = manager.redis.get(manager._get_status_key('transcription', episode_id))
        if data:
            return json.loads(data)
    except:
        pass
    return None


def clear_status(episode_id: str = "current"):
    """Clear transcription status for a specific episode."""
    manager = get_pipeline_status_manager()
    manager.clear_service_status('transcription', episode_id)
    # Reset stats to 0/0 (only if clearing "current" or last one)
    if episode_id == "current":
        manager.update_stats('transcription', 0, 0)


def update_progress(stage: str, progress: float = 0.0, log: Optional[str] = None, episode_id: str = "current"):
    """Update only the stage, progress, and optionally add a log using shared method."""
    manager = get_pipeline_status_manager()
    manager.update_service_status(
        service='transcription',
        episode_id=episode_id,
        stage=stage,
        progress=progress,
        log_message=log
    )

