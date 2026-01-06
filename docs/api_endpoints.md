# API Endpoints and Contracts

This document lists the API endpoints that the frontend consumes. The new design must support the data requirements of these endpoints.

## 1. RAG Service (Chat & Search)
**Base URL**: `http://localhost:8000` (Default)

### Chat
- **POST `/chat`**
    - **Payload**: `{ question: string, conversation_history?: Array }`
    - **Response**: `{ answer: string, sources: Array, processing_time_ms: number }`
    - **Purpose**: Main chat interface. Sends a user question and gets an AI response with citations.

### Summaries (Search View)
- **GET `/summaries`**
    - **Response**: `Array<Summary>`
    - **Purpose**: Lists all available summaries. Used for the "Library" or "Dashboard" view.

- **GET `/summaries/{episodeTitle}`**
    - **Response**: `Summary`
    - **Purpose**: Gets detailed summary for a specific episode.

### System
- **GET `/health`**
    - **Response**: `{ status: string, qdrant_connected: boolean, ... }`
- **GET `/stats/pipeline`**
    - **Response**: `PipelineStatus` (from shared `status_monitor.py`)

---

## 2. Summarization Service (Ollama/Gemini)
**Base URL**: `http://localhost:8002`

### Summaries
- **GET `/summaries`**
    - **Response**: `Array<Summary>`
    - **Purpose**: List completed summaries from the database.

- **GET `/summaries/{episodeId}`**
    - **Response**: `Summary`
    - **Purpose**: Get detailed summary for a specific episode.

### System
- **GET `/health`**
    - **Response**: `{ status: string, ollama_connected: boolean, ... }`

---

## 3. Transcription API (Management)
**Base URL**: `http://localhost:8001`

### Feed Management
- **GET `/feeds`**: List RSS feeds.
- **POST `/feeds`**: Add a new RSS feed URL.
- **DELETE `/feeds/{feedId}`**: Remove a feed.

### Episode Management
- **GET `/episodes`**: List all known episodes.
- **POST `/episodes/sync`**: Trigger a fetch of new episodes from active feeds.
- **PUT `/episodes/{episodeId}/select`**: Toggle/Set selection state.
- **GET `/episodes/selection`**: Get current selections.

### Transcription Worker Status
- **GET `/status`**: Aggregate pipeline status (via shared `PipelineStatusManager`).
- **POST `/status/clear`**: Manually clear stale status in Redis.

### Health
- **GET `/health`**: Service health status.
