import asyncio
import os
import sys

# Add project root to path so we can import shared
sys.path.append(os.getcwd())

from shared.podcast_transcriber_shared.events import get_event_bus, EpisodeTranscribed

async def main():
    print("🚀 Publishing test event...")
    bus = get_event_bus()
    
    event = EpisodeTranscribed(
        event_id="evt_test_manual_1",
        service="manual_test",
        episode_id="yt:video:c5yDkwjZG80",
        episode_title="Learning Skills with Deepagents",
        podcast_name="Test Podcast"
    )
    
    success = await bus.publish(bus.STREAM_TRANSCRIBED, event)
    
    if success:
        print("✅ Event published successfully!")
    else:
        print("❌ Failed to publish event")
        
    await bus.close()

if __name__ == "__main__":
    asyncio.run(main())
