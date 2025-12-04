# Quick Start Guide

Get up and running with the Podcast Transcriber in minutes!

## Prerequisites

- **OS**: Windows 10/11 (Linux/Mac compatible with minor changes)
- **GPU**: NVIDIA GPU with 8GB+ VRAM (for transcription service)
- **Conda**: Anaconda or Miniconda installed
- **Docker**: For RAG service (optional)

## 🚀 Transcription Service Setup

### 1. Create Conda Environment

```bash
# Navigate to project root
cd podcast-transcriber

# Create transcription environment
conda env create -f transcription-service/environment.yml
```

This takes 10-15 minutes on first install (downloads CUDA binaries and models).

### 2. Configure Environment

```bash
# Copy example environment file
copy .env.example .env

# Edit .env and add your tokens:
# - HUGGINGFACE_TOKEN (required for diarization)
# - GEMINI_API_KEY (optional, for RAG service)
```

**Get tokens:**
- HuggingFace: https://huggingface.co/settings/tokens
- Gemini API: https://makersuite.google.com/app/apikey

### 3. Verify Installation

```bash
conda activate podcast_bot
python -c "import whisperx; import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

✅ You should see: `CUDA: True`

### 4. Launch Dashboard

**Windows:**
```bash
cd scripts
launch_ui.bat
```

**Linux/Mac:**
```bash
streamlit run transcription-service/src/ui/dashboard.py
```

Opens at http://localhost:8501

### 5. Add Podcast Feeds

1. Go to **"Feed Manager"** tab
2. Paste RSS feed URL (see examples below)
3. Click **"Add Feed"**

**Example RSS Feeds:**
- Lex Fridman: `https://lexfridman.com/feed/podcast/`
- The Joe Rogan Experience: `http://joeroganexp.joerogan.libsynpro.com/rss`
- 99% Invisible: `https://feeds.99percentinvisible.org/99percentinvisible`

### 6. Select & Transcribe Episodes

#### Option A: Manual Selection (Recommended)
1. Go to **"Episode Queue"** tab
2. Click **"Fetch Episodes"** for your feeds
3. Select episodes you want to transcribe
4. Click **"Run Transcription"** in Dashboard

#### Option B: Via Command Line
```bash
conda activate podcast_bot

# Process selected episodes
python transcription-service/src/cli.py

# Or fetch and process latest episode automatically
python transcription-service/src/cli.py --schedule --limit-episodes 1
```

### 7. View Transcripts

Transcripts are saved to:
```
shared/output/
  └── Podcast Name/
      └── Episode Title.txt
```

Example transcript format:
```
[SPEAKER_00] 00:15:32: Welcome to the show!
[SPEAKER_01] 00:15:35: Thanks for having me!
```

---

## 🤖 RAG Service Setup (Optional)

Add semantic search and Q&A capabilities over your transcripts.

### 1. Start Qdrant Vector Database

```bash
# Using Docker
docker run -p 6333:6333 -v "${pwd}/qdrant_data:/qdrant/storage" qdrant/qdrant

# Or using docker-compose (includes RAG service)
docker-compose up -d qdrant
```

### 2. Create RAG Environment

```bash
conda env create -f rag-service/rag-environment.yml
conda activate rag_env
```

### 3. Add Gemini API Key

Edit `.env` and add:
```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. Start RAG Service

```bash
cd rag-service
python -m src.main
```

Service starts at http://localhost:8000
API docs at http://localhost:8000/docs

### 5. Test the Service

```bash
# Health check
curl http://localhost:8000/health

# Ask a question
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What topics were discussed?"}'
```

---

## ⚡ Quick Commands Reference

### Transcription Service

```bash
# Activate environment
conda activate podcast_bot

# Show help
python transcription-service/src/cli.py --help

# Process selected episodes (default mode)
python transcription-service/src/cli.py

# Auto-process all new episodes from feeds
python transcription-service/src/cli.py --auto

# Fetch and process latest 2 episodes per feed
python transcription-service/src/cli.py --schedule --limit-episodes 2

# Launch dashboard
streamlit run transcription-service/src/ui/dashboard.py
```

### RAG Service

```bash
# Activate environment
conda activate rag_env

# Start service
cd rag-service && python -m src.main

# Health check
curl http://localhost:8000/health
```

### Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

## 🎯 Expected Performance

**Transcription (RTX 3070, 8GB VRAM):**
- 10-min episode: ~2-3 minutes
- 30-min episode: ~6-8 minutes
- 60-min episode: ~12-15 minutes

**RAG Service:**
- Embedding: ~1-2 seconds
- Search: <100ms
- Q&A: 2-5 seconds (Gemini API)

---

## 🐛 Troubleshooting

### "CUDA not available"

**Check NVIDIA drivers:**
```bash
nvidia-smi
```

**Verify PyTorch CUDA:**
```bash
python -c "import torch; print(torch.version.cuda)"
```

**Solution:** Update NVIDIA drivers or reinstall PyTorch with CUDA support.

### "Out of Memory" Error

**Reduce batch size in `.env`:**
```bash
BATCH_SIZE=2  # Change from 4 to 2
```

**Or use smaller model:**
```bash
WHISPER_MODEL=medium  # Instead of large-v2
```

### "Import Error: No module named..."

**Ensure correct environment:**
```bash
# Check active environment
conda env list

# Activate correct one
conda activate podcast_bot  # For transcription
conda activate rag_env      # For RAG
```

### "Qdrant connection refused"

**Start Qdrant:**
```bash
docker run -p 6333:6333 qdrant/qdrant
```

**Or check if running:**
```bash
docker ps
```

### "File not found" Errors

**Run from project root:**
```bash
cd podcast-transcriber  # Make sure you're in project root
python transcription-service/src/cli.py
```

### Dashboard Won't Launch

**Check Streamlit is installed:**
```bash
conda activate podcast_bot
streamlit --version
```

**Reinstall if needed:**
```bash
pip install streamlit
```

---

## 📁 Project Structure Quick Reference

```
podcast-transcriber/
├── transcription-service/     # AI transcription service
│   ├── src/cli.py             # Main entry point
│   └── src/ui/dashboard.py    # Streamlit UI
│
├── rag-service/               # Semantic search service
│   └── src/main.py            # FastAPI server
│
├── shared/                    # Shared resources
│   ├── config/                # Configuration files
│   ├── output/                # Transcripts
│   └── summaries/             # Episode summaries
│
├── scripts/                   # Launcher scripts
│   ├── launch_ui.bat          # Windows UI launcher
│   └── run_bot.bat            # Windows transcription runner
│
├── .env                       # Your configuration
└── docker-compose.yml         # Docker orchestration
```

---

## 🎓 Next Steps

1. **Monitor First Transcription:** Watch VRAM usage with `nvidia-smi -l 1`
2. **Check Accuracy:** Review first transcript for quality
3. **Automate:** Set up weekly processing with Task Scheduler (Windows) or cron (Linux)
4. **Explore RAG:** Ask questions about your transcripts via the RAG API
5. **Star the Repo:** If you find this useful! ⭐

---

## 🆘 Need More Help?

- **Full Documentation:** See [README.md](README.md)
- **Service Details:**
  - [Transcription Service README](transcription-service/README.md)
  - [RAG Service README](rag-service/README.md)
- **Configuration:** Check [.env.example](.env.example) for all options
- **Upgrading:** See [MIGRATION.md](MIGRATION.md) if coming from old version

## 🚀 You're Ready!

Start transcribing and enjoy searchable podcast content!
