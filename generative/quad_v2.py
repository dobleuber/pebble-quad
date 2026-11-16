"""The quadruped with the structural parts the generative pipeline in this folder improved: the thighs and the
chassis tray. The lower legs stay hand-drawn (the pipeline did not beat them: see README.md), and everything
else, the joints and the moves are src/robot.py's.

    cad run generative/quad_v2.py

A document holds B-rep, and these parts are meshes: each comes in as a faceted solid built from the triangles
of its light copy (parts/<part>_lite.stl, a few thousand of them), close enough for the interference, travel
and mass checks. The meshes to print are parts/<part>.stl.
"""
import sys
from pathlib import Path

import build123d as bd
from bd_materials import plastics
from cad import model, stl
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
import parts  # noqa: E402
from robot import assemble  # noqa: E402

GROWN = "#8d939b"     # the grown parts, a shade lighter than the frame so they read


def faceted(name, label):
    """A mesh file as a solid of flat triangular faces."""
    mesh = stl.read(HERE / "parts" / f"{name}_lite.stl")
    points = [bd.Vector(*v) for v in mesh.vertices]
    sewing = BRepBuilderAPI_Sewing(1e-3)
    for triangle in mesh.triangles:
        a, b, c = (points[i] for i in triangle)
        if min((b - a).length, (c - b).length, (a - c).length) > 1e-4:      # no face on an edge of no length
            sewing.Add(bd.Face(bd.Wire.make_polygon([a, b, c])).wrapped)
    sewing.Perform()
    shells = bd.Shape.cast(sewing.SewedShape()).shells()         # a few triangles may sew apart: the part is the big one
    solid = bd.Solid(max(shells, key=lambda shell: shell.area))
    if solid.volume < 0:
        solid = bd.Solid(solid.wrapped.Reversed())
    assert solid.is_valid, f"{name}: the light copy does not close into a solid"
    solid.label = label
    solid.material = plastics.pla()
    solid.color = GROWN
    return solid


@model
def thigh_a():
    return faceted("thigh", "thigh")


@model
def thigh_b():
    return faceted("thigh_b", "thigh")


@model
def tray():
    return faceted("tray", "tray")


@model
def quad_v2():
    return assemble(tray().shape, lambda hand: (thigh_a if hand > 0 else thigh_b)().shape,
                    lambda hand: (parts.shank_a if hand > 0 else parts.shank_b)().shape)


if __name__ == "__main__":
    quad_v2()
