"""Structured logging configuration for the AI automation agent."""

import logging
import sys
from typing import Any, Dict
import structlog
from pythonjsonlogger import jsonlogger

from ..config import settings


def setup_logging():
    """Configure structured logging for the application."""
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper())
    )
    
    # Configure structlog
    if settings.log_format.lower() == "json":
        # JSON logging for production
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    else:
        # Human-readable logging for development
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
                structlog.dev.ConsoleRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def log_api_call(
    logger: structlog.BoundLogger,
    service: str,
    method: str,
    endpoint: str,
    status_code: int,
    response_time_ms: float,
    user_id: int = None,
    **kwargs
):
    """
    Log API call with structured metadata.
    
    Args:
        logger: Structlog logger instance
        service: Service name (slack, jira, etc.)
        method: HTTP method
        endpoint: API endpoint
        status_code: HTTP status code
        response_time_ms: Response time in milliseconds
        user_id: User ID making the request
        **kwargs: Additional context
    """
    logger.info(
        "API call completed",
        service=service,
        method=method,
        endpoint=endpoint,
        status_code=status_code,
        response_time_ms=response_time_ms,
        user_id=user_id,
        **kwargs
    )


def log_automation_action(
    logger: structlog.BoundLogger,
    action_id: int,
    user_id: int,
    command: str,
    status: str,
    duration_ms: int = None,
    error: str = None,
    **kwargs
):
    """
    Log automation action with structured metadata.
    
    Args:
        logger: Structlog logger instance
        action_id: Automation action ID
        user_id: User ID
        command: Original command
        status: Action status
        duration_ms: Execution duration
        error: Error message if failed
        **kwargs: Additional context
    """
    logger.info(
        "Automation action",
        action_id=action_id,
        user_id=user_id,
        command=command,
        status=status,
        duration_ms=duration_ms,
        error=error,
        **kwargs
    )


# Initialize logging on module import
setup_logging() 