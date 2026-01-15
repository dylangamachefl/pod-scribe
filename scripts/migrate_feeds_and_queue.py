import os
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add shared package to path
import sys
sys.path.append(os.path.join(os.getcwd(), 'shared'))

from podcast_transcriber_shared.database import (
    get_session_maker, 
    Feed as FeedModel, 
    Episode as EpisodeModel, 
    EpisodeStatus,
    init_db
)

# Paths
CONFIG_DIR = Path("shared/config")
SUBSCRIPTIONS_FILE = CONFIG_DIR / "subscriptions.json"
PENDING_EPISODES_FILE = CONFIG_DIR / "pending_episodes.json"

async def migrate():
    logger.info("🚀 Starting Migration: JSON -> PostgreSQL")
    
    # Initialize DB (create tables if they don't exist)
    await init_db()
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        # 1. Migrate Subscriptions -> feeds
        if SUBSCRIPTIONS_FILE.exists():
            logger.info(f"📂 Reading {SUBSCRIPTIONS_FILE}")
            with open(SUBSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
                subscriptions = json.load(f)
            
            for sub in subscriptions:
                feed_id = sub.get('id')
                url = sub.get('url')
                title = sub.get('title', 'Unknown Podcast')
                is_active = sub.get('active', True)
                
                logger.info(f"   - Migrating Feed: {title} ({url})")
                
                try:
                    # Use ID for conflict resolution as it's the Primary Key
                    stmt = insert(FeedModel).values(
                        id=feed_id,
                        url=url,
                        title=title,
                        is_active=is_active
                    ).on_conflict_do_update(
                        index_elements=['id'],
                        set_={'title': title, 'is_active': is_active, 'url': url}
                    )
                    await session.execute(stmt)
                    await session.commit() # Commit each to avoid transaction abort
                except Exception as e:
                    await session.rollback()
                    logger.error(f"❌ Error migrating feed {title}: {e}")
        else:
            logger.warning("⚠️ subscriptions.json not found, skipping feeds migration.")

        # 2. Migrate Pending Episodes -> episodes
        if PENDING_EPISODES_FILE.exists():
            logger.info(f"📂 Reading {PENDING_EPISODES_FILE}")
            with open(PENDING_EPISODES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                episodes = data.get('episodes', [])
            
            for ep in episodes:
                ep_id = ep.get('id')
                ep_title = ep.get('episode_title', 'Unknown')
                ep_url = ep.get('audio_url', '')
                podcast_name = ep.get('feed_title', 'Unknown')
                feed_url = ep.get('feed_url')
                is_selected = ep.get('selected', False)
                
                logger.info(f"   - Migrating Pending Episode: {ep_title}")
                
                # Try to find feed_id if not present
                feed_id = None
                if feed_url:
                    try:
                        feed_result = await session.execute(select(FeedModel.id).where(FeedModel.url == feed_url))
                        feed_id = feed_result.scalar_one_or_none()
                    except Exception as e:
                        logger.warning(f"⚠️ Could not find feed ID for {feed_url}: {e}")
                
                try:
                    stmt = insert(EpisodeModel).values(
                        id=ep_id,
                        url=ep_url,
                        title=ep_title,
                        podcast_name=podcast_name,
                        feed_id=feed_id,
                        status=EpisodeStatus.PENDING,
                        is_selected=is_selected,
                        meta_data={
                            'feed_url': feed_url,
                            'audio_url': ep_url,
                            'published_date': ep.get('published_date'),
                            'selected': is_selected
                        }
                    ).on_conflict_do_update(
                        index_elements=['id'],
                        set_={'is_selected': is_selected, 'status': EpisodeStatus.PENDING, 'url': ep_url}
                    )
                    await session.execute(stmt)
                    await session.commit()
                except Exception as e:
                    await session.rollback()
                    logger.error(f"❌ Error migrating episode {ep_title}: {e}")
        else:
            logger.warning("⚠️ pending_episodes.json not found, skipping episodes migration.")
        logger.info("✅ Migration committed to database.")

    # 3. Rename files
    if SUBSCRIPTIONS_FILE.exists():
        new_path = SUBSCRIPTIONS_FILE.with_suffix('.json.old')
        SUBSCRIPTIONS_FILE.rename(new_path)
        logger.info(f"📦 Renamed {SUBSCRIPTIONS_FILE.name} -> {new_path.name}")
        
    if PENDING_EPISODES_FILE.exists():
        new_path = PENDING_EPISODES_FILE.with_suffix('.json.old')
        PENDING_EPISODES_FILE.rename(new_path)
        logger.info(f"📦 Renamed {PENDING_EPISODES_FILE.name} -> {new_path.name}")

    logger.info("✨ Migration Complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
