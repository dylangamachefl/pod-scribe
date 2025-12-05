"""
Audio Processing Module
Functions for downloading and transcribing audio files.
"""
import gc
from pathlib import Path
from typing import Optional, Dict

import requests
import torch
import whisperx
import yt_dlp

from managers.status_monitor import update_progress


def download_youtube_audio(url: str, output_path: Path) -> bool:
    """Download audio from YouTube video.

    Args:
        url: YouTube video URL
        output_path: Path where audio should be saved

    Returns:
        True if download successful, False otherwise
    """
    try:
        print(f"⬇️  Downloading from YouTube: {url}")
        update_progress("downloading", 0.0)

        # Configure yt-dlp to download best audio and convert to mp3
        # Note: output_path usually has an extension (e.g. .mp3)
        # We need to strip it because yt-dlp adds it
        out_base = str(output_path.with_suffix(''))

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': out_base,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Ensure the file exists with the expected extension (mp3)
        # If output_path was .mp3, it should be there.
        # If output_path was something else, we might need to rename or check.
        # But we forced preferredcodec mp3, so yt-dlp produced .mp3.

        expected_file = Path(out_base + '.mp3')
        if expected_file.exists():
            if expected_file != output_path:
                if output_path.exists():
                    output_path.unlink()
                expected_file.rename(output_path)

            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"✅ Downloaded {file_size_mb:.1f} MB")
            update_progress("downloading", 1.0)
            return True
        else:
            print(f"❌ Download failed: File not found at {expected_file}")
            return False

    except Exception as e:
        print(f"❌ YouTube download failed: {e}")
        return False


def download_audio(url: str, output_path: Path) -> bool:
    """Download audio file from URL.
    
    Args:
        url: URL of the audio file
        output_path: Path where audio should be saved
        
    Returns:
        True if download successful, False otherwise
    """
    if "youtube.com" in url or "youtu.be" in url:
        return download_youtube_audio(url, output_path)

    try:
        print(f"⬇️  Downloading: {url}")
        update_progress("downloading", 0.0)
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"✅ Downloaded {file_size_mb:.1f} MB")
        update_progress("downloading", 1.0)
        return True
    
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False


def transcribe_audio(audio_path: Path, whisper_model: str, device: str, 
                     compute_type: str, batch_size: int) -> Optional[Dict]:
    """Transcribe audio using WhisperX with int8 quantization.
    
    Args:
        audio_path: Path to audio file
        whisper_model: WhisperX model name (e.g., "large-v2")
        device: Device to use ("cuda" or "cpu")
        compute_type: Compute type for quantization (e.g., "int8")
        batch_size: Batch size for transcription
        
    Returns:
        Aligned transcript segments dict, or None if failed
    """
    try:
        print(f"🎤 Loading Whisper model ({whisper_model})...")
        update_progress("transcribing", 0.1)
        model = whisperx.load_model(
            whisper_model,
            device,
            compute_type=compute_type,
            language="en"
        )
        
        print(f"🔄 Transcribing: {audio_path.name}")
        update_progress("transcribing", 0.3)
        audio = whisperx.load_audio(str(audio_path))
        result = model.transcribe(audio, batch_size=batch_size)
        
        # Align timestamps
        print("⏱️  Aligning timestamps...")
        update_progress("transcribing", 0.7)
        model_a, metadata = whisperx.load_align_model(
            language_code=result["language"],
            device=device
        )
        result = whisperx.align(
            result["segments"],
            model_a,
            metadata,
            audio,
            device,
            return_char_alignments=False
        )
        
        # Clean up alignment model
        del model_a
        gc.collect()
        
        # Clean up transcription model
        del model
        gc.collect()
        torch.cuda.empty_cache()
        
        print("✅ Transcription complete")
        update_progress("transcribing", 1.0)
        return result
    
    except Exception as e:
        print(f"❌ Transcription failed: {e}")
        return None
