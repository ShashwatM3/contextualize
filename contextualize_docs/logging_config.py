"""Structured logging setup for the docs compiler."""

from __future__ import annotations

import logging
import sys


_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def setup_logging(*, verbose: bool = False) -> None:
    """Configure root logger for the ``contextualize_docs`` namespace.

    Parameters
    ----------
    verbose:
        If *True* set level to DEBUG, otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    logger = logging.getLogger("contextualize_docs")
    logger.setLevel(level)
    # Avoid duplicate handlers if called more than once
    if not logger.handlers:
        logger.addHandler(handler)
    logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``contextualize_docs`` namespace."""
    return logging.getLogger(f"contextualize_docs.{name}")
