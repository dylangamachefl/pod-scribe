@echo off
REM ========================================================================
REM Podcast Transcriber - Universal Startup Script
REM ========================================================================

echo.
echo ========================================================================
echo   Podcast Transcriber
echo   Starting full application stack...
echo ========================================================================
echo.

REM 1. Start Dockerized Services
echo [1/3] Launching Docker services...
echo       - Frontend (Port 3000)
echo       - RAG Service (Port 8000)
echo       - Transcription API (Port 8001)
echo       - Summarization Service (Port 8002)
echo       - Qdrant Vector DB (Port 6333)
echo.

docker-compose up -d

if errorlevel 1 (
    echo.
    echo ERROR: Failed to start Docker services.
    echo Please ensure Docker Desktop is running and try again.
    pause
    exit /b 1
)


REM [2/3] Launching Host-Side Listener
REM Listens on port 8080 to trigger transcription from the Containerized API
echo.
echo [2/3] Starting Host Listener...
echo       - Listening on localhost:8080
echo.

REM Start the listener in the background using python (assuming python is in path)
REM We use start /b to run it in the same window background or minimal intrusion
start /b python scripts\host_listener.py

REM [3/3] Wait for services to be ready and open browser
echo.
echo [3/3] Waiting for services to initialize...
echo.
timeout /t 5 /nobreak >nul

REM Open browser to the web interface
echo Opening browser to http://localhost:3000...
start http://localhost:3000

echo.
echo ========================================================================
echo   Startup Completed Successfully!
echo ========================================================================
echo.
echo   Web Interface:    http://localhost:3000  [OPENED]
echo   RAG API Docs:     http://localhost:8000/docs
echo   Transcribe API:   http://localhost:8001/docs
echo   Summary API:      http://localhost:8002/docs
echo.
echo   [TIP] To run transcription:
echo         1. Queue episodes in the Web Interface
echo         2. Run 'scripts\run_bot.bat' manually
echo ========================================================================
echo.
pause
