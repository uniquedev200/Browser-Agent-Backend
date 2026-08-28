from __future__ import annotations

import logging
import sys
from typing import Any


def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("browserauto")
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logger.level)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    return logger


def log_request(
    logger: logging.Logger,
    *,
    session_id: str,
    page_url: str = "",
    element_count: int = 0,
    action_count: int = 0,
    phase: str = "",
    latency_ms: float = 0.0,
    extra: dict[str, Any] | None = None,
) -> None:
    parts = [
        f"session={session_id}",
        f"page={page_url}",
        f"elements={element_count}",
        f"action_count={action_count}",
        f"phase={phase}",
        f"latency_ms={latency_ms:.1f}",
    ]
    if extra:
        for k, v in extra.items():
            parts.append(f"{k}={v}")
    logger.info(" | ".join(parts))
