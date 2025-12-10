import sys
sys.path.insert(0, '/app/src')
from managers.episode_manager import fetch_episodes_from_feed

url = 'https://www.youtube.com/feeds/videos.xml?playlist_id=PLMMe55HRKxY0pcraHitjU_BhX0iM8dx-N'
episodes, title = fetch_episodes_from_feed(url, 'Learn', days_limit=365)

print(f"Feed: {title}")
print(f"New episodes returned: {len(episodes)}")

if len(episodes) == 0:
    print("\nNo new episodes found. This likely means:")
    print("1. All episodes are already in pending_episodes.json")
    print("2. Or all episodes are in history.json (already processed)")
    
    # Let's check what the feed actually has
    import feedparser
    feed = feedparser.parse(url)
    print(f"\nFeed actually has {len(feed.entries)} total entries")
    
    if feed.entries:
        print("\nFirst entry details:")
        entry = feed.entries[0]
        print(f"  ID: {entry.get('id')}")
        print(f"  Title: {entry.get('title')}")
        if hasattr(entry, 'link'):
            print(f"  Link: {entry.link}")
else:
    print("\nSample episodes:")
    for ep in episodes[:3]:
        print(f"  - {ep['episode_title'][:60]}")
        print(f"    URL: {ep['audio_url']}")
