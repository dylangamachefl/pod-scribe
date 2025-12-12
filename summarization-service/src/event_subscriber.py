"""
Summarization Event Subscriber
Listens for EpisodeTranscribed events and generates summaries.
"""
import asyncio
from pathlib import Path

from podcast_transcriber_shared.events import get_event_bus, EpisodeTranscribed, EpisodeSummarized
from services.gemini_service import get_gemini_service
from utils.transcript_parser import extract_metadata_from_transcript
from config import SUMMARY_OUTPUT_PATH
import json
import uuid



async def process_transcription_event(event_data: dict):
    """
    Process an EpisodeTranscribed event asynchronously.
    
    Called when a new transcript is available.
    Generates a structured summary using Gemini.
    
    Args:
        event_data: Event data dictionary from Redis
    """
    try:
        # Parse event
        event = EpisodeTranscribed(**event_data)
        
        print(f"\n{'='*60}")
        print(f"📥 Received EpisodeTranscribed event")
        print(f"   Event ID: {event.event_id}")
        print(f"   Episode: {event.episode_title}")
        print(f"   Podcast: {event.podcast_name}")
        print(f"{'='*60}")
        
        # Use Docker path (we're running in container)
        file_path = Path(event.docker_transcript_path)
        
        if not file_path.exists():
            print(f"❌ Transcript file not found: {file_path}")
            return
        
        # Check if summary already exists
        summary_file = SUMMARY_OUTPUT_PATH / f"{file_path.stem}_summary.json"
        if summary_file.exists():
            print(f"⏭️  Summary already exists, skipping: {summary_file.name}")
            return
        
        # Read transcript (blocking I/O - run in executor)
        loop = asyncio.get_running_loop()
        
        def read_transcript():
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        content = await loop.run_in_executor(None, read_transcript)
        
        # Extract metadata (potentially heavy parsing - run in executor)
        metadata = await loop.run_in_executor(
            None, extract_metadata_from_transcript, content, file_path.name
        )
        
        print(f"📄 Episode: {metadata['episode_title']}")
        print(f"🎙️  Podcast: {metadata['podcast_name']}")
        
        # Generate summary with Gemini (heavy API call - run in executor)
        print(f"🤖 Generating summary with Gemini...")
        gemini_service = get_gemini_service()
        
        summary_result = await loop.run_in_executor(
            None,
            gemini_service.summarize_transcript,
            content,
            metadata["episode_title"],
            metadata["podcast_name"]
        )
        
        # Save summary (blocking I/O - run in executor)
        complete_summary_data = {
            "episode_title": metadata["episode_title"],
            "podcast_name": metadata["podcast_name"],
            "processed_date": metadata.get("processed_date"),
            "created_at": metadata.get("processed_date"),
            # Unpack all structured summary fields
            **summary_result.model_dump(),
            # Add metadata fields
            "speakers": metadata.get("speakers", []),
            "duration": metadata.get("duration"),
            "audio_url": event.audio_url,
            "source_file": str(file_path)
        }
        
        def save_summary():
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(complete_summary_data, f, indent=2)
        
        await loop.run_in_executor(None, save_summary)
        
        print(f"✅ Summary saved: {summary_file.name}")
        
        # Publish EpisodeSummarized event
        try:
            event_bus = get_event_bus()
            summarized_event = EpisodeSummarized(
                event_id=f"evt_{uuid.uuid4().hex[:12]}",
                service="summarization",
                episode_id=event.episode_id,
                episode_title=event.episode_title,
                podcast_name=event.podcast_name,
                summary_path=str(summary_file),
                summary_data=complete_summary_data
            )
            event_bus.publish(event_bus.CHANNEL_SUMMARIZED, summarized_event)
            print(f"📤 Published EpisodeSummarized event")
        except Exception as e:
            print(f"⚠️  Failed to publish EpisodeSummarized event: {e}")
        
        print(f"{'='*60}")
        print(f"✅ Event processing complete: {event.episode_title}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ Error processing transcription event: {e}")
        import traceback
        traceback.print_exc()


def start_summarization_event_subscriber():
    """Start the summarization event subscriber (blocking)."""
    print("\n" + "="*60)
    print("🚀 Starting Summarization Event Subscriber")
    print("="*60)
    print("   Listening for: EpisodeTranscribed events")
    print("   Channel: episodes:transcribed")
    print("="*60 + "\n")
    
    # Get event bus and subscribe
    event_bus = get_event_bus()
    
    # This is a blocking call
    event_bus.subscribe(
        channel=event_bus.CHANNEL_TRANSCRIBED,
        callback=process_transcription_event
    )


if __name__ == "__main__":
    # Initialize services before subscribing
    print("📦 Initializing Summarization services...")
    get_gemini_service()
    print("✅ Services initialized\n")
    
    # Start subscriber (blocking)
    start_summarization_event_subscriber()
