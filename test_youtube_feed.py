"""Test script to verify feedparser correctly extracts YouTube feed links"""
import feedparser

youtube_feed_url = "https://www.youtube.com/feeds/videos.xml?playlist_id=PLMMe55HRKxY0pcraHitjU_BhX0iM8dx-N"

print("Fetching YouTube feed...")
feed = feedparser.parse(youtube_feed_url)

print(f"\nFeed title: {feed.feed.get('title', 'No title')}")
print(f"Number of entries: {len(feed.entries)}\n")

if feed.entries:
    entry = feed.entries[0]  # Test first entry
    print("=" * 60)
    print(f"First entry title: {entry.get('title', 'No title')}")
    print("\nAvailable attributes on entry:")
    print(f"  - hasattr(entry, 'link'): {hasattr(entry, 'link')}")
    print(f"  - hasattr(entry, 'links'): {hasattr(entry, 'links')}")
    print(f"  - entry.get('link'): {entry.get('link', 'None')}")
    
    if hasattr(entry, 'link'):
        print(f"\n  entry.link = {entry.link}")
    
    if hasattr(entry, 'links'):
        print(f"\n  entry.links:")
        for link_item in entry.links:
            print(f"    - rel={link_item.get('rel')}, href={link_item.get('href')}")
    
    print("\nEnclosures:")
    print(f"  {entry.get('enclosures', [])}")
    print("=" * 60)
    
    # Test our extraction logic
    print("\nTesting extraction logic:")
    audio_url = None
    
    # Method 1: Check for audio enclosures
    for enclosure in entry.get('enclosures', []):
        if enclosure.get('type', '').startswith('audio/'):
            audio_url = enclosure.get('href')
            print(f"  Method 1 (audio enclosures): {audio_url}")
            break
    
    # Method 2: Check direct link attribute
    if not audio_url and hasattr(entry, 'link'):
        audio_url = entry.link
        print(f"  Method 2 (entry.link): {audio_url}")
    
    # Method 3: Check links array
    if not audio_url and hasattr(entry, 'links'):
        for link_item in entry.links:
            if link_item.get('rel') == 'alternate':
                audio_url = link_item.get('href')
                print(f"  Method 3 (links array): {audio_url}")
                break
    
    # Method 4: Fallback to dict access
    if not audio_url:
        audio_url = entry.get('link', '')
        print(f"  Method 4 (dict access): {audio_url}")
    
    print(f"\nFinal extracted URL: {audio_url}")
    print(f"Is valid YouTube URL: {'youtube.com' in audio_url or 'youtu.be' in audio_url}")
