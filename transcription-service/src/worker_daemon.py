"""
Transcription Worker Daemon

Continuously polls Redis for transcription jobs and processes them.
This replaces the one-shot CLI approach with a long-running worker.

Usage:
    python worker_daemon.py

The worker will:
1. Connect to Redis
2. Poll for jobs on the 'transcription_queue' key
3. Process jobs using the existing transcription pipeline
4. Return to idle state when done
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
from core.processor import process_episode, load_history, save_history
from podcast_transcriber_shared.database import create_episode, update_episode_status, EpisodeStatus


# Global flag for graceful shutdown
shutdown_event = asyncio.Event()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    print("\n🛑 Received shutdown signal, finishing current job...")
    shutdown_event.set()


async def main():
    """Main worker daemon loop."""
    
    # Apply PyTorch patch for Pyannote compatibility
    apply_pytorch_patch()
    
    # Load configuration
    config = TranscriptionConfig.from_env()
    
    # Setup signal handlers for graceful shutdown (must be done in main thread)
    # asyncio.run handles the loop, so we can't use signal.signal with async callback directly easily
    # but we can set the event.
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, lambda: shutdown_event.set())
        loop.add_signal_handler(signal.SIGTERM, lambda: shutdown_event.set())
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        signal.signal(signal.SIGINT, lambda s, f: shutdown_event.set())
        signal.signal(signal.SIGTERM, lambda s, f: shutdown_event.set())
    
    print("\n")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║          Podcast Transcription Worker Daemon v2.0           ║")
    print("║          Redis Queue-Based Architecture                      ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\n📡 Connecting to Redis: {config.redis_url}")
    
    try:
        # Connect to Redis
        r = redis.from_url(config.redis_url, decode_responses=True)
        await r.ping()  # Test connection
        print("✅ Redis connection established")
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        print("   Make sure Redis is running and accessible")
        sys.exit(1)
    
    print(f"\n🔄 Worker started in daemon mode")
    print(f"📋 Polling queue: 'transcription_queue'")
    print(f"⏱️  Poll interval: 5 seconds")
    print(f"💡 Tip: Click 'Run Transcription' in the UI to add jobs\n")
    print("=" * 64)
    
    job_count = 0
    
    # Load processing history
    history = load_history(config)
    
    while not shutdown_event.is_set():
        try:
            # Non-blocking pop with timeout using async redis
            # blpop returns a tuple (key, value) or None if timeout
            result = await r.blpop('transcription_queue', timeout=5)
            
            if result:
                _, job_data = result
                job_count += 1
                
                print(f"\n📥 Job #{job_count} received from queue")
                print(f"📄 Raw job data: {job_data}")
                print("="* 64)
                
                episode_id = None
                try:
                    # Parse the job payload
                    job_payload = json.loads(job_data)
                    
                    print(f"📋 Parsed job payload:")
                    print(f"   Episode: {job_payload.get('episode_title', 'Unknown')}")
                    print(f"   Podcast: {job_payload.get('feed_title', 'Unknown')}")
                    print(f"   Audio URL: {job_payload.get('audio_url', 'N/A')[:50]}...")
                    print("="* 64)
                    
                    episode_id = job_payload.get('id', '')
                    if episode_id:
                        try:
                            # Create or update episode to PROCESSING status
                            await create_episode(
                                episode_id=episode_id,
                                url=job_payload.get('audio_url', ''),
                                title=job_payload.get('episode_title', 'Unknown'),
                                podcast_name=job_payload.get('feed_title', 'Unknown'),
                                status=EpisodeStatus.PROCESSING,
                                meta_data={"audio_url": job_payload.get('audio_url')}
                            )
                            print(f"💾 Episode created in DB with status=PROCESSING")
                        except Exception as e:
                            # Episode might already exist, try updating status
                            try:
                                await update_episode_status(episode_id, EpisodeStatus.PROCESSING)
                                print(f"💾 Episode status updated to PROCESSING")
                            except Exception as db_e:
                                print(f"⚠️  Failed to update episode status: {db_e}")

                    # Process the specific episode from the payload
                    # The process_episode function expects episode_data with specific fields
                    # process_episode is synchronous and CPU-bound (ML), so we run it in executor
                    success, episode_id = await loop.run_in_executor(
                        None,
                        lambda: process_episode(
                            episode_data=job_payload,
                            config=config,
                            history=history,
                            from_queue=True
                        )
                    )
                    
                    if success:
                        # Save updated history
                        save_history(config, history)
                        print("="* 64)
                        print(f"✅ Job #{job_count} completed successfully\n")
                    else:
                        # Update episode status to FAILED if processing failed
                        if episode_id:
                            try:
                                await update_episode_status(episode_id, EpisodeStatus.FAILED)
                                print(f"💾 Episode status updated to FAILED")
                            except Exception as e:
                                print(f"⚠️  Failed to update episode status: {e}")
                        
                        print("="* 64)
                        print(f"⚠️  Job #{job_count} completed with warnings\n")
                    
                except json.JSONDecodeError as e:
                    print(f"❌ Failed to parse job payload as JSON: {e}")
                    print(f"   Raw data: {job_data}")
                except Exception as e:
                    # Update episode status to FAILED on exception
                    if episode_id:
                        try:
                            await update_episode_status(episode_id, EpisodeStatus.FAILED)
                            print(f"💾 Episode status updated to FAILED")
                        except Exception as db_e:
                            print(f"⚠️  Failed to update episode status: {db_e}")
                    
                    print(f"❌ Error processing job payload: {e}")
                    import traceback
                    traceback.print_exc()
                
                print("🔄 Returning to idle state, waiting for next job...")
                print("=" * 64)
            
        except redis.ConnectionError as e:
            print(f"❌ Redis connection error: {e}")
            print("   Retrying in 10 seconds...")
            await asyncio.sleep(10)
            try:
                await r.ping()
                print("✅ Reconnected to Redis")
            except:
                pass
                
        except asyncio.CancelledError:
             print("\n🛑 Task cancelled")
             break

        except Exception as e:
            print(f"❌ Error in worker loop: {e}")
            import traceback
            traceback.print_exc()
            print("   Waiting 5 seconds before continuing...")
            await asyncio.sleep(5)

    # Clean up Redis connection
    await r.close()
    
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║          Worker Daemon Shut Down                            ║")
    print(f"║          Processed {job_count} job(s) this session                     ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
