@echo off
REM ========================================================================
REM Transcription Trigger Listener Service
REM ========================================================================
REM This script starts the host listener service that triggers Docker
REM transcription when requested by the web UI.
REM ========================================================================

echo.
echo ========================================================================
echo   Starting Transcription Trigger Listener
echo ========================================================================
echo.

REM Change to scripts directory
cd /d "%~dp0"

REM Check if Flask is installed
python -c "import flask" 2>nul
if errorlevel 1 (
    echo Installing required dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

REM Start the listener service
echo Starting listener on http://localhost:8080
echo Press Ctrl+C to stop
echo.

python host_listener.py

pause
