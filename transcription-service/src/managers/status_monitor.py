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


def write_status(
    is_running: bool,
    current_episode: str = "",
    current_podcast: str = "",
    stage: str = "idle",
    progress: float = 0.0,
    episodes_completed: int = 0,
    episodes_total: int = 0,
    start_time: Optional[str] = None,
    log_message: Optional[str] = None
):
    """Write current transcription status to Redis.
    
    Args:
        is_running: Whether transcription is currently running
        current_episode: Title of episode being processed
        current_podcast: Name of podcast
        stage: Current processing stage
        progress: Progress of current episode (0.0 to 1.0)
        episodes_completed: Number of episodes completed
        episodes_total: Total number of episodes to process
        start_time: ISO format start time
        log_message: Optional log message to append to recent logs
    """
    if not redis_client:
        return

    # Get GPU stats
    gpu_stats = get_gpu_stats()
    
    # Get existing status to preserve logs and start time
    existing_status = read_status() or {}
    recent_logs = existing_status.get('recent_logs', [])
    
    # Auto-generate start time if starting and not provided
    if is_running and start_time is None:
        if existing_status.get('is_running'):
            start_time = existing_status.get('start_time')
        else:
            start_time = datetime.now().isoformat()
            # Clear logs on new run start
            recent_logs = []
            
    # Append new log message if provided
    if log_message:
        timestamp = datetime.now().strftime("%H:%M:%S")
        recent_logs.insert(0, f"[{timestamp}] {log_message}")
        # Keep last 50 logs
        recent_logs = recent_logs[:50]
    
    status = {
        "is_running": is_running,
        "current_episode": current_episode,
        "current_podcast": current_podcast,
        "stage": stage,
        "progress": progress,
        "gpu_name": gpu_stats["gpu_name"],
        "gpu_usage": gpu_stats["gpu_usage"],
        "vram_used_gb": gpu_stats["vram_used_gb"],
        "vram_total_gb": gpu_stats["vram_total_gb"],
        "start_time": start_time,
        "episodes_completed": episodes_completed,
        "episodes_total": episodes_total,
        "last_updated": datetime.now().isoformat(),
        "recent_logs": recent_logs
    }
    
    try:
        redis_client.set(STATUS_KEY, json.dumps(status))
    except Exception as e:
        print(f"Error writing status to Redis: {e}")


def read_status() -> Optional[Dict]:
    """Read current status from Redis.
    
    Returns:
        Status dict or None if key doesn't exist
    """
    if not redis_client:
        return None
    
    try:
        data = redis_client.get(STATUS_KEY)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        print(f"Error reading status from Redis: {e}")
        return None


def clear_status():
    """Clear status (set to idle state)."""
    write_status(
        is_running=False,
        current_episode="",
        current_podcast="",
        stage="idle",
        progress=0.0,
        episodes_completed=0,
        episodes_total=0,
        start_time=None,
        log_message="Ready"
    )


def update_progress(stage: str, progress: float = 0.0, log: Optional[str] = None):
    """Update only the stage, progress, and optionally add a log.
    
    Args:
        stage: Current processing stage
        progress: Progress of current stage (0.0 to 1.0)
        log: Optional log message
    """
    existing = read_status()
    if existing:
        write_status(
            is_running=existing.get('is_running', False),
            current_episode=existing.get('current_episode', ''),
            current_podcast=existing.get('current_podcast', ''),
            stage=stage,
            progress=progress,
            episodes_completed=existing.get('episodes_completed', 0),
            episodes_total=existing.get('episodes_total', 0),
            start_time=existing.get('start_time'),
            log_message=log
        )

