#!/usr/bin/env python3
"""
Podcast Transcription Engine - Backward Compatibility Wrapper
This file provides backward compatibility for scripts that call main.py directly.
The actual implementation has been refactored into modular components.

For the new modular structure, see:
- cli.py: Main CLI entry point
- config.py: Configuration management
- core/audio.py: Audio download and transcription
- core/diarization.py: Speaker identification
- core/formatting.py: Text formatting utilities
- core/processor.py: High-level episode processing
"""

# Simply import and call the CLI
from cli import main

if __name__ == "__main__":
    main()
