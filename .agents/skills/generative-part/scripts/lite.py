"""Step 5: hand the finished meshes to an assembly.

    cad run lite.py <problems.py> <part>          (or: blender -b -P lite.py -- <problems.py> <part>)

Copies out/<part>.stl (and its mirror image) to parts/, the meshes to print, and writes beside each a light
copy, <part>_lite.stl: the same shape in a few thousand triangles, which a CAD assembly can turn into a faceted
solid for interference, travel and mass checks (references/assembly.md). Thinning a mesh moves its faces by a
few hundredths, so the light copy is trimmed to the box and cut by the keep-outs once more: it never reaches
into a motor, a screw head or a neighbour.
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_ops as ops  # noqa: E402
from genpart import load  # noqa: E402

problem, _ = load(__doc__.split("\n")[2].strip())
triangles = problem.extra.get("lite", 3000)
within = ops.limits(problem.bounds)

shutil.copyfile(problem.path("out", f"{problem.name}.stl"), problem.path("parts", f"{problem.name}.stl"))
part = ops.load(problem.path("out", f"{problem.name}.stl"))
ops.modifier(part, "DECIMATE", ratio=min(1.0, triangles / len(part.data.polygons)), use_collapse_triangulate=True)
ops.boolean(part, ops.combine(problem.keepout + ops.outside(problem.bounds), within), "DIFFERENCE", "MANIFOLD")
cut = part.data
for distance in (0.002, 0.0005, 0.0):                        # weld the cuts' slivers (a solid's faces need area), as
    part.data = cut.copy()                                   # far as the surface stays closed
    if distance:
        ops.weld(part, distance)
    _, _, open_edges = ops.tidy(part)
    if not open_edges:
        break
assert not open_edges, f"the light copy is not a closed surface: {open_edges} open edges"
print("wrote", f"parts/{problem.name}_lite.stl", ops.export(part, problem.path("parts", f"{problem.name}_lite.stl")), "triangles")
if problem.mirrored:
    shutil.copyfile(problem.path("out", f"{problem.name}_b.stl"), problem.path("parts", f"{problem.name}_b.stl"))
    ops.mirror_y(part)
    print("wrote", f"parts/{problem.name}_b_lite.stl", ops.export(part, problem.path("parts", f"{problem.name}_b_lite.stl")), "triangles")
