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

# Gemini API Configuration
# Support Docker Secrets (file-based) or direct environment variable
GEMINI_API_KEY_FILE = os.getenv("GEMINI_API_KEY_FILE")
if GEMINI_API_KEY_FILE:
    # Read from Docker Secret file
    with open(GEMINI_API_KEY_FILE, 'r') as f:
        GEMINI_API_KEY = f.read().strip()
else:
    # Fallback to environment variable for backward compatibility
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found. Set GEMINI_API_KEY_FILE or GEMINI_API_KEY.")

# Model Configuration
# Two-Stage Pipeline Configuration
# Stage 1: High-fidelity summarization (The Thinker)
STAGE1_MODEL = os.getenv("STAGE1_MODEL", "gemini-2.5-flash")

# Stage 2: Structured extraction (The Structurer)
STAGE2_MODEL = os.getenv("STAGE2_MODEL", "gemini-2.5-flash-lite")

# Backward compatibility: if SUMMARIZATION_MODEL is set, use it for Stage 1
if os.getenv("SUMMARIZATION_MODEL"):
    STAGE1_MODEL = os.getenv("SUMMARIZATION_MODEL")
    print(f"⚠️  Using legacy SUMMARIZATION_MODEL env var. Consider migrating to STAGE1_MODEL.")

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
