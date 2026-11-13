"""Example generator: a generic method Figure 1 built with drawlib.

  python example_fig1.py OUT_DIR

Writes OUT_DIR/Figure1.drawio (+ .png/.pdf when draw.io desktop is installed).
Copy this file into a paper's figure_src/, replace the panels with the paper's own
pipeline, swap the palette, and feed real thumbnails/curves through uri()/uri_fig().
The curve and heat-map below are synthetic placeholders only.
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drawlib import Drawing, PILL, uri_fig  # noqa: E402

# a new palette per paper (never reuse the last paper's colours)
NAVY, TEAL, VIOLET, AMBER = "#22356B", "#0E7C86", "#6B3FA0", "#C77C02"
PILL.update({
    "res": dict(fill="#D7F0EE", grad="#7CC8C2", stroke=TEAL),
    "ag": dict(fill="#EDE5F7", grad="#A890D6", stroke=VIOLET),
    "up": dict(fill="#FFE7A8", stroke=AMBER, hatch="#F2B33D"),
    "cls": dict(fill="#2B4A8B", grad="#1C3366", stroke="#13254D", fc="#FFFFFF", bold=True),
})


def placeholder_curve():
    fig, ax = plt.subplots(figsize=(2.2, 1.0))
    t = np.linspace(0, 6, 200)
    ax.plot(t, np.sin(t) + 0.15 * np.cos(5 * t), color=TEAL, lw=2)
    ax.axis("off")
    return uri_fig(fig)


def placeholder_heat():
    fig, ax = plt.subplots(figsize=(1.4, 1.4))
    ax.imshow(np.add.outer(np.sin(np.linspace(0, 3, 16)), np.cos(np.linspace(0, 3, 16))), cmap="magma")
    ax.axis("off")
    return uri_fig(fig)


def main(out):
    d = Drawing()
    W, H = 1500, 640
    # (A) input
    d.panel(20, 20, 330, 520, "A", "Input data", NAVY, "#F3F5FA", fs=24, bar=48)
    d.image(55, 90, 260, 120, placeholder_curve(), stroke=NAVY)
    d.label(55, 215, 260, 30, "raw signal", fs=24)
    d.image(110, 280, 150, 150, placeholder_heat(), stroke=NAVY)
    d.label(55, 440, 260, 30, "feature map", fs=24)
    # (B) encoder
    d.panel(400, 20, 470, 520, "B", "Encoder", TEAL, "#F0F8F8", fs=24, bar=48)
    for k in range(4):
        d.cube(440 + k * 100, 120 + k * 25, 60, 300 - k * 50, "#D7F0EE", TEAL, size=14, text="block %d" % (k + 1), fs=22)
    d.op(840, 280, "+", d=34, fs=24)
    # (C) novel block, zoomed
    d.panel(920, 20, 300, 520, "C", "New block", VIOLET, "#F6F2FB", fs=24, bar=48)
    d.pill(950, 110, 240, 54, "gating", kind="ag", fs=24)
    d.pill(950, 200, 240, 54, "update rule", kind="ag", fs=24)
    d.pill(950, 290, 240, 54, "pooling", kind="up", fs=24)
    d.label(950, 380, 240, 40, "h = g ⊙ u", fs=26, italic=True)
    # (D) output
    d.panel(1270, 20, 210, 520, "D", "Output", AMBER, "#FFF8EA", fs=24, bar=48)
    d.pill(1295, 230, 160, 70, "decision", kind="cls", fs=24)
    # arrows and legend
    d.flow(350, 280, 400, 280)
    d.flow(870, 280, 920, 280)
    d.flow(1220, 280, 1270, 280)
    d.legend(40, 580, [("res", "layer"), ("ag", "new component"), ("up", "pooling"), ("cls", "output")], fs=24)
    os.makedirs(out, exist_ok=True)
    d.save(os.path.join(out, "Figure1.drawio"), W, H)
    print("wrote", os.path.join(out, "Figure1.drawio"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
