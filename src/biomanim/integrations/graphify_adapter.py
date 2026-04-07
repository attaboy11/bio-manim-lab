"""Graphify importer (optional).

The blueprint is explicit:
  - Graphify may *enrich* extraction but never replace concept_map.json.
  - Imported edges must be tagged low-confidence until confirmed by the
    app's own extraction stage or by explicit source support.

This adapter reads a `graph.json` and an optional `GRAPH_REPORT.md` from a
Graphify output folder, normalises edges into our CausalEdge schema with
confidence='low', and writes them to `imports/graphify_edges.json` inside
the current run directory. The extract stage can then merge them.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import CausalEdge
from ..utils.io import ensure_dir, run_dir, write_json


def import_graphify(*, graphify_path: str, run_id: str) -> Path:
    src = Path(graphify_path).expanduser().resolve()
    graph_json = src / "graph.json"
    if not graph_json.exists():
        raise FileNotFoundError(f"graph.json not found in {src}")

    raw = json.loads(graph_json.read_text(encoding="utf-8"))
    edges = []
    for e in raw.get("edges", []):
        edges.append(
            CausalEdge(
                source=str(e.get("source") or e.get("src") or e.get("from") or ""),
                target=str(e.get("target") or e.get("dst") or e.get("to") or ""),
                relation=str(e.get("relation") or e.get("type") or "related"),
                note=e.get("note") or "imported from Graphify",
                confidence="low",
            )
        )
    out_dir = ensure_dir(run_dir(run_id) / "imports")
    out = write_json(out_dir / "graphify_edges.json",
                     [e.model_dump(mode="json") for e in edges])
    report = src / "GRAPH_REPORT.md"
    if report.exists():
        (out_dir / "GRAPH_REPORT.md").write_text(report.read_text(encoding="utf-8"),
                                                 encoding="utf-8")
    return out
