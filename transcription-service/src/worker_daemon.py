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
import redis
import json
import time
import signal
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import TranscriptionConfig
from core.diarization import apply_pytorch_patch
from core.processor import process_selected_episodes


# Global flag for graceful shutdown
shutdown_flag = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_flag
    print("\n🛑 Received shutdown signal, finishing current job...")
    shutdown_flag = True


def main():
    """Main worker daemon loop."""
    global shutdown_flag
    
    # Apply PyTorch patch for Pyannote compatibility
    apply_pytorch_patch()
    
    # Load configuration
    config = TranscriptionConfig.from_env()
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("\n")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║          Podcast Transcription Worker Daemon v2.0           ║")
    print("║          Redis Queue-Based Architecture                      ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\n📡 Connecting to Redis: {config.redis_url}")
    
    try:
        # Connect to Redis
        r = redis.from_url(config.redis_url, decode_responses=True)
        r.ping()  # Test connection
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
    
    while not shutdown_flag:
        try:
            # Blocking pop with 5 second timeout
            # This waits up to 5 seconds for a job, then returns None if queue is empty
            result = r.blpop('transcription_queue', timeout=5)
            
            if result:
                _, job_data = result
                job_count += 1
                
                print(f"\n📥 Job #{job_count} received from queue")
                print(f"📄 Job data: {job_data}")
                print("="* 64)
                
                # Process the transcription job
                # The existing function reads selected episodes from the config files
                process_selected_episodes(config)
                
                print("=" * 64)
                print(f"✅ Job #{job_count} completed successfully\n")
                print("🔄 Returning to idle state, waiting for next job...")
                print("=" * 64)
            
        except redis.ConnectionError as e:
            print(f"❌ Redis connection error: {e}")
            print("   Retrying in 10 seconds...")
            time.sleep(10)
            try:
                r.ping()
                print("✅ Reconnected to Redis")
            except:
                pass
                
        except KeyboardInterrupt:
            print("\n🛑 Keyboard interrupt received")
            break
            
        except Exception as e:
            print(f"❌ Error processing job: {e}")
            import traceback
            traceback.print_exc()
            print("   Waiting 5 seconds before continuing...")
            time.sleep(5)
    
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║          Worker Daemon Shut Down                            ║")
    print(f"║          Processed {job_count} job(s) this session                     ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")


if __name__ == "__main__":
    main()
