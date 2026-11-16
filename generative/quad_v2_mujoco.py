"""The generative build as a MuJoCo model: src/quad_mujoco.py's collisions, servos and actuators on quad_v2.

    cad run generative/quad_v2_mujoco.py   ->  generative/sim/quad.xml (+ assets/)

Masses and inertias are the CAD's (the faceted solids). What is drawn is the mesh that prints: the structural
parts' light copies are swapped for the full meshes, in the same frames.
"""
import shutil
import sys
from pathlib import Path

from cad.mujoco import save

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from quad_mujoco import quad_mujoco  # noqa: E402
from quad_v2 import quad_v2  # noqa: E402

# mesh in the model (a part's first prototype keeps the part's name, the mirrored one gets _2) -> mesh that prints
PRINTED = {"tray": "tray", "thigh": "thigh", "thigh_2": "thigh_b"}

if __name__ == "__main__":
    s = quad_mujoco(robot=quad_v2())
    for name, printed in PRINTED.items():
        mesh = s.mesh(name)
        mesh.file = str(HERE / "parts" / f"{printed}.stl")
        mesh.scale = [0.001, 0.001, 0.001]                    # the parts' meshes are in mm
    save(s, str(HERE / "sim" / "quad.xml"))
    if not (HERE / "sim" / "scene.xml").exists():
        shutil.copyfile(HERE.parent / "sim" / "scene.xml", HERE / "sim" / "scene.xml")
