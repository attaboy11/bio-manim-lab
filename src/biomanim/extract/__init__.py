"""Extract stage.

Builds a biological concept graph (concept_map.json) from the ingest payload.
The LLM call is structured: it must produce JSON that validates against the
ConceptMap schema. If no LLM provider is available, the call falls back to
a pre-baked golden artifact.
"""

from __future__ import annotations

from ..models import ConceptMap
from ..utils.io import run_dir, write_json
from ..utils.llm import call_structured


def extract(*, ingest_payload: dict, run_id: str) -> ConceptMap:
    topic = ingest_payload["topic"]
    cm = call_structured(
        prompt_path="extract/concept_graph.md",
        user_inputs=ingest_payload,
        schema=ConceptMap,
        topic=topic,
        artifact_name="concept_map.json",
    )
    # Sanity floors. Drift is the enemy — but one weak LLM call shouldn't
    # tank the whole run. Floors are deliberately loose; the prompt carries
    # the real quality requirements.
    if len(cm.entities) < 2:
        raise ValueError(f"extract produced too few entities ({len(cm.entities)})")
    if len(cm.processes) < 1:
        raise ValueError(f"extract produced too few processes ({len(cm.processes)})")
    write_json(run_dir(run_id) / "concept_map.json", cm.model_dump(mode="json"))
    return cm
