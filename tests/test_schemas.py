"""Schema validation tests. Drift is the failure mode this project fears most."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from biomanim.models import (
    ConceptMap,
    LessonOutline,
    Quiz,
    Scene,
    ScenePlan,
    Flashcard,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "atp_synthase"


def test_concept_map_loads_and_validates():
    cm = ConceptMap.model_validate_json((EXAMPLES / "concept_map.json").read_text())
    assert cm.topic.startswith("ATP synthase")
    assert len(cm.entities) >= 4
    assert len(cm.processes) >= 2
    # Every causal edge must reference a real id (entity or process).
    ids = {e.id for e in cm.entities} | {p.id for p in cm.processes}
    for edge in cm.causal_edges:
        assert edge.source in ids, f"unknown source: {edge.source}"
        assert edge.target in ids, f"unknown target: {edge.target}"


def test_concept_map_unique_ids():
    cm_data = json.loads((EXAMPLES / "concept_map.json").read_text())
    cm_data["entities"].append(cm_data["entities"][0])  # duplicate
    with pytest.raises(ValidationError):
        ConceptMap.model_validate(cm_data)


def test_lesson_outline_loads():
    o = LessonOutline.model_validate_json((EXAMPLES / "lesson_outline.json").read_text())
    assert len(o.mechanism_steps) >= 5
    assert len(o.checkpoint_questions) >= 4


def test_scene_plan_loads_and_validates():
    sp = ScenePlan.model_validate_json((EXAMPLES / "scene_plan.json").read_text())
    assert len(sp.scenes) >= 4
    assert sp.total_estimated_duration > 0
    # Each scene has positive duration and a non-empty narration.
    for s in sp.scenes:
        assert s.estimated_duration > 0
        assert s.narration_segment.strip()
        assert s.animation_steps


def test_scene_rejects_zero_duration():
    with pytest.raises(ValidationError):
        Scene(
            id="x", title="x", teaching_goal="x",
            biological_claims=["x"], visual_strategy="x",
            animation_steps=["x"], labels=[], narration_segment="x",
            estimated_duration=0,
        )


def test_quiz_loads():
    q = Quiz.model_validate_json((EXAMPLES / "quiz.json").read_text())
    kinds = {qq.kind for qq in q.questions}
    assert {"recall", "transfer", "misconception_correction"} <= kinds


def test_flashcards_load():
    cards_raw = json.loads((EXAMPLES / "flashcards.json").read_text())
    cards = [Flashcard.model_validate(c) for c in cards_raw]
    assert len(cards) >= 10
    # Hard cards exist.
    assert any(c.difficulty == "hard" for c in cards)
