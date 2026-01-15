# Podcast Summarization Service

Two-stage Map-Reduce summarization service for podcast transcripts using local Ollama models with Rolling State Refinery.

## Overview

This service automatically processes new podcast transcripts using an advanced **Map-Reduce Synthesis Engine** that maintains narrative context across long documents:

### Two-Stage Pipeline
1. **Stage 1 (Thinker)**: Map-Reduce synthesis with rolling state for high-fidelity unstructured summaries.
2. **Stage 2 (Structurer)**: Instructor-powered extraction for guaranteed JSON schema validation.

### Key Outputs
- Concise episode summaries
- Key topics discussed
- Main insights and takeaways
- Notable quotes
- Processing metrics (stage timings, chunk counts)

## Features

- **Map-Reduce Synthesis**: Processes long transcripts in chunks with contextual carry-forward via rolling state.
- **Rolling State Refinery**: Maintains narrative thread across chunk boundaries to prevent context loss.
- **VRAM Guard**: Active memory management (`torch.cuda.empty_cache()`) between chunks to prevent OOM errors.
- **Event-Driven Processing**: Redis Streams consumer for reliable, automatic processing.
- **Heartbeat Reaper**: Background task that resets stuck `SUMMARIZING` jobs (>5 minutes).
- **Structured Output**: Instructor-powered extraction with Pydantic validation for guaranteed schema compliance.
- **Local Processing**: Uses local Ollama `qwen3:summarizer` model (no external API dependencies).

## Architecture

The summarization service is event-driven and decoupled from the RAG service:
- **Input**: Consumes `BatchTranscribed` events from Redis Streams (`stream:episodes:batch_transcribed`).
- **Processing**: Two-stage Map-Reduce pipeline using local Ollama API with GPU lock coordination.
- **Output**: Saves structured summaries to PostgreSQL with rich metadata.
- **API**: Provides REST endpoints for manual summarization and summary retrieval.

## Configuration

### Environment Variables

Create a `.env` file in the project root with:

```env
# Required
OLLAMA_API_URL=http://host.docker.internal:11434
OLLAMA_SUMMARIZER_MODEL=qwen3:summarizer

# Optional (with defaults)
SUMMARIZATION_API_PORT=8002
SUMMARIZATION_FRONTEND_URL=http://localhost:3000
```

### Model Configuration

The service uses the local Ollama model `qwen3:summarizer`. Ensure this model is available by running:

```bash
ollama list
```

If the model is not available, create it using the provided Modelfile:

```bash
ollama create qwen3:summarizer -f Modelfile_sum
```

## Setup

### 1. Create Conda Environment

```bash
conda env create -f summarization-environment.yml
conda activate summarization-service
```

### 2. Install Dependencies

```bash
pip install -e .
```

### 3. Configure Environment

Set `OLLAMA_API_URL` and `OLLAMA_SUMMARIZER_MODEL` in your `.env` file.

### 4. Run the Service

```bash
# Development mode
python src/main.py

# Or with uvicorn
uvicorn src.main:app --host 0.0.0.0 --port 8002 --reload
```

## API Endpoints

### Health Check
```bash
GET /health
```

Returns service health status and configuration.

### Generate Summary (Manual)
```bash
POST /summaries/generate
Content-Type: application/json

{
  "podcast_name": "Example Podcast",
  "episode_title": "Episode 1",
  "transcript_text": "Full transcript text..."
}
```

### List All Summaries
```bash
GET /summaries
```

Returns array of all generated summaries.

### Get Specific Summary
```bash
GET /summaries/{episode_title}
```

Returns summary for a specific episode.


## Output Format

Summaries are saved to PostgreSQL with the following schema:

```json
{
  "episode_title": "Episode Title",
  "podcast_name": "Podcast Name",
  "processed_date": "2025-12-05T09:00:00",
  "summary": "Episode summary paragraph...",
  "key_topics": ["Topic 1", "Topic 2"],
  "insights": ["Insight 1", "Insight 2"],
  "quotes": ["Quote 1", "Quote 2"],
  "stage1_processing_time_ms": 45000.0,
  "stage2_processing_time_ms": 8000.0,
  "total_processing_time_ms": 53000.0
}
```

## Event-Driven Processing

### Ingestion Flow

1. **Event Subscription**: Listens to `stream:episodes:batch_transcribed` with consumer group `summarization_service_group`.
2. **Batch Processing**: Receives `BatchTranscribed` events containing `episode_ids` array.
3. **Idempotency Check**: Queries PostgreSQL for existing summary to prevent duplicate processing.
4. **GPU Lock Acquisition**: Coordinates with other services via Redis-based distributed lock.
5. **Map-Reduce Synthesis**: Processes transcript in chunks with rolling state maintenance.
6. **Heartbeat Updates**: Updates PostgreSQL `heartbeat` column every 30s during processing.
7. **Structured Extraction**: Uses Instructor for guaranteed JSON schema compliance.
8. **Event Publication**: Publishes `EpisodeSummarized` event to `stream:episodes:summarized` for downstream consumers (e.g., RAG service).

### Heartbeat Reaper

Background task that runs continuously:
- Queries for episodes in `SUMMARIZING` state with stale heartbeats (>5 minutes).
- Resets stuck episodes to `TRANSCRIBED` status for retry.
- Ensures system resilience against worker crashes or network issues.

## Architecture Details

This service is part of the podcast transcriber monorepo:
- **Transcription Service**: Generates transcripts from audio, publishes `BatchTranscribed` events.
- **Summarization Service** (this): Consumes transcripts, generates summaries, publishes `EpisodeSummarized` events.
- **RAG Service**: Consumes summaries for enhanced Q&A context.
- **Frontend**: React UI for user interaction and summary viewing.
