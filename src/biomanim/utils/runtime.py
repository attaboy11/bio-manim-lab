"""Runtime helpers for environment-driven configuration."""

from __future__ import annotations

import os
from pathlib import Path

_DOTENV_LOADED = False


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def dotenv_path() -> Path:
    override = os.environ.get("BIOMANIM_DOTENV_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return repo_root() / ".env"


def load_dotenv_if_present(*, override: bool = False) -> None:
    """Populate os.environ from `.env` once, without requiring python-dotenv."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return

    path = dotenv_path()
    if not path.exists():
        _DOTENV_LOADED = True
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if override or key not in os.environ:
            os.environ[key] = value

    _DOTENV_LOADED = True
