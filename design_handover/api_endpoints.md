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
- **GET `/ingest/stats`**
    - **Response**: `{ total_chunks: number, ... }`

---

## 2. Summarization Service (GenAI)
**Base URL**: `http://localhost:8002` (Default)

### Summaries
- **GET `/summaries`**
    - **Response**: `Array<Summary>` (with structured JSON parsing on client)
    - **Purpose**: Redundant with RAG service, but may be used for fresher data or direct access.

- **POST `/summaries/generate`**
    - **Payload**: `{ transcript_text: string, episode_title: string, podcast_name: string }`
    - **Response**: `Summary`
    - **Purpose**: Manually trigger generation of a summary for a transcript.

---

## 3. Transcription Service (Management & Processing)
**Base URL**: `http://localhost:8001` (Default)

### Feed Management
- **GET `/feeds`**: List RSS feeds.
- **POST `/feeds`**: Add a new RSS feed URL.
- **PUT `/feeds/{feedId}`**: Update feed (active/inactive).
- **DELETE `/feeds/{feedId}`**: Remove a feed.

### Episode Queue
- **GET `/episodes/queue`**: List episodes currently in the processing queue.
- **POST `/episodes/fetch`**: Trigger a fetch of new episodes from feeds.
- **PUT `/episodes/{episodeId}/select`**: Toggle selection of an episode for transcription.
- **POST `/episodes/bulk-select`**: Select multiple episodes.
- **DELETE `/episodes/processed`**: Clear finished episodes from the queue view.

### Transcription Control
- **GET `/transcription/status`**: Real-time status of the worker (progress, current episode, GPU usage).
- **POST `/transcription/start`**: Start the transcription worker process.

### Transcript Browsing
- **GET `/transcripts`**: List podcasts that have transcripts.
- **GET `/transcripts/{podcastName}`**: List episodes for a podcast.
- **GET `/files/{podcastName}/{episodeName}.txt`**: Download/View raw transcript text.

### Stats & Health
- **GET `/stats`**: Overall stats (total episodes, etc.).
- **GET `/health`**: Service health status.
