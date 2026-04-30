from __future__ import annotations

from pathlib import Path
import threading

from biomanim.ingest import ingest
from biomanim.models import ConceptMap, LessonOutline
from biomanim.render import _find_final_mp4, render
from biomanim.supervisor import _timeout
from biomanim.utils import llm


def test_ingest_accepts_pasted_notes_without_topic(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BIOMANIM_OUTPUT_ROOT", str(tmp_path))
    payload = ingest(
        topic=None,
        notes="ATP synthase and oxidative phosphorylation\nThe proton gradient powers rotation.",
        input_path=None,
        run_id="notes-only",
    )
    assert payload["topic"] == "ATP synthase and oxidative phosphorylation"
    assert payload["source"] == "notes"
    assert "proton gradient" in payload["notes"]


def test_call_structured_prefers_golden_in_auto_mode_even_with_api_key(monkeypatch):
    monkeypatch.setenv("BIOMANIM_LLM_PROVIDER", "auto")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("golden cache should win for canonical topics in auto mode")

    monkeypatch.setattr(llm, "_call_openai", _boom)
    concept_map = llm.call_structured(
        prompt_path="extract/concept_graph.md",
        user_inputs={"topic": "ATP synthase and oxidative phosphorylation", "notes": "", "source": "topic"},
        schema=ConceptMap,
        topic="ATP synthase and oxidative phosphorylation",
        artifact_name="concept_map.json",
    )
    assert concept_map.topic.startswith("ATP synthase")


def test_call_structured_repairs_schema_mismatch(monkeypatch):
    monkeypatch.setenv("BIOMANIM_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    responses = iter([
        """{
          "topic": "CRISPR-Cas9",
          "one_paragraph_intuition": "Cas9 uses guide RNA to find a target and cut it.",
          "mechanism_steps": ["Guide RNA binds Cas9", "Target DNA is recognized", "Cas9 cleaves DNA"],
          "why_it_matters": "It enables precise genome editing.",
          "common_confusions": ["Cas9 does not rewrite DNA on its own."],
          "checkpoint_questions": ["What determines where Cas9 cuts?"],
          "key_takeaways": "Guide RNA directs Cas9 to a matching DNA sequence."
        }""",
        """{
          "topic": "CRISPR-Cas9",
          "one_paragraph_intuition": "Cas9 uses guide RNA to find a target and cut it.",
          "mechanism_steps": ["Guide RNA binds Cas9", "Target DNA is recognized", "Cas9 cleaves DNA"],
          "why_it_matters": "It enables precise genome editing.",
          "common_confusions": ["Cas9 does not rewrite DNA on its own."],
          "checkpoint_questions": ["What determines where Cas9 cuts?"],
          "key_takeaways": ["Guide RNA directs Cas9 to a matching DNA sequence."]
        }""",
    ])

    monkeypatch.setattr(llm, "_call_openai", lambda *args, **kwargs: next(responses))

    outline = llm.call_structured(
        prompt_path="pedagogy/lesson_outline.md",
        user_inputs={"concept_map": {"topic": "CRISPR-Cas9"}},
        schema=LessonOutline,
        topic="CRISPR-Cas9",
        artifact_name="lesson_outline.json",
    )
    assert outline.key_takeaways == ["Guide RNA directs Cas9 to a matching DNA sequence."]


def test_timeout_context_is_safe_off_main_thread():
    errors: list[Exception] = []

    def _worker():
        try:
            with _timeout(1):
                pass
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    thread = threading.Thread(target=_worker)
    thread.start()
    thread.join()
    assert errors == []


def test_render_normalizes_nested_manim_output(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BIOMANIM_OUTPUT_ROOT", str(tmp_path))
    run_id = "render-nested"
    run_dir = tmp_path / run_id
    render_dir = run_dir / "render"
    nested_final = render_dir / "videos" / "manim_script" / "480p15" / "final.mp4"
    nested_final.parent.mkdir(parents=True, exist_ok=True)
    (run_dir / "manim_script.py").write_text("class BioScene: pass\n", encoding="utf-8")
    nested_final.write_bytes(b"fake-mp4")

    monkeypatch.setattr("biomanim.render.shutil.which", lambda name: "/usr/bin/manim")
    monkeypatch.setattr("biomanim.render.subprocess.run", lambda *args, **kwargs: None)

    result = render(run_id=run_id)

    assert result == render_dir / "final.mp4"
    assert result.exists()
    assert result.read_bytes() == b"fake-mp4"
    assert _find_final_mp4(render_dir) is not None
