"""Logging configuration for Knowledge Activation System."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def configure_logging(
    level: int = logging.INFO,
    log_file: str | Path | None = None,
    json_format: bool = False,
) -> None:
    """
    Configure application logging.

    Args:
        level: Logging level (default: INFO)
        log_file: Optional file path for log output
        json_format: Use JSON format for structured logging
    """
    handlers: list[logging.Handler] = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if json_format:
        # JSON format for production
        console_format = (
            '{"time":"%(asctime)s","level":"%(levelname)s",'
            '"logger":"%(name)s","message":"%(message)s"}'
        )
    else:
        # Human-readable format for development
        console_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    console_handler.setFormatter(logging.Formatter(console_format, datefmt="%Y-%m-%d %H:%M:%S"))
    handlers.append(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True,  # Override any existing configuration
    )

    # Set levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)
