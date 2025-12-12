#!/usr/bin/env python3
"""
Podcast Transcription Engine CLI
Command-line interface for the transcription service.
"""
import sys
import argparse
import warnings
import torch
from datetime import datetime

# Apply PyTorch patch before any other imports
from core.diarization import apply_pytorch_patch
apply_pytorch_patch()

# Now safe to import other modules
from config import get_config
from core.processor import (
    load_subscriptions,
    load_history,
    process_feed,
    process_selected_episodes
)
from managers.episode_manager import fetch_episodes_from_feed, add_episode_to_queue

# Filter out warnings that pollute logs
warnings.filterwarnings("ignore", category=UserWarning, module="pyannote")
warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio")
warnings.filterwarnings("ignore", category=UserWarning, module="speechbrain")


def main():
    """Main execution flow."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Podcast Transcription Engine - Automated transcription with AI'
    )
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Automatically process all new episodes from active feeds (legacy mode)'
    )
    parser.add_argument(
        '--schedule',
        action='store_true',
        help='Schedule mode: fetch and process latest episodes from feeds'
    )
    parser.add_argument(
        '--limit-episodes',
        type=int,
        metavar='N',
        help='When using --schedule, limit to N most recent episodes per feed (default: 1)'
    )
    args = parser.parse_args()
    
    # Validate arguments
    if args.limit_episodes and not args.schedule:
        print("❌ Error: --limit-episodes can only be used with --schedule")
        sys.exit(1)
    
    # Load configuration
    config = get_config()
    
    # Route to appropriate processing mode
    if args.auto:
        # Legacy "process all" mode
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║          Podcast Transcription Engine v1.0                  ║
║          Auto Mode: Processing All New Episodes              ║
╚══════════════════════════════════════════════════════════════╝
     """)\n        \n        # Check CUDA availability and set device\n        if torch.cuda.is_available():\n            gpu_name = torch.cuda.get_device_name(0)\n            vram = torch.cuda.get_device_properties(0).total_memory / 1024**3\n            print(f"🎮 GPU: {gpu_name}")\n            print(f"💾 VRAM: {vram:.1f} GB\n")\n        else:\n            print("⚠️  WARNING: CUDA not available, falling back to CPU")\n            print("   Transcription will be significantly slower on CPU")\n            print("   For GPU support, ensure CUDA drivers are installed\n")
        
        # Load configuration
        subscriptions = load_subscriptions(config)
        if not subscriptions:
            print("⚠️  No active subscriptions found. Add feeds via the web dashboard.")
            print("   Open the frontend at http://localhost:3000 and go to the Feeds page")
            return
        
        history = load_history(config)
        
        # Process each subscription
        start_time = datetime.now()
        for sub in subscriptions:
            process_feed(sub, config, history)
        
        duration = (datetime.now() - start_time).total_seconds()
        print(f"\n{'='*60}")
        print(f"✅ Processing complete!")
        print(f"⏱️  Total time: {duration/60:.1f} minutes")
        print(f"{'='*60}\n")
    
    elif args.schedule:
        # Schedule mode: fetch latest N episodes and process them
        limit = args.limit_episodes if args.limit_episodes else 1
        
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║          Podcast Transcription Engine v1.0                  ║
║          Schedule Mode: Latest {limit} Episode(s) per Feed             ║
╚══════════════════════════════════════════════════════════════╝
    """)
        
        print(f"⚠️  This will automatically fetch and process the latest {limit} episode(s) from each feed\n")
        
        # Check CUDA availability and set device
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"🎮 GPU: {gpu_name}")
            print(f"💾 VRAM: {vram:.1f} GB\n")
        else:
            print("⚠️  WARNING: CUDA not available, falling back to CPU")
            print("   Transcription will be significantly slower on CPU")
            print("   For GPU support, ensure CUDA drivers are installed\n")
        
        # Load subscriptions
        subscriptions = load_subscriptions(config)
        active_subs = [sub for sub in subscriptions if sub.get('active', True)]
        
        if not active_subs:
            print("❌ No active feeds found. Add feeds via the web dashboard.")
            print("   Open the frontend at http://localhost:3000 and go to the Feeds page")
            return
        
        print(f"📡 Found {len(active_subs)} active feed(s)\n")
        
        # Fetch episodes from feeds
        total_fetched = 0
        for sub in active_subs:
            episodes, feed_title = fetch_episodes_from_feed(
                sub.get('url'),
                sub.get('title')
            )
            
            # Limit to N most recent
            episodes = episodes[:limit]
            
            # Add to queue and mark as selected
            for episode in episodes:
                episode['selected'] = True  # Auto-select for schedule mode
                if add_episode_to_queue(episode):
                    total_fetched += 1
                    print(f"📥 Queued: {episode.get('episode_title')} ({feed_title})")
        
        if total_fetched == 0:
            print("\nℹ️  No new episodes found to process")
            return
        
        print(f"\n✅ Fetched and queued {total_fetched} episode(s)\n")
        
        # Process the selected episodes
        process_selected_episodes(config)
    
    else:
        # Default: Manual mode - process selected episodes
        process_selected_episodes(config)


if __name__ == "__main__":
    main()
