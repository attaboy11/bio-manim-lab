"""bio-manim-lab CLI.

Single entry point. Each subcommand is a thin wrapper that:
  1. Resolves config and run id.
  2. Loads any prerequisite artifacts from disk.
  3. Calls the relevant stage module.
  4. Updates the run manifest.

The pipeline is local-first and resumable. Every stage writes its artifact;
re-running a single stage on an existing run id is the supported workflow.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .utils.runtime import load_dotenv_if_present

load_dotenv_if_present()

try:
    import typer  # type: ignore
except ImportError:
    from types import SimpleNamespace
    from . import _compat as _c
    typer = SimpleNamespace(  # type: ignore
        Typer=_c.Typer,
        Option=_c.Option,
        BadParameter=_c.BadParameter,
    )
from ._compat import Console, Tree

from . import __version__
from .ingest import ingest as do_ingest
from .extract import extract as do_extract
from .pedagogy import plan as do_plan
from .scenes import plan_scenes as do_plan_scenes
from .codegen import codegen as do_codegen
from .render import render as do_render
from .study import build_study as do_study
from .quant import run_quant
from .integrations.graphify_adapter import import_graphify
from .supervisor import Supervisor
from .models import ConceptMap, LessonOutline, ScenePlan, RunManifest
from .utils.io import (
    DEFAULT_OUTPUT_ROOT,
    find_run,
    latest_run_dir,
    load_default_config,
    now_run_id,
    output_root,
    read_json,
    read_text,
    run_dir,
    write_json,
)

app = typer.Typer(
    add_completion=False,
    help="bio-manim-lab — turn biology topics into structured teaching artifacts.",
    no_args_is_help=True,
)
console = Console()


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def _resolve_run_dir(run_id: Optional[str]) -> Path:
    if run_id:
        return find_run(run_id)
    latest = latest_run_dir()
    if latest is None:
        raise typer.BadParameter("No runs found and --run not provided.")
    return latest


def _load_concept_map(rd: Path) -> ConceptMap:
    return ConceptMap.model_validate(read_json(rd / "concept_map.json"))


def _load_outline(rd: Path) -> LessonOutline:
    return LessonOutline.model_validate(read_json(rd / "lesson_outline.json"))


def _load_scene_plan(rd: Path) -> ScenePlan:
    return ScenePlan.model_validate(read_json(rd / "scene_plan.json"))


def _save_manifest(manifest: RunManifest, rd: Path) -> None:
    write_json(rd / "run_manifest.json", manifest.model_dump(mode="json"))


def _load_or_init_manifest(rd: Path, topic: str, quant: bool) -> RunManifest:
    p = rd / "run_manifest.json"
    if p.exists():
        return RunManifest.model_validate(read_json(p))
    return RunManifest(
        run_id=rd.name,
        topic=topic,
        created_at=datetime.utcnow(),
        quant=quant,
    )


# ----------------------------------------------------------------------------
# commands
# ----------------------------------------------------------------------------

@app.command()
def version() -> None:
    """Print version."""
    console.print(f"bio-manim-lab {__version__}")


@app.command()
def run(
    topic: Optional[str] = typer.Option(None, "--topic", "-t", help="Biology topic."),
    input: Optional[str] = typer.Option(None, "--input", "-i", help="Path to a notes file."),  # noqa: A002
    quant: bool = typer.Option(False, "--quant", help="Enable optional MathCode adapter."),
    fail_fast: bool = typer.Option(False, "--fail-fast", help="Stop at the first failed stage."),
) -> None:
    """Full pipeline end-to-end."""
    cfg = load_default_config()
    if not topic and not input:
        raise typer.BadParameter("Provide either --topic or --input.")

    work_topic = topic or Path(input).stem  # type: ignore[arg-type]
    run_id = now_run_id(work_topic)
    rd = run_dir(run_id)
    manifest = _load_or_init_manifest(rd, work_topic, quant)

    sup = Supervisor(
        timeout_seconds=int(cfg["llm"].get("timeout_seconds", 120)),
        max_retries=int(cfg["llm"].get("max_retries", 1)),
        fail_fast=fail_fast,
    )

    payload = sup.run("ingest", lambda: do_ingest(topic=topic, input_path=input, run_id=run_id))
    if payload is None:
        _finish(sup, manifest, rd)
        return
    manifest.topic = payload["topic"]

    cm = sup.run("extract", lambda: do_extract(ingest_payload=payload, run_id=run_id))
    if cm is None:
        _finish(sup, manifest, rd)
        return

    if quant:
        sup.run("quant", lambda: run_quant(topic=cm.topic, run_id=run_id))

    outline = sup.run("pedagogy", lambda: do_plan(concept_map=cm, run_id=run_id))
    if outline is None:
        _finish(sup, manifest, rd)
        return

    scene_plan = sup.run(
        "scenes",
        lambda: do_plan_scenes(concept_map=cm, lesson_outline=outline, run_id=run_id),
    )
    if scene_plan is None:
        _finish(sup, manifest, rd)
        return

    sup.run("codegen", lambda: do_codegen(scene_plan=scene_plan, run_id=run_id))
    sup.run("render", lambda: do_render(run_id=run_id, quality=cfg["codegen"]["manim_quality"]))
    sup.run("study", lambda: do_study(concept_map=cm, lesson_outline=outline, run_id=run_id))

    _finish(sup, manifest, rd)


def _finish(sup: Supervisor, manifest: RunManifest, rd: Path) -> None:
    manifest.stages_completed = [r.name for r in sup.results if r.ok]
    manifest.stages_failed = [r.name for r in sup.results if not r.ok]
    for name in ("concept_map.json", "lesson_outline.md", "scene_plan.json",
                 "narration.md", "manim_script.py", "run_manifest.json"):
        if (rd / name).exists():
            manifest.artifacts[name] = str(rd / name)
    final_mp4 = rd / "render" / "final.mp4"
    if final_mp4.exists():
        manifest.artifacts["render/final.mp4"] = str(final_mp4)
    for sname in ("summary.md", "flashcards.json", "quiz.json"):
        sp = rd / "study" / sname
        if sp.exists():
            manifest.artifacts[f"study/{sname}"] = str(sp)
    _save_manifest(manifest, rd)
    console.rule()
    console.print(sup.summary())
    console.print(f"\n[bold]Run id:[/] {rd.name}")
    console.print(f"[bold]Output:[/] {rd}")


@app.command()
def extract(
    topic: Optional[str] = typer.Option(None, "--topic", "-t"),
    input: Optional[str] = typer.Option(None, "--input", "-i"),  # noqa: A002
) -> None:
    """Concept extraction only."""
    if not topic and not input:
        raise typer.BadParameter("Provide --topic or --input.")
    work_topic = topic or Path(input).stem  # type: ignore[arg-type]
    run_id = now_run_id(work_topic)
    payload = do_ingest(topic=topic, input_path=input, run_id=run_id)
    cm = do_extract(ingest_payload=payload, run_id=run_id)
    console.print(f"[green]✓[/] concept_map.json written for run {run_id}")
    console.print(f"  entities={len(cm.entities)}  processes={len(cm.processes)}  edges={len(cm.causal_edges)}")


@app.command()
def plan(run: Optional[str] = typer.Option(None, "--run")) -> None:
    """Lesson outline + scene plan."""
    rd = _resolve_run_dir(run)
    cm = _load_concept_map(rd)
    outline = do_plan(concept_map=cm, run_id=rd.name)
    sp = do_plan_scenes(concept_map=cm, lesson_outline=outline, run_id=rd.name)
    console.print(f"[green]✓[/] outline + scene_plan written ({len(sp.scenes)} scenes)")


@app.command()
def codegen(run: Optional[str] = typer.Option(None, "--run")) -> None:
    """Generate Manim script from an existing scene plan."""
    rd = _resolve_run_dir(run)
    sp = _load_scene_plan(rd)
    out = do_codegen(scene_plan=sp, run_id=rd.name)
    console.print(f"[green]✓[/] {out}")


@app.command()
def render(run: Optional[str] = typer.Option(None, "--run")) -> None:
    """Run Manim and produce video."""
    rd = _resolve_run_dir(run)
    cfg = load_default_config()
    result = do_render(run_id=rd.name, quality=cfg["codegen"]["manim_quality"])
    if result is None:
        console.print(f"[yellow]ℹ render skipped[/] — see {rd / 'render' / 'STATUS.md'}")
    else:
        console.print(f"[green]✓ rendered[/] {result}")


@app.command()
def study(run: Optional[str] = typer.Option(None, "--run")) -> None:
    """Generate study assets."""
    rd = _resolve_run_dir(run)
    cm = _load_concept_map(rd)
    outline = _load_outline(rd)
    paths = do_study(concept_map=cm, lesson_outline=outline, run_id=rd.name)
    for k, v in paths.items():
        console.print(f"[green]✓[/] {k}: {v}")


@app.command()
def inspect(run: Optional[str] = typer.Option(None, "--run")) -> None:
    """View intermediate artifacts."""
    rd = _resolve_run_dir(run)
    tree = Tree(f"[bold]{rd.name}[/]")
    for p in sorted(rd.rglob("*")):
        if p.is_file():
            tree.add(str(p.relative_to(rd)))
    console.print(tree)
    manifest_path = rd / "run_manifest.json"
    if manifest_path.exists():
        console.rule("manifest")
        console.print_json(json.dumps(read_json(manifest_path), default=str))


@app.command(name="import-graphify")
def import_graphify_cmd(
    path: str = typer.Option(..., "--path", help="Graphify output folder."),
    run: Optional[str] = typer.Option(None, "--run"),
) -> None:
    """Import Graphify outputs into the current run as low-confidence edges."""
    rd = _resolve_run_dir(run)
    out = import_graphify(graphify_path=path, run_id=rd.name)
    console.print(f"[green]✓ imported[/] -> {out}")


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
