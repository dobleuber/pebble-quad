"""Step 4: compare a generative part with the hand-drawn one it replaces, on one voxel grid.

    python generative/evaluate.py <part> [voxel_mm]

Both meshes are sampled on the same voxels and solved with the same linear FE the optimizer uses (8-node
bricks, PLA), held and loaded as the problem says, once per load case. It reports, per design: volume and
mass (from the mesh), and per case the compliance (the work of the loads: lower is stiffer) and an indicative
stress (the uniaxial stress with the same strain energy density, 99th percentile over the material away from
the supports and the loaded patches). Voxel stresses are rough: read them as a ratio between the two designs.

Reads out/v1_<baseline>.stl (cad model export of the hand-drawn part) and out/<part>.stl; writes
out/<part>_eval.json. Needs pytopo3d, trimesh, rtree.
"""
import json
import os
import sys

import numpy as np
import trimesh
from scipy.ndimage import binary_dilation

from fe import E, VoxelModel
from problems import PROBLEMS

DENSITY = 1.24e-3                                        # PLA, g/mm3
problem = PROBLEMS[sys.argv[1]]()
h = float(sys.argv[2]) if len(sys.argv) > 2 else problem.voxel
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
model = VoxelModel(problem, h)
X, Y, Z, nx, ny, nz = model.X, model.Y, model.Z, model.nx, model.ny, model.nz


def voxelize(mesh):
    """Which cell centres are inside the mesh: a ray up each column, counting the crossings below each cell."""
    zc = Z[0, 0, :]
    origins = np.stack([X[:, :, 0].ravel() + 1.37e-4, Y[:, :, 0].ravel() + 0.71e-4, np.full(nx * ny, zc[0] - 50.0)], axis=1)
    hits, ray, _ = mesh.ray.intersects_location(origins, np.tile([0.0, 0.0, 1.0], (len(origins), 1)), multiple_hits=True)
    crossings = np.zeros((nx * ny, nz + 1), int)
    np.add.at(crossings, (ray, np.searchsorted(zc, hits[:, 2])), 1)
    return (np.cumsum(crossings, axis=1)[:, :nz] % 2 == 1).reshape(ny, nx, nz)


def study(mesh):
    solid = voxelize(mesh)
    result = {"volume_mm3": round(float(abs(mesh.volume)), 1), "mass_g": round(float(abs(mesh.volume)) * DENSITY, 2),
              "voxel_volume_mm3": round(float(solid.sum() * h ** 3), 1), "cases": {}}
    for case, solved in model.solve(solid).items():
        sigma = np.sqrt(2 * E * solved["energy"])
        judged = solid & ~binary_dilation(solved["touched"], iterations=2)
        result["cases"][case] = {"compliance_Nmm": round(solved["compliance"], 4),
                                 "stress_p99_MPa": round(float(np.percentile(sigma[judged], 99)), 2),
                                 "load_N": round(float(sum(np.linalg.norm(l.force) for l in problem.cases[case])), 2)}
    return result


report = {"part": problem.name, "voxel_mm": h,
          "v1": study(trimesh.load(os.path.join(OUT, f"v1_{problem.baseline}.stl"))),
          "v2": study(trimesh.load(os.path.join(OUT, f"{problem.name}.stl")))}
with open(os.path.join(OUT, f"{problem.name}_eval.json"), "w") as f:
    json.dump(report, f, indent=1)

a, b = report["v1"], report["v2"]
print(f"{problem.name} ({h} mm voxels): hand-drawn {a['mass_g']} g, generative {b['mass_g']} g ({b['mass_g'] / a['mass_g'] - 1:+.0%})")
for case in problem.cases:
    ca, cb = a["cases"][case], b["cases"][case]
    print(f"  {case:<24} compliance {ca['compliance_Nmm']:8.3f} -> {cb['compliance_Nmm']:8.3f} N*mm (stiffness x{ca['compliance_Nmm'] / cb['compliance_Nmm']:.2f})"
          f"   stress p99 {ca['stress_p99_MPa']:6.2f} -> {cb['stress_p99_MPa']:6.2f} MPa (x{cb['stress_p99_MPa'] / ca['stress_p99_MPa']:.2f})")
