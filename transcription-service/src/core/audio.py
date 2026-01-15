"""
Audio Processing Module
Functions for downloading and transcribing audio files.
Includes TranscriptionWorker class for persistent model loading.
"""
import asyncio
import gc
import os
import socket
import ipaddress
from urllib.parse import urlparse
from pathlib import Path
from typing import Optional, Dict

import httpx
import torch
import whisperx
import yt_dlp

# Suppress tqdm progress bars in Docker/Non-interactive logs
os.environ["TQDM_DISABLE"] = "1"

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


class SSRFTransport(httpx.AsyncBaseTransport):
    """
    Custom httpx transport that validates the target IP before connection.
    Hardens against SSRF and DNS Rebinding while preserving SNI for HTTPS.
    """
    def __init__(self, **kwargs):
        self.transport = httpx.AsyncHTTPTransport(**kwargs)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        hostname = url.host

        # 1. Resolve hostname to IP
        try:
            # We use a simple socket check since httpx will do its own connection later,
            # but we want to pre-verify the destination.
            ip_str = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_str)
        except socket.gaierror:
            raise httpx.ConnectError(f"DNS resolution failed for {hostname}")

        # 2. Check for private/loopback/link-local addresses
        if (ip.is_private or
            ip.is_loopback or
            ip.is_link_local or
            ip.is_reserved or
            str(ip).startswith("169.254")):
            print(f"🛑 Security Alert: SSRF attempt blocked to {ip} ({hostname})")
            raise httpx.ConnectError(f"Restricted IP address: {ip}")

        # 3. Allow the request to proceed through the real transport
        return await self.transport.handle_async_request(request)

    async def aclose(self):
        await self.transport.aclose()


async def download_audio(url: str, output_path: Path) -> bool:
    """
    Download audio file from URL using httpx with SSRF protection.
    """
    if "youtube.com" in url or "youtu.be" in url:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, download_youtube_audio, url, output_path)

    try:
        print(f"⬇️  Downloading: {url}")
        update_progress("downloading", 0.0)

        # Use custom transport for SSRF protection
        async with httpx.AsyncClient(transport=SSRFTransport(verify=True), timeout=300) as client:
            async with client.stream("GET", url, follow_redirects=True) as response:
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
        if output_path.exists():
            output_path.unlink()
        return False


class ModelLoadingError(Exception):
    """Raised when models fail to load after retries."""
    pass


class TranscriptionWorker:
    """
    Persistent worker that maintains loaded WhisperX and Alignment models.
    """
    
    def __init__(
        self, 
        whisper_model: str, 
        device: str,
        compute_type: str,
        batch_size: int,
        huggingface_token: str
    ) -> None:
        self.whisper_model = whisper_model
        self.device = device
        self.compute_type = compute_type
        self.batch_size = batch_size
        self.huggingface_token = huggingface_token
        
        # Lazy loading holders
        self.model = None
        self.align_model = None
        self.align_metadata = None
        self.diarize_model = None
        self.models_loaded = False

    def _ensure_models_loaded(self):
        """Lazy load models if not already loaded. Resilience for HF API failures."""
        if self.models_loaded:
            return

        max_retries = 3
        last_exception = None

        for attempt in range(max_retries):
            try:
                if self.model is None:
                    print(f"🎤 Loading Whisper model ({self.whisper_model}) - attempt {attempt+1}/{max_retries}...")
                    self.model = whisperx.load_model(
                        self.whisper_model,
                        self.device,
                        compute_type=self.compute_type,
                        language="en"
                    )
                
                if self.align_model is None:
                    print(f"⏱️  Pre-loading alignment model (en)...")
                    self.align_model, self.align_metadata = whisperx.load_align_model(
                        language_code="en",
                        device=self.device
                    )

                if self.diarize_model is None:
                    print(f"👥 Pre-loading diarization model (Pyannote 3.1)...")
                    from pyannote.audio import Pipeline
                    self.diarize_model = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1",
                        use_auth_token=self.huggingface_token
                    )
                    if self.diarize_model is not None:
                        self.diarize_model.to(torch.device(self.device))
                    else:
                        raise RuntimeError("Failed to load Pyannote diarization model (Pipeline returned None)")
                
                self.models_loaded = True
                print(f"✅ Models loaded successfully and ready for reuse")
                return # Success!
                
            except torch.cuda.OutOfMemoryError as e:
                # OOM is usually not recoverable via retries
                raise torch.cuda.OutOfMemoryError(
                    f"Insufficient GPU memory to load models. "
                    "Try using a smaller model or increase GPU memory."
                ) from e
            except Exception as e:
                print(f"⚠️  Model loading attempt {attempt+1} failed: {e}")
                last_exception = e
                # Clean up partial loads if any
                if attempt < max_retries - 1:
                    time.sleep(2) # Short wait before retry
                else:
                    break
        
        # If we reach here, all retries failed
        raise ModelLoadingError(f"Failed to load Whisper/Pyannote models after {max_retries} attempts: {last_exception}")
    
    def process(self, audio_path: Path) -> Optional[Dict]:
        """Transcribe and align audio using pre-loaded models."""
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Ensure models are loaded before processing
        self._ensure_models_loaded()
        
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
        if self.diarize_model is not None:
            del self.diarize_model
        gc.collect()
        torch.cuda.empty_cache()
        print("🧹 TranscriptionWorker cleaned up")
