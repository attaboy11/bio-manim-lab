"""Render stage.

Runs Manim on the codegen output. If Manim is not installed, this stage
writes a stub note to render/STATUS.md and returns gracefully — the rest
of the pipeline (study assets) is still useful and the manim_script.py
can be rendered later by the user.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..utils.io import ensure_dir, run_dir, write_text


def render(*, run_id: str, quality: str = "low_quality") -> Path | None:
    rd = run_dir(run_id)
    script = rd / "manim_script.py"
    render_dir = ensure_dir(rd / "render")

    if not script.exists():
        write_text(render_dir / "STATUS.md", f"manim_script.py missing in {rd}\n")
        return None

    if shutil.which("manim") is None:
        write_text(
            render_dir / "STATUS.md",
            "Manim CLI not found on PATH. Install with `pip install manim` "
            "and re-run `python -m biomanim render --run "
            f"{run_id}`. The rest of the pipeline is unaffected.\n",
        )
        return None

    quality_flag = {
        "low_quality": "-ql",
        "medium_quality": "-qm",
        "high_quality": "-qh",
        "production_quality": "-qp",
    }.get(quality, "-ql")

    cmd = [
        "manim",
        quality_flag,
        "--media_dir", str(render_dir),
        "--output_file", "final",
        str(script),
        "BioScene",
    ]
    try:
        subprocess.run(cmd, check=True, cwd=str(rd))
    except subprocess.CalledProcessError as e:
        write_text(render_dir / "STATUS.md", f"Manim render failed: {e}\n")
        raise

    final = _find_final_mp4(render_dir)
    if final is not None and final.name != "final.mp4":
        # Normalise the location so callers can rely on render/final.mp4.
        target = render_dir / "final.mp4"
        try:
            shutil.copy2(final, target)
            return target
        except OSError:
            return final
    return final


def _find_final_mp4(render_dir: Path) -> Path | None:
    for p in render_dir.rglob("*.mp4"):
        return p
    return None
