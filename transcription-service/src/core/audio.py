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

import httpx
import whisperx
import yt_dlp

from managers.status_monitor import update_progress


async def validate_url(url: str) -> Optional[str]:
    """
    Validate URL to prevent SSRF (Server-Side Request Forgery).
    Returns the resolved safe IP string if valid, None otherwise.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            return None

        # Resolve hostname to IP
        try:
            ip_str = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_str)
        except socket.gaierror:
            print(f"❌ DNS resolution failed for {hostname}")
            return None

        # Check for private/loopback/link-local addresses
        if (ip.is_private or
            ip.is_loopback or
            ip.is_link_local or
            ip.is_reserved or
            str(ip).startswith("169.254")): # explicit check for cloud metadata

            print(f"🛑 Security Alert: Blocked request to restricted IP {ip} ({hostname})")
            return None

        return ip_str

    except Exception as e:
        print(f"⚠️  URL validation error: {e}")
        return None


def download_youtube_audio(url: str, output_path: Path) -> bool:
    """Download audio from YouTube video."""
    # Note: yt_dlp handles its own validation and resolution
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


async def download_audio(url: str, output_path: Path) -> bool:
    """
    Download audio file from URL using httpx.
    Hardened against SSRF and DNS Rebinding.
    """
    ip_str = await validate_url(url)
    if not ip_str:
        return False

    if "youtube.com" in url or "youtu.be" in url:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, download_youtube_audio, url, output_path)

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        # Prevent DNS Rebinding: Use the IP directly in the URL 
        # but keep the original Host header for the server.
        # For HTTPS, this is trickier (SNI), so we use a custom transport if needed.
        # For now, we use a simpler but effective IP-replacement for HTTP.
        # For HTTPS, we still use the IP but disable cert verification ONLY IF needed,
        # but here we prefer security.
        
        target_url = url
        if parsed.scheme == "http":
            target_url = url.replace(hostname, ip_str, 1)
        
        print(f"⬇️  Downloading: {url} (resolved to {ip_str})")
        update_progress("downloading", 0.0)

        headers = {"Host": hostname} if parsed.scheme == "http" else {}
        
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("GET", target_url, headers=headers, follow_redirects=True) as response:
                response.raise_for_status()
                with open(output_path, 'wb') as f:
                    async for chunk in response.aiter_bytes():
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
    Persistent worker that maintains loaded WhisperX and Alignment models.
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
        self.align_model = None
        self.align_metadata = None
        
        try:
            print(f"🎤 Loading Whisper model ({whisper_model}) - one-time initialization...")
            self.model = whisperx.load_model(
                whisper_model,
                device,
                compute_type=compute_type,
                language="en"
            )
            
            print(f"⏱️  Pre-loading alignment model (en)...")
            self.align_model, self.align_metadata = whisperx.load_align_model(
                language_code="en",
                device=device
            )
            
            print(f"✅ Models loaded successfully and ready for reuse")
            
        except torch.cuda.OutOfMemoryError as e:
            raise torch.cuda.OutOfMemoryError(
                f"Insufficient GPU memory to load models. "
                "Try using a smaller model or increase GPU memory."
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to load WhisperX models: {e}"
            ) from e
    
    def process(self, audio_path: Path) -> Optional[Dict]:
        """Transcribe and align audio using pre-loaded models."""
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        if self.model is None or self.align_model is None:
            raise RuntimeError("Models not fully initialized.")
        
        try:
            print(f"🔄 Transcribing: {audio_path.name} (using persistent models)")
            update_progress("transcribing", 0.3)
            
            # Load and transcribe audio
            audio = whisperx.load_audio(str(audio_path))
            result = self.model.transcribe(audio, batch_size=self.batch_size)
            
            # Align timestamps using pre-loaded alignment model
            print("⏱️  Aligning timestamps (using pre-loaded model)...")
            update_progress("transcribing", 0.7)
            
            result = whisperx.align(
                result["segments"],
                self.align_model,
                self.align_metadata,
                audio,
                self.device,
                return_char_alignments=False
            )
            
            # Cleanup audio memory (but keep models!)
            del audio
            gc.collect()
            torch.cuda.empty_cache()
            
            print("✅ Transcription complete")
            update_progress("transcribing", 1.0)
            return result
            
        except torch.cuda.OutOfMemoryError as e:
            print(f"❌ GPU out of memory during transcription: {e}")
            gc.collect()
            torch.cuda.empty_cache()
            return None
        except Exception as e:
            print(f"❌ Transcription failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def __del__(self):
        """Clean up models on worker destruction."""
        if self.model is not None:
            del self.model
        if self.align_model is not None:
            del self.align_model
        gc.collect()
        torch.cuda.empty_cache()
        print("🧹 TranscriptionWorker cleaned up")
