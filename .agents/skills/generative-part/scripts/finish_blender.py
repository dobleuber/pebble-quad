"""Step 3: finish the cleaned-up shape in Blender, then restore what must be exact.

    cad run finish_blender.py <problems.py> <part>          (text-to-cad brings Blender's Python)
    blender -b -P finish_blender.py -- <problems.py> <part>   (or a Blender 4.5 or later of your own)

1. Voxel remesh: one even skin over the whole part. Smooth it, push the skin back out a little so thin walls
   keep their thickness, skin it again, subdivide.
2. Booleans: add the crisp features, then cut the keep-outs, the screw holes and whatever is outside the
   envelope's box.

Reads out/<part>_clean.stl; writes out/<part>.stl and, for a mirrored part, <part>_b.stl, its mirror image in y.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_ops as ops  # noqa: E402
from genpart import load  # noqa: E402

problem, _ = load(__doc__.split("\n")[2].strip())
settings = {"voxel": 0.35, "smooth": 25, "swell": 0.12, "subdivide": 1, **problem.extra.get("blender", {})}
within = ops.limits(problem.bounds)


def finish(voxel):
    part = ops.load(problem.path("out", f"{problem.name}_clean.stl"))
    ops.modifier(part, "REMESH", mode="VOXEL", voxel_size=voxel, adaptivity=0.0)
    ops.modifier(part, "SMOOTH", factor=0.8, iterations=settings["smooth"])
    ops.modifier(part, "DISPLACE", strength=settings["swell"], mid_level=0.0)     # along the normals: what smoothing took off
    ops.modifier(part, "REMESH", mode="VOXEL", voxel_size=voxel, adaptivity=0.0)  # a swollen skin can cross itself in a
    ops.modifier(part, "SMOOTH", factor=0.5, iterations=3)                        # crease: the booleans need a clean one
    if settings["subdivide"]:
        ops.modifier(part, "SUBSURF", levels=settings["subdivide"])
    # Two booleans on the fine mesh, each with one tool made of all its primitives: the crisp features added, then
    # the keep-outs, the holes and everything outside the box cut away.
    if problem.preserve:
        ops.boolean(part, ops.combine(problem.preserve, within), "UNION", "MANIFOLD")
    ops.boolean(part, ops.combine(problem.keepout + problem.holes + ops.outside(problem.bounds), within), "DIFFERENCE", "MANIFOLD")
    return part, ops.tidy(part)


# A boolean can still leave an open surface on an unlucky skin: another voxel size is another skin.
for voxel in (settings["voxel"], settings["voxel"] - 0.03, settings["voxel"] + 0.03, settings["voxel"] - 0.06):
    part, (crumbs, doubles, open_edges) = finish(voxel)
    print(f"skin of {voxel:.2f} mm voxels: {crumbs} crumbs and {doubles} doubled faces dropped, {open_edges} open edges")
    if not open_edges:
        break
else:
    sys.exit(f"{problem.name}: no closed surface from any skin")

print("wrote", f"out/{problem.name}.stl", ops.export(part, problem.path("out", f"{problem.name}.stl")), "triangles")
if problem.mirrored:
    ops.mirror_y(part)
    print("wrote", f"out/{problem.name}_b.stl", ops.export(part, problem.path("out", f"{problem.name}_b.stl")), "triangles")
