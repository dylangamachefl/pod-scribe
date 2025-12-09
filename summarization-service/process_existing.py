"""
One-time script to process all existing transcripts and generate summaries.
Run this ONCE to catch up on all your existing transcripts.
"""
import sys
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import TRANSCRIPTION_WATCH_PATH, SUMMARY_OUTPUT_PATH
from utils.transcript_parser import extract_metadata_from_transcript
from services.gemini_service import get_gemini_service

def process_existing_transcripts():
    """Process all transcripts that don't have summaries yet."""
    
    print("\n" + "="*60)
    print("📝 Processing Existing Transcripts")
    print("="*60)
    
    # Get all transcript files
    transcript_files = list(TRANSCRIPTION_WATCH_PATH.rglob("*.txt"))
    
    print(f"\n📂 Found {len(transcript_files)} transcript files")
    
    # Get existing summaries
    existing_summaries = {f.stem.replace("_summary", "") for f in SUMMARY_OUTPUT_PATH.glob("*_summary.json")}
    
    print(f"✅ Already have {len(existing_summaries)} summaries")
    
    # Process each transcript
    gemini_service = get_gemini_service()
    processed = 0
    skipped = 0
    errors = 0
    
    for transcript_file in transcript_files:
        # Check if summary already exists
        if transcript_file.stem in existing_summaries:
            print(f"⏭️  Skipping (already summarized): {transcript_file.name}")
            skipped += 1
            continue
        
        try:
            print(f"\n{'='*60}")
            print(f"📝 Processing: {transcript_file.name}")
            print(f"{'='*60}")
            
            # Read transcript
            with open(transcript_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract metadata
            metadata = extract_metadata_from_transcript(content)
            
            print(f"📄 Episode: {metadata['episode_title']}")
            print(f"🎙️  Podcast: {metadata['podcast_name']}")
            
            # Generate summary
            print(f"🤖 Generating summary with Gemini...")
            summary_result = gemini_service.summarize_transcript(
                content,
                metadata["episode_title"],
                metadata["podcast_name"]
            )
            
            # Save summary
            summary_file = SUMMARY_OUTPUT_PATH / f"{transcript_file.stem}_summary.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "episode_title": metadata["episode_title"],
                    "podcast_name": metadata["podcast_name"],
                    "processed_date": metadata.get("processed_date"),
                    "summary": summary_result.get("summary", ""),
                    "key_topics": summary_result.get("key_topics", []),
                    "insights": summary_result.get("insights", []),
                    "quotes": summary_result.get("quotes", []),
                    "speakers": metadata.get("speakers", []),
                    "duration": metadata.get("duration"),
                    "audio_url": metadata.get("audio_url"),
                    "source_file": str(transcript_file),
                    "processing_time_ms": summary_result.get("processing_time_ms", 0)
                }, f, indent=2)
            
            print(f"✅ Summary saved: {summary_file.name}")
            processed += 1
            
        except Exception as e:
            print(f"❌ Error processing {transcript_file.name}: {e}")
            import traceback
            traceback.print_exc()
            errors += 1
    
    print(f"\n{'='*60}")
    print(f"✅ Processing Complete!")
    print(f"   Processed: {processed}")
    print(f"   Skipped: {skipped}")
    print(f"   Errors: {errors}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    process_existing_transcripts()
