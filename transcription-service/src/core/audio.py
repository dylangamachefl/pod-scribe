"""
Audio Processing Module
Functions for downloading and transcribing audio files.
Includes TranscriptionWorker class for persistent model loading.
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


class TranscriptionWorker:
    """
    Persistent worker that maintains loaded WhisperX model.
    
    This class loads the model once during initialization and reuses it
    for multiple transcription requests, eliminating the 5-10 second
    model loading overhead per request.
    """
    
    def __init__(
        self, 
        whisper_model: str, 
        device: str,
        compute_type: str,
        batch_size: int
    ) -> None:
        """
        Load and persist WhisperX model.
        
        Args:
            whisper_model: WhisperX model name (e.g., "large-v2")
            device: Device to use ("cuda" or "cpu") 
            compute_type: Compute type for quantization (e.g., "int8")
            batch_size: Batch size for transcription
            
        Raises:
            RuntimeError: If model loading fails
            torch.cuda.OutOfMemoryError: If GPU memory insufficient
        """
        self.whisper_model = whisper_model
        self.device = device
        self.compute_type = compute_type
        self.batch_size = batch_size
        self.model = None
        
        try:
            print(f"🎤 Loading Whisper model ({whisper_model}) - one-time initialization...")
            self.model = whisperx.load_model(
                whisper_model,
                device,
                compute_type=compute_type,
                language="en"
            )
            print(f"✅ Model loaded successfully and ready for reuse")
            
        except torch.cuda.OutOfMemoryError as e:
            raise torch.cuda.OutOfMemoryError(
                f"Insufficient GPU memory to load {whisper_model}. "
                f"Try using a smaller model or increase GPU memory."
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to load WhisperX model {whisper_model}: {e}"
            ) from e
    
    def process(self, audio_path: Path) -> Optional[Dict]:
        """
        Transcribe audio using pre-loaded model.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Aligned transcript segments dict, or None if failed
            
        Raises:
            FileNotFoundError: If audio file doesn't exist
            RuntimeError: If transcription fails
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        if self.model is None:
            raise RuntimeError("Model not initialized. Worker may have failed during construction.")
        
        try:
            print(f"🔄 Transcribing: {audio_path.name} (using persistent model)")
            update_progress("transcribing", 0.3)
            
            # Load and transcribe audio
            audio = whisperx.load_audio(str(audio_path))
            result = self.model.transcribe(audio, batch_size=self.batch_size)
            
            # Align timestamps
            print("⏱️  Aligning timestamps...")
            update_progress("transcribing", 0.7)
            
            model_a, metadata = whisperx.load_align_model(
                language_code=result["language"],
                device=self.device
            )
            
            result = whisperx.align(
                result["segments"],
                model_a,
                metadata,
                audio,
                self.device,
                return_char_alignments=False
            )
            
            # Clean up alignment model (but keep main model!)
            del model_a
            del audio
            gc.collect()
            
            print("✅ Transcription complete")
            update_progress("transcribing", 1.0)
            return result
            
        except FileNotFoundError:
            raise
        except torch.cuda.OutOfMemoryError as e:
            print(f"❌ GPU out of memory during transcription: {e}")
            # Try to recover memory
            gc.collect()
            torch.cuda.empty_cache()
            return None
        except RuntimeError as e:
            print(f"❌ Transcription runtime error: {e}")
            return None
        except Exception as e:
            print(f"❌ Transcription failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def __del__(self):
        """Clean up model on worker destruction."""
        if self.model is not None:
            del self.model
            gc.collect()
            torch.cuda.empty_cache()
            print("🧹 TranscriptionWorker cleaned up")


# Legacy function for backward compatibility
# TODO: Deprecated - use TranscriptionWorker class instead
def transcribe_audio(
    audio_path: Path, 
    whisper_model: str, 
    device: str, 
    compute_type: str, 
    batch_size: int
) -> Optional[Dict]:
    """
    Transcribe audio using WhisperX with int8 quantization.
    
    DEPRECATED: This function creates a new model for each call.
    Use TranscriptionWorker class for better performance.
    
    Args:
        audio_path: Path to audio file
        whisper_model: WhisperX model name (e.g., "large-v2")
        device: Device to use ("cuda" or "cpu")
        compute_type: Compute type for quantization (e.g., "int8")
        batch_size: Batch size for transcription
        
    Returns:
        Aligned transcript segments dict, or None if failed
    """
    print("⚠️  Using deprecated transcribe_audio function (creates new model each time)")
    print("   Consider using TranscriptionWorker class for better performance")
    
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
