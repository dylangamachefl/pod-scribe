# Hybrid Search for Episode-Scoped RAG

## Overview

The RAG service uses **hybrid search** (BM25 + FAISS) to answer questions about podcast episodes. Every query is scoped to a single episode for focused, relevant results.

## How It Works

When a user selects an episode in their library:

1. **Episode Selection** → Frontend provides `episode_title`
2. **Hybrid Search** → Combines BM25 (keywords) + FAISS (semantics)
3. **Episode Filtering** → Results limited to selected episode only
4. **Answer Generation** → Ollama generates answer from retrieved chunks
5. **Source Citations** → Returns relevant excerpts with timestamps

## Quick Start

### Install Dependencies

```bash
conda activate rag-service
pip install langchain langchain-community rank-bm25 faiss-cpu
```

### Start the Service

```bash
cd rag-service
uvicorn src.main:app --reload
```

## API Usage

### Basic Request

```python
import requests

response = requests.post("http://localhost:8000/chat", json={
    "question": "What did they discuss about AI?",
    "episode_title": "Episode Title Here"  # REQUIRED
})

result = response.json()
print(result["answer"])
print(f"Sources: {len(result['sources'])}")
```

### With Custom Weights

Adjust the balance between keyword matching (BM25) and semantic similarity (FAISS):

```python
# Favor keyword matching (good for specific terms/names)
response = requests.post("http://localhost:8000/chat", json={
    "question": "machine learning neural networks",
    "episode_title": "AI Episode",
    "bm25_weight": 0.7,  # 70% keywords
    "faiss_weight": 0.3   # 30% semantics
})

# Favor semantic similarity (good for conceptual questions)
response = requests.post("http://localhost:8000/chat", json={
    "question": "What are the ethical implications?",
    "episode_title": "Ethics Episode",
    "bm25_weight": 0.3,  # 30% keywords
    "faiss_weight": 0.7   # 70% semantics
})
```

### With Conversation History

```python
response = requests.post("http://localhost:8000/chat", json={
    "question": "Can you elaborate on that point?",
    "episode_title": "Episode Title",
    "conversation_history": [
        {"role": "user", "content": "What was the main topic?"},
        {"role": "assistant", "content": "The main topic was..."}
    ]
})
```

## Response Format

```json
{
  "answer": "Based on the episode content...",
  "sources": [
    {
      "podcast_name": "Tech Talks",
      "episode_title": "AI Future",
      "speaker": "Speaker 1",
      "timestamp": "00:15:30",
      "text_snippet": "...relevant excerpt...",
      "relevance_score": 1.0
    }
  ],
  "processing_time_ms": 423.5
}
```

## Configuration

Environment variables (`.env`):

```env
# Ollama Configuration
OLLAMA_API_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen3:rag
OLLAMA_EMBED_MODEL=nomic-embed-text

# Hybrid Search Weights (default: 0.5 each)
BM25_WEIGHT=0.5
FAISS_WEIGHT=0.5
HYBRID_TOP_K=5
```

## How Hybrid Search Works

### BM25 (Keyword Matching)
- Traditional information retrieval algorithm
- Finds exact keyword matches
- Great for: names, specific terms, technical jargon
- Example: "neural network architecture ResNet"

### FAISS (Semantic Similarity)
- Vector similarity search using embeddings
- Finds conceptually similar content
- Great for: paraphrased questions, conceptual queries
- Example: "How do AI models learn patterns?"

### Ensemble Combination
- Weights control contribution from each retriever
- Default: 50% BM25 + 50% FAISS
- LangChain's `EnsembleRetriever` merges results

## Index Management

### Automatic Rebuilding

Indexes are automatically rebuilt when:
- New episodes are ingested via `/ingest` endpoint
- First request to chat endpoint (if indexes don't exist)

### Manual Rebuild

```python
from services.embeddings import get_embedding_service
from services.qdrant_client import get_qdrant_service
from services.hybrid_retriever import get_hybrid_retriever_service

embeddings = get_embedding_service()
qdrant = get_qdrant_service()
hybrid = get_hybrid_retriever_service(embeddings, qdrant)

hybrid.build_indexes()
hybrid.save_indexes()
```

### Index Storage

Indexes are saved to `shared/indexes/`:
- `bm25_retriever.pkl` - BM25 index
- `faiss_index/` - FAISS vector store
- `documents_metadata.json` - Document metadata

## Testing

### Integration Test

```bash
python tests/test_hybrid_search_example.py
```

### Manual cURL Test

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What were the main topics?",
    "episode_title": "Your Episode Title"
  }'
```

## Performance

- **Index Build**: ~5-10 seconds for 1000 documents
- **Query Latency**: ~100-500ms
- **Memory**: FAISS keeps vectors in RAM
- **Disk**: Indexes ~same size as Qdrant collection

## Troubleshooting

### "No content found for episode"

The episode hasn't been ingested yet. Check:
```bash
curl http://localhost:8000/ingest/stats
```

### "Indexes not built"

Trigger manual rebuild or wait for first chat request.

### Dependencies missing

```bash
pip install langchain langchain-community rank-bm25 faiss-cpu
```

## Architecture

```
User selects episode → episode_title required
                  ↓
         ┌────────────────┐
         │  Chat Endpoint │
         └────────┬───────┘
                  │
    ┌─────────────┴──────────────┐
    │ HybridRetrieverService     │
    │ (episode_filter applied)   │
    └─────────────┬──────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
  ┌──────────┐      ┌──────────┐
  │   BM25   │      │  FAISS   │
  │Keywords  │      │Semantics │
  └──────────┘      └──────────┘
        │                   │
        └─────────┬─────────┘
                  │
        ┌─────────▼──────────┐
        │ EnsembleRetriever  │
        │ (weighted combine) │
        └─────────┬──────────┘
                  │
     Retrieved chunks (episode-scoped)
                  │
                  ▼
        ┌─────────────────┐
        │ Ollama generates│
        │     answer      │
        └─────────────────┘
```

## Key Design Principles

✅ **Episode-Scoped Only** - No cross-episode search  
✅ **Always Hybrid** - Combines BM25 + FAISS for best results  
✅ **Required Episode** - `episode_title` is mandatory  
✅ **Configurable Weights** - Adjust per query or globally  
✅ **Persistent Indexes** - Fast restarts with saved indexes  

## Dependencies

- `langchain>=0.1.0` - Ensemble retriever framework
- `langchain-community>=0.0.10` - BM25Retriever implementation
- `rank-bm25>=0.2.2` - BM25 algorithm
- `faiss-cpu>=1.7.4` - Vector similarity search
