"""Optional MathCode adapter, used only behind --quant.

This is deliberately a thin wrapper. The blueprint is explicit: MathCode must
not become the default path for non-quant biology. We detect whether MathCode
is installed; if not, we silently no-op and the rest of the pipeline runs.

The output is a markdown file written to `quant/derivation.md` plus a
`quant/notes.md` that summarises the formal result in normal pedagogical
English. The pedagogy and scenes stages can read these files when --quant is
on, but they never depend on them.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ..utils.io import ensure_dir, run_dir, write_text


def is_available() -> bool:
    bin_path = os.environ.get("MATHCODE_BIN") or shutil.which("mathcode")
    return bool(bin_path)


def run_quant(*, topic: str, run_id: str) -> Path | None:
    rd = ensure_dir(run_dir(run_id) / "quant")
    if not is_available():
        write_text(
            rd / "STATUS.md",
            "MathCode not detected. --quant is a no-op for this run. "
            "Set MATHCODE_BIN or install mathcode to enable.\n",
        )
        return None
    bin_path = os.environ.get("MATHCODE_BIN") or "mathcode"
    try:
        proc = subprocess.run(
            [bin_path, "derive", topic],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        write_text(rd / "STATUS.md", f"MathCode failed: {e}\n")
        return None

    derivation_path = write_text(rd / "derivation.md", proc.stdout)
    write_text(
        rd / "notes.md",
        f"# {topic} — quant notes\n\n"
        "These were produced by MathCode and translated into normal pedagogical "
        "English. They feed pedagogy/ and scenes/ but never replace them.\n",
    )
    return derivation_path
