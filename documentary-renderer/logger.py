"""Logging setup for the renderer."""

from __future__ import annotations

import logging


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure and return the project logger."""

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")
    return logging.getLogger("documentary_renderer")
