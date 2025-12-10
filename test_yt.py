"""Test YouTube feed parsing"""
import feedparser

feed = feedparser.parse('https://www.youtube.com/feeds/videos.xml?playlist_id=PLMMe55HRKxY0pcraHitjU_BhX0iM8dx-N')
if feed.entries:
    entry = feed.entries[0]
    print("Title:", entry.get('title'))
    print("Has link attr:", hasattr(entry, 'link'))
    if hasattr(entry, 'link'):
        print("entry.link value:", entry.link)
    print("entry.get('link'):", entry.get('link'))
