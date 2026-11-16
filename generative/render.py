"""Pictures of the generative build, with the parts drawn as they print.

    cad model export <quad_v2's id> generative/out/quad_v2.glb --tolerance 0.02 --angle 5
    cad run generative/render.py [--final] [--no-shell]

The GLB holds the light, faceted copies the checks use; here each is swapped for the full mesh, in the same
frame. Writes media/quad_v2.png (and quad_v2_open.png with --no-shell) with Cycles: a quick draft, or --final.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

from cad.blender import load

HERE = Path(__file__).resolve().parent
FINAL, OPEN = "--final" in sys.argv, "--no-shell" in sys.argv
PRINTED = {"thigh_fl/thigh": "thigh", "thigh_rr/thigh": "thigh", "thigh_fr/thigh": "thigh_b", "thigh_rl/thigh": "thigh_b",
           "chassis/tray": "tray"}



def box_of(mesh):
    corners = [v.co for v in mesh.vertices]
    return [f(c[i] for c in corners) for i in range(3) for f in (min, max)]


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
model = load(HERE / "out" / "quad_v2.glb")

for path, name in PRINTED.items():                       # the light copy's object keeps its place and look
    part = model.objects[path]
    look = part.data.materials[0] if part.data.materials else None
    bpy.ops.wm.stl_import(filepath=str(HERE / "parts" / f"{name}.stl"))
    full = bpy.context.selected_objects[0]
    mesh = full.data
    bpy.data.objects.remove(full, do_unlink=True)
    if look:
        mesh.materials.append(look)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    # The file is Y up and Blender turns its objects, not their vertices: find the quarter turn about X that puts
    # the full mesh in the light copy's box.
    was = box_of(part.data)
    for turn in (Matrix.Identity(4), Matrix.Rotation(math.pi / 2, 4, "X"), Matrix.Rotation(-math.pi / 2, 4, "X")):
        trial = mesh.copy()
        trial.transform(turn)
        if all(abs(a - b) < 0.5 for a, b in zip(box_of(trial), was)):
            part.data = trial
            break
    else:
        sys.exit(f"{path}: the full mesh does not fit the light copy's box in any orientation")
if OPEN:
    for path in ("chassis/shell", "chassis/visor"):
        model.objects[path].hide_render = True

scene.render.resolution_x, scene.render.resolution_y = 1600, 1200
aim = bpy.data.objects.new("aim", None)
aim.location = model.center + Vector((0, 0, -0.008 if not OPEN else -0.015))
camera = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
camera.data.lens = 70
view = math.tan(camera.data.angle / 2) * min(1, scene.render.resolution_y / scene.render.resolution_x)
distance = model.size.length / 2 / view * 0.72
camera.location = aim.location + distance * Vector((1.0, -1.25, 0.42 if not OPEN else 0.6)).normalized()
camera.constraints.new("TRACK_TO").target = aim
scene.collection.objects.link(aim)
scene.collection.objects.link(camera)
scene.camera = camera

bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, model.box[0].z if hasattr(model.box[0], "z") else model.box[0][2]))
floor = bpy.context.active_object
paper = bpy.data.materials.new("floor")
paper.diffuse_color = (0.55, 0.56, 0.58, 1)
floor.data.materials.append(paper)

for name, kind, energy, place, size in (("key", "AREA", 3.0, (0.25, -0.30, 0.40), 0.35), ("fill", "AREA", 1.0, (-0.35, -0.20, 0.25), 0.5),
                                        ("rim", "AREA", 2.0, (-0.10, 0.40, 0.30), 0.3)):
    light = bpy.data.objects.new(name, bpy.data.lights.new(name, kind))
    light.data.energy, light.data.size = energy, size
    light.location = model.center + Vector(place)
    light.constraints.new("TRACK_TO").target = aim
    scene.collection.objects.link(light)
scene.world = bpy.data.worlds.new("world")
background = scene.world.node_tree.nodes["Background"]
background.inputs["Color"].default_value = (0.85, 0.87, 0.90, 1)
background.inputs["Strength"].default_value = 0.35

scene.render.engine = "CYCLES"                           # on the CPU: it needs no display, which EEVEE does
scene.cycles.samples = 128 if FINAL else 16
scene.cycles.use_denoising = True
if not FINAL:
    scene.render.resolution_percentage = 50
scene.render.filepath = str(HERE / "media" / ("quad_v2_open.png" if OPEN else "quad_v2.png"))
bpy.ops.render.render(write_still=True)
print("wrote", scene.render.filepath, "; parts in the file:", ", ".join(sorted(model.objects)[:60]))
