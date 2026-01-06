"""
Transcription Worker Daemon

Continuously polls Redis for transcription jobs and processes them.
This replaces the one-shot CLI approach with a long-running worker.
Now uses Redis Streams for reliable job queuing and Distributed GPU Lock.

Usage:
    python worker_daemon.py
"""
import asyncio
import json
import time
import signal
import sys
from pathlib import Path
import warnings

# Suppress specific torchaudio deprecation warnings
warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio._backend")
warnings.filterwarnings("ignore", message=".*AudioMetaData has been deprecated.*")
warnings.filterwarnings("ignore", message=".*torchaudio.load_with_torchcodec.*")
warnings.filterwarnings("ignore", message=".*torchaudio._backend.utils.info has been deprecated.*")
warnings.filterwarnings("ignore", message=".*torchaudio._backend.list_audio_backends has been deprecated.*")


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import TranscriptionConfig
from core.diarization import apply_pytorch_patch
from core.processor import process_episode_async
from core.audio import TranscriptionWorker
from podcast_transcriber_shared.database import create_episode, update_episode_status, EpisodeStatus, get_episode_by_id
from podcast_transcriber_shared.events import get_event_bus, EventBus
from podcast_transcriber_shared.gpu_lock import get_gpu_lock
from podcast_transcriber_shared.logging_config import configure_logging, get_logger, bind_correlation_id
from managers.status_monitor import write_status, clear_status

# Configure structured logging
configure_logging("transcription-worker")
logger = get_logger(__name__)

# Global flag for graceful shutdown
shutdown_event = asyncio.Event()

async def process_job(job_data: dict) -> bool:
    """
    Process a single transcription job.
    Returns True if successful, False otherwise.
    """
    config = TranscriptionConfig.from_env()

    episode_id = job_data.get('episode_id')
    if not episode_id:
        logger.warning("job_missing_episode_id", job_data=job_data)
        return True # Skip invalid jobs (don't retry)

    # Bind correlation ID for tracking
    bind_correlation_id(episode_id)
    logger.info("processing_episode_started", episode_id=episode_id)
    write_status(
        is_running=True,
        episode_id=episode_id,
        current_episode=episode_id,
        stage="preparing",
        log_message=f"Processing Request: {episode_id}"
    )

    try:
        # Fetch full episode data from PostgreSQL
        episode = await get_episode_by_id(episode_id, load_transcript=False)

        if not episode:
            logger.warning("episode_not_found_in_database", episode_id=episode_id)
            return True # Skip missing episodes

        logger.info("episode_metadata_retrieved", episode_id=episode_id, title=episode.title, podcast=episode.podcast_name)
        write_status(
            is_running=True,
            episode_id=episode_id,
            current_episode=episode.title,
            current_podcast=episode.podcast_name,
            stage="preparing",
            log_message=f"Found Metadata: {episode.title}"
        )

        # Convert Episode object to dict for process_episode_async
        episode_data = {
            'id': episode.id,
            'episode_title': episode.title,
            'feed_title': episode.podcast_name,
            'audio_url': episode.meta_data.get('audio_url') if episode.meta_data else None,
            'published_date': episode.meta_data.get('published_date') if episode.meta_data else None,
        }

        # Update status to PROCESSING
        await update_episode_status(episode_id, EpisodeStatus.PROCESSING)

        # Acquire GPU Lock and Initialize Worker
        logger.info("waiting_for_gpu_lock", episode_id=episode_id)
        async with get_gpu_lock().acquire():
            logger.info("gpu_lock_acquired_initializing_worker", episode_id=episode_id, model=config.whisper_model)
            worker = None
            try:
                loop = asyncio.get_running_loop()
                worker = await loop.run_in_executor(
                    None,
                    lambda: TranscriptionWorker(
                        whisper_model=config.whisper_model,
                        device=config.device,
                        compute_type=config.compute_type,
                        batch_size=config.batch_size
                    )
                )

                # Process Episode
                success, _ = await process_episode_async(
                    episode_data=episode_data,
                    config=config,
                    worker=worker,
                    from_queue=True
                )

                # Unload worker
                del worker
                import gc
                import torch
                gc.collect()
                torch.cuda.empty_cache()
                logger.info("worker_unloaded_memory_freed", episode_id=episode_id)

                if success:
                    logger.info("episode_completed_successfully", episode_id=episode_id, title=episode.title)
                    return True
                else:
                    await update_episode_status(episode_id, EpisodeStatus.FAILED)
                    logger.error("episode_processing_failed", episode_id=episode_id)
                    return False
            except Exception as e:
                logger.error("worker_error", episode_id=episode_id, error=str(e), exc_info=True)
                if worker:
                    del worker
                return False

    except Exception as e:
        logger.error("job_processing_error", episode_id=episode_id, error=str(e), exc_info=True)
        await update_episode_status(episode_id, EpisodeStatus.FAILED)
        return False
    finally:
        clear_status(episode_id=episode_id)
        clear_status(episode_id="current")


async def main():
    """Main worker daemon loop."""
    
    # Apply PyTorch patch for Pyannote compatibility
    apply_pytorch_patch()
    
    # Load configuration
    config = TranscriptionConfig.from_env()
    
    logger.info("worker_daemon_starting", version="v2.1", stream=EventBus.STREAM_TRANSCRIPTION_JOBS)

    event_bus = get_event_bus()
    event_bus.register_signal_handlers()
    
    # Startup Cleanup
    download_dir = Path(config.temp_dir)
    if download_dir.exists():
        logger.info("startup_cleanup", directory=str(download_dir))
        for temp_file in download_dir.glob("*.mp3"):
            try:
                temp_file.unlink()
            except:
                pass
    
    logger.info("worker_subscribed_to_stream", stream=EventBus.STREAM_TRANSCRIPTION_JOBS, group="transcription_workers")
    
    # Start subscribing
    # This will block until shutdown signal
    await event_bus.subscribe(
        stream=EventBus.STREAM_TRANSCRIPTION_JOBS,
        group_name="transcription_workers",
        consumer_name="worker-1", # In a real scaled env, use hostname/uuid
        callback=process_job
    )
    
    logger.info("worker_daemon_shutdown")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
