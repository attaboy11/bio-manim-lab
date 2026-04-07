"""ATP synthase and oxidative phosphorylation — golden Manim scene.

This is the hand-crafted reference scene for the bio-manim-lab vertical slice.
It teaches the topic in six visual sections that mirror the scene plan in
`scene_plan.json`. The codegen stage copies this file directly when the
topic matches; for any other topic the LLM-generated script is used instead.

Manim CE >= 0.18.
"""

from __future__ import annotations

import numpy as np

try:
    from manim import (
        Annulus,
        Arrow,
        Circle,
        Create,
        Dot,
        FadeIn,
        FadeOut,
        Line,
        Polygon,
        Rectangle,
        Rotate,
        Scene,
        Text,
        Transform,
        VGroup,
        Write,
        config,
        DOWN,
        LEFT,
        ORIGIN,
        PI,
        RIGHT,
        TAU,
        UP,
        WHITE,
    )
except Exception:  # pragma: no cover
    # Manim is optional. The render stage handles its absence.
    raise


# ----------------------------------------------------------------------------
# palette (mirrors configs/styles.yaml)
# ----------------------------------------------------------------------------
BG = "#0b0d12"
MEMBRANE = "#7a8aa6"
MATRIX = "#152033"
IMS = "#1a2840"
PROTON = "#f0c750"
ELECTRON = "#5fc7e0"
PROTEIN = "#a37bc4"
PROTEIN_ALT = "#c47b9b"
ARROW = "#ffffff"
TEXT_DIM = "#9aa3b2"

config.background_color = BG


def _label(text: str, size: int = 22, color: str = WHITE) -> Text:
    return Text(text, font_size=size, color=color)


class BioScene(Scene):
    def construct(self) -> None:
        self._scene_orientation()
        self._scene_etc_pumping()
        self._scene_gradient()
        self._scene_synthase_rotation()
        self._scene_f1_synthesis()
        self._scene_failure_modes()

    # --- scene s1_orientation: where this happens ---
    def _scene_orientation(self) -> None:
        title = _label("ATP synthase & oxidative phosphorylation",
                       size=32).to_edge(UP)
        self.play(Write(title))

        membrane = Rectangle(
            width=12, height=0.45, color=MEMBRANE, fill_color=MEMBRANE,
            fill_opacity=0.85, stroke_width=0,
        )
        membrane_label = _label("Inner mitochondrial membrane",
                                size=20, color=TEXT_DIM).next_to(membrane, RIGHT, buff=0.2)
        membrane_label.shift(LEFT * 6.5 + UP * 0.45)

        matrix_label = _label("Matrix", size=24, color=TEXT_DIM).shift(DOWN * 2.2)
        ims_label = _label("Intermembrane space", size=24, color=TEXT_DIM).shift(UP * 1.4)
        impermeable = _label("H+ impermeable", size=18, color=PROTON).next_to(membrane, RIGHT, buff=0.4)
        impermeable.shift(RIGHT * 2.5)

        self.play(FadeIn(membrane), FadeIn(matrix_label), FadeIn(ims_label))
        self.play(FadeIn(impermeable))
        self.wait(1.0)

        # Remember the membrane for downstream scenes.
        self.membrane = membrane
        self.title = title
        self.matrix_label = matrix_label
        self.ims_label = ims_label
        self.play(FadeOut(impermeable), FadeOut(title))
        self.wait(0.4)

    # --- scene s2_etc_pumping: the chain pumps protons ---
    def _scene_etc_pumping(self) -> None:
        # Three ETC complexes embedded in the membrane.
        complexes = VGroup()
        complex_centers = [LEFT * 4.5, LEFT * 1.0, RIGHT * 2.5]
        complex_labels = ["I", "III", "IV"]
        for c, lab in zip(complex_centers, complex_labels):
            box = Rectangle(width=1.4, height=1.0, color=PROTEIN,
                            fill_color=PROTEIN, fill_opacity=0.85, stroke_width=0)
            box.move_to(c)
            tag = _label(lab, size=24).move_to(c)
            complexes.add(box, tag)
        self.play(Create(complexes))

        # Electron travels left to right, lifting a proton at each complex.
        e = Dot(color=ELECTRON, radius=0.12).move_to(LEFT * 6.0)
        self.play(FadeIn(e))

        for c in complex_centers:
            self.play(e.animate.move_to(c + UP * 0.0), run_time=0.6)
            proton = Dot(color=PROTON, radius=0.13).move_to(c + DOWN * 0.9)
            arrow = Arrow(start=c + DOWN * 0.9, end=c + UP * 1.0,
                          color=ARROW, buff=0.05, stroke_width=4)
            self.play(FadeIn(proton), Create(arrow), run_time=0.4)
            self.play(proton.animate.move_to(c + UP * 1.0), run_time=0.4)
            self.play(FadeOut(arrow), run_time=0.2)

        # Electron meets oxygen.
        o2_label = _label("O2 → H2O", size=22).next_to(e, RIGHT, buff=0.3)
        self.play(e.animate.move_to(RIGHT * 5.0), FadeIn(o2_label))
        self.play(FadeOut(e))
        self.wait(0.6)

        self.complexes = complexes
        self.play(FadeOut(o2_label))
        self.wait(0.3)

    # --- scene s3_gradient: a gradient builds ---
    def _scene_gradient(self) -> None:
        rng = np.random.default_rng(42)
        upper = VGroup()
        for _ in range(60):
            x = rng.uniform(-6, 6)
            y = rng.uniform(0.5, 2.8)
            upper.add(Dot(point=np.array([x, y, 0]), color=PROTON, radius=0.06))
        lower = VGroup()
        for _ in range(8):
            x = rng.uniform(-6, 6)
            y = rng.uniform(-2.8, -0.5)
            lower.add(Dot(point=np.array([x, y, 0]), color=PROTON, radius=0.06))
        self.play(FadeIn(upper), FadeIn(lower))

        plus = _label("+", size=42, color=PROTON).move_to(LEFT * 6.2 + UP * 1.6)
        minus = _label("−", size=42, color=PROTON).move_to(LEFT * 6.2 + DOWN * 1.6)
        pmf_label = _label("proton-motive force", size=24, color=PROTON).to_edge(DOWN)
        self.play(Write(plus), Write(minus), Write(pmf_label))
        self.wait(1.2)

        self.protons_upper = upper
        self.protons_lower = lower
        self.pmf_label = pmf_label
        self.plus = plus
        self.minus = minus
        self.play(FadeOut(plus), FadeOut(minus), FadeOut(pmf_label))
        self.wait(0.3)

    # --- scene s4_synthase_rotation: protons spin the rotor ---
    def _scene_synthase_rotation(self) -> None:
        # Fade out ETC complexes to make room.
        self.play(FadeOut(self.complexes))

        # F0 = annulus straddling the membrane on the right.
        center = RIGHT * 3.0
        f0 = Annulus(inner_radius=0.55, outer_radius=0.95,
                     color=PROTEIN, fill_color=PROTEIN, fill_opacity=0.85,
                     stroke_width=0).move_to(center)
        rotor = Circle(radius=0.5, color=PROTEIN_ALT, fill_color=PROTEIN_ALT,
                       fill_opacity=0.95, stroke_width=0).move_to(center)
        marker = Line(start=center, end=center + UP * 0.45,
                      color=BG, stroke_width=4)
        stalk = Line(start=center, end=center + UP * 1.6,
                     color=PROTEIN_ALT, stroke_width=6)
        labels = VGroup(
            _label("F0", size=20).next_to(f0, DOWN, buff=0.1),
            _label("rotor", size=18, color=TEXT_DIM).next_to(f0, RIGHT, buff=0.4),
            _label("stalk", size=18, color=TEXT_DIM).next_to(stalk, RIGHT, buff=0.2),
        )
        self.play(Create(f0), Create(rotor), Create(stalk), FadeIn(marker), FadeIn(labels))

        rotor_group = VGroup(rotor, marker, stalk)

        # 4 protons drop from above and rotate the rotor 1/4 turn each.
        for i in range(4):
            p = Dot(color=PROTON, radius=0.12).move_to(center + UP * 2.2 + RIGHT * 0.2 * (i - 1.5))
            self.play(FadeIn(p), run_time=0.2)
            self.play(p.animate.move_to(center + DOWN * 1.6), Rotate(rotor_group, angle=PI / 2, about_point=center), run_time=0.6)
            self.play(FadeOut(p), run_time=0.15)

        self.f0 = f0
        self.rotor_group = rotor_group
        self.synthase_center = center
        self.synthase_labels = labels

    # --- scene s5_f1_synthesis: rotation makes ATP ---
    def _scene_f1_synthesis(self) -> None:
        center = self.synthase_center + UP * 2.0

        # F1 head: a triangle of three β-subunits around the stalk top.
        triangle = Polygon(
            center + UP * 0.85,
            center + DOWN * 0.55 + LEFT * 0.75,
            center + DOWN * 0.55 + RIGHT * 0.75,
            color=PROTEIN, fill_color=PROTEIN, fill_opacity=0.6, stroke_width=2,
        )
        f1_label = _label("F1", size=20).next_to(triangle, UP, buff=0.1)
        states = VGroup(
            _label("Loose", size=14, color=TEXT_DIM).move_to(center + DOWN * 0.45 + LEFT * 0.6),
            _label("Tight", size=14, color=TEXT_DIM).move_to(center + DOWN * 0.45 + RIGHT * 0.6),
            _label("Open", size=14, color=TEXT_DIM).move_to(center + UP * 0.55),
        )
        self.play(Create(triangle), FadeIn(f1_label), FadeIn(states))

        # ADP+Pi → ATP
        substrate = _label("ADP + Pi", size=18, color=PROTON).next_to(triangle, LEFT, buff=0.5)
        product = _label("ATP", size=20, color=PROTON).next_to(triangle, UP, buff=0.6)
        self.play(FadeIn(substrate))
        self.play(substrate.animate.move_to(center + DOWN * 0.45 + LEFT * 0.55), run_time=0.6)
        self.play(Transform(substrate, product), run_time=0.6)

        # One more rotation cycle to drive the point home.
        self.play(Rotate(self.rotor_group, angle=TAU, about_point=self.synthase_center), run_time=2.4)

        self.f1 = VGroup(triangle, f1_label, states, substrate)
        self.wait(0.6)

    # --- scene s6_relevance_failure: when it breaks ---
    def _scene_failure_modes(self) -> None:
        # Two captions, no full panel split (kept simple to render reliably).
        cyanide = _label("cyanide → Complex IV blocked → no pumping",
                         size=22, color=PROTEIN_ALT).to_edge(DOWN).shift(UP * 0.6)
        uncoupler = _label("uncoupler → membrane leaks H+ → gradient collapses",
                           size=22, color=PROTEIN_ALT).to_edge(DOWN)
        self.play(FadeIn(cyanide))
        self.wait(1.0)
        self.play(FadeIn(uncoupler))

        # Make the proton cloud above the membrane drift downward to visualise
        # the gradient collapsing.
        animations = []
        for d in self.protons_upper:
            target = d.copy().shift(DOWN * 2.0 + np.array([np.random.uniform(-0.3, 0.3), 0, 0]))
            animations.append(d.animate.move_to(target.get_center()))
        self.play(*animations, run_time=1.6)

        no_atp = _label("no ATP", size=36, color=PROTEIN_ALT).to_edge(UP)
        self.play(Write(no_atp))
        self.wait(1.5)
        self.play(FadeOut(no_atp), FadeOut(cyanide), FadeOut(uncoupler))
        self.wait(0.4)
