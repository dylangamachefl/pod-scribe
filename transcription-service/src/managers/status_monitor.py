#!/usr/bin/env python3
"""
Status Monitor Module
Tracks transcription status and GPU metrics for dashboard display.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# Get absolute paths
# Navigate up from: transcription-service/src/managers/ -> transcription-service/ -> root/ -> shared/
SCRIPT_DIR = Path(os.path.abspath(__file__)).parent.parent.parent.parent
CONFIG_DIR = SCRIPT_DIR / "shared" / "config"
STATUS_FILE = CONFIG_DIR / "status.json"



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
    start_time: Optional[str] = None
):
    """Write current transcription status to file.
    
    Args:
        is_running: Whether transcription is currently running
        current_episode: Title of episode being processed
        current_podcast: Name of podcast
        stage: Current processing stage (idle, downloading, transcribing, diarizing, saving)
        progress: Progress of current episode (0.0 to 1.0)
        episodes_completed: Number of episodes completed
        episodes_total: Total number of episodes to process
        start_time: ISO format start time (auto-generated if None and is_running=True)
    """
    # Get GPU stats
    gpu_stats = get_gpu_stats()
    
    # Auto-generate start time if starting
    if is_running and start_time is None:
        # Try to read existing start time
        existing_status = read_status()
        if existing_status and existing_status.get('is_running'):
            start_time = existing_status.get('start_time')
        else:
            start_time = datetime.now().isoformat()
    
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
        "last_updated": datetime.now().isoformat()
    }
    
    # Ensure config directory exists
    CONFIG_DIR.mkdir(exist_ok=True)
    
    # Write status file
    with open(STATUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(status, f, indent=2)


def read_status() -> Optional[Dict]:
    """Read current status from file.
    
    Returns:
        Status dict or None if file doesn't exist
    """
    if not STATUS_FILE.exists():
        return None
    
    try:
        with open(STATUS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not read status file: {e}")
        return None


def clear_status():
    """Clear status file (set to idle state)."""
    write_status(
        is_running=False,
        current_episode="",
        current_podcast="",
        stage="idle",
        progress=0.0,
        episodes_completed=0,
        episodes_total=0,
        start_time=None
    )


def update_progress(stage: str, progress: float = 0.0):
    """Update only the stage and progress, keeping other fields intact.
    
    Args:
        stage: Current processing stage
        progress: Progress of current stage (0.0 to 1.0)
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
            start_time=existing.get('start_time')
        )
