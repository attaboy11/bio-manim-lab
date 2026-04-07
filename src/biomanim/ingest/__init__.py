"""Ingest stage.

Normalises a topic string, pasted notes, or a local text file into a single
canonical input dict that downstream stages consume.
"""

from __future__ import annotations

from pathlib import Path

from ..utils.io import write_json, run_dir


def ingest(*, topic: str | None, input_path: str | None, run_id: str) -> dict:
    if not topic and not input_path:
        raise ValueError("ingest requires either --topic or --input")

    notes = ""
    if input_path:
        p = Path(input_path).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"Input file not found: {p}")
        notes = p.read_text(encoding="utf-8")
        if not topic:
            # Use the first non-blank line as a working topic.
            topic = next((ln.strip() for ln in notes.splitlines() if ln.strip()), p.stem)

    payload = {
        "topic": (topic or "").strip(),
        "notes": notes,
        "source": "topic" if not input_path else f"file:{input_path}",
    }
    write_json(run_dir(run_id) / "ingest.json", payload)
    return payload
