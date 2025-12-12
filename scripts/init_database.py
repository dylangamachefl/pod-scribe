"""
Database Initialization Script
Automatically creates database tables on first run.

Usage:
    python scripts/init_database.py
"""
import asyncio
import os
import sys
from pathlib import Path

# Add shared to path
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from database import init_db


async def main():
    """Initialize database tables."""
    print("\n" + "="*60)
    print("  PostgreSQL Database Initialization")
    print("="*60)
    
    # Check DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("\n❌ ERROR: DATABASE_URL environment variable not set")
        print("   Please ensure .env file contains DATABASE_URL")
        sys.exit(1)
    
    print(f"\n📊 Database URL: {database_url.split('@')[1] if '@' in database_url else 'unknown'}")
    print("\n🔄 Creating tables...")
    
    try:
        await init_db()
        print("\n" + "="*60)
        print("✅ Database initialization complete!")
        print("="*60)
        print("\nTables created:")
        print("  - episodes  (id, url, title, podcast_name, status, transcript_text, ...)")
        print("  - summaries (id, episode_id, content, created_at)")
        print("\n")
    except Exception as e:
        print(f"\n❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
