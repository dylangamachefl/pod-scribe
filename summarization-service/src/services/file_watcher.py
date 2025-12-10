"""
File Watcher Service for Summarization
Monitors transcription folder for new files and triggers automatic summarization.
"""
import time
from pathlib import Path
from typing import Set
from watchdog.observers.polling import PollingObserver
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
        print("📋 File handler initialized")
    
    def on_created(self, event):
        """Called when a new file is created."""
        if event.is_directory:
            print(f"📁 Directory created: {event.src_path}")
            return
            
        file_path = Path(event.src_path)
        print(f"🔔 File created event: {file_path.name} (in {file_path.parent.name}/)")
        
        # Only process .txt files
        if file_path.suffix.lower() == '.txt':
            print(f"✅ Queuing transcript for processing: {file_path.name}")
            self.pending_files[str(file_path)] = time.time()
        else:
            print(f"⏭️  Skipping non-txt file: {file_path.name}")
    
    def on_modified(self, event):
        """Called when a file is modified."""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        
        # Only process .txt files that aren't already pending or processed
        if file_path.suffix.lower() == '.txt':
            file_str = str(file_path)
            if file_str not in self.pending_files and file_str not in self.processed_files:
                # Check if file has content (avoid partial writes)
                try:
                    if file_path.exists() and file_path.stat().st_size > 1000:  # At least 1KB
                        print(f"🔔 File modified event (new content): {file_path.name} (in {file_path.parent.name}/)")
                        print(f"✅ Queuing transcript for processing: {file_path.name}")
                        self.pending_files[file_str] = time.time()
                except Exception as e:
                    print(f"⚠️  Error checking file {file_path.name}: {e}")
    
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
                print(f"\n⏰ Debounce period elapsed, processing: {Path(file_path).name}")
                self._summarize_transcript(Path(file_path))
                self.processed_files.add(file_path)
            else:
                print(f"⏭️  Already processed, skipping: {Path(file_path).name}")
    
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
            metadata = extract_metadata_from_transcript(content, file_path.name)
            
            print(f"📄 Episode: {metadata['episode_title']}")
            print(f"🎙️  Podcast: {metadata['podcast_name']}")
            
            # Generate summary with Gemini (returns StructuredSummary Pydantic model)
            print(f"🤖 Generating summary with Gemini...")
            gemini_service = get_gemini_service()
            summary_result = gemini_service.summarize_transcript(
                content,
                metadata["episode_title"],
                metadata["podcast_name"]
            )
            
            # Save summary - use Pydantic model's dict() method for complete serialization
            summary_file = SUMMARY_OUTPUT_PATH / f"{file_path.stem}_summary.json"
            
            # Combine metadata with the complete structured summary
            complete_summary_data = {
                "episode_title": metadata["episode_title"],
                "podcast_name": metadata["podcast_name"],
                "processed_date": metadata.get("processed_date"),
                "created_at": metadata.get("processed_date"),  # Map to created_at for frontend
                # Unpack all structured summary fields from Pydantic model
                **summary_result.model_dump(),
                # Add metadata fields
                "speakers": metadata.get("speakers", []),
                "duration": metadata.get("duration"),
                "audio_url": metadata.get("audio_url"),
                "source_file": str(file_path)
            }
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(complete_summary_data, f, indent=2)
            
            print(f"✅ Summary saved: {summary_file.name}")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"❌ Error summarizing {file_path.name}: {e}")
            import traceback
            traceback.print_exc()



def scan_existing_transcripts(watch_path: Path, event_handler: TranscriptFileHandler):
    """
    Scan for existing transcript files that don't have summaries.
    Process them on startup to catch any missed files.
    """
    print(f"\n🔍 Scanning for existing transcripts without summaries...")
    
    transcripts_found = 0
    transcripts_to_process = []
    
    # Walk through directory tree
    for txt_file in watch_path.rglob("*.txt"):
        transcripts_found += 1
        
        # Check if summary already exists
        summary_file = SUMMARY_OUTPUT_PATH / f"{txt_file.stem}_summary.json"
        
        if not summary_file.exists():
            transcripts_to_process.append(txt_file)
            print(f"   📝 Found unprocessed: {txt_file.name} (in {txt_file.parent.name}/)")
        else:
            # Mark as already processed
            event_handler.processed_files.add(str(txt_file))
    
    print(f"\n📊 Scan Results:")
    print(f"   Total transcripts: {transcripts_found}")
    print(f"   Already summarized: {transcripts_found - len(transcripts_to_process)}")
    print(f"   Needs processing: {len(transcripts_to_process)}")
    
    # Process any unprocessed transcripts
    if transcripts_to_process:
        print(f"\n🚀 Processing {len(transcripts_to_process)} transcript(s)...\n")
        for txt_file in transcripts_to_process:
            event_handler._summarize_transcript(txt_file)
            event_handler.processed_files.add(str(txt_file))
    else:
        print(f"\n✅ All transcripts are up to date!\n")


def start_file_watcher():
    """Start watching the transcription folder for new files."""
    watch_path = TRANSCRIPTION_WATCH_PATH
    
    if not watch_path.exists():
        print(f"⚠️  Watch path does not exist: {watch_path}")
        print(f"   Creating directory...")
        watch_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"👁️  File Watcher Configuration")
    print(f"{'='*60}")
    print(f"   Watch path: {watch_path}")
    print(f"   Recursive: Yes")
    print(f"   Monitored extensions: .txt")
    print(f"   Debounce: 2 seconds")
    print(f"   Observer type: PollingObserver (Docker-compatible)")
    print(f"   Poll interval: 1 second")
    print(f"{'='*60}\n")
    
    event_handler = TranscriptFileHandler()
    
    # Scan for existing transcripts on startup
    scan_existing_transcripts(watch_path, event_handler)
    
    # Start watching for new files using PollingObserver (works with Docker bind mounts)
    print(f"👁️  Starting real-time file monitoring...")
    observer = PollingObserver(timeout=1.0)  # Poll every 1 second
    observer.schedule(event_handler, str(watch_path), recursive=True)
    observer.start()
    print(f"✅ File watcher is now active and monitoring for changes\n")
    
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
