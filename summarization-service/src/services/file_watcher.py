"""
File Watcher Service for Summarization
Monitors transcription folder for new files and triggers automatic summarization.
"""
import time
from pathlib import Path
from typing import Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
import json

from config import TRANSCRIPTION_WATCH_PATH, SUMMARY_OUTPUT_PATH
from utils.transcript_parser import extract_metadata_from_transcript
from services.gemini_service import get_gemini_service


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
                self._summarize_transcript(Path(file_path))
                self.processed_files.add(file_path)
    
    def _summarize_transcript(self, file_path: Path):
        """Summarize a transcript file."""
        try:
            print(f"\n{'='*60}")
            print(f"📝 Summarizing: {file_path.name}")
            print(f"{'='*60}")
            
            # Read transcript
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract metadata
            metadata = extract_metadata_from_transcript(content)
            
            print(f"📄 Episode: {metadata['episode_title']}")
            print(f"🎙️  Podcast: {metadata['podcast_name']}")
            
            # Generate summary with Gemini
            print(f"🤖 Generating summary with Gemini...")
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
                    "source_file": str(file_path),
                    "processing_time_ms": summary_result.get("processing_time_ms", 0)
                }, f, indent=2)
            
            print(f"✅ Summary saved: {summary_file.name}")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"❌ Error summarizing {file_path.name}: {e}")
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
