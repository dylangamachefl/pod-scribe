# Transcription Service

Automated podcast transcription service using WhisperX and Pyannote for speaker diarization.

## Architecture

This service follows a modular architecture with clear separation of concerns:

```
transcription-service/
├── src/
│   ├── cli.py              # CLI entry point
│   ├── config.py           # Configuration management
│   ├── main.py             # Backward compatibility wrapper
│   ├── core/               # Core processing logic
│   │   ├── audio.py        # Audio download & transcription
│   │   ├── diarization.py  # Speaker identification
│   │   ├── formatting.py   # Text formatting utilities
│   │   └── processor.py    # High-level orchestration
│   ├── managers/           # State management
│   │   ├── episode_manager.py  # Episode queue
│   │   └── status_monitor.py   # Processing status
│   └── ui/                 # User interfaces
│       └── dashboard.py    # Streamlit dashboard
├── temp/                   # Temporary audio files
└── tests/                  # Unit and integration tests
```

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

### CLI Entry Point

```bash
# Default: Process selected episodes from queue
python src/cli.py

# Auto mode: Process all new episodes from feeds
python src/cli.py --auto

# Schedule mode: Fetch and process latest N episodes
python src/cli.py --schedule --limit-episodes 2
```

### Programmatic Usage

```python
from config import get_config
from core.processor import process_selected_episodes

# Load configuration
config = get_config()

# Process selected episodes
process_selected_episodes(config)
```

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

### With RAG Service

Transcripts are saved to `../../shared/output/` where the RAG service watches for new files to ingest.

### With Dashboard

The dashboard (`ui/dashboard.py`) provides a web interface for:
- Managing RSS feed subscriptions
- Selecting episodes for transcription
- Monitoring transcription progress
- Viewing transcripts

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
