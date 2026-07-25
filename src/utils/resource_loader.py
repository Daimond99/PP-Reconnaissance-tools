"""
Resource Loader — the only component allowed to read resource JSON files.

Business logic must never call open() on a resource file directly; it must
go through load_json() so every resource is read once, cached in memory,
and a missing/malformed file degrades to an empty dict instead of crashing
the wizard (docs/Resource System.md #9).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

RESOURCES_ROOT = Path(__file__).resolve().parent.parent / "resources"

_cache: Dict[str, dict] = {}


def load_json(relative_path: str) -> dict:
    """
    Load a JSON resource file relative to src/resources/, caching the result.

    Example: load_json("wizard/menu.json")

    Returns an empty dict (and logs a warning) if the file is missing or
    malformed — the application must never crash because a resource is gone.
    """
    if relative_path in _cache:
        return _cache[relative_path]

    path = RESOURCES_ROOT / relative_path
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        logger.warning("Resource not found: %s", path)
        data = {}
    except json.JSONDecodeError as exc:
        logger.warning("Malformed resource JSON in %s: %s", path, exc)
        data = {}

    _cache[relative_path] = data
    return data
