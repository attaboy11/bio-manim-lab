"""End-to-end smoke test.

Runs the full pipeline on the canonical ATP synthase topic with the golden
provider, and checks that every expected artifact lands on disk.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from biomanim.cli import app


def test_run_atp_synthase(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BIOMANIM_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.setenv("BIOMANIM_LLM_PROVIDER", "golden")
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--topic", "ATP synthase and oxidative phosphorylation"])
    assert result.exit_code == 0, result.output

    runs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(runs) == 1
    rd = runs[0]

    expected = [
        "ingest.json",
        "concept_map.json",
        "lesson_outline.json",
        "lesson_outline.md",
        "scene_plan.json",
        "narration.md",
        "manim_script.py",
        "study/summary.md",
        "study/flashcards.json",
        "study/quiz.json",
        "run_manifest.json",
    ]
    for rel in expected:
        assert (rd / rel).exists(), f"missing artifact: {rel}"

    manifest = json.loads((rd / "run_manifest.json").read_text())
    assert "extract" in manifest["stages_completed"]
    assert "scenes" in manifest["stages_completed"]
    # render is allowed to be missing if Manim is not installed.
    assert manifest["topic"].startswith("ATP synthase")
