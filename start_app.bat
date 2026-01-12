@echo off
:: Force the script to run in the current directory (fixes shortcut issues)
cd /d "%~dp0"

TITLE Podcast Transcriber & RAG System
CLS

ECHO ========================================================
ECHO   Podcast Transcriber & RAG System - Startup
ECHO ========================================================
ECHO.

:: ----------------------------------------------------------
:: 1. CHECK AND START DOCKER DESKTOP
:: ----------------------------------------------------------
ECHO [1/6] Checking Docker status...
docker info >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO       Docker is not running. Starting Docker Desktop...
    
    IF EXIST "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
        start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    ) ELSE (
        ECHO       ERROR: Could not find Docker Desktop.
        PAUSE
        EXIT /B
    )
    
    ECHO       Waiting for Docker Engine...
    :WAIT_DOCKER
    timeout /t 5 /nobreak >nul
    docker info >nul 2>&1
    IF %ERRORLEVEL% NEQ 0 GOTO WAIT_DOCKER
    ECHO       Docker is now running!
) ELSE (
    ECHO       Docker is already running.
)

:: ----------------------------------------------------------
:: 2. CHECK AND START OLLAMA
:: ----------------------------------------------------------
ECHO.
ECHO [2/6] Checking Ollama status...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
IF "%ERRORLEVEL%"=="0" (
    ECHO       Ollama is already running.
) ELSE (
    ECHO       Ollama is not running. Starting background service...
    start "Ollama Server" /MIN ollama serve
    timeout /t 5 /nobreak >nul
)

:: ----------------------------------------------------------
:: 3. VERIFY BASE MODEL
:: ----------------------------------------------------------
ECHO.
ECHO [3/6] Verifying Base Model (qwen3:8b)...
ollama list | findstr "qwen3:8b" >nul
IF %ERRORLEVEL% NEQ 0 (
    ECHO       Base model not found. Pulling qwen3:8b...
    ollama pull qwen3:8b
) ELSE (
    ECHO       Base model found.
)

:: ----------------------------------------------------------
:: 4. VERIFY CUSTOM MODELS
:: ----------------------------------------------------------
ECHO.
ECHO [4/6] Verifying Custom Models...

REM Check RAG Model
ollama list | findstr "qwen3:rag" >nul
IF %ERRORLEVEL% NEQ 0 (
    ECHO       Creating 'qwen3:rag' from Modelfile...
    IF EXIST "models\Modelfile_rag" (
        ollama create qwen3:rag -f models\Modelfile_rag
    ) ELSE (
        ECHO       WARNING: models\Modelfile_rag missing!
    )
) ELSE (
    ECHO       Model 'qwen3:rag' is ready.
)

REM Check Summarizer Model
ollama list | findstr "qwen3:sum" >nul
IF %ERRORLEVEL% NEQ 0 (
    ECHO       Creating 'qwen3:sum' from Modelfile...
    IF EXIST "models\Modelfile_sum" (
        ollama create qwen3:sum -f models\Modelfile_sum
    ) ELSE (
        ECHO       WARNING: models\Modelfile_sum missing!
    )
) ELSE (
    ECHO       Model 'qwen3:sum' is ready.
)

:: ----------------------------------------------------------
:: 5. START DOCKER SERVICES
:: ----------------------------------------------------------
ECHO.
ECHO [5/6] Starting Application Services...
docker-compose up -d
IF %ERRORLEVEL% NEQ 0 (
    ECHO.
    ECHO       ERROR: Docker Compose failed.
    PAUSE
    EXIT /B
)

:: ----------------------------------------------------------
:: 6. LAUNCH FRONTEND
:: ----------------------------------------------------------
ECHO.
ECHO [6/6] Launching Web Interface...
timeout /t 3 /nobreak >nul
start "" "http://localhost:3000"

ECHO.
ECHO ========================================================
ECHO   System is running!
ECHO   - Frontend: http://localhost:3000
ECHO.
ECHO   Press any key to STOP all services and exit.
ECHO ========================================================
PAUSE >nul

ECHO.
ECHO Stopping services...
docker-compose stop