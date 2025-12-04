"""
RAG Backend Configuration
Loads environment variables for the RAG service.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get project root (navigate from rag-service/src/ -> rag-service/ -> root/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Qdrant Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "podcast_transcripts")

# File Paths - Use shared directories
TRANSCRIPTION_WATCH_PATH = PROJECT_ROOT / "shared" / "output"
SUMMARY_OUTPUT_PATH = PROJECT_ROOT / "shared" / "summaries"

# Ensure directories exist
SUMMARY_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)


# Embedding Configuration
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))

# API Configuration
RAG_API_PORT = int(os.getenv("RAG_API_PORT", "8000"))
RAG_FRONTEND_URL = os.getenv("RAG_FRONTEND_URL", "http://localhost:3000")

# Chunking Strategy
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))  # characters per chunk
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))  # overlap between chunks

# Retrieval Configuration
TOP_K_RESULTS = int(os.getenv("TOP_K_RESULTS", "5"))  # number of chunks to retrieve
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))  # minimum similarity score
