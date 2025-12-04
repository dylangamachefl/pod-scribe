# RAG Service

Retrieval-Augmented Generation service for semantic search and Q&A over podcast transcripts.

## Architecture

The RAG service provides a FastAPI backend that enables semantic search and question-answering capabilities over podcast transcripts using vector embeddings and the Gemini LLM.

```
rag-service/
├── src/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration management
│   ├── models.py            # Pydantic request/response models
│   ├── exceptions.py        # Custom exception hierarchy
│   ├── routers/             # API endpoints
│   │   ├── chat.py          # Q&A endpoint
│   │   ├── summaries.py     # Summary retrieval
│   │   └── ingest.py        # Manual ingestion
│   ├── services/            # Core business logic
│   │   ├── embeddings.py    # Sentence transformers
│   │   ├── qdrant_client.py # Vector database  
│   │   ├── gemini_client.py # Gemini LLM integration
│   │   └── file_watcher.py  # Auto-ingestion of new transcripts
│   └── utils/               # Utility functions
│       └── chunking.py      # Text chunking strategies
└── tests/                   # Unit and integration tests
```

## Features

### Core Capabilities
- 🔍 **Semantic Search**: Vector-based similarity search across all transcripts
- 💬 **Q&A**: Ask questions and get answers with source citations
- 📊 **Summarization**: Auto-generate episode summaries with Gemini
- 🔄 **Auto-Ingestion**: Watches for new transcripts and ingests automatically
- 🗃️ **Vector Storage**: Qdrant for efficient similarity search

### API Endpoints

#### `POST /chat`
Ask questions about podcast content.

**Request:**
```json
{
  "question": "What did they say about machine learning?",
  "conversation_history": []
}
```

**Response:**
```json
{
  "answer": "Based on the transcripts, they discussed...",
  "sources": [
    {
      "podcast_name": "Tech Podcast",
      "episode_title": "ML in Production",
      "speaker": "SPEAKER_00",
      "timestamp": "00:15:32",
      "text_snippet": "Machine learning in production requires...",
      "relevance_score": 0.89
    }
  ],
  "processing_time_ms": 1234.56
}
```

#### `GET /summaries/{podcast_name}/{episode_title}`
Retrieve episode summary.

**Response:**
```json
{
  "episode_title": "ML in Production",
  "podcast_name": "Tech Podcast",
  "summary": "This episode covers...",
  "key_topics": ["Machine Learning", "Production Systems"],
  "speakers": ["SPEAKER_00", "SPEAKER_01"],
  "created_at": "2025-12-04T10:00:00"
}
```

#### `POST /ingest`
Manually trigger transcript ingestion.

**Request:**
```json
{
  "file_path": "/path/to/transcript.txt"
}
```

#### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "qdrant_connected": true,
  "embedding_model_loaded": true,
  "gemini_api_configured": true
}
```

## Setup

### Prerequisites

- Docker (for Qdrant)
- Python 3.8+
- Gemini API key
- Conda environment

### 1. Start Qdrant Vector Database

```bash
docker run -p 6333:6333 -v "$(pwd)/qdrant_data:/qdrant/storage" qdrant/qdrant
```

Qdrant will be available at `http://localhost:6333`

### 2. Create Conda Environment

```bash
conda env create -f rag-environment.yml
conda activate rag_env
```

### 3. Configure Environment

Add to `.env` in project root:

```bash
# Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# Qdrant (optional overrides)
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=podcast_transcripts

# Embedding model
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# API server
RAG_API_PORT=8000
RAG_FRONTEND_URL=http://localhost:3000
```

### 4. Start RAG Service

```bash
cd rag-service
python -m src.main
```

Server will start at `http://localhost:8000`

API docs available at `http://localhost:8000/docs`

## Usage

### Via API

```python
import requests

# Ask a question
response = requests.post("http://localhost:8000/chat", json={
    "question": "What topics were discussed about AI?"
})

answer = response.json()
print(answer["answer"])
for source in answer["sources"]:
    print(f"- {source['podcast_name']}: {source['text_snippet']}")
```

### Via curl

```bash
# Health check
curl http://localhost:8000/health

# Ask question
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What did they say about AI?"}'
```

## How It Works

### Ingestion Pipeline

1. **File Watcher** monitors `shared/output/` for new transcripts
2. **Parser** extracts metadata (podcast, episode, speakers)
3. **Chunker** splits transcript into semantic chunks (500 chars, 100 overlap)
4. **Embedder** generates vector embeddings with Sentence Transformers
5. **Vector DB** stores embeddings in Qdrant with metadata
6. **Summarizer** (optional) generates Gemini summary

### Query Pipeline

1. **Embed Question** using same embedding model
2. **Vector Search** in Qdrant for similar chunks (top 5)
3. **RAG Prompt** construct context with retrieved chunks
4. **Gemini** generates answer with citations
5. **Format Response** with sources and timestamps

## Configuration

### Embedding Model

Default: `all-MiniLM-L6-v2` (384 dimensions, fast)

Alternatives:
- `all-mpnet-base-v2` (768 dimensions, higher quality)
- `multi-qa-MiniLM-L6-cos-v1` (384 dimensions, optimized for Q&A)

Set via `EMBEDDING_MODEL` in `.env`

### Chunking Strategy

**Default:**
- Chunk size: 500 characters
- Overlap: 100 characters

Adjust via `CHUNK_SIZE` and `CHUNK_OVERLAP` in `.env`

**Tradeoffs:**
- Smaller chunks: More precise retrieval, less context
- Larger chunks: More context, less precision
- More overlap: Better context continuity, more storage

### Retrieval Parameters

**Top K**: Number of chunks to retrieve (default: 5)
**Similarity Threshold**: Minimum score to include (default: 0.7)

Set via `TOP_K_RESULTS` and `SIMILARITY_THRESHOLD` in `.env`

## Services

### Embeddings Service

**File:** `services/embeddings.py`
**Model:** Sentence Transformers
**Purpose:** Convert text to vector embeddings

**Key Methods:**
- `embed_text(text)` - Single text embedding
- `embed_batch(texts)` - Batch processing

### Qdrant Service

**File:** `services/qdrant_client.py`
**Purpose:** Vector database operations

**Key Methods:**
- `create_collection()` - Initialize collection
- `insert_vectors()` - Store embeddings
- `search_similar()` - Similarity search
- `get_collection_stats()` - Database status

### Gemini Service

**File:** `services/gemini_client.py`
**Purpose:** LLM for Q&A and summarization

**Key Methods:**
- `generate_answer(question, context)` - RAG Q&A
- `generate_summary(transcript)` - Episode summarization

### File Watcher Service

**File:** `services/file_watcher.py`
**Purpose:** Auto-detect and ingest new transcripts

**Behavior:**
- Monitors `shared/output/` directory
- Detects new `.txt` files
- Automatically ingests and indexes
- Runs in background thread

## Error Handling

The service uses custom exception hierarchy:

```python
RAGServiceError          # Base exception
├── ConfigurationError   # Config issues
├── EmbeddingError       # Embedding failures
├── VectorDBError        # Qdrant errors
├── GeminiAPIError       # Gemini API errors
├── FileProcessingError  # File parsing errors
└── ChunkingError        # Text chunking errors
```

Errors return structured JSON:

```json
{
  "error": "VectorDBError",
  "message": "Failed to connect to Qdrant",
  "details": {"host": "localhost:6333"}
}
```

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
# Format code
black src/

# Lint
ruff check src/

# Type check
mypy src/
```

### Adding New Endpoints

1. Create router in `routers/`
2. Define Pydantic models in `models.py`
3. Implement business logic in `services/`
4. Register router in `main.py`

## Performance

### Embedding Generation
- Single text: ~10-50ms
- Batch (10 chunks): ~100-200ms

### Vector Search
- Query time: <100ms
- Indexing: Real-time

### Gemini API
- Answer generation: 2-5 seconds
- Depends on API latency and prompt complexity

### Optimization Tips
- Use batch embedding for bulk ingestion
- Adjust `TOP_K` based on use case
- Cache frequently asked questions
- Use smaller embedding model for speed

## Troubleshooting

### Qdrant Connection Error

```
VectorDBError: Failed to connect to Qdrant
```

**Solution:**
1. Verify Docker container is running: `docker ps`
2. Check port 6333 is accessible
3. Verify `QDRANT_URL` in `.env`

### Gemini API Error

```
GeminiAPIError: Invalid API key
```

**Solution:**
1. Check `GEMINI_API_KEY` in `.env`
2. Verify key is active in Google Cloud Console
3. Check API quota/rate limits

### Embedding Model Download

First run downloads model (~100MB). This is normal and cached locally.

## Integration

### With Transcription Service

Transcripts saved to `shared/output/` are automatically:
1. Detected by file watcher
2. Parsed and chunked
3. Embedded and indexed
4. Available for search/Q&A

### With Frontend (Planned)

React frontend will:
- Send questions via `/chat` endpoint
- Display answers with source citations
- Browse summaries via `/summaries`
- Show real-time ingestion status

## License

MIT License - See project root LICENSE file.
