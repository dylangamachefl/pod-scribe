# Transcription Service

Event-driven podcast transcription service using WhisperX and Pyannote for speaker diarization.

## Architecture

This service is built around a **long-running worker daemon** that consumes jobs from Redis Streams and manages GPU resources efficiently:

```
transcription-service/
├── src/
│   ├── worker_daemon.py    # Main worker entry point (long-running)
│   ├── config.py           # Configuration management
│   ├── core/               # Core processing logic
│   │   ├── audio.py        # Audio download & transcription (GPU-managed)
│   │   ├── diarization.py  # Speaker identification
│   │   ├── formatting.py   # Text formatting utilities
│   │   └── processor.py    # High-level orchestration
│   ├── managers/           # State management
│   │   ├── episode_manager.py  # Episode queue (SQL SSOT)
│   │   └── status_monitor.py   # Processing status
│   ├── api/                # FastAPI management endpoints
│   └── scripts/            # Utility scripts (recovery, etc.)
├── temp/                   # Temporary audio files
└── tests/                  # Unit and integration tests
```

## Key Features

- **Event-Driven Architecture**: Consumes `TranscriptionJob` events from Redis Streams with consumer groups for reliability.
- **Heartbeat Reaper**: Background task that automatically resets stuck jobs (episodes in `TRANSCRIBING` state for >5 minutes).
- **Distributed GPU Lock**: Coordinates GPU access across services using Redis-based locking.
- **Immediate Release Strategy**: Releases GPU resources immediately after batch completion using `total_batch_count`.
- **SQL Source of Truth**: Queries PostgreSQL directly for batch completion status instead of in-memory tracking.

## Modules

### Core Modules

#### `config.py`
Centralized configuration management with type safety.

**Key Classes:**
- `TranscriptionConfig`: Dataclass for all configuration
- `get_config()`: Singleton for configuration access

**Features:**
- Environment variable loading with validation
- Automatic path derivation
- Directory creation on initialization

#### `core/audio.py`
Audio download and transcription.

**Functions:**
- `download_audio(url, output_path)`: Download from URL
- `transcribe_audio(audio_path, ...)`: WhisperX transcription with alignment

#### `core/diarization.py`
Speaker identification using Pyannote.

**Functions:**
- `apply_pytorch_patch()`: PyTorch 2.6+ compatibility fix
- `diarize_transcript(audio_path, transcript, ...)`: Speaker identification

#### `core/formatting.py`
Text formatting utilities.

**Functions:**
- `sanitize_filename(filename)`: Remove invalid characters
- `format_transcript(result)`: Format with timestamps and speakers
- `format_timestamp(seconds)`: Convert to HH:MM:SS

#### `core/processor.py`
High-level episode processing orchestration.

**Functions:**
- `process_episode(episode_data, config, history)`: Full pipeline
- `process_feed(subscription, config, history)`: Process RSS feed
- `process_selected_episodes(config)`: Process from queue

### Management Modules

#### `managers/episode_manager.py`
Episode queue and RSS feed management.

**Functions:**
- `get_selected_episodes()`: Get episodes marked for processing
- `add_episode_to_queue(episode)`: Add new episode
- `fetch_episodes_from_feed(url, title)`: Parse RSS feed

#### `managers/status_monitor.py`
Real-time processing status tracking.

**Functions:**
- `write_status(...)`: Update processing status
- `read_status()`: Get current status
- `clear_status()`: Reset status

### UI Modules

#### `ui/dashboard.py`
Streamlit-based web dashboard for management and monitoring.

## Usage

### Worker Daemon (Primary)

The worker daemon is the main entry point for production use:

```bash
# Start the worker daemon (runs continuously)
python src/worker_daemon.py

# Or via Docker (recommended)
docker-compose up transcription-worker
```

**Worker Features:**
- Continuously polls Redis Streams for `TranscriptionJob` events
- Manages GPU lifecycle with automatic cleanup
- Implements heartbeat mechanism during processing
- Publishes `BatchTranscribed` events upon completion
- Graceful shutdown on SIGINT/SIGTERM

### API Management

The transcription API provides endpoints for managing the queue:

```bash
# Start the API server
cd transcription-service
python -m src.api.main

# Or via Docker
docker-compose up transcription-api
```

**API Endpoints:**
- `POST /episodes/queue` - Add episodes to transcription queue
- `GET /episodes` - List all episodes with status
- `GET /status` - Get worker status and pipeline health
- `POST /status/stop` - Signal worker to stop gracefully

## Configuration

Configuration is managed through environment variables in `.env`:

```bash
# Required
HUGGINGFACE_TOKEN=hf_your_token_here

# Optional (with defaults)
DEVICE=cuda                    # or "cpu"
COMPUTE_TYPE=int8             # Critical for 8GB VRAM
BATCH_SIZE=4                  # Batch size for transcription
WHISPER_MODEL=large-v2        # WhisperX model
```

## Dependencies

- Python 3.8+
- PyTorch with CUDA support
- WhisperX
- Pyannote Audio
- See `environment.yml` for full list

## Development

### Adding New Features

1. **New processing step**: Add to `core/`
2. **New management logic**: Add to `managers/`
3. **New UI component**: Add to `ui/`
4. **New configuration**: Add to `config.py`

### Testing

```bash
# Validate syntax
python ../../validate_syntax.py

# Run tests (when implemented)
pytest tests/
```

### Code Style

- Type hints throughout
- Docstrings for all public functions
- Configuration injected as dependencies
- Pure functions where possible

## Backward Compatibility

`main.py` provides backward compatibility for scripts that call it directly:

```python
# main.py
from cli import main

if __name__ == "__main__":
    main()
```

## Integration

### Event-Driven Pipeline

The transcription worker integrates with other services via Redis Streams:

1. **Receives Jobs**: Subscribes to `stream:transcription:jobs` with consumer group `transcription_workers`.
2. **Processes Episodes**: Downloads audio, transcribes with WhisperX, applies diarization.
3. **Publishes Events**: On batch completion, publishes `BatchTranscribed` event to `stream:episodes:batch_transcribed`.
4. **Downstream Consumers**: Summarization and RAG services consume these events for further processing.

### With PostgreSQL

All episode state is managed in PostgreSQL:
- Episode status transitions: `PENDING` → `TRANSCRIBING` → `TRANSCRIBED` → `FAILED`
- Heartbeat column updated every 30s during processing
- Batch completion determined by SQL query (no in-memory state)

### With Shared Storage

Transcripts are saved to `shared/output/` where downstream services can access them:
- Filename format: `{podcast_name}_{episode_title}_transcript.txt`
- Includes speaker labels and timestamps
- Metadata stored in PostgreSQL, content in filesystem

## Performance

Optimized for NVIDIA RTX 3070 (8GB VRAM):
- INT8 quantization for models
- Chunked processing
- Automatic memory cleanup
- Progress tracking

## Troubleshooting

### Import Errors
Ensure you're running from the project root and the conda environment is activated.

### CUDA Errors
Check GPU drivers and ensure `DEVICE=cuda` in `.env`.

### Diarization Errors
The PyTorch patch in `core/diarization.py` fixes compatibility with PyTorch 2.6+. It must be applied before importing whisperx.

## License

See project root LICENSE file.
