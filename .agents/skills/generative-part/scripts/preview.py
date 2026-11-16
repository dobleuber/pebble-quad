"""Step 0: look at a problem before spending minutes on it.

    python preview.py <problems.py> <part>

Draws out/<part>_problem.png, three views of what the optimizer will be told: the design space (grey), the
keep-outs (red), the crisp features (blue), where the part is held (green), where each case loads it (orange)
and the holes (dark), with each force as an arrow (dashed, at the nearest edge, when it acts off the picture). With a baseline, its edges are drawn over them. Prints the numbers that decide whether the
problem can work: cells, how much of the space the crisp features take, and what each load lands on.
Needs matplotlib, and trimesh for a baseline.
"""
import os

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402

from genpart import load, sdf, union  # noqa: E402

problem, _ = load(__doc__.split("\n")[2].strip())
h = min(problem.voxel, 0.5)
X, Y, Z = problem.coords(h)
x0, x1, y0, y1, z0, z1 = problem.bounds
obstacle = (problem.envelope(X, Y, Z) > 0) | (union(problem.keepout, X, Y, Z) < 0)
keepout = (union(problem.keepout, X, Y, Z) < 0) & (problem.envelope(X, Y, Z) <= 0)
solid = (union(problem.preserve, X, Y, Z) < 0) & ~obstacle
support = (union(problem.support, X, Y, Z) < 0) & ~obstacle
loaded = np.zeros(X.shape, bool)
for loads in problem.cases.values():
    for one in loads:
        for patch in one.patches:
            loaded |= (sdf(patch, X, Y, Z) < 0) & ~obstacle

Xo, Yo, Zo = problem.coords(problem.voxel)                   # the numbers, on the optimizer's own cells
blocked = (problem.envelope(Xo, Yo, Zo) > 0) | (union(problem.keepout, Xo, Yo, Zo) < 0)
space = (~blocked).sum() * problem.voxel ** 3
kept = ((union(problem.preserve, Xo, Yo, Zo) < 0) & ~blocked).sum() * problem.voxel ** 3
print(f"{problem.name}: {Xo.shape[0]} x {Xo.shape[1]} x {Xo.shape[2]} = {Xo.size} cells of {problem.voxel} mm for the optimizer; design space "
      f"{space:.0f} mm3; crisp features {kept:.0f} mm3 = {kept / space:.2f} of it; volume fraction {problem.volfrac} "
      f"-> about {problem.volfrac * space:.0f} mm3, {problem.volfrac * space * problem.density:.2f} g before cleanup (which adds 5 to 20 %)")
problems = []
if not support.any():
    problems.append("nothing is held: `support` falls outside the design space")
if problem.volfrac < kept / space + 0.03:
    problems.append(f"the crisp features alone fill {kept / space:.2f} of the space: volfrac must be well above that")
for case, loads in problem.cases.items():
    for one in loads:
        cells = [int(((sdf(p, X, Y, Z) < 0) & ~obstacle).sum()) for p in one.patches]
        try:                                                  # the same distribution the optimizer will use
            problem.load_field(case, Xo, Yo, Zo, ~blocked)
        except AssertionError as error:
            if str(error) not in problems:
                problems.append(str(error))
        if not all(cells):
            problems.append(f"case {case!r}: a load patch holds no material (it lies in a keep-out or outside the envelope)")
        print(f"  case {case!r}: force {tuple(round(float(f), 2) for f in one.force)} N at {tuple(round(float(c), 1) for c in one.point)}, "
              f"on {len(one.patches)} patch(es) of {[round(c * h ** 3, 1) for c in cells]} mm3")
for message in problems:
    print("  PROBLEM:", message)

outline = None
if problem.baseline:
    import trimesh
    outline = trimesh.load(os.path.join(problem.folder, problem.baseline))

views = (("top (x, y)", 2, (x0, x1, y0, y1), 0, 1), ("side (x, z)", 1, (x0, x1, z0, z1), 0, 2), ("end (y, z)", 0, (y0, y1, z0, z1), 1, 2))
fig, axes = plt.subplots(1, 3, figsize=(18, 6), facecolor="white")
holes = (union(problem.holes, X, Y, Z) < 0) & (problem.envelope(X, Y, Z) <= 0)
layers = ((~obstacle, (0.80, 0.80, 0.80)), (keepout, (0.90, 0.35, 0.30)), (solid, (0.25, 0.45, 0.85)),
          (support, (0.20, 0.65, 0.30)), (loaded, (0.95, 0.60, 0.10)), (holes, (0.15, 0.15, 0.15)))
for ax, (title, axis, extent, a, b) in zip(axes, views):
    picture = np.ones(tuple(s for i, s in enumerate(X.shape) if i != axis)[::-1] + (3,))
    for mask, colour in layers:
        seen = mask.any(axis=axis).T
        picture[seen] = 0.45 * picture[seen] + 0.55 * np.array(colour)
    ax.imshow(picture, origin="lower", extent=extent, interpolation="nearest")
    if outline is not None:
        edges = outline.vertices[outline.edges_unique][:: max(1, len(outline.edges_unique) // 20000)][:, :, [a, b]]
        ax.add_collection(LineCollection(edges, colors="black", linewidths=0.4, alpha=0.35))
    span = max(extent[1] - extent[0], extent[3] - extent[2])
    drawn = set()
    for loads in problem.cases.values():                 # each force where it acts; one that acts off the picture is
        for one in loads:                                # drawn dashed at the nearest edge, with where it really is
            u, v = one.point[a], one.point[b]
            push = np.array([one.force[a], one.force[b]])
            size = float(np.linalg.norm(one.force))
            if np.linalg.norm(push) < 0.15 * size or (round(u, 1), round(v, 1), tuple(np.sign(push))) in drawn:
                continue                                 # it points at the viewer, or is already there
            drawn.add((round(u, 1), round(v, 1), tuple(np.sign(push))))
            cu = min(max(u, extent[0] - 0.08 * span), extent[1] + 0.08 * span)
            cv = min(max(v, extent[2] - 0.08 * span), extent[3] + 0.08 * span)
            off = (cu, cv) != (u, v)
            du, dv = 0.16 * span * push / np.linalg.norm(push)
            ax.annotate("", xy=(cu + du, cv + dv), xytext=(cu, cv),
                        arrowprops={"arrowstyle": "->", "color": "black", "lw": 1.4, "linestyle": "--" if off else "-"})
            ax.annotate(f"{size:.3g} N" + (f", acts at {tuple(round(float(c), 1) for c in one.point)}" if off else ""),
                        xy=(cu, cv), fontsize=7, ha="center", va="top")
    ax.set_xlim(extent[0] - 0.1 * span, extent[1] + 0.1 * span)
    ax.set_ylim(extent[2] - 0.1 * span, extent[3] + 0.1 * span)
    ax.set_title(title)
    ax.set_aspect("equal")
fig.suptitle(f"{problem.name}: design space grey, keep-outs red, crisp features blue, held green, loaded orange, holes dark"
             + (", baseline in thin lines" if outline is not None else ""), fontsize=13)
fig.tight_layout()
target = problem.path("out", f"{problem.name}_problem.png")
fig.savefig(target, dpi=90)
print("wrote", target)
