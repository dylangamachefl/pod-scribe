import asyncio
import os
import sys
from pathlib import Path

# In container, the structure is:
# /app/src/ - contains api, utils, etc.
# /app/shared/ - contains podcast_transcriber_shared
sys.path.insert(0, "/app/src")
sys.path.insert(0, "/app/shared")

try:
    from podcast_transcriber_shared.database import create_episode, init_db, EpisodeStatus
except ImportError as e:
    print(f"Import error: {e}")
    # Show what's in sys.path
    print(f"sys.path: {sys.path}")
    sys.exit(1)

async def test_concurrent_inserts():
    """Attempt multiple concurrent inserts of the same episode ID."""
    print("Initializing database...")
    await init_db()
    
    episode_id = f"test-episode-{os.getpid()}"
    print(f"Testing with episode ID: {episode_id}")
    
    # Run multiple insertions concurrently
    tasks = []
    for i in range(5):
        tasks.append(
            create_episode(
                episode_id=episode_id,
                url=f"http://example.com/audio-{i}.mp3",
                title=f"Concurrent Test Episode {i}",
                podcast_name="Concurrent Test Podcast",
                status=EpisodeStatus.PENDING
            )
        )
    
    print(f"Launching {len(tasks)} concurrent insert requests...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    inserted_count = 0
    skipped_count = 0
    error_count = 0
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"Task {i} failed with error: {result}")
            error_count += 1
        elif result is None:
            print(f"Task {i} was skipped (conflict handled)")
            skipped_count += 1
        else:
            print(f"Task {i} succeeded (newly inserted)")
            inserted_count += 1
            
    print("-" * 40)
    print(f"Results Summary:")
    print(f"  Total Tasks: {len(tasks)}")
    print(f"  Inserted:    {inserted_count}")
    print(f"  Skipped:     {skipped_count}")
    print(f"  Errors:      {error_count}")
    print("-" * 40)
    
    if error_count == 0 and inserted_count == 1:
        print("✅ SUCCESS: Race condition handled correctly!")
    else:
        print("❌ FAILURE: Unexpected results.")

if __name__ == "__main__":
    # Ensure DATABASE_URL is set for local testing if needed
    if not os.getenv("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@postgres:5432/podcast_db"
        print(f"Notice: DATABASE_URL not set, using default: {os.environ['DATABASE_URL']}")
        
    asyncio.run(test_concurrent_inserts())
