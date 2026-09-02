"""
shared.py – Shared utilities for the GitHub profile README generator.

Provides config loading from YAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# ─── Project root (directory containing this file's parent) ──────────────────
_SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _SCRIPTS_DIR.parent


# ═══════════════════════════════════════════════════════════════════════════════
#  Config loading
# ═══════════════════════════════════════════════════════════════════════════════

def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load and return the YAML configuration dictionary.

    Args:
        path: Optional explicit path.  Defaults to ``<project_root>/config.yaml``.

    Returns:
        Parsed config as a plain Python dict.
    """
    config_path = Path(path) if path else PROJECT_ROOT / "config.yaml"
    with config_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
