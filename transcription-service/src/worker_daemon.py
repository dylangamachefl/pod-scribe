"""
Transcription Worker Daemon

Continuously polls Redis for transcription jobs and processes them.
This replaces the one-shot CLI approach with a long-running worker.

Usage:
    python worker_daemon.py
"""
import asyncio
import json
import time
import signal
import sys
from pathlib import Path
import redis.asyncio as redis

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import TranscriptionConfig
from core.diarization import apply_pytorch_patch
from core.processor import process_episode_async, load_history, save_history
from core.audio import TranscriptionWorker
from podcast_transcriber_shared.database import create_episode, update_episode_status, EpisodeStatus


# Global flag for graceful shutdown
shutdown_event = asyncio.Event()


async def main():
    """Main worker daemon loop."""
    
    # Apply PyTorch patch for Pyannote compatibility
    apply_pytorch_patch()
    
    # Load configuration
    config = TranscriptionConfig.from_env()
    
    # Setup signal handlers
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, lambda: shutdown_event.set())
        loop.add_signal_handler(signal.SIGTERM, lambda: shutdown_event.set())
    except NotImplementedError:
        signal.signal(signal.SIGINT, lambda s, f: shutdown_event.set())
        signal.signal(signal.SIGTERM, lambda s, f: shutdown_event.set())
    
    print("\n")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║          Podcast Transcription Worker Daemon v2.0           ║")
    print("║          Redis Queue-Based Architecture                      ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    
    # Connect to Redis
    try:
        r = redis.from_url(config.redis_url, decode_responses=True)
        await r.ping()
        print(f"✅ Redis connection established: {config.redis_url}")
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        sys.exit(1)

    # Initialize Persistent Transcription Worker (Heavy Model Load)
    print(f"\n📦 Initializing Transcription Worker (Loading Models)...")
    try:
        # Run worker initialization in executor to avoid blocking the loop
        worker = await loop.run_in_executor(
            None,
            lambda: TranscriptionWorker(
                whisper_model=config.whisper_model,
                device=config.device,
                compute_type=config.compute_type,
                batch_size=config.batch_size
            )
        )
        print("✅ Worker initialized and models loaded")
    except Exception as e:
        print(f"❌ Failed to initialize worker: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print(f"\n🔄 Worker started in daemon mode")
    print(f"📋 Polling queue: 'transcription_queue'")
    print("=" * 64)
    
    job_count = 0
    history = load_history(config)
    
    while not shutdown_event.is_set():
        try:
            # Poll Redis queue
            result = await r.blpop('transcription_queue', timeout=5)
            
            if result:
                _, job_data = result
                job_count += 1
                
                print(f"\n📥 Job #{job_count} received from queue")
                
                episode_id = None
                try:
                    job_payload = json.loads(job_data)
                    
                    # Parse episode_id from simplified job payload
                    # New format: {"episode_id": "yt:video:123", "timestamp": "..."}
                    episode_id = job_payload.get('episode_id')
                    
                    if not episode_id:
                        print(f"⚠️  Job contains no episode_id, skipping")
                        continue
                    
                    print(f"📋 Processing episode: {episode_id}")
                    
                    # Fetch full episode data from PostgreSQL (not SQLite)
                    from podcast_transcriber_shared.database import get_episode_by_id
                    episode = await get_episode_by_id(episode_id, load_transcript=False)
                    
                    if not episode:
                        print(f"⚠️  Episode {episode_id} not found in database, skipping")
                        continue
                    
                    print(f"✅ Retrieved episode from PostgreSQL: {episode.title}")
                    
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
                    print(f"🔄 Updated status to PROCESSING")

                    # Process Episode (Async)
                    # Worker's process_episode_async will save transcript to PostgreSQL
                    success, episode_id = await process_episode_async(
                        episode_data=episode_data,
                        config=config,
                        history=history,
                        worker=worker,
                        from_queue=True
                    )
                    
                    if success:
                        save_history(config, history)
                        print(f"✅ Episode completed successfully: {episode_id}")
                    else:
                        await update_episode_status(episode_id, EpisodeStatus.FAILED)
                        print(f"⚠️  Episode processing failed: {episode_id}")
                    
                    print(f"✅ Job #{job_count} completed successfully")
                    
                except json.JSONDecodeError:
                    print(f"❌ Invalid JSON in job data")
                except Exception as e:
                    print(f"❌ Error processing job: {e}")
                    import traceback
                    traceback.print_exc()
                    if episode_id:
                        await update_episode_status(episode_id, EpisodeStatus.FAILED)
                
                print("=" * 64)
            
        except redis.ConnectionError:
            print("❌ Redis connection lost, retrying...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            await asyncio.sleep(5)

    # Cleanup
    await r.close()
    del worker
    print("\n🛑 Worker daemon shut down")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
