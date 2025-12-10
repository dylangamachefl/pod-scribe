import sys
sys.path.insert(0, '/app/src')
import feedparser

url = 'https://www.youtube.com/feeds/videos.xml?playlist_id=PLMMe55HRKxY0pcraHitjU_BhX0iM8dx-N'
feed = feedparser.parse(url)

print(f"Feed parsed successfully: {not feed.bozo}")
print(f"Feed title: {feed.feed.get('title', 'No title')}")
print(f"Number of entries: {len(feed.entries)}")

if feed.entries:
    entry = feed.entries[0]
    print(f"\n=== First Entry ===")
    print(f"Title: {entry.get('title', 'No title')}")
    print(f"ID: {entry.get('id', 'No ID')}")
    print(f"Has 'link' attr: {hasattr(entry, 'link')}")
    
    if hasattr(entry, 'link'):
        print(f"entry.link: {entry.link}")
    
    print(f"entry.get('link'): {entry.get('link', 'None')}")
    
    if hasattr(entry, 'links'):
        print(f"\nLinks array ({len(entry.links)} items):")
        for i, link_item in enumerate(entry.links):
            print(f"  [{i}] rel={link_item.get('rel')}, href={link_item.get('href')}")
    
    print(f"\nEnclosures: {entry.get('enclosures', [])}")
