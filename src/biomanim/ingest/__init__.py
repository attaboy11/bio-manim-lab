"""Ingest stage.

Normalises a topic string, pasted notes, or a local text file into a single
canonical input dict that downstream stages consume.
"""

from __future__ import annotations

from pathlib import Path

from ..utils.io import write_json, run_dir


def ingest(
    *,
    topic: str | None,
    input_path: str | None,
    notes: str | None = None,
    run_id: str,
) -> dict:
    if not topic and not input_path and not notes:
        raise ValueError("ingest requires a topic, notes, or --input")

    note_text = (notes or "").strip()
    source = "topic"
    if input_path:
        p = Path(input_path).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"Input file not found: {p}")
        note_text = p.read_text(encoding="utf-8")
        source = f"file:{input_path}"
        if not topic:
            # Use the first non-blank line as a working topic.
            topic = next((ln.strip() for ln in note_text.splitlines() if ln.strip()), p.stem)
    elif note_text and not topic:
        topic = next((ln.strip() for ln in note_text.splitlines() if ln.strip()), "Untitled biology notes")
        source = "notes"
    elif note_text:
        source = "topic+notes"

    payload = {
        "topic": (topic or "").strip(),
        "notes": note_text,
        "source": source,
    }
    write_json(run_dir(run_id) / "ingest.json", payload)
    return payload
