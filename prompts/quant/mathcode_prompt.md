# MathCode prompt

Used only behind `--quant`. Send the topic and ask MathCode for the formal
derivation. The result is then translated by a small post-processing pass
into normal pedagogical English and fed into pedagogy/ and scenes/. Never
expose Lean-level artifacts to the user unless debug mode is on.

Good uses (per blueprint): Michaelis–Menten, Hill functions, diffusion,
Hardy–Weinberg, logistic growth, SIR/SEIR, binding curves, population
genetics. Do not route standard cell biology, immunology, anatomy, or
signalling through this path by default.
