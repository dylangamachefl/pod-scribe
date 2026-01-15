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

# Import recovery script
from scripts.reset_stuck_jobs import recover

# Configure structured logging
configure_logging("transcription-worker")
logger = get_logger(__name__)

# Global flag for graceful shutdown
shutdown_event = asyncio.Event()

class TranscriptionDaemon:
    """
    Stateful daemon for managing transcription jobs, GPU resources, and lifecycles.
    """
    def __init__(self):
        self.config = TranscriptionConfig.from_env()
        self.active_worker = None
        self.active_lock_ctx = None
        self.last_job_time = 0
        self.batch_episodes = {} # batch_id -> list[episode_id]
        self.job_in_progress = False
        self.current_episode_id = None
        self.idle_timeout = 300 # 5 minutes
        self.manager = get_pipeline_status_manager()

    async def force_release(self):
        """Explicitly clear GPU cache and release lock immediately."""
        logger.info("force_releasing_gpu_resources")
        if self.active_worker:
            del self.active_worker
            self.active_worker = None
        
        import gc
        import torch
        gc.collect()
        torch.cuda.empty_cache()
        
        if self.active_lock_ctx:
            try:
                await self.active_lock_ctx.__aexit__(None, None, None)
            except Exception as e:
                logger.warning("failed_to_release_lock_during_force_release", error=str(e))
            self.active_lock_ctx = None
        
        # Update status to idle/offline
        self.manager.update_service_status('transcription', 'current', stage='idle', additional_data={'is_running': False})

    async def process_job(self, job_data: dict) -> bool:
        """Process a single transcription job."""
        self.job_in_progress = True
        episode_id = job_data.get('episode_id')
        self.current_episode_id = episode_id
        
        try:
            if not episode_id:
                logger.warning("job_missing_episode_id", job_data=job_data)
                return True # Skip invalid jobs

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
                # Fetch full episode data
                episode = await get_episode_by_id(episode_id, load_transcript=False)
                if not episode:
                    logger.warning("episode_not_found_in_database", episode_id=episode_id)
                    return True

                batch_id = job_data.get('batch_id', 'default')
                if batch_id not in self.batch_episodes:
                    self.batch_episodes[batch_id] = []
                
                if episode_id not in self.batch_episodes[batch_id]:
                    self.batch_episodes[batch_id].append(episode_id)

                logger.info("episode_metadata_retrieved", episode_id=episode_id, title=episode.title)
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
                }

                await update_episode_status(episode_id, EpisodeStatus.TRANSCRIBING)

                # 1. Acquire GPU Lock and Initialize Worker (if not already held)
                if self.active_worker is None:
                    logger.info("waiting_for_gpu_lock", episode_id=episode_id)
                    self.active_lock_ctx = get_gpu_lock().acquire()
                    await self.active_lock_ctx.__aenter__()
                    
                    logger.info("gpu_lock_acquired_initializing_worker", episode_id=episode_id)
                    loop = asyncio.get_running_loop()
                    self.active_worker = TranscriptionWorker(
                        whisper_model=self.config.whisper_model,
                        device=self.config.device,
                        compute_type=self.config.compute_type,
                        batch_size=self.config.batch_size,
                        huggingface_token=self.config.huggingface_token
                    )
                    # Note: TranscriptionWorker.__init__ no longer loads heavy models, 
                    # it lazy loads them in process().

                # Check for cancellation signals
                if self.manager.is_stopped() or self.manager.is_batch_cancelled(batch_id):
                    logger.info("job_cancelled_skipping", episode_id=episode_id)
                    await update_episode_status(episode_id, EpisodeStatus.FAILED)
                    return True

                # 2. Process Episode
                success, _ = await process_episode_async(
                    episode_data=episode_data,
                    config=self.config,
                    worker=self.active_worker,
                    from_queue=True
                )
                
                self.last_job_time = time.time()

                if success:
                    logger.info("episode_completed_successfully", episode_id=episode_id)
                    
                    # Check if this batch is now complete for immediate release
                    if batch_id != 'default':
                        # Scoped processed count check
                        if episode_id not in self.batch_episodes[batch_id]:
                            self.batch_episodes[batch_id].append(episode_id)
                        
                        processed_count = len(self.batch_episodes[batch_id])
                        total_count = int(job_data.get('total_batch_count', 1))
                        
                        if processed_count >= total_count:
                            logger.info("batch_complete_triggering_immediate_release", 
                                       batch_id=batch_id, processed=processed_count, total=total_count)
                            
                            # 1. Publish BatchTranscribed immediately
                            from podcast_transcriber_shared.events import BatchTranscribed
                            eb = get_event_bus()
                            await eb.publish(eb.STREAM_BATCH_TRANSCRIBED, BatchTranscribed(
                                event_id=f"batch_{uuid.uuid4().hex[:8]}",
                                service="transcription-daemon",
                                batch_id=batch_id,
                                episode_ids=self.batch_episodes[batch_id]
                            ))
                            
                            # 2. Clear batch state and release GPU
                            del self.batch_episodes[batch_id]
                            await self.force_release()
                            
                    return True
                else:
                    await update_episode_status(episode_id, EpisodeStatus.FAILED)
                    return False
                    
            except Exception as e:
                logger.error("job_error", episode_id=episode_id, error=str(e), exc_info=True)
                await update_episode_status(episode_id, EpisodeStatus.FAILED)
                return False
            finally:
                clear_status(episode_id=episode_id)
        finally:
            self.job_in_progress = False
            self.current_episode_id = None

    async def run(self):
        """Main daemon loop."""
        logger.info("transcription_daemon_starting")
        
        # Register signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, shutdown_event.set)
        
        # Apply PyTorch patch
        apply_pytorch_patch()
        
        # 1. Startup Recovery & Cleanup
        logger.info("running_startup_recovery")
        await recover(temp_dir=Path(self.config.temp_dir))
        
        # 2. Subscribe to jobs
        event_bus = get_event_bus()
        subscriber_task = asyncio.create_task(event_bus.subscribe(
            stream=EventBus.STREAM_TRANSCRIPTION_JOBS,
            group_name="transcription_workers",
            consumer_name=f"worker-{uuid.uuid4().hex[:4]}",
            callback=self.process_job
        ))

        async def stop_monitor():
            while not shutdown_event.is_set():
                await asyncio.sleep(2)
                if self.manager.is_stopped():
                    if self.job_in_progress:
                        logger.critical("aborting_job_due_to_stop_signal", episode_id=self.current_episode_id)
                        if self.current_episode_id:
                            await update_episode_status(self.current_episode_id, EpisodeStatus.FAILED)
                        await self.force_release()
                        # We don't os._exit(1) anymore, we allow force_release to clear GPU
                        # and then we continue to loop or shut down gracefully.
                        # However, for GPU stability, some might still prefer process restart.
                        # For now, we follow the "Explicit Handover" refinement.

        monitor_task = asyncio.create_task(stop_monitor())

        try:
            while not shutdown_event.is_set():
                # We no longer need background idle timeout polling because we release GPU 
                # deterministically at the end of each batch using total_batch_count.
                await asyncio.sleep(1)
        finally:
            logger.info("daemon_shutting_down")
            await self.force_release()
            subscriber_task.cancel()
            await event_bus.close()
            logger.info("daemon_stopped")


async def main():
    daemon = TranscriptionDaemon()
    await daemon.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
