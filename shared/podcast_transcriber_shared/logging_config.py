"""
Centralized Logging Configuration for Podcast Transcriber

Provides structured logging with JSON formatting, correlation IDs, and service context.
"""
import os
import sys
import structlog
from typing import Optional


def configure_logging(service_name: str, log_level: Optional[str] = None):
    """
    Configure structured logging for a service.
    
    Args:
        service_name: Name of the service (e.g., "transcription-worker", "rag-service")
        log_level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to INFO.
    """
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")
    
    # Determine if we're in development or production
    is_dev = os.getenv("ENVIRONMENT", "production") == "development"
    
    # Configure structlog processors
    processors = [
        # Add log level
        structlog.stdlib.add_log_level,
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Add service name to all logs
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
        # Stack info for exceptions
        structlog.processors.StackInfoRenderer(),
        # Format exceptions
        structlog.processors.format_exc_info,
    ]
    
    # Add development-friendly console output or production JSON
    if is_dev:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog.stdlib.logging, log_level.upper(), structlog.stdlib.logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Bind service name to all loggers
    structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str = None):
    """
    Get a structured logger instance.
    
    Args:
        name: Optional logger name (typically __name__)
    
    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


def bind_correlation_id(correlation_id: str):
    """
    Bind a correlation ID to the current context.
    
    Args:
        correlation_id: Unique identifier for tracking requests across services
    """
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)


def clear_correlation_id():
    """Clear the correlation ID from the current context."""
    structlog.contextvars.unbind_contextvars("correlation_id")
