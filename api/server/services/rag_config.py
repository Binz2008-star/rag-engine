"""Read-only RAG runtime config loader.

Reads ``data/rag_runtime_config.json`` on every call — no global cache.
The admin dashboard (``admin_routes.py``) owns writes; this module only reads.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_CONFIG_FILE = Path(__file__).resolve().parents[3] / "data" / "rag_runtime_config.json"

_DEFAULTS: Dict[str, Any] = {
    "top_k": 15,
    "score_threshold": 0.38,
    "max_context_chars": 3000,
    "temperature": 0.2,
    "reranker_enabled": True,
    "grounding_strictness": 0.5,
    "version": 1,
    "updated_at": None,
    "updated_by": None,
    "notes": "",
}


def load_rag_config() -> Dict[str, Any]:
    """Return the current RAG runtime config, merged with defaults.

    Called per-request — never cached globally.
    """
    if not _CONFIG_FILE.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        merged = dict(_DEFAULTS)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("rag_config: failed to load %s: %s", _CONFIG_FILE, exc)
        return dict(_DEFAULTS)


def get_config_version() -> int:
    """Return just the config version number (convenience helper)."""
    return int(load_rag_config().get("version", 1))
