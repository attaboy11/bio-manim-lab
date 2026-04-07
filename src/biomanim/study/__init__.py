"""Study stage.

Builds three artifacts from the LessonOutline + ConceptMap:
  - study/summary.md          : a tight written summary
  - study/flashcards.json     : a list of {question, answer, tag, difficulty}
  - study/quiz.json           : recall + transfer + misconception_correction
"""

from __future__ import annotations

from ..models import ConceptMap, Flashcard, LessonOutline, Quiz, QuizQuestion
from ..utils.io import ensure_dir, run_dir, write_json, write_text
from ..utils.llm import call_structured, call_text, golden_text_lookup, golden_lookup


def build_study(
    *, concept_map: ConceptMap, lesson_outline: LessonOutline, run_id: str
) -> dict:
    rd = ensure_dir(run_dir(run_id) / "study")

    summary_md = _build_summary(concept_map, lesson_outline)
    write_text(rd / "summary.md", summary_md)

    cards = _build_flashcards(concept_map, lesson_outline)
    write_json(rd / "flashcards.json", [c.model_dump(mode="json") for c in cards])

    quiz = _build_quiz(concept_map, lesson_outline)
    write_json(rd / "quiz.json", quiz.model_dump(mode="json"))

    return {
        "summary_md": str(rd / "summary.md"),
        "flashcards_json": str(rd / "flashcards.json"),
        "quiz_json": str(rd / "quiz.json"),
    }


# ----------------------------------------------------------------------------
# Each builder prefers a golden artifact, falls back to LLM, and finally
# falls back to a deterministic outline-derived skeleton so the pipeline
# always produces something useful.
# ----------------------------------------------------------------------------

def _build_summary(cm: ConceptMap, lo: LessonOutline) -> str:
    cached = golden_text_lookup(cm.topic, "study_summary.md")
    if cached is not None:
        return cached
    try:
        return call_text(
            prompt_path="study/summary.md",
            user_inputs={"concept_map": cm.model_dump(mode="json"),
                         "lesson_outline": lo.model_dump(mode="json")},
            topic=cm.topic,
            artifact_name="study_summary.md",
        )
    except Exception:
        return _summary_from_outline(lo)


def _summary_from_outline(lo: LessonOutline) -> str:
    parts = [f"# {lo.topic} — Summary", "", lo.one_paragraph_intuition, "",
             "## Mechanism", ""]
    parts += [f"{i+1}. {s}" for i, s in enumerate(lo.mechanism_steps)]
    parts += ["", "## Why it matters", "", lo.why_it_matters, "",
              "## Key takeaways", ""]
    parts += [f"- {k}" for k in lo.key_takeaways]
    parts += [""]
    return "\n".join(parts)


def _build_flashcards(cm: ConceptMap, lo: LessonOutline) -> list[Flashcard]:
    cached = golden_lookup(cm.topic, "flashcards.json")
    if cached is not None:
        return [Flashcard.model_validate(c) for c in cached]
    try:
        # Wrap a list in a tiny model so we can re-use call_structured.
        from pydantic import RootModel

        class _Cards(RootModel[list[Flashcard]]):
            pass

        result = call_structured(
            prompt_path="study/flashcards.md",
            user_inputs={"lesson_outline": lo.model_dump(mode="json")},
            schema=_Cards,
            topic=cm.topic,
            artifact_name="flashcards.json",
        )
        return result.root
    except Exception:
        return _flashcards_from_outline(lo, cm)


def _flashcards_from_outline(lo: LessonOutline, cm: ConceptMap) -> list[Flashcard]:
    cards: list[Flashcard] = []
    for q in lo.checkpoint_questions:
        cards.append(Flashcard(question=q, answer="(see lesson outline)", tag="checkpoint"))
    for e in cm.entities[:6]:
        cards.append(Flashcard(question=f"What is {e.name}?", answer=e.description, tag=e.kind))
    for m in cm.misconceptions[:4]:
        cards.append(Flashcard(question=f"Wrong: {m.wrong}", answer=m.right, tag="misconception", difficulty="hard"))
    return cards


def _build_quiz(cm: ConceptMap, lo: LessonOutline) -> Quiz:
    cached = golden_lookup(cm.topic, "quiz.json")
    if cached is not None:
        return Quiz.model_validate(cached)
    try:
        return call_structured(
            prompt_path="study/quiz.md",
            user_inputs={"concept_map": cm.model_dump(mode="json"),
                         "lesson_outline": lo.model_dump(mode="json")},
            schema=Quiz,
            topic=cm.topic,
            artifact_name="quiz.json",
        )
    except Exception:
        return _quiz_from_outline(lo, cm)


def _quiz_from_outline(lo: LessonOutline, cm: ConceptMap) -> Quiz:
    qs: list[QuizQuestion] = []
    for q in lo.checkpoint_questions[:4]:
        qs.append(QuizQuestion(kind="recall", question=q, answer="(see outline)"))
    for k in lo.key_takeaways[:2]:
        qs.append(QuizQuestion(
            kind="transfer",
            question=f"Apply this idea to a new context: {k}",
            answer="(open-ended)",
        ))
    for m in cm.misconceptions[:2]:
        qs.append(QuizQuestion(
            kind="misconception_correction",
            question=f"What's wrong with this statement: '{m.wrong}'?",
            answer=m.right,
            explanation=m.why_it_sticks,
        ))
    return Quiz(topic=lo.topic, questions=qs)
