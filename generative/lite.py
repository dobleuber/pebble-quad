"""Step 5: hand the finished meshes to the robot's model.

    cad run generative/lite.py <part>

Copies out/<part>.stl (and its mirror image) to parts/, the meshes to print, and writes beside each a light
copy, <part>_lite.stl: the same shape in a few thousand triangles, which the CAD assembly turns into a
faceted solid (generative/quad_v2.py) for its interference, travel and mass checks. Thinning a mesh moves its
faces by a few hundredths, so the light copy is trimmed to the envelope and cut by the keep-outs once more:
it never reaches into a servo, a screw head or the foot.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blender_ops as ops  # noqa: E402
from problems import PROBLEMS  # noqa: E402

problem = PROBLEMS[sys.argv[1]]()
OUT, PARTS = os.path.join(HERE, "out"), os.path.join(HERE, "parts")
os.makedirs(PARTS, exist_ok=True)
triangles = problem.extra.get("lite", 3000)
within = ops.limits(problem.bounds)

shutil.copyfile(os.path.join(OUT, f"{problem.name}.stl"), os.path.join(PARTS, f"{problem.name}.stl"))
part = ops.load(os.path.join(OUT, f"{problem.name}.stl"))
ops.modifier(part, "DECIMATE", ratio=triangles / len(part.data.polygons), use_collapse_triangulate=True)
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
print("wrote", f"parts/{problem.name}_lite.stl", ops.export(part, os.path.join(PARTS, f"{problem.name}_lite.stl")), "triangles")
if problem.mirrored:
    shutil.copyfile(os.path.join(OUT, f"{problem.name}_b.stl"), os.path.join(PARTS, f"{problem.name}_b.stl"))
    ops.mirror_y(part)
    print("wrote", f"parts/{problem.name}_b_lite.stl", ops.export(part, os.path.join(PARTS, f"{problem.name}_b_lite.stl")), "triangles")
