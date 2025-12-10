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

# Ollama Configuration
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen3:rag")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# Qdrant Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "podcast_transcripts")

# File Paths - Use shared directories
TRANSCRIPTION_WATCH_PATH = PROJECT_ROOT / "shared" / "output"
SUMMARY_OUTPUT_PATH = PROJECT_ROOT / "shared" / "summaries"

# Embedding Configuration
# nomic-embed-text has 768 dimensions
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "768"))

# API Configuration
RAG_API_PORT = int(os.getenv("RAG_API_PORT", "8000"))
RAG_FRONTEND_URL = os.getenv("RAG_FRONTEND_URL", "http://localhost:3000")

# Chunking Strategy (for ingestion, not used for chat)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))  # characters per chunk
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))  # overlap between chunks

# Retrieval Configuration
TOP_K_RESULTS = int(os.getenv("TOP_K_RESULTS", "5"))  # number of chunks to retrieve
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))  # minimum similarity score

# Hybrid Search Configuration
HYBRID_SEARCH_ENABLED = os.getenv("HYBRID_SEARCH_ENABLED", "true").lower() == "true"
BM25_WEIGHT = float(os.getenv("BM25_WEIGHT", "0.5"))  # 0.0 to 1.0
QDRANT_WEIGHT = float(os.getenv("QDRANT_WEIGHT", "0.5"))  # 0.0 to 1.0 (replaces FAISS_WEIGHT)
HYBRID_TOP_K = int(os.getenv("HYBRID_TOP_K", "5"))

# Index persistence
INDEXES_PATH = PROJECT_ROOT / "shared" / "indexes"
