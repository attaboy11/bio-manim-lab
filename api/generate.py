"""Vercel Python serverless function: runs the bio-manim-lab pipeline
and returns all artifacts as JSON.

POST /api/generate
Body: { "topic": "ATP synthase and oxidative phosphorylation" }
Returns: { ok, run_id, artifacts: { concept_map, lesson_outline_md, scene_plan,
           narration_md, manim_script, study: { summary_md, flashcards, quiz },
           run_manifest } }
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# Vercel deploys this file as api/generate.py. The biomanim package lives in
# ../src/biomanim relative to this file. Add it to sys.path.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

# All pipeline disk writes go to /tmp on Vercel (the only writable dir).
os.environ.setdefault("BIOMANIM_OUTPUT_ROOT", "/tmp/biomanim-runs")

from biomanim.utils.runtime import load_dotenv_if_present  # noqa: E402

load_dotenv_if_present()

from biomanim.ingest import ingest as do_ingest  # noqa: E402
from biomanim.extract import extract as do_extract  # noqa: E402
from biomanim.pedagogy import plan as do_plan  # noqa: E402
from biomanim.scenes import plan_scenes as do_plan_scenes  # noqa: E402
from biomanim.codegen import codegen as do_codegen  # noqa: E402
from biomanim.study import build_study as do_study  # noqa: E402
from biomanim.supervisor import Supervisor  # noqa: E402
from biomanim.utils.io import run_dir, now_run_id, load_default_config  # noqa: E402
from biomanim.utils.llm import artifact_strategy  # noqa: E402


def _read(rd: Path, name: str, kind: str = "text"):
    p = rd / name
    if not p.exists():
        return None
    if kind == "json":
        return json.loads(p.read_text(encoding="utf-8"))
    return p.read_text(encoding="utf-8")


def _require_stage(stage_name: str, value, sup: Supervisor):
    if value is not None:
        return value
    for result in reversed(sup.results):
        if result.name == stage_name:
            raise RuntimeError(f"{stage_name} failed: {result.error or 'unknown error'}")
    raise RuntimeError(f"{stage_name} failed")


def run_pipeline(topic: str | None, notes: str | None) -> dict:
    cfg = load_default_config()
    run_id = now_run_id((topic or notes or "biology-notes").strip())
    rd = run_dir(run_id)
    sup = Supervisor(
        timeout_seconds=int(cfg["llm"].get("timeout_seconds", 120)),
        max_retries=int(cfg["llm"].get("max_retries", 1)),
        fail_fast=True,
    )

    payload = _require_stage(
        "ingest",
        sup.run("ingest", lambda: do_ingest(topic=topic, notes=notes, input_path=None, run_id=run_id)),
        sup,
    )
    cm = _require_stage("extract", sup.run("extract", lambda: do_extract(ingest_payload=payload, run_id=run_id)), sup)
    outline = _require_stage("pedagogy", sup.run("pedagogy", lambda: do_plan(concept_map=cm, run_id=run_id)), sup)
    scene_plan = _require_stage(
        "scenes",
        sup.run("scenes", lambda: do_plan_scenes(concept_map=cm, lesson_outline=outline, run_id=run_id)),
        sup,
    )
    _require_stage("codegen", sup.run("codegen", lambda: do_codegen(scene_plan=scene_plan, run_id=run_id)), sup)
    _require_stage("study", sup.run("study", lambda: do_study(concept_map=cm, lesson_outline=outline, run_id=run_id)), sup)

    return {
        "ok": True,
        "run_id": run_id,
        "topic": payload["topic"],
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "input_source": payload["source"],
        "generation_mode": artifact_strategy(payload["topic"], "concept_map.json"),
        "artifacts": {
            "concept_map": _read(rd, "concept_map.json", "json"),
            "lesson_outline_md": _read(rd, "lesson_outline.md"),
            "lesson_outline": _read(rd, "lesson_outline.json", "json"),
            "scene_plan": _read(rd, "scene_plan.json", "json"),
            "narration_md": _read(rd, "narration.md"),
            "manim_script": _read(rd, "manim_script.py"),
            "study": {
                "summary_md": _read(rd, "study/summary.md"),
                "flashcards": _read(rd, "study/flashcards.json", "json"),
                "quiz": _read(rd, "study/quiz.json", "json"),
            },
        },
    }


class handler(BaseHTTPRequestHandler):  # noqa: N801 — Vercel expects this name
    def _send(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, {})

    def do_GET(self) -> None:  # noqa: N802
        self._send(200, {
            "ok": True,
            "service": "bio-manim-lab",
            "usage": "POST /api/generate with JSON body {\"topic\": \"...\", \"notes\": \"optional pasted notes\"}",
        })

    def do_POST(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                return self._send(400, {"ok": False, "error": "invalid JSON body"})

            topic = (body.get("topic") or "").strip()
            notes = (body.get("notes") or "").strip()
            if not topic and not notes:
                return self._send(400, {"ok": False, "error": "missing 'topic' or 'notes'"})
            if len(topic) > 200:
                return self._send(400, {"ok": False, "error": "topic too long (max 200 chars)"})
            if len(notes) > 12000:
                return self._send(400, {"ok": False, "error": "notes too long (max 12000 chars)"})

            result = run_pipeline(topic or None, notes or None)
            return self._send(200, result)
        except Exception as e:  # noqa: BLE001
            return self._send(500, {
                "ok": False,
                "error": str(e),
                "type": type(e).__name__,
                "trace": traceback.format_exc().splitlines()[-8:],
            })
