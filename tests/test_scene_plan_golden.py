"""Golden scene plan test for the ATP synthase reference topic.

This test pins quality invariants we never want to drift on, *not* the
exact text of any scene. The blueprint is explicit: this project will fail
by subtle drift, not by obvious syntax. Don't loosen these without thought.
"""

from __future__ import annotations

from pathlib import Path

from biomanim.models import ScenePlan

GOLDEN = Path(__file__).resolve().parents[1] / "examples" / "atp_synthase" / "scene_plan.json"


def test_atp_scene_plan_invariants():
    sp = ScenePlan.model_validate_json(GOLDEN.read_text())

    # Total duration in target window.
    assert 120 <= sp.total_estimated_duration <= 240

    # Scene count in target window.
    assert 4 <= len(sp.scenes) <= 8

    # First scene must orient. Last scene must apply or summarise.
    assert "orientation" in sp.scenes[0].id or "orient" in sp.scenes[0].title.lower()
    last_id = sp.scenes[-1].id.lower()
    assert any(k in last_id for k in ("relevance", "failure", "summary", "apply"))

    # Each scene has at least 2 biological claims and at least 2 animation steps.
    for s in sp.scenes:
        assert len(s.biological_claims) >= 2, f"{s.id} too few claims"
        assert len(s.animation_steps) >= 2, f"{s.id} too few steps"
        assert len(s.narration_segment) >= 80, f"{s.id} narration too short"

    # Sparse labels rule: no scene has more than 8 labels.
    for s in sp.scenes:
        assert len(s.labels) <= 8, f"{s.id} too many labels (rule: sparse)"

    # The crucial mechanism beats must each appear in at least one scene.
    text_blob = " ".join(
        s.title + " " + s.narration_segment + " " + " ".join(s.biological_claims)
        for s in sp.scenes
    ).lower()
    for must in ["membrane", "proton", "rotat", "atp"]:
        assert must in text_blob, f"missing canonical beat: {must}"
