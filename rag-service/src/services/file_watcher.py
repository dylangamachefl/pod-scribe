"""
File Watcher Service
Monitors transcription folder for new files and triggers automatic ingestion.
"""
import time
from pathlib import Path
from typing import Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
import json

from config import TRANSCRIPTION_WATCH_PATH, SUMMARY_OUTPUT_PATH
from utils.chunking import (
    extract_metadata_from_transcript,
    get_transcript_body,
    chunk_by_speaker_turns
)
from services.embeddings import get_embedding_service
from services.qdrant_client import get_qdrant_service
from services.gemini_client import get_gemini_service


class TranscriptFileHandler(FileSystemEventHandler):
    """Handler for new transcript files."""
    
    def __init__(self):
        self.processed_files: Set[str] = set()
        self.debounce_seconds = 2  # Wait 2s before processing to avoid rapid triggers
        self.pending_files = {}
    
    def on_created(self, event):
        """Called when a new file is created."""
        if isinstance(event, FileCreatedEvent):
            file_path = Path(event.src_path)
            
            # Only process .txt files
            if file_path.suffix.lower() == '.txt':
                print(f"\n🔔 Detected new transcript: {file_path.name}")
                self.pending_files[str(file_path)] = time.time()
    
    def process_pending_files(self):
        """Process files that have been pending for debounce period."""
        current_time = time.time()
        files_to_process = []
        
        for file_path, timestamp in list(self.pending_files.items()):
            if current_time - timestamp >= self.debounce_seconds:
                files_to_process.append(file_path)
                del self.pending_files[file_path]
        
        for file_path in files_to_process:
            if file_path not in self.processed_files:
                self._ingest_transcript(Path(file_path))
                self.processed_files.add(file_path)
    
    def _ingest_transcript(self, file_path: Path):
        """Ingest a transcript file into the RAG system."""
        try:
            print(f"\n{'='*60}")
            print(f"📥 Ingesting: {file_path.name}")
            print(f"{'='*60}")
            
            # Read transcript
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract metadata
            metadata = extract_metadata_from_transcript(content)
            metadata["source_file"] = str(file_path)
            
            print(f"📄 Episode: {metadata['episode_title']}")
            print(f"🎙️  Podcast: {metadata['podcast_name']}")
            
            # Extract transcript body
            transcript_lines = get_transcript_body(content)
            
            # Chunk by speaker turns
            print("✂️  Chunking transcript...")
            chunks = chunk_by_speaker_turns(transcript_lines)
            print(f"   Created {len(chunks)} chunks")
            
            # Generate embeddings
            print("🧠 Generating embeddings...")
            embedding_service = get_embedding_service()
            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings = embedding_service.embed_batch(chunk_texts)
            
            # Store in Qdrant
            print("💾 Storing in vector database...")
            qdrant_service = get_qdrant_service()
            num_inserted = qdrant_service.insert_chunks(chunks, embeddings, metadata)
            print(f"✅ Inserted {num_inserted} vectors")
            
            # Generate summary with Gemini
            print("📝 Generating summary with Gemini...")
            gemini_service = get_gemini_service()
            summary_result = gemini_service.summarize_transcript(
                content,
                metadata["episode_title"],
                metadata["podcast_name"]
            )
            
            # Save summary
            summary_file = SUMMARY_OUTPUT_PATH / f"{file_path.stem}_summary.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "episode_title": metadata["episode_title"],
                    "podcast_name": metadata["podcast_name"],
                    "processed_date": metadata.get("processed_date"),
                    "summary": summary_result.get("summary", ""),
                    "key_topics": summary_result.get("key_topics", []),
                    "insights": summary_result.get("insights", []),
                    "quotes": summary_result.get("quotes", []),
                    "num_chunks": len(chunks),
                    "source_file": str(file_path)
                }, f, indent=2)
            
            print(f"📄 Summary saved: {summary_file.name}")
            print(f"{'='*60}\n")
            print(f"✅ Ingestion complete for: {metadata['episode_title']}\n")
            
        except Exception as e:
            print(f"❌ Error ingesting {file_path.name}: {e}")
            import traceback
            traceback.print_exc()


def start_file_watcher():
    """Start watching the transcription folder for new files."""
    watch_path = TRANSCRIPTION_WATCH_PATH
    
    if not watch_path.exists():
        print(f"⚠️  Watch path does not exist: {watch_path}")
        print(f"   Creating directory...")
        watch_path.mkdir(parents=True, exist_ok=True)
    
    print(f"👁️  Watching for new transcripts in: {watch_path}")
    print(f"   File watcher started successfully")
    
    event_handler = TranscriptFileHandler()
    observer = Observer()
    observer.schedule(event_handler, str(watch_path), recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
            # Process any pending files
            event_handler.process_pending_files()
    except KeyboardInterrupt:
        print("\n🛑 Stopping file watcher...")
        observer.stop()
    
    observer.join()


if __name__ == "__main__":
    # For testing
    start_file_watcher()
