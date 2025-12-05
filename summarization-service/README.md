# Podcast Summarization Service

AI-powered summarization service for podcast transcripts using Google Gemini API.

## Overview

This service automatically monitors new podcast transcripts and generates comprehensive summaries including:
- Concise episode summaries
- Key topics discussed
- Main insights and takeaways
- Notable quotes

## Features

- **Automatic Processing**: File watcher monitors transcript directory and auto-generates summaries
- **Configurable Model**: Uses environment variable to specify Gemini model (default: `gemini-2.5-flash-lite`)
- **RESTful API**: FastAPI endpoints for manual summarization and summary retrieval
- **Structured Output**: JSON summaries with topics, insights, and quotes

## Architecture

The summarization service is decoupled from the RAG service to allow independent scaling and configuration:
- **Input**: Reads transcripts from `shared/output/`
- **Processing**: Uses Gemini API for summarization
- **Output**: Saves summaries to `shared/summaries/`
- **API**: Provides REST endpoints for frontend consumption

## Configuration

### Environment Variables

Create a `.env` file in the project root with:

```env
# Required
GEMINI_API_KEY=your_gemini_api_key_here

# Optional (with defaults)
SUMMARIZATION_MODEL=gemini-2.5-flash-lite
SUMMARIZATION_API_PORT=8002
SUMMARIZATION_FRONTEND_URL=http://localhost:3000
```

### Model Configuration

The `SUMMARIZATION_MODEL` environment variable allows you to specify any Gemini model:
- `gemini-2.5-flash-lite` (default, fast and lightweight)
- `gemini-2.5-flash` (faster, good balance)
- `gemini-pro` (higher quality, slower)
- `gemini-1.5-pro` (best quality, slowest)

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

Copy `.env.example` to `.env` and add your Gemini API key.

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

## File Watcher

The service automatically watches the `shared/output/` directory for new `.txt` files. When a new transcript is detected:

1. File is debounced (2-second delay)
2. Metadata is extracted from transcript
3. Summary is generated via Gemini API
4. Result is saved to `shared/summaries/`

## Output Format

Summaries are saved as JSON files:

```json
{
  "episode_title": "Episode Title",
  "podcast_name": "Podcast Name",
  "processed_date": "2025-12-05T09:00:00",
  "summary": "Episode summary paragraph...",
  "key_topics": ["Topic 1", "Topic 2"],
  "insights": ["Insight 1", "Insight 2"],
  "quotes": ["Quote 1", "Quote 2"],
  "source_file": "/path/to/transcript.txt",
  "processing_time_ms": 1234.5
}
```

## Docker Support

Build and run with Docker:

```bash
docker build -t summarization-service .
docker run -p 8002:8002 --env-file ../.env summarization-service
```

Or use docker-compose from project root:

```bash
docker-compose up summarization-service
```

## Development

### Testing

```bash
pytest tests/
```

### API Documentation

Start the service and visit:
- Swagger UI: http://localhost:8002/docs
- ReDoc: http://localhost:8002/redoc

## Troubleshooting

### Gemini API Key Not Found
Ensure `.env` file exists in project root with valid `GEMINI_API_KEY`.

### File Watcher Not Detecting Files
- Check `TRANSCRIPTION_WATCH_PATH` points to correct directory
- Ensure directory exists and has proper permissions
- Check logs for file system events

### Model Not Found
Verify the `SUMMARIZATION_MODEL` value is a valid Gemini model name.

## Architecture

This service is part of the podcast transcriber monorepo:
- **Transcription Service**: Generates transcripts from audio
- **Summarization Service** (this): Generates summaries from transcripts
- **RAG Service**: Handles Q&A using Ollama
- **Frontend**: React UI for user interaction
