"""
Transcription Service Configuration
Centralized configuration management with environment variables and validation.
"""
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class TranscriptionConfig:
    """Centralized configuration for transcription service."""
    
    # Environment
    huggingface_token: str
    device: str = "cuda"
    compute_type: str = "int8"
    batch_size: int = 4
    whisper_model: str = "large-v2"
    
    # Paths (set in __post_init__)
    root_dir: Path = None
    config_dir: Path = None
    output_dir: Path = None
    temp_dir: Path = None
    subscriptions_file: Path = None
    history_file: Path = None
    
    def __post_init__(self):
        """Initialize derived paths after dataclass construction."""
        if self.root_dir is None:
            # Navigate from: transcription-service/src/config.py -> transcription-service/ -> root/
            self.root_dir = Path(__file__).parent.parent.parent
        
        # Set shared directories
        if self.config_dir is None:
            self.config_dir = self.root_dir / "shared" / "config"
        
        if self.output_dir is None:
            self.output_dir = self.root_dir / "shared" / "output"
        
        if self.temp_dir is None:
            # Keep temp in transcription-service/
            self.temp_dir = Path(__file__).parent.parent / "temp"
        
        # Config files
        self.subscriptions_file = self.config_dir / "subscriptions.json"
        self.history_file = self.config_dir / "history.json"
        
        # Create directories
        for dir_path in [self.config_dir, self.output_dir, self.temp_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def from_env(cls):
        """Load configuration from environment variables."""
        # Load .env file from project root
        root = Path(__file__).parent.parent.parent
        env_file = root / ".env"
        load_dotenv(env_file)
        
        token = os.getenv("HUGGINGFACE_TOKEN")
        if not token:
            print("❌ ERROR: HUGGINGFACE_TOKEN not found in .env file")
            print("   Please add your Hugging Face token to .env:")
            print("   HUGGINGFACE_TOKEN=hf_your_token_here")
            sys.exit(1)
        
        return cls(
            huggingface_token=token,
            device=os.getenv("DEVICE", "cuda"),
            compute_type=os.getenv("COMPUTE_TYPE", "int8"),
            batch_size=int(os.getenv("BATCH_SIZE", "4")),
            whisper_model=os.getenv("WHISPER_MODEL", "large-v2")
        )


# Global config instance (lazy loaded)
_config_instance = None


def get_config() -> TranscriptionConfig:
    """Get the global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = TranscriptionConfig.from_env()
    return _config_instance
