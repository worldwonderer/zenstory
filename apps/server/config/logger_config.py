"""
Logging configuration module for zenstory API.

Provides structured JSON logging configuration for Railway deployment.
"""

import json
import logging
import os
import sys

from config.datetime_utils import utcnow


class JsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Formats log records as JSON objects with consistent schema.
    Compatible with Railway's log collection system.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string."""
        log_obj = {
            "timestamp": utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            # Add extra context for better debugging
            "service": os.getenv("APP_NAME", "zenstory API"),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "version": os.getenv("APP_VERSION", "1.0.0"),
        }

        # Add code location info
        log_obj["file"] = f"{record.pathname}"
        log_obj["line"] = record.lineno
        log_obj["function"] = record.funcName

        # Add custom fields if present
        if hasattr(record, "custom_fields") and record.custom_fields:
            log_obj.update(record.custom_fields)

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # Add stack trace if present
        if record.stack_info:
            log_obj["stack"] = self.formatStack(record.stack_info)

        return json.dumps(log_obj, ensure_ascii=False, default=str)


def configure_logging() -> None:
    """
    Configure root logger with JSON formatter.

    Reads LOG_LEVEL from environment variable (default: INFO).
    Configures stream handler to output to stdout.
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Validate log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level not in valid_levels:
        log_level = "INFO"

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create stream handler (output to stdout for Railway)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)

    # Set JSON formatter
    formatter = JsonFormatter()
    stream_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(stream_handler)

    # Prevent log propagation from Uvicorn's access logger
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False

    # Set log level for common third-party libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


# Auto-configure logging on module import
configure_logging()
