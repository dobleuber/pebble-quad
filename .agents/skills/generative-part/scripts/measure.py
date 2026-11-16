"""Measure an existing part and what surrounds it, to start a problem from.

    python measure.py part.stl [neighbour.stl ...]

All files in the same frame and in mm (export them so: the part's own frame, print bed at its lowest face).
Prints the part's box, volume and mass in PLA, a box for the design space snapped outward to the 0.25 mm grid the
cleanup works on, and each neighbour's box as a keep-out line to paste: a first, coarse answer - a round neighbour
wants a zcyl, and a neighbour that only touches the part is a face to mate with, not a volume to avoid.
"""
import math
import sys

import numpy as np
import trimesh

GRID = 0.25
part = trimesh.load(sys.argv[1])
lo, hi = part.bounds
print(f"{sys.argv[1]}: box x {lo[0]:.2f}..{hi[0]:.2f}, y {lo[1]:.2f}..{hi[1]:.2f}, z {lo[2]:.2f}..{hi[2]:.2f} mm; "
      f"{abs(part.volume):.0f} mm3, {abs(part.volume) * 1.24e-3:.2f} g in PLA; {'closed' if part.is_watertight else 'NOT closed'}")
snap = [math.floor(v / GRID) * GRID for v in lo] + [math.ceil(v / GRID) * GRID for v in hi]
print(f"its box on the grid:  bounds=({snap[0]:g}, {snap[3]:g}, {snap[1]:g}, {snap[4]:g}, {snap[2]:g}, {snap[5]:g})"
      "   (widen it wherever the part has room to grow)")
for path in sys.argv[2:]:
    other = trimesh.load(path)
    a, b = other.bounds
    gap = max(max(a[i] - hi[i], lo[i] - b[i]) for i in range(3))
    where = f"{gap:.2f} mm away from the part's box" if gap > 0 else "reaches into the part's box"
    print(f"box({a[0]:.2f}, {b[0]:.2f}, {a[1]:.2f}, {b[1]:.2f}, {a[2]:.2f}, {b[2]:.2f}),   # {path}: {where}")
    if gap <= 0:                                             # how much of the part itself that box would cut away
        axes = [np.arange(max(lo[i], a[i]) + 0.25, min(hi[i], b[i]), 0.5) for i in range(3)]
        if all(len(axis) for axis in axes):
            points = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
            swallowed = part.contains(points).sum() * 0.5 ** 3
            if swallowed > 1:
                print(f"    as one box it would cut {swallowed:.0f} mm3 out of the part itself (features that reach around the "
                      "neighbour, such as posts under a motor's tabs): describe the neighbour as several smaller boxes instead")
