# Quick Start Guide

Get up and running with the Podcast Transcriber in minutes!

## Prerequisites

- **OS**: Windows 10/11
- **GPU**: NVIDIA GPU with 8GB+ VRAM (Recommended for fast transcription)
- **Software**:
  - [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Required for core services)
  - [Ollama](https://ollama.ai/download) (Required for RAG/chat features)
  - [Anaconda](https://www.anaconda.com/download) or Miniconda (Required for transcription worker)

---

## 🚀 Setup

### 1. Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd podcast-transcriber
   ```

2. Create the transcription environment (Required for GPU workers):
   ```bash
   conda env create -f transcription-service/environment.yml
   ```
   *Note: This takes 10-15 minutes as it downloads CUDA binaries and AI models.*

3. Create custom Ollama RAG model (Required for RAG/chat):

   This project uses a custom version of `qwen3:8b` optimized for GPUs with 8GB VRAM (RTX 3070). The context window is tuned to **6144 tokens** to maximize document capacity without running out of memory.

   **a. Pull the base models:**
   ```bash
   ollama pull qwen3:8b
   ollama pull nomic-embed-text
   ```

   **b. Create a `Modelfile`:**
   
   Create a file named `Modelfile` (no extension) in your project root with this content:
   
   ```dockerfile
   FROM qwen3:8b

   # RTX 3070 Optimization (8GB VRAM)
   # Context window set to 6144 to prevent Out-Of-Memory errors while allowing RAG.
   PARAMETER num_ctx 6144

   # Model Parameters for Balanced RAG
   PARAMETER temperature 0.6
   PARAMETER top_k 20
   PARAMETER top_p 0.95
   ```

   **c. Build the custom model:**
   ```bash
   ollama create qwen3:rag -f Modelfile
   ```

   **d. Verify installation:**
   ```bash
   ollama run qwen3:rag
   ```
   Type `/bye` to exit the test chat.

   > [!NOTE]
   > Ensure Ollama is running before starting the application.

### 2. Configuration

1. Create your configuration file:
   ```bash
   copy .env.example .env
   ```

2. Edit `.env` with your API keys:
   - **HUGGINGFACE_TOKEN** (Required): Get from [HuggingFace Settings](https://huggingface.co/settings/tokens) - Used for speaker diarization
   - **GEMINI_API_KEY** (Required): Get from [Google AI Studio](https://makersuite.google.com/app/apikey) - Used for episode summarization

> [!NOTE]
> The app uses **Ollama** (running locally via Docker) for RAG/chat features and **Gemini API** for creating episode summaries.

---

## ▶️ Running the App

We use a universal startup script to launch all services.

### 1. Start the Application
Double-click `start_app.bat` or run in terminal:
```bash
start_app.bat
```

This will:
- Launch Docker containers (Frontend, RAG, API, Database)
- Start the host-side listener for the transcription worker
- Open the Web UI in your browser

### 2. Access the Interface
- **Web UI**: http://localhost:3000
- **API Docs**: http://localhost:8001/docs

---

## 🎙️ How to Transcribe

The transcription process runs separately from the main application to keep your system responsive while using the GPU.

### 1. Queue Episodes
- Go to `http://localhost:3000`
- Add RSS feeds in the **Feeds** tab
- Click "Fetch Episodes" to see available episodes
- Select episodes and add them to your Queue

### 2. Run Transcription Worker

You have **two options** for running the transcription worker:

**Option A: Trigger from UI (Recommended)**
- Click the "Start Transcription" button in the Queue page
- The host listener service (started by `start_app.bat`) will automatically launch the transcription worker in a new window
- This uses your GPU to process all queued episodes

**Option B: Manual Launch**
- Run the script directly when you're ready to process episodes:
  ```bash
  scripts\run_bot.bat
  ```
- Useful for scheduling with Windows Task Scheduler for automated runs

> [!TIP]
> The transcription worker runs in a separate window so you can monitor progress while continuing to use the UI.

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
