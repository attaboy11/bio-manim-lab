# Scene planner

You receive a `ConceptMap` and a `LessonOutline`. Produce a `ScenePlan`: a
sequence of 4–8 scenes that, together, teach the topic visually.

## Per scene

- `id`: short snake_case (e.g. `s1_orientation`).
- `title`: short, descriptive.
- `teaching_goal`: one sentence — what should the learner *understand* by
  the end of this scene.
- `biological_claims`: 2–4 specific claims this scene must visually justify.
- `visual_strategy`: how the scene shows the mechanism. Pick from:
  schematic_mechanism, gradient_field, comparative_split, zoom_in_layered,
  state_diagram, time_series, or describe a custom strategy in one phrase.
- `animation_steps`: an ordered list of small visual events. Each step is
  *something that moves or appears on screen*. Keep them small enough that
  Manim can render each step with a single Play call.
- `labels`: only the labels that must appear. Sparse labels are a hard rule.
- `narration_segment`: 2–4 sentences spoken over the scene. Match the
  visuals exactly. No narration that the visuals do not justify.
- `estimated_duration`: seconds (positive number).

## Global rules

- Total duration should land in 120–240 seconds for a single concept.
- The first scene orients; the last scene either applies or summarises.
- Visual vocabulary is consistent with `configs/styles.yaml`:
  membranes are hard boundaries, gradients are concentration fields,
  arrows mean causation or directed flow, same object → same style across
  scenes, reveal progressively, no decorative nonsense.
