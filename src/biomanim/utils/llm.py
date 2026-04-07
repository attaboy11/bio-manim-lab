"""LLM helper with golden-cache fallback.

Design intent:

- The pipeline must run end-to-end with no API key, on at least one canonical
  topic. We achieve this by checking `examples/<slug>/<artifact>` first.
- When OPENAI_API_KEY is present, we call OpenAI and validate the result
  against a Pydantic model. The caller always passes a Pydantic model class;
  we never hand back unvalidated JSON.
- OpenAI is the only supported provider (by design — keeping dependencies
  minimal).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Type, TypeVar

from .._compat import BaseModel
from .io import EXAMPLES_DIR, PROMPTS_DIR, slug, read_text

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


def load_prompt(relpath: str) -> str:
    """Load a prompt template from prompts/. Path is relative to prompts/."""
    p = PROMPTS_DIR / relpath
    if not p.exists():
        raise LLMError(f"Prompt not found: {p}")
    return read_text(p)


def _provider() -> str:
    explicit = os.environ.get("BIOMANIM_LLM_PROVIDER")
    if explicit:
        return explicit.lower()
    # Auto-detect: if a key is present, use openai; otherwise golden.
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "golden"


def _candidate_golden_dirs(topic: str) -> list[Path]:
    """Return candidate example folders, in priority order.

    We try:
      1. examples/<exact slug with underscores>
      2. examples/<exact slug with hyphens>
      3. Any examples/<subdir> whose concept_map.json has a matching or
         substring-matching topic field. This lets a shipped golden example
         cover several phrasings of the same topic.
      4. Any examples/<subdir> whose name is a prefix of the topic slug.
    """
    s_hyphen = slug(topic)
    s_under = s_hyphen.replace("-", "_")
    out: list[Path] = [EXAMPLES_DIR / s_under, EXAMPLES_DIR / s_hyphen]

    if EXAMPLES_DIR.exists():
        topic_lower = topic.lower()
        for d in sorted(EXAMPLES_DIR.iterdir()):
            if not d.is_dir() or d in out:
                continue
            cm_path = d / "concept_map.json"
            if cm_path.exists():
                try:
                    cm = json.loads(cm_path.read_text(encoding="utf-8"))
                    cm_topic = str(cm.get("topic", "")).lower()
                    if cm_topic == topic_lower:
                        out.append(d)
                        continue
                    # Substring match in either direction.
                    if cm_topic and (cm_topic in topic_lower or topic_lower in cm_topic):
                        out.append(d)
                        continue
                except Exception:
                    pass
            # Prefix match on folder name.
            if s_under.startswith(d.name) or s_hyphen.startswith(d.name):
                out.append(d)
    return out


def _resolve_golden(topic: str, artifact_name: str) -> Path | None:
    for d in _candidate_golden_dirs(topic):
        p = d / artifact_name
        if p.exists():
            return p
    return None


def golden_lookup(topic: str, artifact_name: str) -> dict | None:
    """Return the golden JSON for (topic, artifact) if it exists."""
    p = _resolve_golden(topic, artifact_name)
    if p is not None:
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def golden_text_lookup(topic: str, artifact_name: str) -> str | None:
    p = _resolve_golden(topic, artifact_name)
    if p is not None:
        return p.read_text(encoding="utf-8")
    return None


def call_structured(
    *,
    prompt_path: str,
    user_inputs: dict,
    schema: Type[T],
    topic: str,
    artifact_name: str,
) -> T:
    """Call the LLM and validate the response against `schema`.

    Order of attempts:
      1. If provider is `golden` (or no OPENAI_API_KEY is set), look up the
         pre-baked JSON in examples/<slug>/<artifact_name>.
      2. Otherwise call OpenAI.

    Raises LLMError if neither path is available.
    """
    provider = _provider()

    if provider == "golden" or not os.environ.get("OPENAI_API_KEY"):
        cached = golden_lookup(topic, artifact_name)
        if cached is not None:
            return schema.model_validate(cached)
        raise LLMError(
            f"No OPENAI_API_KEY set and no golden artifact for "
            f"topic={topic!r} artifact={artifact_name!r}. "
            f"Set OPENAI_API_KEY in .env, or pre-bake "
            f"examples/<slug>/{artifact_name}."
        )

    template = load_prompt(prompt_path)
    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    full_prompt = (
        f"{template}\n\n"
        f"## Inputs\n```json\n{json.dumps(user_inputs, indent=2)}\n```\n\n"
        f"## Required JSON Schema\n```json\n{schema_json}\n```\n\n"
        f"Respond with ONLY a single JSON object that satisfies the schema. "
        f"No prose, no markdown fences."
    )

    raw = _call_openai(full_prompt, want_json=True)
    raw = _strip_code_fences(raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM returned non-JSON: {e}\n--- raw ---\n{raw[:1000]}")
    return schema.model_validate(data)


def call_text(*, prompt_path: str, user_inputs: dict, topic: str, artifact_name: str) -> str:
    """Like `call_structured` but for free-text artifacts (markdown, etc)."""
    if _provider() == "golden" or not os.environ.get("OPENAI_API_KEY"):
        cached = golden_text_lookup(topic, artifact_name)
        if cached is not None:
            return cached
        raise LLMError(
            f"No OPENAI_API_KEY set and no golden text for topic={topic!r} "
            f"artifact={artifact_name!r}."
        )

    template = load_prompt(prompt_path)
    full_prompt = (
        f"{template}\n\n"
        f"## Inputs\n```json\n{json.dumps(user_inputs, indent=2)}\n```\n"
    )
    return _call_openai(full_prompt, want_json=False)


def _strip_code_fences(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[: -3]
    return s.strip()


def _call_openai(prompt: str, *, want_json: bool) -> str:
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as e:
        raise LLMError(
            "openai SDK not installed. Run: pip install 'biomanim[llm]'"
        ) from e

    timeout = float(os.environ.get("BIOMANIM_LLM_TIMEOUT", "120"))
    model = os.environ.get("BIOMANIM_LLM_MODEL", "gpt-4o-mini")
    client = OpenAI(timeout=timeout)

    kwargs: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    if want_json:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""
