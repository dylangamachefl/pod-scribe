"""
Backfill RAG Service - Ingest All Existing Transcripts

This script ingests all existing transcripts that were created before
the automatic RAG ingestion feature was implemented.
"""
import os
import requests
from pathlib import Path
import time

# Configuration
RAG_URL = "http://localhost:8000/ingest"
OUTPUT_DIR = Path("shared/output")

def ingest_file(transcript_path: Path):
    """Ingest a single transcript into RAG service."""
    # Convert Windows path to Docker path format
    docker_path = str(transcript_path).replace('\\', '/')
    
    # Convert to /app/shared/output/... format
    parts = docker_path.split('shared')
    if len(parts) > 1:
        docker_path = '/app/shared' + parts[1]
    
    payload = {"file_path": docker_path}
    
    try:
        response = requests.post(RAG_URL, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            chunks = result.get('chunks_created', 0)
            episode = result.get('episode_title', 'Unknown')
            print(f"✅ {transcript_path.name}")
            print(f"   Episode: {episode}")
            print(f"   Chunks: {chunks}\n")
            return True
        else:
            print(f"❌ {transcript_path.name}")
            print(f"   Error: HTTP {response.status_code}")
            print(f"   {response.text}\n")
            return False
            
    except Exception as e:
        print(f"❌ {transcript_path.name}")
        print(f"   Error: {str(e)}\n")
        return False


def main():
    """Main backfill process."""
    print("="*60)
    print("RAG Service Backfill - Ingesting Existing Transcripts")
    print("="*60)
    print()
    
    # Check if RAG service is running
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code != 200:
            print("❌ RAG service is not healthy!")
            print("   Please ensure the RAG service is running.")
            return
    except:
        print("❌ Cannot connect to RAG service at http://localhost:8000")
        print("   Please ensure Docker containers are running:")
        print("   docker-compose up -d")
        return
    
    print("✅ RAG service is running\n")
    
    # Find all transcript files
    transcript_files = []
    for podcast_dir in OUTPUT_DIR.iterdir():
        if podcast_dir.is_dir():
            for transcript_file in podcast_dir.glob("*.txt"):
                transcript_files.append(transcript_file)
    
    if not transcript_files:
        print("ℹ️  No transcript files found in shared/output/")
        return
    
    print(f"📋 Found {len(transcript_files)} transcript file(s)\n")
    
    # Process each file
    success_count = 0
    fail_count = 0
    
    for i, transcript_file in enumerate(transcript_files, 1):
        print(f"[{i}/{len(transcript_files)}] Processing...")
        
        if ingest_file(transcript_file):
            success_count += 1
        else:
            fail_count += 1
        
        # Small delay to avoid overwhelming the service
        if i < len(transcript_files):
            time.sleep(1)
    
    # Summary
    print("="*60)
    print("Backfill Complete!")
    print(f"✅ Success: {success_count}")
    print(f"❌ Failed: {fail_count}")
    print("="*60)


if __name__ == "__main__":
    main()
