"""Step 2: make the optimizer's shape buildable, with distance-field operations on a 0.25 mm grid.

    python generative/cleanup.py <part>

1. The density field becomes a solid; anything thinner than the minimum wall is grown to it.
2. The crisp features are melted in (bosses, seats, liners); the keep-outs and the screw holes are cut exactly;
   the part is trimmed to its envelope (flat on the bed).
3. Cracks are filled, sealed bubbles too, and whatever is still thinner than a printable wall is dropped.
4. Material that works in no load case (stubs of half-formed members) is pruned, and the thinnest walls get a
   margin for the smoothing still to come.

Writes generative/out/<part>_clean.stl and <part>_clean.npy (the final voxels, 6 empty cells around).
Needs pytopo3d, scipy, scikit-image, trimesh.
"""
import os
import sys

import numpy as np
import trimesh
from scipy.ndimage import binary_fill_holes, distance_transform_edt as edt, gaussian_filter, label, map_coordinates
from skimage.measure import marching_cubes

from fe import VoxelModel
from problems import PROBLEMS, sdf, union

problem = PROBLEMS[sys.argv[1]]()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
S, PAD = 0.25, 6                                        # working cell, and empty cells around the box
IDLE = 1e-4                                             # share of the 99th-percentile energy density under which material is idle
h = float(open(os.path.join(OUT, f"{problem.name}_rho.txt")).read())

rho = np.load(os.path.join(OUT, f"{problem.name}_rho.npy")).transpose(1, 0, 2)      # [y, x, z] -> [x, y, z]
X, Y, Z = problem.coords(S, pad=PAD)
x0, _, y0, _, z0, _ = problem.bounds
index = np.stack([(X - x0) / h - 0.5, (Y - y0) / h - 0.5, (Z - z0) / h - 0.5])     # the fine cells, in the coarse grid's indices
solid = gaussian_filter(map_coordinates(rho, index, order=1, mode="nearest"), 0.3 / S) > 0.5
envelope = problem.envelope(X, Y, Z)
keepout = union(problem.keepout, X, Y, Z)                # negative inside what must stay empty
holes = union(problem.holes, X, Y, Z)
allowed = (keepout > 0) & (envelope < 0)


def smin(a, b, k):
    """Smooth union: two shapes melt into each other over about k mm."""
    t = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b + (a - b) * t - k * t * (1 - t)


def thicken(solid, t):
    """Grow whatever is thinner than t to about t: find it (it does not survive an opening), then swell it."""
    r = t / 2
    core = edt(solid, sampling=S) > r
    thin = solid & ~(edt(~core, sampling=S) <= r)
    return solid | (edt(~thin, sampling=S) <= r)


def signed(solid):
    return edt(~solid, sampling=S) - edt(solid, sampling=S)


for _ in range(2):                                       # growing can leave the envelope or enter a keep-out: cut, grow again
    solid = thicken(solid, problem.min_wall) & allowed

sd = gaussian_filter(signed(solid), 0.5 / S)             # melt the voxel steps
for prim in problem.preserve:
    sd = smin(sd, sdf(prim, X, Y, Z), 1.0)
sd = np.maximum(np.maximum(sd, -keepout), np.maximum(-holes, envelope))

# The cuts leave cracks, bubbles, slivers and feather edges where they graze the shape.
part = sd < 0
G = 0.4                                                  # cracks under 0.8 mm are filled (a closing) ...
part = (edt(edt(~part, sampling=S) <= G, sampling=S) > G) & allowed & (holes > 0)
part = binary_fill_holes(part) & (holes > 0)             # ... bubbles sealed inside the material too ...
R = problem.min_wall / 2                                 # ... and walls thinner than the minimum go (an opening)
for _ in range(2):
    core = edt(part, sampling=S) > R
    part &= edt(~core, sampling=S) <= R + S / 2

# Members the optimizer left half-formed end as stubs, and material can sit where no load passes. Solve the
# part once per load case and drop what stores next to no strain energy in any of them (a stub stores none),
# then tidy up what the pruning left.
model = VoxelModel(problem, h)
coarse = map_coordinates(part.astype(float), np.stack([(c - o) / S - 0.5 + PAD for c, o in
                         ((model.X, x0), (model.Y, y0), (model.Z, z0))]), order=0) > 0.5       # [y, x, z], the optimizer's cells
worked = np.zeros(coarse.shape)
for solved in model.solve(coarse).values():
    worked = np.maximum(worked, solved["energy"] / np.percentile(solved["energy"][coarse], 99))
idle = coarse & (worked < IDLE)
fine = map_coordinates(idle.transpose(1, 0, 2).astype(float), index, order=0, mode="nearest") > 0.5
kept = part & ~(fine & (union(problem.preserve, X, Y, Z) > 0.5))
labels, count = label(kept)
if count > 1:                                            # what pruning cut loose goes too
    kept = labels == 1 + np.argmax(np.bincount(labels[labels > 0])[1:])
print(f"pruned {(part.sum() - kept.sum()) * S ** 3:.0f} mm3 of idle material ({count} bodies after pruning)")
part = binary_fill_holes(kept) & allowed & (holes > 0)
for _ in range(2):
    core = edt(part, sampling=S) > R
    part &= edt(~core, sampling=S) <= R + S / 2
# The smoothing still to come (here and in Blender) takes a few tenths off every wall: give the thinnest a
# margin. Thin is what an opening removes; of that, the walls are what is itself thick (an edge's rounding is not).
MARGIN, EDGE = 0.4, 0.35
core = edt(part, sampling=S) > R + MARGIN / 2
thin = part & ~(edt(~core, sampling=S) <= R + MARGIN / 2)
walls = edt(thin, sampling=S) > EDGE
if walls.any():
    grown = part | ((edt(~walls, sampling=S) <= MARGIN / 2 + EDGE) & allowed & (holes > 0))
    print(f"thin walls grown by {(grown.sum() - part.sum()) * S ** 3:.0f} mm3")
    part = grown

np.save(os.path.join(OUT, f"{problem.name}_clean.npy"), part)


# Take the voxel terraces off, then cut exactly once more (a cut into solid leaves no sliver).
sd = gaussian_filter(signed(part), 0.4 / S)
sd = np.maximum(np.maximum(sd, -keepout), np.maximum(-holes, envelope))
v, f, _, _ = marching_cubes(sd, level=0.0, spacing=(S, S, S))
v += np.array([x0, y0, z0]) + S / 2 - PAD * S            # padded, cell-centred samples -> the part's frame
mesh = trimesh.Trimesh(v, f)
trimesh.repair.fix_normals(mesh)
bodies = mesh.split(only_watertight=False)
mesh = max(bodies, key=lambda b: abs(b.volume))          # crumbs the cuts left
mesh.export(os.path.join(OUT, f"{problem.name}_clean.stl"))
print(f"{problem.name}_clean.stl: {len(mesh.faces)} triangles, watertight {mesh.is_watertight}, "
      f"{abs(mesh.volume):.0f} mm3, {len(bodies)} bodies before dropping crumbs, bounds {mesh.bounds.round(1).tolist()}")
