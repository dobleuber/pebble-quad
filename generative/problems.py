"""The generative design problems: for each part, where it may be, what it holds, what loads it.

A problem is plain data (boxes and cylinders along Z, in the part's own frame, mm and N), so the same
description drives the optimizer, the distance-field cleanup, Blender's booleans and the evaluation.
Frames are the parts' own, as in src/parts.py. Pure numpy.
"""
import math
import os
import sys
from dataclasses import dataclass, field

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import params as p  # noqa: E402


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
    """A force acting at a point off the part (a foot), carried by patches of the part as a force and a moment."""
    patches: list
    point: tuple
    force: tuple


@dataclass
class Problem:
    name: str
    bounds: tuple                 # x0, x1, y0, y1, z0, z1: the envelope's box; z0 is the print bed
    keepout: list                 # where nothing may be (servos, battery, the foot)
    preserve: list                # crisp solid features (bosses, seats, liners)
    holes: list                   # exact cuts made last (screws)
    support: list                 # where the part is held
    cases: dict                   # name -> [RemoteLoad]; the first is the case the part is grown for
    round: float = 5.0            # the envelope's corner radius
    round_top: bool = True        # also round the top edges (False: the top is a flat mating face)
    voxel: float = 0.75           # the optimizer's and the evaluation's voxel, mm
    volfrac: float = 0.26         # share of the free design space to fill
    rmin: float = 3.0             # filter radius in voxels: the smallest member
    min_wall: float = 1.2
    baseline: str = ""            # the hand-drawn part's model in src/parts.py, to compare with
    mirrored: bool = False        # legs need the part and its mirror image (in y)
    extra: dict = field(default_factory=dict)

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


# ------------------------------------------------------------------------------------------- thigh

def thigh():
    """Thigh frame: x along the thigh from the hip axis, y across, z outward from the hip horn's top face.
    Held on the hip horn, loaded where the knee servo's tabs sit by the foot's force (hand +1: front left)."""
    seat = p.THIGH_T + p.SERVO_TAB_Z                          # 14.5: the tabs' underside
    c0, c1 = p.L1 + p.SERVO_SHAFT_END - p.SERVO_L, p.L1 + p.SERVO_SHAFT_END    # the knee servo's case along x
    a = math.radians(-2 * p.STANCE)
    foot = (p.L1 + p.L2 * math.cos(a), p.L2 * math.sin(a), p.THIGH_T + p.SERVO_H + p.PEG / 2)
    seats = [box(c0 - p.SERVO_TAB_L + 0.04, c0 - p.FIT - 0.06, -4.2, 4.2, 7.5, seat),
             box(c1 + p.FIT, c1 + p.SERVO_TAB_L, -4.2, 4.2, 7.5, seat)]
    patches = [box(s[1], s[2], 0 if side > 0 else -4.2, 4.2 if side > 0 else 0, seat - 1.5, seat) for s in seats for side in (1, -1)]
    up = (-8.19, 5.74)                                        # 10 N up on the foot, in this frame
    return Problem(
        name="thigh", bounds=(-6.5, 41.5, -8.0, 8.0, 0.0, seat),
        keepout=[box(c0 - p.FIT + 0.04, c1 + p.FIT, -4.5, 4.5, p.THIGH_T, 99),            # the knee servo
                 box(c0 - p.SERVO_TAB_L - 0.06, c1 + p.SERVO_TAB_L + 0.1, -4.5, 4.5, seat, 99),    # its tabs
                 zcyl(0, 0, 2.6, p.THIGH_T, 99), zcyl(6.0, 0, 1.6, p.THIGH_T, 99)],                  # the horn's screw heads
        preserve=[zcyl(0, 0, 6.3, 0, p.THIGH_T)] + seats,
        holes=[zcyl(0, 0, 1.2, -9, 99), zcyl(6.0, 0, 0.6, -9, 6.0),
               zcyl(c0 - p.SERVO_TAB_L / 2 + 0.06, 0, 0.6, 8.5, 99), zcyl(c1 + p.SERVO_TAB_L / 2 + 0.15, 0, 0.6, 8.5, 99)],
        support=[zcyl(0, 0, 5.0, -1, 2.0)],
        cases={"up + out": [RemoteLoad(patches, foot, (*up, 5.0))],
               "up": [RemoteLoad(patches, foot, (*up, 0.0))],
               "up + in": [RemoteLoad(patches, foot, (*up, -5.0))],
               "up + aft": [RemoteLoad(patches, foot, (up[0] - 2.87, up[1] - 4.10, 0.0))]},
        voxel=0.75, volfrac=0.26, rmin=3.0, baseline="thigh", mirrored=True)


# ------------------------------------------------------------------------------------------- lower leg

def shank():
    """Lower-leg frame: x along the leg from the knee axis, y across, z outward from the knee horn's top face.
    Held on the knee horn, loaded at the foot's peg (hand +1: front left).
    Not adopted: at the hand-drawn leg's mass, which this volume fraction gives, the grown one is far less stiff."""
    top = 5.0                                                 # it may be thicker than the 3.5 mm plate it replaces
    peg = box(24.0, p.L2 + 1.5, -p.PEG / 2, p.PEG / 2, 0, p.PEG)
    at_foot = [box(26.4, 28.0 + 3.5, -p.PEG / 2, p.PEG / 2, 0, p.PEG)]
    ball = p.L2 - 3.1 - 0.3                                   # the foot's flat face: the leg stops short of it
    up = (-8.19, -5.74)
    foot = (p.L2, 0.0, p.PEG / 2)
    return Problem(
        name="shank", bounds=(-6.0, p.L2 + p.FOOT_R + 0.5, -6.5, 6.5, 0.0, top),
        keepout=[box(ball, 99, -99, -p.PEG / 2, -9, 99), box(ball, 99, p.PEG / 2, 99, -9, 99),     # the ball foot, around the peg
                 box(ball, 99, -99, 99, p.PEG, 99), box(p.L2 + 1.5, 99, -99, 99, -9, 99),
                 zcyl(0, 0, 2.6, p.SHANK_T, 99), zcyl(6.0, 0, 1.6, p.SHANK_T, 99), zcyl(11.0, 0, 1.6, p.SHANK_T, 99)],   # screw heads
        preserve=[zcyl(0, 0, 5.6, 0, p.SHANK_T), peg,
                  zcyl(6.0, 0, 2.8, 0, top), zcyl(11.0, 0, 2.8, 0, top)],     # a full wall around each arm screw and its head's well
        holes=[zcyl(0, 0, 1.2, -9, 99), zcyl(6.0, 0, 0.6, -9, 99), zcyl(11.0, 0, 0.6, -9, 99)],
        support=[zcyl(0, 0, 5.0, -1, 1.5)],
        cases={"up + out": [RemoteLoad(at_foot, foot, (*up, 5.0))],
               "up": [RemoteLoad(at_foot, foot, (*up, 0.0))],
               "up + in": [RemoteLoad(at_foot, foot, (*up, -5.0))],
               "up + aft": [RemoteLoad(at_foot, foot, (up[0] + 2.87, up[1] - 4.10, 0.0))]},
        round=2.0, voxel=0.5, volfrac=0.28, rmin=5.0, baseline="shank_a", mirrored=True)     # members of 2.5 mm: a small part


# ------------------------------------------------------------------------------------------- chassis tray

def tray():
    """The robot's own frame (x forward, y left, z up; hip axes at z = 0). Held at the four deck screws, where
    the deck, shell and electronics ride; loaded by the four hip servos, each carrying its foot's force."""
    top, bed = p.TRAY_Z1, p.TRAY_Z0
    floor = -p.SERVO_W / 2 - p.FIT
    liner = 1.2
    w = p.SERVO_W / 2
    sx0, sx1 = p.SERVO_SHAFT_END - p.SERVO_L, p.SERVO_SHAFT_END
    servo_boxes = [(sx0, sx1, 0, p.SERVO_CASE_H),                                     # case: x range, y (shaft) range
                   (sx0 - p.SERVO_TAB_L, sx1 + p.SERVO_TAB_L, p.SERVO_TAB_Z, p.SERVO_TAB_Z + p.SERVO_TAB_T),
                   (-6.0, sx1, p.SERVO_CASE_H, p.SERVO_CASE_H + p.SERVO_CAP_H)]
    keepout, preserve = [], []
    loads_all, loads_diag = [], []
    for name, (sx, sy) in p.LEGS.items():
        for a0, a1, b0, b1 in servo_boxes:
            xa, xb = sx * (p.HIP_X + a0 - sx * 0 - p.FIT), sx * (p.HIP_X + a1 + p.FIT)
            ya, yb = sy * (p.HIP_Y0 + b0 - p.FIT), sy * (p.HIP_Y0 + b1 + p.FIT)
            keepout.append(box(xa, xb, ya, yb, floor, 99))
            lo_x, hi_x = min(xa, xb) - liner, max(xa, xb) + liner
            lo_y, hi_y = min(ya, yb) - liner, max(ya, yb) + liner
            preserve.append(box(lo_x, hi_x, lo_y, hi_y, bed, top))
        cx0, cx1 = sx * (p.HIP_X + sx0), sx * (p.HIP_X + sx1)                           # under the case: four patches
        cy0, cy1 = sy * p.HIP_Y0, sy * (p.HIP_Y0 + p.SERVO_CASE_H)
        xm, ym = (cx0 + cx1) / 2, (cy0 + cy1) / 2
        patches = [box(xa, xb, ya, yb, bed, floor) for xa, xb in ((cx0, xm), (xm, cx1)) for ya, yb in ((cy0, ym), (ym, cy1))]
        foot = (sx * p.HIP_X, sy * (p.KNEE_FACE_Y + p.PEG / 2), -(p.L1 + p.L2) * math.cos(math.radians(p.STANCE)))
        loads_all.append(RemoteLoad(patches, foot, (0.0, sy * 5.0, 10.0)))
        if sx * sy > 0:
            loads_diag.append(RemoteLoad(patches, foot, (0.0, sy * 5.0, 10.0)))
    bx, by = p.BATTERY[0] / 2 + 0.5, p.BATTERY[1] / 2 + 0.5
    keepout += [box(-bx, bx, -by, by, floor, 99), box(-23.5, 23.5, -1.5, 1.5, 0.5, 99)]   # battery bay, cable channel
    keepout.append(box(-bx + 3, bx - 3, -by + 3, by - 3, -99, floor + 1))                   # the floor's windows, as in the
    keepout += [box(sx * 26.0, sx * 40.5, sy * 3.5, sy * 14.0, -99, floor + 1) for sx, sy in p.LEGS.values()]   # hand-drawn tray
    # (they reach 1 mm into the pockets above: two cuts that only touch leave a skin between them)
    preserve.append(box(-bx - liner, bx + liner, -by - liner, by + liner, bed, top))
    screws = [(sx * 17.3, sy * 14.4) for sx in (1, -1) for sy in (1, -1)]
    preserve += [zcyl(x, y, 2.3, top - 7.5, top) for x, y in screws]
    return Problem(
        name="tray", bounds=(-p.TRAY_X, p.TRAY_X, -p.TRAY_Y, p.TRAY_Y, bed, top),
        keepout=keepout, preserve=preserve,
        holes=[zcyl(x, y, 0.65, top - 6, 99) for x, y in screws],
        support=[zcyl(x, y, 2.3, top - 2.5, top + 1) for x, y in screws],
        cases={"four feet, up + out": loads_all, "one diagonal, up + out": loads_diag},
        round=3.0, round_top=False, voxel=1.0, rmin=2.0, min_wall=1.2, baseline="tray",
        volfrac=0.62,       # the pockets' liners alone are 0.44 of the space; the hand-drawn tray fills 0.85
        extra={"blender": {"subdivide": 0}})                 # mostly flat walls: nothing to gain from a finer skin


PROBLEMS = {"thigh": thigh, "shank": shank, "tray": tray}
