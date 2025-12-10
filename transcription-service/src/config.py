"""
Transcription Service Configuration
Centralized configuration management with environment variables and validation.
"""
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
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
    
    # Service URLs (no hardcoding!)
    rag_service_url: str = "http://localhost:8000"
    summarization_service_url: str = "http://localhost:8002"
    
    # Service configuration
    service_timeout: int = 60  # seconds
    service_retry_attempts: int = 3
    service_retry_delay: float = 2.0  # seconds
    
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
    
    def get_relative_path_from_shared(self, absolute_path: Path) -> str:
        """
        Convert absolute path to relative path from shared directory.
        
        Args:
            absolute_path: Absolute path to file
            
        Returns:
            Relative path from shared directory (e.g., "output/podcast/episode.txt")
            
        Raises:
            ValueError: If path is not within shared directory
        """
        try:
            shared_dir = self.root_dir / "shared"
            relative = absolute_path.relative_to(shared_dir)
            # Use forward slashes for consistency (Docker paths)
            return str(relative).replace('\\', '/')
        except ValueError:
            raise ValueError(f"Path {absolute_path} is not within shared directory {shared_dir}")
    
    def get_docker_path(self, absolute_path: Path) -> str:
        """
        Convert host absolute path to Docker container path.
        
        Args:
            absolute_path: Absolute path on host machine
            
        Returns:
            Docker container path (e.g., "/app/shared/output/episode.txt")
        """
        relative = self.get_relative_path_from_shared(absolute_path)
        return f"/app/shared/{relative}"
    
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
            whisper_model=os.getenv("WHISPER_MODEL", "large-v2"),
            # Service URLs from environment
            rag_service_url=os.getenv("RAG_SERVICE_URL", "http://localhost:8000"),
            summarization_service_url=os.getenv("SUMMARIZATION_SERVICE_URL", "http://localhost:8002"),
            # Service configuration
            service_timeout=int(os.getenv("SERVICE_TIMEOUT", "60")),
            service_retry_attempts=int(os.getenv("SERVICE_RETRY_ATTEMPTS", "3")),
            service_retry_delay=float(os.getenv("SERVICE_RETRY_DELAY", "2.0"))
        )


# Global config instance (lazy loaded)
_config_instance = None


def get_config() -> TranscriptionConfig:
    """Get the global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = TranscriptionConfig.from_env()
    return _config_instance
