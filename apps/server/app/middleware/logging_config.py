"""Structured logging configuration using structlog.

Provides JSON output in production, console-colored output in dev.
Sensitive fields are redacted before emission.

Call ``configure_logging()`` once at startup from main.py.
"""

import logging
import sys

import structlog

from app.config import settings

# Fields that must never appear in logs in cleartext
_SENSITIVE_KEYS = frozenset({
    "api_key",
    "encrypted_api_key",
    "token",
    "authorization",
    "password",
    "secret",
    "github_token",
})


def _redact_processor(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict,
) -> dict:
    """Redact sensitive fields from log event dicts."""
    for key in _SENSITIVE_KEYS:
        if key in event_dict:
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging() -> None:
    """Configure structlog and stdlib logging for the application.

    - JSON renderer when LOG_FORMAT=json (production default)
    - Console renderer when LOG_FORMAT=console (development)
    - Integrates structlog with stdlib logging so third-party libraries
      also emit structured logs.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Choose renderer based on config
    if settings.LOG_FORMAT == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    # Shared processors for both structlog and stdlib
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _redact_processor,
    ]

    # Configure structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog formatting
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Quiet down noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DEBUG else logging.WARNING
    )
