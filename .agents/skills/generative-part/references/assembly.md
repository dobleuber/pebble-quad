# The grown part in an assembly, in simulation and in pictures

A grown part is a mesh. The design it goes back into is usually CAD, and its checks (do parts collide through
the moves, how far does a joint turn, what does it weigh, does it walk) should run again with the new part.
Keep the original design as it is and make a second build beside it that swaps the parts: the comparison stays
possible, and nothing is lost if the grown part is dropped.

## Contents

- [A solid from the light copy (text-to-cad / build123d)](#a-solid-from-the-light-copy)
- [Left and right hands](#left-and-right-hands)
- [A second build that shares the assembly](#a-second-build-that-shares-the-assembly)
- [MuJoCo: simulate with the solid, show the mesh](#mujoco)
- [Renders in Blender](#renders-in-blender)
- [Other CAD systems](#other-cad-systems)

## A solid from the light copy

A CAD document holds B-rep, not meshes, and a solid of 200 000 triangular faces would stall every boolean.
`lite.py` writes `parts/<part>_lite.stl`: the same shape in about 3000 triangles (within 0.5 % of the volume),
cut by the keep-outs again so it never reaches into a neighbour. Sewn into a solid of flat faces, it goes
through interference, joint travel and mass checks like any part:

```python
from pathlib import Path

import build123d as bd
from bd_materials import plastics
from cad import model, stl
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing

HERE = Path(__file__).resolve().parent


def faceted(name, label):
    """A mesh file as a solid of flat triangular faces."""
    mesh = stl.read(HERE / "parts" / f"{name}_lite.stl")          # read through cad: the model is rebuilt when the file changes
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
    return solid


@model
def thigh():
    return faceted("thigh", "thigh")
```

Give each grown part a model of its own, so the server caches it: the first build of an assembly with a few of
them takes a couple of minutes, later ones seconds. The solid is in the problem's frame, which is the part's
frame: place it exactly as the original was placed.

What to expect from the checks:

- **Interference**: grown parts touch their neighbours on the same faces the originals did (seats, bosses).
  A sliver of shared volume at a press fit means the light copy was not cut by that keep-out: add the neighbour
  to `keepout` and run `lite` again.
- **Envelope**: the grown part usually fills more of its box than the original did. Anything that assumed the
  original's outline (a collision guard in firmware, a clearance to the other leg) must be checked again with
  the new one, not taken on trust.
- **Mass and inertia** come from the solid, within 0.5 % of the mesh.

## Left and right hands

A part that was its own mirror image when drawn by hand (a symmetric plate) rarely is once grown: its loads
are not symmetric. Set `mirrored=True` and the pipeline writes `<part>_b`, the mirror image in y. Which side
gets which: describe the problem for one side, and say which in its docstring; a side that is that one's
reflection takes `_b`. For a leg placed with a right-handed frame (x along the limb, z outward), mirroring the
robot left to right or front to back flips the frame's y, so the part to use is the mirrored one whenever the
product of the two side signs is negative.

## A second build that shares the assembly

Do not copy the assembly's code to swap two parts. Split it once into a function that takes the parts that
vary, and call it twice:

```python
def assemble(tray, thigh_of, shank_of):      # thigh_of(hand) -> the solid for that hand (+1 or -1)
    ...                                      # everything else: motors, joints, poses, moves


@model
def robot():                                 # the original, unchanged for everyone who uses it
    return assemble(tray().shape, lambda hand: thigh().shape, ...)
```

and in the generative folder:

```python
@model
def robot_v2():
    return assemble(tray().shape, lambda hand: (thigh_a if hand > 0 else thigh_b)().shape, ...)
```

After the split, rebuild the original and regenerate whatever is generated from it: nothing should change.

## MuJoCo

Generate the description from the second build as from the first (`cad.mujoco.spec`): masses and inertias then
come from the solids. What it draws is the light copy; swap the drawn mesh for the one that prints, in the
script that generates the model, never by hand in the generated folder:

```python
s = build_spec(robot=robot_v2())             # the project's own function around cad.mujoco.spec
for name, printed in {"thigh": "thigh", "thigh_2": "thigh_b"}.items():   # a mirrored prototype gets _2
    mesh = s.mesh(name)
    mesh.file = str(HERE / "parts" / f"{printed}.stl")
    mesh.scale = [0.001, 0.001, 0.001]       # the parts' meshes are in mm, the model in metres
save(s, str(HERE / "sim" / "robot.xml"))
```

Collision shapes stay primitives fitted to the parts, as for the original. Run the same tests on both builds
and compare them test by test: a few grams rarely change a gait, and marginal tests move either way.

## Renders in Blender

Export the second build as GLB and load it with `cad.blender.load` (the render skill). Its grown parts are the
faceted light copies; replace each one's mesh data with the full mesh, keeping the object, its place and its
material. Two things to know:

- The GLB is Y up and Blender turns the objects, not their vertices: a mesh read from the part's STL is a
  quarter turn about X away from the light copy's data. Try the identity and both quarter turns and keep the one
  whose box matches the light copy's.
- A headless machine has no display for EEVEE. Render with Cycles on the CPU: 16 samples at half size for a
  draft, about 128 for the final, with denoising.

```python
def box_of(mesh):
    corners = [v.co for v in mesh.vertices]
    return [f(c[i] for c in corners) for i in range(3) for f in (min, max)]


part = model.objects["thigh_fl/thigh"]
bpy.ops.wm.stl_import(filepath=str(HERE / "parts" / "thigh.stl"))
full = bpy.context.selected_objects[0]
mesh = full.data
bpy.data.objects.remove(full, do_unlink=True)
mesh.materials.append(part.data.materials[0])
for polygon in mesh.polygons:
    polygon.use_smooth = True
for turn in (Matrix.Identity(4), Matrix.Rotation(math.pi / 2, 4, "X"), Matrix.Rotation(-math.pi / 2, 4, "X")):
    trial = mesh.copy()
    trial.transform(turn)
    if all(abs(a - b) < 0.5 for a, b in zip(box_of(trial), box_of(part.data))):
        part.data = trial
        break
```

Give the grown parts a lighter colour than the rest in the model: organic shapes disappear in a dark one.

## Other CAD systems

- **OpenSCAD**: `import("parts/<part>.stl");` placed with the original's transform. The full mesh is fine there.
- **FreeCAD, Fusion, others**: import the STL as a mesh body for looks and for a printable file; use the light
  copy if the system must convert it to a solid.
- **Only printing**: `parts/<part>.stl` is the deliverable. Print it as modelled, bed at z = 0, with supports.
