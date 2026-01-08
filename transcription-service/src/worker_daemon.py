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
import uuid
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
from managers.status_monitor import write_status, clear_status, read_status, get_pipeline_status_manager

# Configure structured logging
configure_logging("transcription-worker")
logger = get_logger(__name__)

# Global flag for graceful shutdown
shutdown_event = asyncio.Event()

# Global state for batch-retention
_active_worker = None
_active_lock_ctx = None
_last_job_time = 0
_batch_episodes = {} # batch_id -> list[episode_id]
_job_in_progress = False
_current_episode_id = None

async def process_job(job_data: dict) -> bool:
    """
    Process a single transcription job.
    Returns True if successful, False otherwise.
    """
    global _job_in_progress, _current_episode_id
    _job_in_progress = True
    _current_episode_id = job_data.get('episode_id')
    try:
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

            batch_id = job_data.get('batch_id', 'default')
            if batch_id not in _batch_episodes:
                _batch_episodes[batch_id] = []
            
            # Avoid duplicate IDs in the batch list
            if episode_id not in _batch_episodes[batch_id]:
                _batch_episodes[batch_id].append(episode_id)

            logger.info("episode_metadata_retrieved", episode_id=episode_id, title=episode.title, podcast=episode.podcast_name, batch_id=batch_id)
            write_status(
                is_running=True,
                episode_id=episode_id,
                current_episode=episode.title,
                current_podcast=episode.podcast_name,
                stage="preparing",
                log_message=f"Found Metadata: {episode.title}"
            )

            episode_data = {
                'id': episode.id,
                'episode_title': episode.title,
                'feed_title': episode.podcast_name,
                'audio_url': episode.meta_data.get('audio_url') if episode.meta_data else None,
                'published_date': episode.meta_data.get('published_date') if episode.meta_data else None,
            }

            await update_episode_status(episode_id, EpisodeStatus.TRANSCRIBING)

            global _active_worker, _active_lock_ctx, _last_job_time
            
            # 1. Acquire GPU Lock and Initialize Worker (if not already held)
            if _active_worker is None:
                logger.info("waiting_for_gpu_lock", episode_id=episode_id)
                _active_lock_ctx = get_gpu_lock().acquire()
                await _active_lock_ctx.__aenter__()
                
                logger.info("gpu_lock_acquired_initializing_worker", episode_id=episode_id, model=config.whisper_model)
                loop = asyncio.get_running_loop()
                _active_worker = await loop.run_in_executor(
                    None,
                    lambda: TranscriptionWorker(
                        whisper_model=config.whisper_model,
                        device=config.device,
                        compute_type=config.compute_type,
                        batch_size=config.batch_size
                    )
                )

            # Check for cancellation signals before starting work
            manager = get_pipeline_status_manager()
            if manager.is_stopped():
                logger.info("pipeline_stopped_skipping_job", episode_id=episode_id)
                await update_episode_status(episode_id, EpisodeStatus.FAILED)
                manager.update_service_status('transcription', episode_id, "stopped", progress=0.0, log_message="Pipeline stopped by user")
                return True # Acknowledge the job as handled (skipped)

            if manager.is_batch_cancelled(batch_id):
                logger.info("batch_cancelled_skipping_job", episode_id=episode_id, batch_id=batch_id)
                await update_episode_status(episode_id, EpisodeStatus.FAILED)
                manager.update_service_status('transcription', episode_id, "cancelled", progress=0.0, log_message=f"Batch {batch_id} cancelled by user")
                return True # Acknowledge the job as handled (skipped)

            # 2. Process Episode using persistent worker
            try:
                success, _ = await process_episode_async(
                    episode_data=episode_data,
                    config=config,
                    worker=_active_worker,
                    from_queue=True
                )
                
                _last_job_time = time.time()

                if success:
                    logger.info("episode_completed_successfully", episode_id=episode_id, title=episode.title)
                    return True
                else:
                    await update_episode_status(episode_id, EpisodeStatus.FAILED)
                    logger.error("episode_processing_failed", episode_id=episode_id)
                    return False
                    
            except Exception as e:
                logger.error("worker_error", episode_id=episode_id, error=str(e), exc_info=True)
                await update_episode_status(episode_id, EpisodeStatus.FAILED)
                return False

        except Exception as e:
            logger.error("job_processing_error", episode_id=episode_id, error=str(e), exc_info=True)
            await update_episode_status(episode_id, EpisodeStatus.FAILED)
            return False
        finally:
            clear_status(episode_id=episode_id)
            clear_status(episode_id="current")
    finally:
        _job_in_progress = False
        _current_episode_id = None


async def main():
    """Main entry point for the transcription worker daemon."""
    logger.info("worker_daemon_starting", stream=EventBus.STREAM_TRANSCRIPTION_JOBS)

    # Register signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_event.set)
    
    logger.info("signal_handlers_registered")

    # Connect to event bus (happens automatically on subscribe/publish)
    event_bus = get_event_bus()
    
    # Apply PyTorch patch for Pyannote compatibility
    apply_pytorch_patch()
    
    # Load configuration
    config = TranscriptionConfig.from_env()
    
    # Startup Cleanup
    download_dir = Path(config.temp_dir)
    if download_dir.exists():
        logger.info("startup_cleanup", directory=str(download_dir))
        for temp_file in download_dir.glob("*.mp3"):
            try:
                temp_file.unlink()
            except Exception as e:
                logger.warning("failed_to_clean_temp_file", file=str(temp_file), error=str(e))
    
    logger.info("worker_subscribed_to_stream", stream=EventBus.STREAM_TRANSCRIPTION_JOBS, group="transcription_workers")
    
    # Startup Cleanup: Clear stale "is_running" status if no jobs are pending
    manager = get_pipeline_status_manager()
    status = read_status()
    if status and status.get('is_running'):
        logger.info("startup_clearing_stale_running_status")
        manager.update_service_status('transcription', 'current', stage='idle', additional_data={'is_running': False})

    # Subscribe to transcription jobs stream
    subscriber_task = asyncio.create_task(event_bus.subscribe(
        stream=EventBus.STREAM_TRANSCRIPTION_JOBS,
        group_name="transcription_workers",
        consumer_name="worker-1",
        callback=process_job
    ))

    async def stop_monitor():
        """Background monitor to force process exit on stop signal."""
        while not shutdown_event.is_set():
            await asyncio.sleep(2)
            try:
                manager = get_pipeline_status_manager()
                if manager.is_stopped():
                    global _job_in_progress, _current_episode_id
                    if _job_in_progress and _current_episode_id:
                        logger.critical("aborting_transcription_due_to_stop_signal", episode_id=_current_episode_id)
                        # Mark episode as failed in DB
                        try:
                            from podcast_transcriber_shared.database import update_episode_status, EpisodeStatus
                            await update_episode_status(_current_episode_id, EpisodeStatus.FAILED)
                        except Exception as e:
                            logger.error("failed_to_update_episode_status_during_abort", error=str(e))
                        
                        manager.update_service_status('transcription', _current_episode_id, "aborted", progress=0.0, log_message="Aborted: Stop signal received")
                        
                        # Force exit to clear GPU context immediately
                        logger.info("force_restarting_process_to_clear_gpu")
                        import os
                        os._exit(1) 
            except Exception as e:
                logger.error("stop_monitor_error", error=str(e))

    monitor_task = asyncio.create_task(stop_monitor())

    try:
        # Monitor for idle and release GPU if no new jobs come in
        while not shutdown_event.is_set():
            await asyncio.sleep(2)
            global _active_worker, _active_lock_ctx, _last_job_time, _batch_episodes, _job_in_progress
            
            # If we have a worker and it's been idle for more than 10 seconds AND NO JOB IS CURRENTLY RUNNING
            if _active_worker and not _job_in_progress and (time.time() - _last_job_time > 10):
                logger.info("worker_idle_releasing_gpu")
                
                # 1. First, check if we have any completed batches to announce
                completed_batches = list(_batch_episodes.keys())
                for batch_id in completed_batches:
                    if batch_id != 'default':
                        from podcast_transcriber_shared.events import BatchTranscribed
                        eb = get_event_bus()
                        await eb.publish(eb.STREAM_BATCH_TRANSCRIBED, BatchTranscribed(
                            event_id=f"batch_{uuid.uuid4().hex[:8]}",
                            service="transcription-worker",
                            batch_id=batch_id,
                            episode_ids=_batch_episodes[batch_id]
                        ))
                        logger.info("batch_completion_signaled", batch_id=batch_id, count=len(_batch_episodes[batch_id]))
                    del _batch_episodes[batch_id]
                
                # 2. Cleanup GPU
                del _active_worker
                _active_worker = None
                
                import gc
                import torch
                gc.collect()
                torch.cuda.empty_cache()
                
                if _active_lock_ctx:
                    await _active_lock_ctx.__aexit__(None, None, None)
                    _active_lock_ctx = None
                
                # Update status to idle
                manager.update_service_status('transcription', 'current', stage='idle', additional_data={'is_running': False})
                logger.info("gpu_resource_released_for_other_services")
    finally:
        logger.info("worker_daemon_shutting_down")
        # Ensure status is cleared
        manager.update_service_status('transcription', 'current', stage='offline', additional_data={'is_running': False})
        
        subscriber_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass
        
        await event_bus.close()
        logger.info("worker_daemon_stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
