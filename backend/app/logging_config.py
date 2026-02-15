"""
Structured logging configuration for I-ASCAP API.
Optimized for Render stdout and easy parsing.
"""

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import wraps

# Context variable for request tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request ID if available
        request_id = request_id_var.get()
        if request_id:
            log_entry["request_id"] = request_id

        # Add extra fields
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms  # type: ignore
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code  # type: ignore
        if hasattr(record, "method"):
            log_entry["method"] = record.method  # type: ignore
        if hasattr(record, "path"):
            log_entry["path"] = record.path  # type: ignore
        if hasattr(record, "query_time_ms"):
            log_entry["query_time_ms"] = record.query_time_ms  # type: ignore
        if hasattr(record, "rows_affected"):
            log_entry["rows_affected"] = record.rows_affected  # type: ignore

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)  # type: ignore

        return json.dumps(log_entry)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure application-wide structured logging."""

    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(console_handler)

    # Create specific loggers
    loggers = [
        "app",
        "app.api",
        "app.database",
        "app.services",
        "uvicorn",
        "uvicorn.access",
    ]

    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(f"app.{name}")


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())[:8]  # type: ignore


def set_request_id(request_id: str) -> None:
    """Set the current request ID."""
    request_id_var.set(request_id)


def get_request_id() -> str:
    """Get the current request ID."""
    return request_id_var.get()


def log_database_query(query: str, duration_ms: float, rows: int = 0) -> None:
    """Log a database query with timing."""
    logger = get_logger("database")

    # Truncate long queries
    query_preview = query[:200] + "..." if len(query) > 200 else query  # type: ignore

    extra = {
        "query_time_ms": round(float(duration_ms), 2),  # type: ignore
        "rows_affected": rows,
    }

    if duration_ms > 1000:  # Slow query warning
        logger.warning(f"Slow query ({duration_ms:.0f}ms): {query_preview}", extra=extra)
    else:
        logger.debug(f"Query executed: {query_preview}", extra=extra)


def log_api_request(method: str, path: str, status_code: int, duration_ms: float, client_ip: str | None = None) -> None:
    """Log an API request with timing."""
    logger = get_logger("api")

    extra = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(float(duration_ms), 2),  # type: ignore
    }

    level = logging.INFO
    if status_code >= 500:
        level = logging.ERROR
    elif status_code >= 400:
        level = logging.WARNING

    logger.log(level, f"{method} {path} -> {status_code} ({duration_ms:.0f}ms)", extra=extra)


def timed_operation(operation_name: str):
    """Decorator to log operation timing."""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger("operations")
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                logger.debug(f"{operation_name} completed in {duration:.0f}ms")
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                logger.error(f"{operation_name} failed after {duration:.0f}ms: {str(e)}")
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger("operations")
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                logger.debug(f"{operation_name} completed in {duration:.0f}ms")
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                logger.error(f"{operation_name} failed after {duration:.0f}ms: {str(e)}")
                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
