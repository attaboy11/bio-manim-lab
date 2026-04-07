"""Pedagogy stage.

Turns a ConceptMap into a structured LessonOutline that follows the canonical
teaching skeleton (orientation → parts → mechanism → driving logic →
regulation/failure → relevance). Also writes a markdown twin for human reading.
"""

from __future__ import annotations

from ..models import ConceptMap, LessonOutline
from ..utils.io import run_dir, write_json, write_text
from ..utils.llm import call_structured


def plan(*, concept_map: ConceptMap, run_id: str) -> LessonOutline:
    outline = call_structured(
        prompt_path="pedagogy/lesson_outline.md",
        user_inputs={"concept_map": concept_map.model_dump(mode="json")},
        schema=LessonOutline,
        topic=concept_map.topic,
        artifact_name="lesson_outline.json",
    )
    rd = run_dir(run_id)
    write_json(rd / "lesson_outline.json", outline.model_dump(mode="json"))
    write_text(rd / "lesson_outline.md", _to_markdown(outline))
    return outline


def _to_markdown(o: LessonOutline) -> str:
    lines = [f"# {o.topic} — Lesson outline", ""]
    lines += ["## One-paragraph intuition", "", o.one_paragraph_intuition, ""]
    lines += ["## Mechanism in steps", ""]
    lines += [f"{i+1}. {step}" for i, step in enumerate(o.mechanism_steps)]
    lines += ["", "## Why it matters", "", o.why_it_matters, ""]
    lines += ["## Common confusions", ""]
    lines += [f"- {c}" for c in o.common_confusions]
    lines += ["", "## Checkpoint questions", ""]
    lines += [f"- {q}" for q in o.checkpoint_questions]
    lines += ["", "## Key takeaways", ""]
    lines += [f"- {k}" for k in o.key_takeaways]
    lines += [""]
    return "\n".join(lines)
