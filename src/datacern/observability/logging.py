"""Structured logging for DataCern."""

from __future__ import annotations

import logging
import sys

_configured = False


def get_logger(name: str = "datacern") -> logging.Logger:
    """Return a module logger, configuring the root handler once."""
    global _configured
    if not _configured:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        root = logging.getLogger("datacern")
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        _configured = True
    return logging.getLogger(f"datacern.{name}" if name != "datacern" else name)
