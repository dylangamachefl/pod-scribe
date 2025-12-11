@echo off
REM ========================================================================
REM DEPRECATED: This script is no longer used
REM ========================================================================
REM The transcription worker now runs via Docker instead of conda.
REM Use the web dashboard "Run Transcription" button at http://localhost:3000
REM 
REM Docker command equivalent:
REM   docker-compose run --rm transcription-worker
REM ========================================================================

echo.
echo ========================================================================
echo   DEPRECATED: This script is no longer maintained
echo ========================================================================
echo   The transcription service now runs in Docker.
echo   Please use the web dashboard to trigger transcriptions:
echo     1. Open http://localhost:3000
echo     2. Go to Dashboard
echo     3. Click "Run Transcription" button
echo.
echo   For manual Docker execution:
echo     docker-compose run --rm transcription-worker
echo ========================================================================
echo.
pause
exit /b 1
