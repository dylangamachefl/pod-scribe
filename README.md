# Automated Podcast Transcription & RAG System

A modular, production-ready system for automated podcast transcription with speaker diarization and semantic search powered by RAG (Retrieval-Augmented Generation).

## 🎯 Overview

This monorepo contains three integrated services:

1. **Transcription Service**: Downloads and transcribes podcasts using WhisperX + Pyannote
2. **RAG Service**: Provides semantic search and Q&A over transcripts using Gemini
3. **Frontend**: React-based UI for interacting with transcripts (planned)

## ✨ Features

### Transcription Service
- 🎙️ **Automatic RSS Feed Processing**: Subscribe to podcast feeds
- 🤖 **AI-Powered Transcription**: WhisperX with int8 quantization
- 👥 **Speaker Diarization**: Pyannote Audio for speaker identification
- 💾 **Smart Deduplication**: Tracks processed episodes
- 🎨 **Web Dashboard**: Streamlit UI for management
- ⚡ **GPU Optimized**: 8GB VRAM (RTX 3070 tested)
- 📋 **Episode Queue**: Manual selection workflow

### RAG Service  
- 🔍 **Semantic Search**: Vector-based transcript search
- 💬 **AI Q&A**: Ask questions about podcast content
- 📊 **Auto-Summarization**: Gemini-powered episode summaries
- 🔄 **Auto-Ingestion**: Watches for new transcripts
- 🗃️ **Qdrant Vector DB**: Efficient similarity search

## 🏗️ Architecture

```
podcast-transcriber/
├── transcription-service/      # Podcast transcription
│   ├── src/
│   │   ├── cli.py             # CLI entry point
│   │   ├── config.py          # Configuration
│   │   ├── core/              # Core processing modules
│   │   ├── managers/          # State management
│   │   └── ui/                # Streamlit dashboard
│   ├── tests/
│   ├── README.md
│   └── pyproject.toml
│
├── rag-service/                # RAG backend
│   ├── src/
│   │   ├── main.py            # FastAPI server
│   │   ├── config.py          # Configuration
│   │   ├── routers/           # API endpoints
│   │   ├── services/          # Business logic
│   │   └── utils/             # Utilities
│   └── tests/
│
├── frontend/                   # React UI (planned)
│
├── shared/                     # Shared resources
│   ├── config/                # Configuration files
│   ├── output/                # Transcripts
│   ├── summaries/             # Generated summaries
│   └── logs/                  # Application logs
│
├── scripts/                    # Launcher scripts
│   ├── launch_ui.bat          # Dashboard launcher
│   └── run_bot.bat            # Transcription runner
│
├── environment.yml             # Transcription conda env
├── rag-environment.yml         # RAG conda env
└── README.md                   # This file
```

## 🚀 Quick Start

### Prerequisites

- **OS**: Windows 10/11 (Linux/Mac compatible with minor changes)
- **GPU**: NVIDIA GPU with 8GB+ VRAM (for transcription)
- **CUDA**: 11.8 or compatible
- **Conda**: Anaconda or Miniconda
- **Docker**: For Qdrant (RAG service)

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/podcast-transcriber.git
cd podcast-transcriber
```

### 2. Setup Transcription Service

```bash
# Create conda environment
conda env create -f transcription-service/environment.yml
conda activate podcast_bot

# Configure environment
cp .env.example .env
# Edit .env and add your HUGGINGFACE_TOKEN
```

### 3. Setup RAG Service (Optional)

```bash
# Start Qdrant vector database
docker run -p 6333:6333 -v "$(pwd)/qdrant_data:/qdrant/storage" qdrant/qdrant

# Create RAG conda environment
conda env create -f rag-service/rag-environment.yml
conda activate rag_env

# Add GEMINI_API_KEY to .env
```

### 4. Launch Dashboard

```bash
# Windows
cd scripts
./launch_ui.bat

# Linux/Mac
streamlit run transcription-service/src/ui/dashboard.py
```

## 📖 Usage

### Transcription Service

#### Via Dashboard (Recommended)
1. Navigate to **Feed Manager** → Add podcast RSS feeds
2. Go to **Episode Queue** → Fetch and select episodes
3. Click **Run Transcription** in Dashboard

#### Via CLI

```bash
# Manual mode: Process selected episodes from queue
python transcription-service/src/cli.py

# Auto mode: Process all new episodes from feeds
python transcription-service/src/cli.py --auto

# Schedule mode: Fetch and process latest N episodes
python transcription-service/src/cli.py --schedule --limit-episodes 2
```

### RAG Service

```bash
# Start RAG server
cd rag-service
python -m src.main

# Access at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Transcription Service
HUGGINGFACE_TOKEN=hf_your_token_here
DEVICE=cuda
COMPUTE_TYPE=int8
BATCH_SIZE=4
WHISPER_MODEL=large-v2

# RAG Service  
GEMINI_API_KEY=your_gemini_api_key
QDRANT_URL=http://localhost:6333
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### HuggingFace Setup (Required for Diarization)

1. Create account at [huggingface.co](https://huggingface.co)
2. Accept licenses:
   - [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
   - [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
3. Get access token from settings
4. Add to `.env` as `HUGGINGFACE_TOKEN`

## 📦 Service Details

### Transcription Service

**Tech Stack:**
- WhisperX (transcription)
- Pyannote Audio (diarization)
- Streamlit (dashboard)
- PyTorch + CUDA

**See:** [transcription-service/README.md](transcription-service/README.md)

### RAG Service

**Tech Stack:**
- FastAPI (API server)
- Qdrant (vector database)
- Google Gemini (LLM)
- Sentence Transformers (embeddings)

**See:** [RAG_README.md](RAG_README.md)

## 🎨 Dashboard Features

- **📡 Feed Management**: Add/remove/toggle podcast feeds
- **📥 Episode Queue**: Fetch, select, and manage episodes
- **📊 Dashboard**: Real-time processing status and GPU monitoring
- **📄 Transcript Viewer**: Browse and search transcripts
- **⚙️ Settings**: Configure paths and automation

## 🔄 Workflow

```mermaid
graph LR
    A[RSS Feed] --> B[Episode Queue]
    B --> C[User Selection]
    C --> D[Download Audio]
    D --> E[Transcribe]
    E --> F[Diarize]
    F --> G[Save Transcript]
    G --> H[shared/output/]
    H --> I[RAG Auto-Ingest]
    I --> J[Vector DB]
    J --> K[Search & Q&A]
```

## ⚡ Performance

**Transcription (RTX 3070):**
- 10-min episode: ~2-3 minutes
- 30-min episode: ~6-8 minutes  
- 60-min episode: ~12-15 minutes

**RAG:**
- Embedding: ~1-2 seconds
- Search: <100ms
- Q&A: 2-5 seconds (Gemini API)

## 🧪 Testing

```bash
# Syntax validation
python validate_syntax.py

# Run tests (when implemented)
cd transcription-service
pytest tests/

cd ../rag-service
pytest tests/
```

## 📚 Documentation

- [Transcription Service README](transcription-service/README.md)
- [RAG Service README](RAG_README.md)
- [Refactoring Summary](REFACTORING_SUMMARY.md)
- [Quick Start Guide](QUICKSTART.md)

## 🛠️ Development

### Code Structure

Each service follows clean architecture:
- **Modular design**: Clear separation of concerns
- **Type safety**: Type hints throughout
- **Configuration injection**: Testable components
- **Comprehensive documentation**: Inline docs and READMEs

### Contributing

See individual service READMEs for development guidelines.

## 🐛 Troubleshooting

### Transcription Service

**CUDA Out of Memory:**
- Reduce `BATCH_SIZE` in `.env`
- Use smaller model: `WHISPER_MODEL=medium`
- Close other GPU applications

**Import Errors:**
- Ensure conda environment is activated
- Run from project root directory

### RAG Service

**Qdrant Connection Error:**
- Verify Docker container is running
- Check `QDRANT_URL` in `.env`

**Gemini API Error:**
- Verify `GEMINI_API_KEY` is valid
- Check API quota/rate limits

## 📝 License

MIT License - See [LICENSE](LICENSE)

## 🙏 Acknowledgments

- [WhisperX](https://github.com/m-bain/whisperx) - Fast speech recognition
- [Pyannote Audio](https://github.com/pyannote/pyannote-audio) - Speaker diarization
- [Qdrant](https://qdrant.tech/) - Vector database
- [Google Gemini](https://deepmind.google/technologies/gemini/) - LLM & embeddings
