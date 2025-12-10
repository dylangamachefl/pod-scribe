"""
One-time script to process all existing transcripts and generate summaries.
Run this ONCE to catch up on all your existing transcripts.
"""
import sys
from pathlib import Path
import json
import argparse
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import TRANSCRIPTION_WATCH_PATH, SUMMARY_OUTPUT_PATH
from utils.transcript_parser import extract_metadata_from_transcript
from services.gemini_service import get_gemini_service

def process_existing_transcripts(delay: float = 2.0, skip_existing: bool = True):
    """Process all transcripts that don't have summaries yet.
    
    Args:
        delay: Delay in seconds between processing each transcript
        skip_existing: Whether to skip files that already have summaries
    """
    
    print("\n" + "="*60)
    print("📝 Processing Existing Transcripts")
    print("="*60)
    print(f"⏱️  Delay between transcripts: {delay}s")
    print(f"⏭️  Skip existing: {skip_existing}")
    
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
    
    for idx, transcript_file in enumerate(transcript_files):
        # Check if summary already exists
        if skip_existing and transcript_file.stem in existing_summaries:
            print(f"⏭️  Skipping (already summarized): {transcript_file.name}")
            skipped += 1
            continue
        
        try:
            print(f"\n{'='*60}")
            print(f"📝 Processing [{idx + 1}/{len(transcript_files)}]: {transcript_file.name}")
            print(f"{'='*60}")
            
            # Read transcript
            with open(transcript_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract metadata
            metadata = extract_metadata_from_transcript(content, transcript_file.name)
            
            print(f"📄 Episode: {metadata['episode_title']}")
            print(f"🎙️  Podcast: {metadata['podcast_name']}")
            
            # Generate summary (returns StructuredSummary Pydantic model)
            print(f"🤖 Generating summary with Gemini...")
            summary_result = gemini_service.summarize_transcript(
                content,
                metadata["episode_title"],
                metadata["podcast_name"]
            )
            
            # Check if summary generation failed
            if "Error" in summary_result.summary:
                print(f"⚠️  Summary generation had errors")
                errors += 1
            
            # Save summary with complete structured data
            summary_file = SUMMARY_OUTPUT_PATH / f"{transcript_file.stem}_summary.json"
            
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
                "source_file": str(transcript_file)
            }
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(complete_summary_data, f, indent=2)
            
            print(f"✅ Summary saved: {summary_file.name}")
            processed += 1
            
            # Add delay between API calls to avoid quota errors
            if delay > 0 and idx < len(transcript_files) - 1:
                print(f"⏱️  Waiting {delay}s before next transcript...")
                time.sleep(delay)
            
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
    parser = argparse.ArgumentParser(description="Process existing transcripts and generate summaries")
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay in seconds between processing each transcript (default: 2.0)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-processing of transcripts that already have summaries"
    )
    
    args = parser.parse_args()
    process_existing_transcripts(
        delay=args.delay,
        skip_existing=not args.force
    )
