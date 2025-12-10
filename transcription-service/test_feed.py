#!/usr/bin/env python3
"""Test YouTube feed fetching"""
import sys
sys.path.insert(0, '/app/src')

from managers.episode_manager import fetch_episodes_from_feed

# Test the YouTube feed
youtube_url = 'https://www.youtube.com/feeds/videos.xml?playlist_id=PLMMe55HRKxY0pcraHitjU_BhX0iM8dx-N'
episodes, title = fetch_episodes_from_feed(youtube_url, 'Learn', days_limit=365)

print(f"Feed Title: {title}")
print(f"Total Episodes Found: {len(episodes)}")
print("\nFirst 3 episodes:")
for i, ep in enumerate(episodes[:3], 1):
    print(f"\n{i}. {ep['episode_title']}")
    print(f"   URL: {ep['audio_url']}")
    print(f"   ID: {ep['id']}")
