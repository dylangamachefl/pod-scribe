"""
Summarization Service Configuration
Loads environment variables for the summarization service.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get project root (navigate from summarization-service/src/ -> summarization-service/ -> root/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Model Configuration
# Allow configurable model name with default to gemini-2.5-flash-lite
SUMMARIZATION_MODEL = os.getenv("SUMMARIZATION_MODEL", "gemini-2.5-flash-lite")

# File Paths - Use shared directories
TRANSCRIPTION_WATCH_PATH = PROJECT_ROOT / "shared" / "output"
SUMMARY_OUTPUT_PATH = PROJECT_ROOT / "shared" / "summaries"

# Ensure directories exist
SUMMARY_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

# API Configuration
SUMMARIZATION_API_PORT = int(os.getenv("SUMMARIZATION_API_PORT", "8002"))
SUMMARIZATION_FRONTEND_URL = os.getenv("SUMMARIZATION_FRONTEND_URL", "http://localhost:3000")
