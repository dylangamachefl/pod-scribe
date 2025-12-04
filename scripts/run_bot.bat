@echo off
REM ========================================================================
REM Podcast Transcription Bot - Windows Task Scheduler Launcher
REM ========================================================================
REM This script activates the Conda environment and runs the transcription
REM pipeline. Designed for use with Windows Task Scheduler.
REM ========================================================================

echo.
echo ========================================================================
echo   Podcast Transcription Bot
echo   Starting automated transcription run...
echo ========================================================================
echo.

REM Save current directory
set ORIGINAL_DIR=%CD%

REM Hardcoded to your Miniconda installation
set CONDA_PATH=C:\Users\Dylan\miniconda3

REM Verify Conda was found
if not exist "%CONDA_PATH%\Scripts\activate.bat" (
    echo ERROR: Could not locate Conda installation!
    echo Searched locations:
    echo   - %USERPROFILE%\anaconda3
    echo   - %USERPROFILE%\miniconda3
    echo   - C:\ProgramData\anaconda3
    echo   - C:\ProgramData\miniconda3
    echo.
    echo Please edit run_bot.bat and set CONDA_PATH manually.
    pause
    exit /b 1
)

echo Found Conda at: %CONDA_PATH%
echo.

REM Change to project root directory (script is in scripts/ folder)
cd /d "%~dp0.."
echo Working directory: %CD%
echo.

REM Initialize Conda for batch
call "%CONDA_PATH%\Scripts\activate.bat"

REM Activate podcast_bot environment
echo Activating podcast_bot environment...
call conda activate podcast_bot

if errorlevel 1 (
    echo ERROR: Failed to activate conda environment 'podcast_bot'
    echo Make sure the environment exists:
    echo   conda env create -f environment.yml
    pause
    exit /b 1
)

echo Environment activated successfully
echo.

REM Clear Python cache to ensure latest code is used
if exist transcription-service\src\__pycache__ (
    echo Clearing Python cache...
    rmdir /s /q transcription-service\src\__pycache__
)

REM Run the transcription pipeline
echo Starting transcription pipeline...
echo.

REM Prevent Python from caching bytecode
set PYTHONDONTWRITEBYTECODE=1
python transcription-service\src\cli.py

REM Capture exit code
set PIPELINE_EXIT=%ERRORLEVEL%

echo.
if %PIPELINE_EXIT% equ 0 (
    echo ========================================================================
    echo   Transcription completed successfully!
    echo ========================================================================
) else (
    echo ========================================================================
    echo   WARNING: Transcription exited with code %PIPELINE_EXIT%
    echo ========================================================================
)

REM Deactivate environment
call conda deactivate

REM Return to original directory
cd /d "%ORIGINAL_DIR%"

REM Log timestamp
echo Run completed at %date% %time% >> shared\logs\run_history.log

echo.
REM Uncomment the line below if running manually (prevents window from closing)
pause

exit /b %PIPELINE_EXIT%
