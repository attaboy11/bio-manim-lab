# bio-manim-lab

A local-first CLI that converts a biology topic (or pasted notes) into a
structured teaching artifact set: concept map, lesson outline, scene plan,
narration, Manim script, rendered MP4, and study assets (summary, flashcards,
quiz).

This is **not** an AI video toy. It is a biology teaching compiler. The
animation is one surface; the real asset is the structured biological
understanding underneath it.

See `BIO-MANIM-LAB MASTER BLUEPRINT` for full design intent. This README only
covers how to run the thing.

## Install

Requires **Python 3.11**.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
# Optional, only needed if you want to actually render an MP4:
pip install "manim>=0.18"
```

The pipeline is local-first. It runs without any LLM API key by falling back
to **golden cached outputs** for known topics (currently: ATP synthase). Set
`OPENAI_API_KEY` in `.env` to enable real LLM calls for new topics.

## Run the vertical slice

```bash
python -m biomanim run --topic "ATP synthase and oxidative phosphorylation"
```

This produces, under `outputs/<run_id>/`:

```
concept_map.json
lesson_outline.md
scene_plan.json
narration.md
manim_script.py
render/final.mp4          # only if Manim is installed
study/summary.md
study/flashcards.json
study/quiz.json
run_manifest.json
```

If Manim is not installed, the render stage writes a stub note and the rest of
the pipeline still completes successfully. This is intentional: the structured
artifacts are the real product.

## Other commands

```bash
python -m biomanim extract --topic "ATP synthase and oxidative phosphorylation"
python -m biomanim plan    --run <run_id>
python -m biomanim codegen --run <run_id>
python -m biomanim render  --run <run_id>
python -m biomanim study   --run <run_id>
python -m biomanim inspect --run <run_id>
python -m biomanim import-graphify --path ../bio-raw/graphify-out
python -m biomanim run --topic "Michaelis-Menten kinetics" --quant
```

Every stage writes its artifact to disk. Any stage can be re-run independently
on an existing run directory. The pipeline can resume from a failed stage.

## Architecture

```
src/biomanim/
  cli.py            # entry point
  ingest/           # normalises topic strings, pasted notes, local text files
  extract/          # builds biological concept graph
  pedagogy/         # turns concept structure into a teaching plan
  scenes/           # maps concepts to visual scenes
  codegen/          # generates executable Manim code from scene plan
  render/           # runs Manim, produces video
  study/            # builds summary, flashcards, quiz
  quant/            # optional MathCode adapter (--quant)
  integrations/     # graphify_adapter.py — optional importer
  supervisor/       # local orchestration: interrupt, retry, timeout
  models/           # Pydantic schemas (canonical data contracts)
  utils/            # shared helpers (io, llm, slugs)
```

All prompts live in `prompts/`. All structured LLM output is schema-validated
through Pydantic. There is no hidden global state.

## Tests

```bash
pytest -q
```

Runs schema validation, CLI smoke (full run produces expected files), and the
ATP synthase scene-plan golden test.

## What this project is not

A generic content generator. A motivational edtech toy. A flashy animation
demo. A "learn anything" platform. A theorem prover pretending to teach
biology. A web app with auth, billing, and growth hacks before the core works.

It must stay focused on one thing: helping the user achieve deep biological
understanding quickly and reliably.
