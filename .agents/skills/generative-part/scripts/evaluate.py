"""Step 4: measure a generative part and, when the problem names one, the part it replaces, on one voxel grid.

    python evaluate.py <problems.py> <part> [voxel_mm]

Each mesh is sampled on the same voxels and solved with the linear FE the optimizer uses (8-node bricks), held
and loaded as the problem says, once per load case. It reports, per design: volume and mass (from the mesh),
and per case the compliance (the work of the loads: lower is stiffer) and an indicative stress (the uniaxial
stress with the same strain energy density, 99th percentile over the material away from the supports and the
loaded patches). Voxel stresses are rough: with a baseline, read them as a ratio between the two designs, and
never as a safety factor.

Reads out/<part>.stl and the problem's `baseline` STL (same frame); writes out/<part>_eval.json and adds the
run to out/<part>_attempts.json.
Needs pytopo3d, trimesh, rtree.
"""
import json
import os
import time

import numpy as np
import trimesh
from scipy.ndimage import binary_dilation

from fe import VoxelModel, voxelize
from genpart import load

problem, rest = load(__doc__.split("\n")[2].strip())
h = float(rest[0]) if rest else problem.voxel
model = VoxelModel(problem, h)


def study(path):
    mesh = trimesh.load(path)
    solid = voxelize(model, mesh)
    volume = float(abs(mesh.volume))
    result = {"file": os.path.relpath(path, problem.folder), "volume_mm3": round(volume, 1), "mass_g": round(volume * problem.density, 2),
              "voxel_volume_mm3": round(float(solid.sum() * h ** 3), 1), "cases": {}}
    for case, solved in model.solve(solid).items():
        sigma = np.sqrt(2 * problem.youngs * solved["energy"])
        judged = solid & ~binary_dilation(solved["touched"], iterations=2)
        result["cases"][case] = {"compliance_Nmm": round(solved["compliance"], 4),
                                 "stress_p99_MPa": round(float(np.percentile(sigma[judged], 99)), 2),
                                 "load_N": round(float(sum(np.linalg.norm(l.force) for l in problem.cases[case])), 2)}
    return result


report = {"part": problem.name, "voxel_mm": h, "generative": study(problem.path("out", f"{problem.name}.stl"))}
if problem.baseline:
    report["baseline"] = study(os.path.join(problem.folder, problem.baseline))
with open(problem.path("out", f"{problem.name}_eval.json"), "w") as f:
    json.dump(report, f, indent=1)

# Every evaluation is an attempt: keep its settings and numbers, so runs can be compared after out/ is overwritten.
log = problem.path("out", f"{problem.name}_attempts.json")
attempts = json.load(open(log)) if os.path.exists(log) else []
attempts.append({"when": time.strftime("%Y-%m-%d %H:%M"), "voxel": problem.voxel, "volfrac": problem.volfrac, "rmin": problem.rmin,
                 "balance": problem.balance, "weights": problem.weights, "bounds": list(problem.bounds), "cases": list(problem.cases),
                 "mass_g": report["generative"]["mass_g"], "baseline_mass_g": report.get("baseline", {}).get("mass_g"),
                 "stiffness_x": {c: round(report["baseline"]["cases"][c]["compliance_Nmm"] / report["generative"]["cases"][c]["compliance_Nmm"], 2)
                                 for c in problem.cases} if "baseline" in report else None})
with open(log, "w") as f:
    json.dump(attempts, f, indent=1)

b, g = report.get("baseline"), report["generative"]
if b:
    print(f"{problem.name} ({h} mm voxels): baseline {b['mass_g']} g, generative {g['mass_g']} g ({g['mass_g'] / b['mass_g'] - 1:+.0%})")
else:
    print(f"{problem.name} ({h} mm voxels): generative {g['mass_g']} g; no baseline to compare with")
for case in problem.cases:
    cg = g["cases"][case]
    if b:
        cb = b["cases"][case]
        print(f"  {case:<24} compliance {cb['compliance_Nmm']:8.3f} -> {cg['compliance_Nmm']:8.3f} N*mm (stiffness x{cb['compliance_Nmm'] / cg['compliance_Nmm']:.2f})"
              f"   stress p99 {cb['stress_p99_MPa']:6.2f} -> {cg['stress_p99_MPa']:6.2f} MPa (x{cg['stress_p99_MPa'] / cb['stress_p99_MPa']:.2f})")
    else:
        print(f"  {case:<24} compliance {cg['compliance_Nmm']:8.3f} N*mm   stress p99 {cg['stress_p99_MPa']:6.2f} MPa (indicative)")
