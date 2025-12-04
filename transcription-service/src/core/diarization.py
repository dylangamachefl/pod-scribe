"""
Speaker Diarization Module
Functions for identifying speakers in audio using Pyannote.
"""
import gc
from pathlib import Path
from typing import Optional, Dict

import torch
import pandas as pd
import whisperx
import torchaudio

from managers.status_monitor import update_progress


def apply_pytorch_patch():
    """Apply PyTorch 2.6+ compatibility patch for Pyannote models.
    
    CRITICAL: This must be applied BEFORE importing whisperx or any libraries 
    that use torch.load. Pyannote models use OmegaConf configs which aren't in 
    PyTorch's default safe list.
    """
    if hasattr(torch, 'load'):
        _original_load = torch.load
        def _patched_load(*args, **kwargs):
            # ALWAYS force weights_only=False to allow OmegaConf/Pyannote objects
            # This is safe for local, trusted models like Pyannote
            kwargs['weights_only'] = False
            return _original_load(*args, **kwargs)
        torch.load = _patched_load
        print("✅ Applied PyTorch 2.6 compatibility patch for Pyannote models")


def diarize_transcript(audio_path: Path, transcript_result: Dict, 
                       huggingface_token: str, device: str) -> Optional[Dict]:
    """Perform speaker diarization using Pyannote.
    
    Sanitizes audio to WAV first to prevent MP3 duration mismatches.
    
    Args:
        audio_path: Path to audio file
        transcript_result: Transcript result from whisperx
        huggingface_token: Hugging Face authentication token
        device: Device to use ("cuda" or "cpu")
        
    Returns:
        Transcript with speaker labels assigned, or None if failed
    """
    clean_wav_path = None
    try:
        print("👥 Loading diarization model...")
        update_progress("diarizing", 0.1)
        
        # Load pipeline (V3.1)
        from pyannote.audio import Pipeline
        diarize_model = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=huggingface_token
        )
        diarize_model.to(torch.device(device))
        
        print("🔄 Sanitizing audio (Converting to WAV)...")
        # 1. Load the messy MP3 into raw numbers
        audio = whisperx.load_audio(str(audio_path))
        
        # 2. Save as a clean, uncompressed WAV file
        clean_wav_path = audio_path.with_suffix(".clean.wav")
        waveform = torch.from_numpy(audio).unsqueeze(0) 
        torchaudio.save(str(clean_wav_path), waveform, 16000)
        
        print("🔄 Identifying speakers...")
        update_progress("diarizing", 0.4)
        
        # 3. Feed the CLEAN WAV to Pyannote
        diarize_segments = diarize_model(str(clean_wav_path))
        
        # Convert Pyannote Annotation to Pandas DataFrame
        # WhisperX expects a DataFrame with start, end, and speaker columns
        diarize_df = pd.DataFrame(
            [
                {"start": segment.start, "end": segment.end, "speaker": speaker}
                for segment, _, speaker in diarize_segments.itertracks(yield_label=True)
            ]
        )
        
        # Assign speakers to segments
        update_progress("diarizing", 0.8)
        result = whisperx.assign_word_speakers(diarize_df, transcript_result)
        
        # Cleanup memory
        del diarize_model
        gc.collect()
        torch.cuda.empty_cache()
        
        print("✅ Speaker identification complete")
        update_progress("diarizing", 1.0)
        return result
    
    except Exception as e:
        print(f"❌ Diarization failed: {e}")
        # Helpful debugging if it fails again
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        if clean_wav_path and clean_wav_path.exists():
            try:
                clean_wav_path.unlink()
            except:
                pass
