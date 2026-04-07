"""Scenes stage.

Maps the LessonOutline + ConceptMap into a ScenePlan: a list of scenes, each
with a teaching_goal, biological_claims, visual_strategy, animation_steps,
labels, narration_segment, and estimated_duration.
"""

from __future__ import annotations

from ..models import ConceptMap, LessonOutline, ScenePlan
from ..utils.io import run_dir, write_json, write_text
from ..utils.llm import call_structured


def plan_scenes(
    *, concept_map: ConceptMap, lesson_outline: LessonOutline, run_id: str
) -> ScenePlan:
    sp = call_structured(
        prompt_path="scenes/scene_planner.md",
        user_inputs={
            "concept_map": concept_map.model_dump(mode="json"),
            "lesson_outline": lesson_outline.model_dump(mode="json"),
        },
        schema=ScenePlan,
        topic=concept_map.topic,
        artifact_name="scene_plan.json",
    )
    rd = run_dir(run_id)
    write_json(rd / "scene_plan.json", sp.model_dump(mode="json"))
    # Narration is just the concatenation of scene narration segments,
    # newline-separated. The codegen stage uses scene_plan; humans read this.
    narration = _build_narration(sp)
    write_text(rd / "narration.md", narration)
    return sp


def _build_narration(sp: ScenePlan) -> str:
    parts = [f"# {sp.topic} — Narration", ""]
    for s in sp.scenes:
        parts.append(f"## Scene {s.id}: {s.title}  *(~{s.estimated_duration:.0f}s)*")
        parts.append("")
        parts.append(s.narration_segment)
        parts.append("")
    return "\n".join(parts)
