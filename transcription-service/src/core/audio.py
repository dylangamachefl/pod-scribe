"""
Audio Processing Module
Functions for downloading and transcribing audio files.
Includes TranscriptionWorker class for persistent model loading.
"""
import gc
import socket
import ipaddress
from urllib.parse import urlparse
from pathlib import Path
from typing import Optional, Dict

import requests
import torch
import whisperx
import yt_dlp

from managers.status_monitor import update_progress


def validate_url(url: str) -> bool:
    """
    Validate URL to prevent SSRF (Server-Side Request Forgery).
    Blocks requests to localhost, private IPs, and cloud metadata services.

    Args:
        url: URL to validate

    Returns:
        True if URL is safe, False otherwise
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            return False

        # Resolve hostname to IP
        try:
            ip_str = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_str)
        except socket.gaierror:
            print(f"❌ DNS resolution failed for {hostname}")
            return False

        # Check for private/loopback/link-local addresses
        if (ip.is_private or
            ip.is_loopback or
            ip.is_link_local or
            ip.is_reserved or
            str(ip).startswith("169.254")): # explicit check for cloud metadata

            print(f"🛑 Security Alert: Blocked request to restricted IP {ip} ({hostname})")
            return False

        return True

    except Exception as e:
        print(f"⚠️  URL validation error: {e}")
        return False


def download_youtube_audio(url: str, output_path: Path) -> bool:
    """Download audio from YouTube video."""
    if not validate_url(url):
        return False

    try:
        print(f"⬇️  Downloading from YouTube: {url}")
        update_progress("downloading", 0.0)

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
    """Download audio file from URL."""
    if not validate_url(url):
        return False

    if "youtube.com" in url or "youtu.be" in url:
        return download_youtube_audio(url, output_path)

    try:
        print(f"⬇️  Downloading: {url}")
        update_progress("downloading", 0.0)

        # Stream download with timeout
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
    """
    
    def __init__(
        self, 
        whisper_model: str, 
        device: str,
        compute_type: str,
        batch_size: int
    ) -> None:
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
        """Transcribe audio using pre-loaded model."""
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
            torch.cuda.empty_cache()
            
            print("✅ Transcription complete")
            update_progress("transcribing", 1.0)
            return result
            
        except FileNotFoundError:
            raise
        except torch.cuda.OutOfMemoryError as e:
            print(f"❌ GPU out of memory during transcription: {e}")
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
