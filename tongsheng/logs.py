"""Logging setup: rotating file + console, never crashes the tray."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def setup_logging(log_dir: str | Path | None, level: str = "INFO") -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger("tongsheng")
    if _CONFIGURED:
        return logger
    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    if log_dir:
        try:
            target = Path(log_dir)
            target.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(target / "app.log", maxBytes=4 * 1024 * 1024,
                                          backupCount=4, encoding="utf-8")
            handler.setFormatter(fmt)
            logger.addHandler(handler)
        except OSError:
            pass

    logger.propagate = False
    _CONFIGURED = True
    return logger


def get_logger(name: str = "tongsheng") -> logging.Logger:
    if name == "tongsheng":
        return logging.getLogger("tongsheng")
    return logging.getLogger(f"tongsheng.{name}")
