"""
Custom Exception Classes for Transcription Service
Provides specific exception types for better error handling and debugging.
"""


class TranscriptionError(Exception):
    """Base exception for all transcription-related errors."""
    def __init__(self, message: str, episode_title: str = None, **context):
        self.episode_title = episode_title
        self.context = context
        super().__init__(message)


class DownloadError(TranscriptionError):
    """Raised when audio download fails."""
    def __init__(self, message: str, audio_url: str = None, **context):
        self.audio_url = audio_url
        super().__init__(message, **context)


class AudioProcessingError(TranscriptionError):
    """Raised when audio processing (transcription/diarization) fails."""
    def __init__(self, message: str, audio_file: str = None, **context):
        self.audio_file = audio_file
        super().__init__(message, **context)


class IngestionError(TranscriptionError):
    """Raised when RAG/summarization ingestion fails."""
    def __init__(self, message: str, service_name: str = None, **context):
        self.service_name = service_name
        super().__init__(message, **context)


class ConfigurationError(TranscriptionError):
    """Raised when configuration is invalid or missing."""
    pass


class FileOperationError(TranscriptionError):
    """Raised when file I/O operations fail."""
    def __init__(self, message: str, file_path: str = None, **context):
        self.file_path = file_path
        super().__init__(message, **context)
