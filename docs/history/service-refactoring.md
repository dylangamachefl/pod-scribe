# Service Decoupling and Reorganization - Summary

## What Changed

Successfully decoupled the RAG and summarization services into two separate services with distinct responsibilities:

### New Architecture

**Summarization Service** (Port 8002)
- Standalone FastAPI service for podcast transcript summarization
- Uses Google Gemini API with configurable model (default: `gemini-2.5-flash-lite`)
- File watcher monitors `shared/output/` for new transcripts
- Saves summaries to `shared/summaries/`
- Completely independent from RAG service

**RAG Service** (Port 8000)
- Focused exclusively on Q&A functionality
- Uses Ollama with Qwen 2.5 7B for chat
- Uses Ollama with nomic-embed-text for embeddings (768 dimensions)
- Removed all summarization logic
- Removed file watcher (handled by summarization service)

### Key Changes

1. **Created `summarization-service/`** directory with:
   - FastAPI application
   - Gemini client with configurable model
   - File watcher for auto-processing
   - Summaries router for API endpoints
   - Complete documentation

2. **Updated `rag-service/`** to:
   - Use Ollama instead of Gemini API
   - Use nomic-embed-text embeddings (768 dim) instead of sentence-transformers (384 dim)
   - Remove summarization logic, file watcher, and summaries router
   - Update dependencies (removed google-generativeai, sentence-transformers, watchdog)

3. **Updated Configuration**:
   - `.env.example` with Ollama and summarization variables
   - `docker-compose.yml` with summarization service
   - Embedding dimension changed from 384 to 768

### Prerequisites

**Ollama Setup (Required for RAG Service)**:
```bash
# Install Ollama
# Download from: https://ollama.ai/download

# Pull required models
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

**Gemini API (Required for Summarization Service)**:
- Get API key from: https://makersuite.google.com/app/apikey
- Add to `.env` file as `GEMINI_API_KEY`

### Environment Variables

New variables added to `.env`:

```env
# Ollama Configuration (RAG Service)
OLLAMA_API_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5:7b
OLLAMA_EMBED_MODEL=nomic-embed-text

# Summarization Configuration
SUMMARIZATION_MODEL=gemini-2.5-flash-lite
SUMMARIZATION_API_PORT=8002
SUMMARIZATION_FRONTEND_URL=http://localhost:3000

# Updated Embedding Dimension
EMBEDDING_DIMENSION=768
```

### Running the Services

```bash
# Start all services with Docker
docker-compose up -d

# Or start individually
docker-compose up -d qdrant
docker-compose up -d rag-service
docker-compose up -d summarization-service
docker-compose up -d frontend
```

**Note**: Ollama must be running on the host machine before starting the RAG service.

### API Endpoints

**Summarization Service** (`http://localhost:8002`):
- `POST /summaries/generate` - Manual summarization
- `GET /summaries` - List all summaries
- `GET /summaries/{episode_title}` - Get specific summary
- `GET /health` - Health check

**RAG Service** (`http://localhost:8000`):
- `POST /chat` - Q&A with full transcript context
- `POST /ingest` - Ingest transcripts into vector DB
- `GET /downloads/{episode_title}` - Download transcripts
- `GET /health` - Health check

### Migration Notes

> [!WARNING]
> **Breaking Change**: The embedding dimension has changed from 384 to 768. Existing vectors in Qdrant will need to be re-ingested.

To re-ingest transcripts:
1. Clear Qdrant: `docker-compose down -v && docker-compose up -d qdrant`
2. Re-process transcripts through the RAG service `/ingest` endpoint

### Files Created

- `summarization-service/` (complete service directory)
- `summarization-service/src/main.py`
- `summarization-service/src/config.py`
- `summarization-service/src/models.py`
- `summarization-service/src/services/gemini_service.py`
- `summarization-service/src/services/file_watcher.py`
- `summarization-service/src/routers/summaries.py`
- `summarization-service/src/utils/transcript_parser.py`
- `summarization-service/pyproject.toml`
- `summarization-service/summarization-environment.yml`
- `summarization-service/Dockerfile`
- `summarization-service/README.md`
- `rag-service/src/services/ollama_client.py`

### Files Modified

- `rag-service/src/services/embeddings.py` - Use Ollama API
- `rag-service/src/config.py` - Ollama configuration
- `rag-service/src/routers/chat.py` - Use Ollama client
- `rag-service/src/main.py` - Remove file watcher, summaries
- `rag-service/pyproject.toml` - Updated dependencies
- `rag-service/rag-environment.yml` - Updated dependencies
- `.env.example` - Added Ollama and summarization variables
- `docker-compose.yml` - Added summarization service

### Files Deleted

- `rag-service/src/services/gemini_client.py`
- `rag-service/src/services/file_watcher.py`
- `rag-service/src/routers/summaries.py`

## Next Steps

1. Copy `.env.example` to `.env` and configure:
   - Add your `GEMINI_API_KEY`
   - Verify Ollama settings

2. Install and setup Ollama:
   ```bash
   ollama pull qwen2.5:7b
   ollama pull nomic-embed-text
   ```

3. Start services:
   ```bash
   docker-compose up -d
   ```

4. Verify services are healthy:
   - RAG: http://localhost:8000/health
   - Summarization: http://localhost:8002/health

5. Test the workflow:
   - Add a transcript to `shared/output/`
   - Summarization service will auto-generate summary
   - Use RAG service to ask questions about the episode
