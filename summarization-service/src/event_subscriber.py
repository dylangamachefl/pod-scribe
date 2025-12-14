"""
Summarization Event Subscriber
Listens for EpisodeTranscribed events and generates summaries.
"""
import asyncio
from pathlib import Path
import uuid
import json

from podcast_transcriber_shared.events import get_event_bus, EpisodeTranscribed, EpisodeSummarized
from services.gemini_service import get_gemini_service
from utils.transcript_parser import extract_metadata_from_transcript
from config import SUMMARY_OUTPUT_PATH


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
        
        # Fetch transcript from database
        # Database operations are async, so we just await them directly!
        from podcast_transcriber_shared.database import get_episode_by_id, get_summary_by_episode_id, save_summary as db_save_summary
        
        # Check if summary already exists
        existing_summary = await get_summary_by_episode_id(event.episode_id)
        
        if existing_summary:
            print(f"⏭️  Summary already exists, skipping: {event.episode_title}")
            return
        
        # Fetch episode from database
        episode = await get_episode_by_id(event.episode_id, load_transcript=True)
        
        if not episode:
            print(f"❌ Episode not found in database: {event.episode_id}")
            return
        
        if not episode.transcript_text:
            print(f"❌ No transcript text for episode: {event.episode_id}")
            return
        
        content = episode.transcript_text
        metadata = episode.meta_data or {}
        
        print(f"📄 Episode: {metadata.get('episode_title', event.episode_title)}")
        print(f"🎙️  Podcast: {metadata.get('podcast_name', event.podcast_name)}")
        
        # Generate summary with Gemini (heavy API call - run in executor)
        print(f"🤖 Generating summary with Gemini...")
        gemini_service = get_gemini_service()
        
        loop = asyncio.get_running_loop()
        summary_result = await loop.run_in_executor(
            None,
            gemini_service.summarize_transcript,
            content,
            metadata.get("episode_title", event.episode_title),
            metadata.get("podcast_name", event.podcast_name)
        )
        
        # Prepare summary data
        complete_summary_data = {
            "episode_title": metadata.get("episode_title", event.episode_title),
            "podcast_name": metadata.get("podcast_name", event.podcast_name),
            "processed_date": metadata.get("processed_date"),
            "created_at": metadata.get("processed_date"),
            # Unpack all structured summary fields
            **summary_result.model_dump(),
            # Add metadata fields
            "speakers": metadata.get("speakers", []),
            "duration": metadata.get("duration"),
            "audio_url": event.audio_url,
        }
        
        # Save summary to database (async)
        summary = await db_save_summary(event.episode_id, complete_summary_data)
        
        print(f"✅ Summary saved to database for episode: {event.episode_id}")
        
        # Publish EpisodeSummarized event
        try:
            event_bus = get_event_bus()

            # Since we are saving to DB, we don't have a file path.
            # We can use a virtual path or empty string, or update the event schema.
            # For now, we'll use a virtual DB path.
            virtual_summary_path = f"db://summaries/{summary.id}"

            summarized_event = EpisodeSummarized(
                event_id=f"evt_{uuid.uuid4().hex[:12]}",
                service="summarization",
                episode_id=event.episode_id,
                episode_title=event.episode_title,
                podcast_name=event.podcast_name,
                summary_path=virtual_summary_path,
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
