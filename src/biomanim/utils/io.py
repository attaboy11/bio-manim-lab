"""Filesystem helpers. Every stage writes to disk through these."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .._compat import safe_load_yaml, slugify as _slugify


def slugify(text: str, max_length: int | None = None) -> str:
    return _slugify(text, max_length=max_length)

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = REPO_ROOT / "prompts"
EXAMPLES_DIR = REPO_ROOT / "examples"
CONFIGS_DIR = REPO_ROOT / "configs"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "outputs"


def slug(topic: str) -> str:
    return _slugify(topic, max_length=64)


def now_run_id(topic: str) -> str:
    return f"{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{slug(topic)}"


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_json(path: Path, data: Any) -> Path:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> Path:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")
    return path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_yaml(path: Path) -> dict:
    return safe_load_yaml(path.read_text(encoding="utf-8")) or {}


def load_default_config() -> dict:
    return load_yaml(CONFIGS_DIR / "default.yaml")


def load_models_config() -> dict:
    return load_yaml(CONFIGS_DIR / "models.yaml")


def load_styles_config() -> dict:
    return load_yaml(CONFIGS_DIR / "styles.yaml")


def output_root() -> Path:
    env = os.environ.get("BIOMANIM_OUTPUT_ROOT")
    if env:
        return Path(env)
    return DEFAULT_OUTPUT_ROOT


def run_dir(run_id: str) -> Path:
    return ensure_dir(output_root() / run_id)


def find_run(run_id: str) -> Path:
    candidate = output_root() / run_id
    if not candidate.exists():
        raise FileNotFoundError(f"Run not found: {run_id} (looked in {candidate})")
    return candidate


def latest_run_dir() -> Path | None:
    root = output_root()
    if not root.exists():
        return None
    subdirs = [p for p in root.iterdir() if p.is_dir()]
    if not subdirs:
        return None
    return max(subdirs, key=lambda p: p.stat().st_mtime)
