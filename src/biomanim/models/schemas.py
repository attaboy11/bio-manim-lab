"""Canonical Pydantic schemas for bio-manim-lab.

These schemas are the data contracts. Every stage reads and writes to disk
through these models. If a stage produces something that does not validate,
the run fails loudly — silent drift is the failure mode this project is most
afraid of.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from .._compat import BaseModel, Field, ConfigDict, field_validator


# ----------------------------------------------------------------------------
# shared types
# ----------------------------------------------------------------------------

Scale = Literal["molecular", "cellular", "tissue", "organ", "organism", "population"]
Confidence = Literal["high", "medium", "low"]


class StrictBase(BaseModel):
    """Forbid unknown fields. Drift is the enemy."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Provenance(StrictBase):
    source: str = Field(..., description="Source label, e.g. 'llm:gpt-4o' or 'graphify:bio-raw'.")
    confidence: Confidence = "medium"
    note: Optional[str] = None


# ----------------------------------------------------------------------------
# concept_map.json
# ----------------------------------------------------------------------------

class Entity(StrictBase):
    id: str
    name: str
    kind: str = Field(..., description="e.g. protein, complex, ion, metabolite, membrane, compartment.")
    scale: Scale
    description: str
    aliases: list[str] = Field(default_factory=list)


class Process(StrictBase):
    id: str
    name: str
    description: str
    inputs: list[str] = Field(default_factory=list, description="Entity ids consumed.")
    outputs: list[str] = Field(default_factory=list, description="Entity ids produced.")
    location: Optional[str] = None
    scale: Scale = "molecular"


class CausalEdge(StrictBase):
    source: str = Field(..., description="Entity or process id.")
    target: str = Field(..., description="Entity or process id.")
    relation: str = Field(..., description="e.g. drives, inhibits, produces, requires, transports.")
    note: Optional[str] = None
    confidence: Confidence = "medium"


class Prerequisite(StrictBase):
    concept: str
    why: str


class Misconception(StrictBase):
    wrong: str
    right: str
    why_it_sticks: Optional[str] = None


class ConfidenceNote(StrictBase):
    claim: str
    confidence: Confidence
    reason: str


class ConceptMap(StrictBase):
    topic: str
    entities: list[Entity]
    processes: list[Process]
    causal_edges: list[CausalEdge]
    scales: list[Scale]
    prerequisites: list[Prerequisite] = Field(default_factory=list)
    misconceptions: list[Misconception] = Field(default_factory=list)
    confidence_notes: list[ConfidenceNote] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)

    @field_validator("entities")
    @classmethod
    def _entities_have_unique_ids(cls, v: list[Entity]) -> list[Entity]:
        ids = [e.id for e in v]
        if len(ids) != len(set(ids)):
            raise ValueError("entity ids must be unique")
        return v

    @field_validator("processes")
    @classmethod
    def _processes_have_unique_ids(cls, v: list[Process]) -> list[Process]:
        ids = [p.id for p in v]
        if len(ids) != len(set(ids)):
            raise ValueError("process ids must be unique")
        return v


# ----------------------------------------------------------------------------
# lesson_outline (markdown body, but the metadata is structured)
# ----------------------------------------------------------------------------

class LessonOutline(StrictBase):
    """The structured form. The pedagogy stage also writes a markdown twin."""

    topic: str
    one_paragraph_intuition: str
    mechanism_steps: list[str]
    why_it_matters: str
    common_confusions: list[str]
    checkpoint_questions: list[str]
    key_takeaways: list[str]


# ----------------------------------------------------------------------------
# scene_plan.json
# ----------------------------------------------------------------------------

class Scene(StrictBase):
    id: str
    title: str
    teaching_goal: str
    biological_claims: list[str]
    visual_strategy: str
    animation_steps: list[str]
    labels: list[str]
    narration_segment: str
    estimated_duration: float = Field(..., description="Seconds.")

    @field_validator("estimated_duration")
    @classmethod
    def _positive_duration(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("estimated_duration must be positive")
        return v


class ScenePlan(StrictBase):
    topic: str
    scenes: list[Scene]
    total_estimated_duration: float

    @field_validator("scenes")
    @classmethod
    def _scenes_have_unique_ids(cls, v: list[Scene]) -> list[Scene]:
        ids = [s.id for s in v]
        if len(ids) != len(set(ids)):
            raise ValueError("scene ids must be unique")
        if not v:
            raise ValueError("scene plan must contain at least one scene")
        return v


# ----------------------------------------------------------------------------
# study assets
# ----------------------------------------------------------------------------

class Flashcard(StrictBase):
    question: str
    answer: str
    tag: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class QuizQuestion(StrictBase):
    kind: Literal["recall", "transfer", "misconception_correction"]
    question: str
    answer: str
    distractors: list[str] = Field(default_factory=list)
    explanation: Optional[str] = None


class Quiz(StrictBase):
    topic: str
    questions: list[QuizQuestion]


class StudySummary(StrictBase):
    """Just the metadata. The body is written as study/summary.md."""

    topic: str
    word_count: int
    sections: list[str]


# ----------------------------------------------------------------------------
# run manifest
# ----------------------------------------------------------------------------

class RunManifest(StrictBase):
    run_id: str
    topic: str
    created_at: datetime
    quant: bool = False
    stages_completed: list[str] = Field(default_factory=list)
    stages_failed: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
