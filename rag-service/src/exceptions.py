"""
Custom exceptions for the RAG service.
Provides clear error handling and messages for different failure scenarios.
"""


class RAGServiceError(Exception):
    """Base exception for all RAG service errors."""
    
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationError(RAGServiceError):
    """Raised when configuration is invalid or missing."""
    pass


class EmbeddingError(RAGServiceError):
    """Raised when embedding generation fails."""
    pass


class VectorDBError(RAGServiceError):
    """Raised when Qdrant operations fail."""
    pass


class GeminiAPIError(RAGServiceError):
    """Raised when Gemini API calls fail."""
    pass


class FileProcessingError(RAGServiceError):
    """Raised when transcript file processing fails."""
    pass


class ChunkingError(RAGServiceError):
    """Raised when text chunking fails."""
    pass


def format_error_response(error: RAGServiceError) -> dict:
    """Format error for API response.
    
    Args:
        error: RAG service error
        
    Returns:
        Dict with error information suitable for JSON API response
    """
    return {
        "error": error.__class__.__name__,
        "message": error.message,
        "details": error.details
    }
