# Shared Configuration Files

This directory contains configuration files shared across all services in the podcast transcriber monorepo.

## Files

### `subscriptions.json`
**Purpose:** Podcast RSS feed subscriptions

**Schema:**
```json
[
  {
    "url": "https://feeds.example.com/podcast.rss",
    "title": "Podcast Name",
    "active": true,
    "added_date": "2024-01-15"
  }
]
```

**Fields:**
- `url` (required): RSS feed URL
- `title` (required): Display name for the podcast
- `active` (required): Whether to check this feed for new episodes
- `added_date` (optional): When this subscription was added

**Used By:**
- Transcription Service (reads feeds, processes episodes)
- Dashboard UI (manages subscriptions)

**Managed By:**
- Dashboard UI (Add/Edit/Delete operations)
- Can be manually edited if needed

---

### `history.json`
**Purpose:** Track processed podcast episodes to avoid duplicates

**Schema:**
```json
{
  "processed_episodes": [
    "guid-or-url-1",
    "guid-or-url-2",
    "guid-or-url-3"
  ]
}
```

**Fields:**
- `processed_episodes`: Array of episode GUIDs or URLs that have been transcribed

**Used By:**
- Transcription Service (checks before processing)
- Episode Manager (deduplication logic)

**Managed By:**
- Automatically updated by transcription service
- Can be manually edited to reprocess episodes (remove GUID)

---

### `pending_episodes.json`
**Purpose:** Queue of episodes waiting to be transcribed

**Schema:**
```json
[
  {
    "id": "unique-episode-guid",
    "episode_title": "Episode Title",
    "feed_title": "Podcast Name",
    "audio_url": "https://example.com/audio.mp3",
    "duration": "45:23",
    "published_date": "2024-12-04",
    "selected": true,
    "added_date": "2024-12-04T10:30:00"
  }
]
```

**Fields:**
- `id` (required): Unique episode identifier (usually GUID from RSS feed)
- `episode_title` (required): Episode name
- `feed_title` (required): Podcast name
- `audio_url` (required): Direct link to audio file
- `duration` (optional): Episode length
- `published_date` (optional): Original publish date
- `selected` (required): Whether this episode is marked for transcription
- `added_date` (required): When added to queue

**Used By:**
- Dashboard UI (displays queue, allows selection)
- Transcription Service (processes selected episodes)

**Managed By:**
- Dashboard UI (Fetch Episodes, Select/Deselect)
- Episode Manager (programmatic queue management)

---

### `status.json`
**Purpose:** Real-time transcription progress tracking

**Schema:**
```json
{
  "is_running": true,
  "current_episode": "Episode Title",
  "current_podcast": "Podcast Name",
  "stage": "transcribing",
  "progress": 0.45,
  "episodes_completed": 2,
  "episodes_total": 5,
  "last_updated": "2024-12-04T10:30:00"
}
```

**Fields:**
- `is_running` (required): Whether transcription is currently running
- `current_episode` (optional): Episode being processed
- `current_podcast` (optional): Podcast being processed
- `stage` (optional): Current stage: "preparing", "downloading", "transcribing", "diarizing", "saving"
- `progress` (optional): Stage progress (0.0 to 1.0)
- `episodes_completed` (optional): Number of episodes finished in this run
- `episodes_total` (optional): Total episodes to process
- `last_updated` (required): ISO timestamp of last update

**Used By:**
- Dashboard UI (displays progress in real-time)
- Status Monitor (updates during processing)

**Managed By:**
- Status Monitor service (automatic updates)
- Cleared when processing completes

---

## File Locations

All configuration files are located in:
```
<project-root>/shared/config/
```

This centralized location allows all services to access the same configuration.

## Path References

Services reference these files using:

**Transcription Service:**
```python
from config import get_config

config = get_config()
# Automatically uses shared/config/ directory
```

**RAG Service:**
```python
from config import PROJECT_ROOT

config_dir = PROJECT_ROOT / "shared" / "config"
```

## Backup Recommendations

These files contain application state and should be backed up regularly:

```bash
# Backup all config
cp -r shared/config shared/config.backup

# Or individually
cp shared/config/subscriptions.json shared/config/subscriptions.json.backup
cp shared/config/history.json shared/config/history.json.backup
```

## Migration Notes

If upgrading from the old structure, configuration files have been moved:

**Old Location → New Location:**
- `config/subscriptions.json` → `shared/config/subscriptions.json`
-  `config/history.json` → `shared/config/history.json`
- `config/pending_episodes.json` → `shared/config/pending_episodes.json`
- `config/status.json` → `shared/config/status.json`

The application will automatically use the new location. Old files can be safely deleted after verifying the new structure works.

## Troubleshooting

### "File not found" errors
- Ensure you're running from the project root directory
- Check that `shared/config/` directory exists
- Verify file permissions

### Configuration not loading
- Check JSON syntax is valid (use JSONLint)
- Ensure files are UTF-8 encoded
- Look for error messages in logs

### Reprocessing episodes
To reprocess an episode that's already in history:
1. Open `shared/config/history.json`
2. Find and remove the episode GUID from `processed_episodes` array
3. Save the file
4. Run transcription again

## Schema Validation

To validate configuration files:

```python
import json
from pathlib import Path

config_dir = Path("shared/config")

# Load and validate subscriptions
with open(config_dir / "subscriptions.json") as f:
    subs = json.load(f)
    assert isinstance(subs, list), "Subscriptions must be an array"
    for sub in subs:
        assert "url" in sub, "Each subscription needs a URL"
        assert "title" in sub, "Each subscription needs a title"
        assert "active" in sub, "Each subscription needs active flag"

print("✅ Configuration valid!")
```
