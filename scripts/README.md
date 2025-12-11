# Transcription Trigger - Host Listener Service

## Overview

The host listener service runs on your Windows machine and listens for transcription requests from the web UI. When you click the "Run Transcription" button in the dashboard, it triggers the Docker transcription worker.

## Architecture

```
UI Button (localhost:3000) 
  ↓
Transcription API (Docker container on port 8001)
  ↓  
Host Listener Service (localhost:8080) ← YOU ARE HERE
  ↓
docker-compose run transcription-worker
```

## Quick Start

### Option 1: Using the batch script (Recommended)
1. Double-click `scripts/start_listener.bat`
2. The service will start and show: `Running on http://localhost:8080`
3. Leave this window open (minimize it if you want)
4. Go to http://localhost:3000 and click "Run Transcription"

### Option 2: Manual start
```bash
cd scripts
python host_listener.py
```

## What It Does

- **Listens on port 8080** for HTTP requests
- **Receives trigger** from transcription-API when you click the UI button
- **Executes** `docker-compose run --rm transcription-worker`
- **Runs transcription** in an isolated Docker container with GPU access

## Endpoints

- `GET /health` - Health check
- `POST /start` - Start transcription worker
- `GET /status` - Get listener status

## Requirements

- Python 3.7+
- Flask (installed automatically by start_listener.bat)
- Docker Desktop running
- Docker-compose available in PATH

## Troubleshooting

**Service won't start:**
- Make sure port 8080 is not in use
- Check that Flask is installed: `pip install flask flask-cors`

**Button doesn't work:**
- Make sure the listener service is running
- Check that you can access: http://localhost:8080/health
- Look for errors in the listener console window

**Transcription doesn't start:**
- Check Docker Desktop is running
- Verify transcription-worker image exists: `docker images | grep transcription-worker`
- Check console output for errors

## Stopping the Service

- Press `Ctrl+C` in the console window
- Or just close the window

## Auto-Start on Boot (Optional)

To have the listener start automatically:
1. Press `Win+R`, type `shell:startup`, press Enter
2. Create a shortcut to `scripts/start_listener.bat`
3. The service will start when Windows boots

Alternatively, you can set it up as a Windows Service using tools like NSSM.
