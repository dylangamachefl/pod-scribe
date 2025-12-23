"""
Summarization Service Configuration
Loads environment variables for the summarization service.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get project root (navigate from summarization-service/src/ -> summarization-service/)
# In Docker: /app/src/config.py -> /app
PROJECT_ROOT = Path(__file__).parent.parent

# Ollama API Configuration
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://host.docker.internal:11434")
OLLAMA_SUMMARIZER_MODEL = os.getenv("OLLAMA_SUMMARIZER_MODEL", "qwen3:summarizer")

# Two-Stage Pipeline Configuration
# Both stages use the same local Ollama model
# Stage 1: High-fidelity summarization (The Thinker)
# Stage 2: Structured extraction (The Structurer)

# Rate limiting configuration
STAGE1_MAX_RETRIES = int(os.getenv("STAGE1_MAX_RETRIES", "3"))
STAGE1_BASE_DELAY = float(os.getenv("STAGE1_BASE_DELAY", "2.0"))
STAGE2_MAX_RETRIES = int(os.getenv("STAGE2_MAX_RETRIES", "3"))
STAGE2_BASE_DELAY = float(os.getenv("STAGE2_BASE_DELAY", "1.0"))

# File Paths - Use shared directories
TRANSCRIPTION_WATCH_PATH = PROJECT_ROOT / "shared" / "output"
SUMMARY_OUTPUT_PATH = PROJECT_ROOT / "shared" / "summaries"

# Ensure directories exist
SUMMARY_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

# API Configuration
SUMMARIZATION_API_PORT = int(os.getenv("SUMMARIZATION_API_PORT", "8002"))
SUMMARIZATION_FRONTEND_URL = os.getenv("SUMMARIZATION_FRONTEND_URL", "http://localhost:3000")
