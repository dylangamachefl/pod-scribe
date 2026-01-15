# RAG Service

Retrieval-Augmented Generation service for hybrid semantic search and streaming Q&A over podcast transcripts using local Ollama.

## Architecture

The RAG service provides a FastAPI backend with **hybrid search** (BM25 + Qdrant) and **streaming chat** capabilities using local Ollama models.

```
rag-service/
├── src/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration management
│   ├── models.py            # Pydantic request/response models
│   ├── event_subscriber.py  # Redis Streams consumer for ingestion
│   ├── routers/             # API endpoints
│   │   ├── chat.py          # Q&A endpoints (streaming + non-streaming)
│   │   ├── downloads.py     # Audio download proxy
│   │   └── ingest.py        # Manual ingestion trigger
│   ├── services/            # Core business logic
│   │   ├── embeddings.py    # Ollama nomic-embed-text wrapper
│   │   ├── qdrant_service.py # Vector database (deterministic UUIDs)
│   │   ├── ollama_client.py # Ollama chat client (qwen3:rag)
│   │   ├── hybrid_retriever.py # RRF fusion of BM25 + Qdrant
│   │   └── summaries_service.py # Summary retrieval
│   └── utils/               # Utility functions
│       └── chunking.py      # Text chunking strategies
└── tests/                   # Unit and integration tests
```

## Features

### Core Capabilities
- 🔍 **Hybrid Search**: Reciprocal Rank Fusion (RRF) combining BM25 keyword matching and Qdrant vector similarity.
- 💬 **Streaming Q&A**: Real-time answer generation with `METADATA:` protocol for sources and timestamps.
- 📊 **Episode & Global Search**: Filter by episode or search across entire library.
- 🔄 **Event-Driven Ingestion**: Redis Streams consumer for reliable, idempotent indexing.
- 🗃️ **Deterministic Vector IDs**: UUID v5 based on `episode_id` + `chunk_index` for safe re-indexing.
- 🔗 **Search-to-Seek Integration**: Returns `audio_url` in citations for frontend navigation.

### API Endpoints

#### `POST /chat/stream`
Stream answers in real-time with metadata protocol.

**Request:**
```json
{
  "question": "What did they say about machine learning?",
  "episode_title": "ML in Production",  // Optional: null for global search
  "conversation_history": []
}
```

**Response (Streaming):**
```
METADATA:{"sources":[{"speaker":"SPEAKER_00","timestamp":"00:15:32","episode":"ML in Production","audio_url":"https://..."}]}
Based on the transcripts, they discussed...
```

#### `POST /chat`
Non-streaming Q&A endpoint.

**Request:**
```json
{
  "question": "What did they say about machine learning?",
  "episode_title": "ML in Production",  // Optional
  "bm25_weight": 0.5,  // Optional: default 0.5
  "faiss_weight": 0.5  // Optional: default 0.5
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
      "audio_url": "https://example.com/episode.mp3",
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
  "checks": {
    "qdrant": true,
    "ollama": true,
    "redis": true,
    "postgres": true
  }
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
# Ollama Configuration
OLLAMA_API_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen3:rag
OLLAMA_EMBED_MODEL=nomic-embed-text

# Qdrant (optional overrides)
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=podcast_transcripts

# Embedding model
EMBEDDING_DIMENSION=768

# Hybrid Search
BM25_WEIGHT=0.5
QDRANT_WEIGHT=0.5
HYBRID_TOP_K=5

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

### Ingestion Pipeline (Event-Driven)

1. **Event Subscriber** listens to `stream:episodes:batch_transcribed` on Redis Streams.
2. **Idempotency Check**: Queries Qdrant for existing `episode_id` to avoid duplicate indexing.
3. **Chunker** splits transcript into semantic chunks (2000 chars, 200 overlap).
4. **Embedder** generates vector embeddings using Ollama `nomic-embed-text` (768-dim).
5. **Vector DB** stores embeddings in Qdrant with deterministic UUIDs (`uuid.uuid5(namespace, f"{episode_id}_{chunk_index}")`).
6. **BM25 Index** incrementally updated with new documents for hybrid search.

### Query Pipeline (Hybrid Search)

1. **Embed Question** using Ollama `nomic-embed-text`.
2. **BM25 Search**: Keyword-based retrieval from local BM25 index (built from Qdrant).
3. **Qdrant Search**: Semantic vector search with optional episode filtering.
4. **RRF Fusion**: Merge results using Reciprocal Rank Fusion for balanced ranking.
5. **Ollama Generation**: Generate answer using `qwen3:rag` with retrieved context.
6. **Format Response**: Return answer with sources, timestamps, and `audio_url` for navigation.

## Configuration

### Embedding Model

Default: `nomic-embed-text` via Ollama (768 dimensions)

Set via `OLLAMA_EMBED_MODEL` in `.env`

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

**Hybrid Search Weights**: Control the balance between BM25 and Qdrant
- `BM25_WEIGHT`: 0.0 to 1.0 (default: 0.5)
- `QDRANT_WEIGHT`: 0.0 to 1.0 (default: 0.5)

**Top K**: Number of chunks to retrieve (default: 5)

Set via `BM25_WEIGHT`, `QDRANT_WEIGHT`, and `HYBRID_TOP_K` in `.env`

## Services

### Embeddings Service

**File:** `services/embeddings.py`
**Model:** Sentence Transformers
**Purpose:** Convert text to vector embeddings

**Key Methods:**
- `embed_text(text)` - Single text embedding
- `embed_batch(texts)` - Batch processing

### Qdrant Service

**File:** `services/qdrant_service.py`
**Purpose:** Vector database operations with deterministic UUIDs

**Key Methods:**
- `initialize()` - Ensure collection exists
- `insert_chunks()` - Store embeddings with UUID v5 IDs
- `search()` - Similarity search with optional filters
- `get_collection_stats()` - Database status

### Ollama Service

**File:** `services/ollama_client.py`
**Purpose:** LLM for Q&A generation

**Key Methods:**
- `answer_with_retrieved_chunks()` - Non-streaming RAG Q&A
- `generate_answer_stream()` - Streaming RAG Q&A

### Hybrid Retriever Service

**File:** `services/hybrid_retriever.py`
**Purpose:** Combine BM25 and Qdrant using RRF

**Key Methods:**
- `build_bm25_index()` - Build/rebuild BM25 from Qdrant
- `search()` - Hybrid search with configurable weights
- `add_documents()` - Incrementally update BM25 index

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

### With Transcription Service (Event-Driven)

The RAG service consumes transcription events via Redis Streams:

1. **Event Subscription**: Listens to `stream:episodes:batch_transcribed` with consumer group `rag_service_group`.
2. **Batch Processing**: Receives `BatchTranscribed` events containing `episode_ids` array.
3. **Idempotent Ingestion**: Checks Qdrant for existing `episode_id` before indexing to prevent duplicates.
4. **Automatic Indexing**: Fetches transcript from PostgreSQL, chunks, embeds, and stores in Qdrant.
5. **BM25 Update**: Incrementally adds new documents to BM25 index for hybrid search.

### With Frontend

React frontend integrates via:
- `POST /chat/stream` - Streaming answers with real-time token generation
- `POST /chat` - Non-streaming answers for simpler use cases
- `METADATA:` protocol - Frontend parses sources/timestamps for "Search-to-Seek" navigation
- `audio_url` in citations - Enables direct audio playback at specific timestamps

## License

MIT License - See project root LICENSE file.
