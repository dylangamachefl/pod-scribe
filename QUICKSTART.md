# Quick Start Guide

Get up and running with the Podcast Transcriber in minutes!

## Prerequisites

- **OS**: Windows 10/11
- **GPU**: NVIDIA GPU with 8GB+ VRAM (Recommended for fast transcription)
- **Software**:
  - [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Required for all services)
  - [Ollama](https://ollama.ai/download) (Required for RAG/chat features)

> [!NOTE]
> **Transcription Options**: The transcription service runs in Docker using your GPU. No conda environment needed unless you want to run transcription on the host instead of Docker.

---

## 🚀 Setup

### 1. Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd podcast-transcriber
   ```

### 2. Create Ollama Models (Required)

This project uses custom Ollama models optimized for balanced performance and memory usage.

**a. Pull the base models:**
```bash
ollama pull qwen3:8b
ollama pull nomic-embed-text
```

**b. Create the custom models:**

We provide Modelfiles in the `models/` directory for both RAG and Summarization.

```bash
# Create RAG model (optimized context for 8GB VRAM)
ollama create qwen3:rag -f models/Modelfile_rag

# Create Summarizer model (optimized for extraction)
ollama create qwen3:summarizer -f models/Modelfile_sum
```

**c. Verify installation:**
```bash
ollama list
```
You should see `qwen3:rag` and `qwen3:summarizer` in the list.

> [!NOTE]
> Ensure Ollama is running before starting the application.

### 3. Configuration

1. Create your configuration file:
   ```bash
   copy .env.example .env
   ```

2. Create Docker secrets directory (Recommended for Gemini API Key):
   ```bash
   mkdir secrets
   echo "your_gemini_api_key_here" > secrets/gemini_api_key.txt
   ```

3. Edit `.env` with your API keys:
   - **HUGGINGFACE_TOKEN** (Required): Get from [HuggingFace Settings](https://huggingface.co/settings/tokens) - Used for speaker diarization.
   - **GEMINI_API_KEY** (Optional): The system now defaults to local Ollama (`qwen3:summarizer`) for summaries, but Gemini remains supported as a high-quality alternative.

> [!NOTE]
> The app uses **Ollama** (running on your **host machine**) for both RAG/chat features and local summarization.

---

## ▶️ Running the App

### 1. Start the Application
Double-click `start_app.bat` or run in terminal:
```bash
start_app.bat
```

This will:
- Launch Docker containers (Frontend, RAG, Transcription API, Transcription Worker, Summarization, PostgreSQL, Redis)
- Open the Web UI in your browser

### 2. Access the Interface
- **Web UI**: http://localhost:3000
- **Transcription API**: http://localhost:8001/docs
- **RAG API**: http://localhost:8000/docs
- **Summarization API**: http://localhost:8002/docs

---

## 🎙️ How to Transcribe

The transcription service runs automatically in Docker, processing queued episodes using your GPU.
### 1. Queue Episodes
The **Transcription API** handles episode management and enqueues jobs into Redis.
- Go to `http://localhost:3000`
- Add RSS feeds in the **Feeds** tab
- Click "Fetch Episodes" to see available episodes
- Select episodes and add them to your Queue

### 2. Transcription Processing

The **Transcription Worker** (Docker container) automatically processes queued episodes using your GPU.
 You can monitor progress:

```bash
# View transcription worker logs
docker-compose logs -f transcription-worker
```

> [!TIP]
> The transcription worker runs continuously in the background. It automatically picks up new episodes from the queue.

> [!NOTE]
> **GPU Configuration**: The Docker transcription-worker uses your NVIDIA GPU if properly configured. See [GPU_SETUP.md](GPU_SETUP.md) for GPU setup with Docker.

### 3. View Results
- Refresh the **Library** page to see completed transcripts
- Episode summaries are automatically generated after transcription
- You can chat with episodes using the RAG features

---

## 🛠️ Troubleshooting

### Docker Services Failed to Start
- Ensure Docker Desktop is running.
- Run `docker-compose logs` to see errors.

### "Conda not found" in `run_bot.bat`
- Use the standard `Anaconda Prompt` or `Miniconda Prompt` to run the script.
- If using standard CMD, you may need to add Conda to your PATH or edit `scripts\run_bot.bat` to point to your installation.

### Ollama Connection Issues
- Ensure Ollama is installed and running:
  ```bash
  ollama list
  ```
- Verify required models are downloaded:
  ```bash
  ollama pull qwen3:rag
  ollama pull nomic-embed-text
  ```
- Check Ollama is accessible:
  ```bash
  curl http://localhost:11434/api/tags
  ```

### GPU Not Used / CUDA Errors
- Ensure you have the latest NVIDIA Drivers installed.
- Verify installation:
  ```bash
  conda activate podcast_bot
  python -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}')"
  ```
