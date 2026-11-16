"""What a generative design problem is, and how the pipeline's steps find one.

A problem is plain data in the part's own frame (mm, N): boxes and cylinders along Z say where the part may be,
what must stay empty, what must stay crisp, where it is held and what loads it. The same description drives the
optimizer, the distance-field cleanup, Blender's booleans and the evaluation. A project keeps its problems in a
Python file that defines PROBLEMS = {"name": function returning a Problem, ...}; every step takes that file and a
name:  python optimize.py path/to/problems.py bracket
"""
import importlib.util
import math
import os
import sys
from dataclasses import dataclass, field

import numpy as np


def box(x0, x1, y0, y1, z0, z1):
    return ("box", min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1))


def zcyl(cx, cy, r, z0, z1):
    return ("zcyl", cx, cy, r, z0, z1)


def sdf(prim, X, Y, Z):
    """Signed distance to a primitive (negative inside)."""
    kind, *v = prim
    if kind == "box":
        x0, x1, y0, y1, z0, z1 = v
        q = np.stack([np.maximum(x0 - X, X - x1), np.maximum(y0 - Y, Y - y1), np.maximum(z0 - Z, Z - z1)])
    else:
        cx, cy, r, z0, z1 = v
        q = np.stack([np.hypot(X - cx, Y - cy) - r, np.maximum(z0 - Z, Z - z1)])
    return np.linalg.norm(np.maximum(q, 0), axis=0) + np.minimum(q.max(axis=0), 0)


def union(prims, X, Y, Z):
    """Signed distance to the union of primitives (far outside when there are none)."""
    out = np.full(X.shape, 1e6)
    for prim in prims:
        out = np.minimum(out, sdf(prim, X, Y, Z))
    return out


@dataclass
class RemoteLoad:
    """A force acting at a point, carried by patches of the part. With one patch the force goes on it as it is;
    with several, they share the force and the moment it has about them (a force at a foot, carried by a seat)."""
    patches: list
    point: tuple
    force: tuple


@dataclass
class Problem:
    name: str
    bounds: tuple                 # x0, x1, y0, y1, z0, z1: the envelope's box; z0 is the print bed
    keepout: list                 # where nothing may be (motors, screw heads, neighbours)
    preserve: list                # crisp solid features (bosses, seats, pocket walls)
    holes: list                   # exact cuts made last (screws)
    support: list                 # where the part is held
    cases: dict                   # name -> [RemoteLoad]: every case the part is grown for and judged in
    round: float = 5.0            # the envelope's corner radius
    round_top: bool = True        # also round the top edges (False: the top is a flat mating face)
    voxel: float = 0.75           # the optimizer's and the evaluation's voxel, mm
    volfrac: float = 0.26         # share of the design space to fill (the preserved features count in it)
    rmin: float = 3.0             # filter radius in voxels: the smallest member
    min_wall: float = 1.2
    iterations: int = 80
    baseline: str = ""            # an STL of the part this one replaces, in the same frame, to compare with
    mirrored: bool = False        # also write the mirror image in y (left and right hands)
    youngs: float = 3500.0        # MPa (PLA)
    poisson: float = 0.3
    density: float = 1.24e-3      # g/mm3 (PLA)
    extra: dict = field(default_factory=dict)      # "blender": {voxel, smooth, swell, subdivide}; "lite": triangles
    folder: str = ""              # the problems file's folder, set when it is loaded

    def path(self, *parts):
        """A path beside the problems file: out/ holds the steps' files, parts/ the finished meshes."""
        target = os.path.join(self.folder, *parts)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        return target

    def coords(self, h, pad=0, layout="xyz"):
        """Cell centres of a grid of h mm cells over the box, `pad` empty cells around it."""
        x0, x1, y0, y1, z0, z1 = self.bounds
        # enough cells to cover the box (the last one may reach past it: the envelope cuts there)
        ax = [lo + (np.arange(math.ceil((hi - lo) / h - 1e-9) + 2 * pad) - pad + 0.5) * h for lo, hi in ((x0, x1), (y0, y1), (z0, z1))]
        if layout == "yxz":                                   # the optimizer's array layout
            Y, X, Z = np.meshgrid(ax[1], ax[0], ax[2], indexing="ij")
        else:
            X, Y, Z = np.meshgrid(*ax, indexing="ij")
        return X, Y, Z

    def envelope(self, X, Y, Z):
        """Signed distance to the space the part may fill: the box with round corners, flat on the bed."""
        x0, x1, y0, y1, z0, z1 = self.bounds
        r = self.round
        if self.round_top:                                    # mirrored below the bed, so the walls meet it square
            half = np.array([(x1 - x0) / 2, (y1 - y0) / 2, z1 - z0]).reshape(3, 1, 1, 1)
            q = np.stack([np.abs(X - (x0 + x1) / 2), np.abs(Y - (y0 + y1) / 2), np.abs(Z - z0)]) - half + r
            sd = np.linalg.norm(np.maximum(q, 0), axis=0) + np.minimum(q.max(axis=0), 0) - r
            return np.maximum(sd, z0 - Z)
        half = np.array([(x1 - x0) / 2, (y1 - y0) / 2]).reshape(2, 1, 1, 1)
        q = np.stack([np.abs(X - (x0 + x1) / 2), np.abs(Y - (y0 + y1) / 2)]) - half + r
        plan = np.linalg.norm(np.maximum(q, 0), axis=0) + np.minimum(q.max(axis=0), 0) - r
        return np.maximum(plan, np.maximum(z0 - Z, Z - z1))

    def load_field(self, case, X, Y, Z, available):
        """The case's loads as a force per cell (array X.shape + (3,)), on the cells of each patch that hold material."""
        out = np.zeros(X.shape + (3,))
        for load in self.cases[case]:
            masks = [(sdf(prim, X, Y, Z) < 0) & available for prim in load.patches]
            assert all(m.sum() for m in masks), f"{self.name}: a load patch of case {case!r} holds no material"
            centres = [np.array([X[m].mean(), Y[m].mean(), Z[m].mean()]) for m in masks]
            c0 = np.mean(centres, axis=0)
            force = np.asarray(load.force, float)
            if len(masks) == 1:                               # one patch: it takes the force (the point is at it)
                forces = [force]
            else:                                             # several: the least forces with that resultant and moment
                a = np.zeros((6, 3 * len(masks)))
                for i, c in enumerate(centres):
                    r = c - c0
                    a[0:3, 3 * i:3 * i + 3] = np.eye(3)
                    a[3:6, 3 * i:3 * i + 3] = [[0, -r[2], r[1]], [r[2], 0, -r[0]], [-r[1], r[0], 0]]
                moment = np.cross(np.asarray(load.point, float) - c0, force)
                forces = (np.linalg.pinv(a) @ np.concatenate([force, moment])).reshape(-1, 3)
            for m, f in zip(masks, forces):
                out[m] += f / m.sum()
        return out


def arguments():
    """The script's own arguments, also when Blender runs it (blender -b -P script.py -- args)."""
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]


def load(usage):
    """The problem the command line names: <problems.py> <part> [more]. Returns (problem, the other arguments)."""
    args = arguments()
    if len(args) < 2:
        sys.exit(f"usage: {usage}")
    file, name, rest = os.path.abspath(args[0]), args[1], args[2:]
    here = os.path.dirname(os.path.abspath(__file__))
    for folder in (here, os.path.dirname(file)):               # the file imports genpart, and its project's own modules
        if folder not in sys.path:
            sys.path.insert(0, folder)
    spec = importlib.util.spec_from_file_location("problems", file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    problems = getattr(module, "PROBLEMS", None)
    if not problems or name not in problems:
        sys.exit(f"{file} defines no problem {name!r}: it has {', '.join(problems or []) or 'no PROBLEMS'}")
    problem = problems[name]() if callable(problems[name]) else problems[name]
    problem.folder = os.path.dirname(file)
    return problem, rest
