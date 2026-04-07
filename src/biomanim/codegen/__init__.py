"""Codegen stage.

Generates an executable Manim script from a ScenePlan. The default behaviour
is to look for a hand-crafted golden script in `examples/<slug>/manim_script.py`
and use that. Otherwise it asks the LLM to write one (using prompts/codegen/).

Either way, we write the file to disk and let the render stage actually run it.
"""

from __future__ import annotations

from pathlib import Path

from ..models import ScenePlan
from ..utils.io import EXAMPLES_DIR, run_dir, slug, write_text
from ..utils.llm import call_text


def codegen(*, scene_plan: ScenePlan, run_id: str) -> Path:
    topic = scene_plan.topic
    golden = EXAMPLES_DIR / slug(topic).replace("-", "_") / "manim_script.py"
    rd = run_dir(run_id)
    out = rd / "manim_script.py"

    if golden.exists():
        out.write_text(golden.read_text(encoding="utf-8"), encoding="utf-8")
        return out

    code = call_text(
        prompt_path="codegen/manim_generator.md",
        user_inputs={"scene_plan": scene_plan.model_dump(mode="json")},
        topic=topic,
        artifact_name="manim_script.py",
    )
    code = _sanitize(code)
    write_text(out, code)
    return out


def _sanitize(code: str) -> str:
    s = code.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[: -3]
    return s.strip() + "\n"
