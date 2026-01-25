"""Structured logging configuration for Knowledge Seeder."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.logging import RichHandler


class LogFormat(str, Enum):
    """Log output format options."""

    TEXT = "text"       # Human-readable text
    JSON = "json"       # JSON lines for log aggregation
    RICH = "rich"       # Rich console output with colors


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(
        self,
        include_timestamp: bool = True,
        include_context: bool = True,
    ) -> None:
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_context = include_context

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if self.include_timestamp:
            log_data["timestamp"] = datetime.now(timezone.utc).isoformat()

        if self.include_context:
            log_data["module"] = record.module
            log_data["function"] = record.funcName
            log_data["line"] = record.lineno

        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Include extra fields
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "message",
            ):
                # Serialize non-standard types
                try:
                    json.dumps(value)
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)

        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter with context."""

    FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self) -> None:
        super().__init__(fmt=self.FORMAT, datefmt=self.DATE_FORMAT)


def configure_logging(
    level: str = "INFO",
    format: LogFormat = LogFormat.RICH,
    log_file: Path | None = None,
    json_file: Path | None = None,
) -> logging.Logger:
    """Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        format: Console output format
        log_file: Optional file path for text logs
        json_file: Optional file path for JSON logs

    Returns:
        Root logger for the application
    """
    # Get root logger for our package
    logger = logging.getLogger("knowledge_seeder")
    logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    if format == LogFormat.RICH:
        console = Console(stderr=True)
        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=True,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
        )
        console_handler.setLevel(logging.DEBUG)
    elif format == LogFormat.JSON:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(StructuredFormatter())
        console_handler.setLevel(logging.DEBUG)
    else:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(TextFormatter())
        console_handler.setLevel(logging.DEBUG)

    logger.addHandler(console_handler)

    # Optional text file handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(TextFormatter())
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

    # Optional JSON file handler (for log aggregation)
    if json_file:
        json_file.parent.mkdir(parents=True, exist_ok=True)
        json_handler = logging.FileHandler(json_file, encoding="utf-8")
        json_handler.setFormatter(StructuredFormatter())
        json_handler.setLevel(logging.DEBUG)
        logger.addHandler(json_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(f"knowledge_seeder.{name}")


class LogContext:
    """Context manager for adding context to log messages."""

    def __init__(self, logger: logging.Logger, **context: Any) -> None:
        """Initialize log context.

        Args:
            logger: Logger to add context to
            **context: Key-value pairs to add to log records
        """
        self.logger = logger
        self.context = context
        self._old_factory: Any = None

    def __enter__(self) -> "LogContext":
        """Enter context."""
        self._old_factory = logging.getLogRecordFactory()

        context = self.context

        def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
            record = self._old_factory(*args, **kwargs)
            for key, value in context.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context."""
        if self._old_factory:
            logging.setLogRecordFactory(self._old_factory)


class OperationLogger:
    """Logger for tracking operation progress."""

    def __init__(self, logger: logging.Logger, operation: str) -> None:
        """Initialize operation logger.

        Args:
            logger: Base logger
            operation: Operation name
        """
        self.logger = logger
        self.operation = operation
        self.start_time: datetime | None = None
        self.items_processed = 0
        self.items_failed = 0

    def start(self, total_items: int | None = None) -> None:
        """Start operation logging."""
        self.start_time = datetime.now(timezone.utc)
        msg = f"Starting {self.operation}"
        if total_items:
            msg += f" ({total_items} items)"
        self.logger.info(msg)

    def progress(self, current: int, total: int, item: str | None = None) -> None:
        """Log progress update."""
        pct = (current / total * 100) if total > 0 else 0
        msg = f"{self.operation}: {current}/{total} ({pct:.1f}%)"
        if item:
            msg += f" - {item}"
        self.logger.info(msg)

    def item_success(self, item: str, details: str | None = None) -> None:
        """Log successful item processing."""
        self.items_processed += 1
        msg = f"Processed: {item}"
        if details:
            msg += f" - {details}"
        self.logger.debug(msg)

    def item_failure(self, item: str, error: str) -> None:
        """Log failed item processing."""
        self.items_failed += 1
        self.logger.error(f"Failed: {item} - {error}")

    def complete(self) -> None:
        """Log operation completion."""
        if not self.start_time:
            return

        duration = datetime.now(timezone.utc) - self.start_time
        total = self.items_processed + self.items_failed
        success_rate = (self.items_processed / total * 100) if total > 0 else 0

        self.logger.info(
            f"Completed {self.operation}: "
            f"{self.items_processed}/{total} succeeded ({success_rate:.1f}%), "
            f"duration: {duration.total_seconds():.1f}s"
        )
