"""This robot's parts as generative design problems: for each, where it may be, what it holds, what loads it.

The generative-part skill's pipeline reads them (.agents/skills/generative-part): a problem is plain data, boxes
and cylinders along Z in the part's own frame (mm, N), as in src/parts.py. The baselines are exports of the
hand-drawn parts (cad model export <id> generative/baselines/<part>.stl --tolerance 0.02).
"""
import math
import os
import sys

from genpart import Problem, RemoteLoad, box, zcyl

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import params as p  # noqa: E402


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
        voxel=0.75, volfrac=0.26, rmin=3.0, baseline="baselines/thigh.stl", mirrored=True,
        balance="sum")            # as it was grown: all cases alike, each against its own start


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
        round=2.0, voxel=0.5, volfrac=0.28, rmin=5.0, baseline="baselines/shank.stl", mirrored=True,     # members of 2.5 mm: a small part
        balance="sum")


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
        round=3.0, round_top=False, voxel=1.0, rmin=2.0, min_wall=1.2, baseline="baselines/tray.stl", balance="sum",
        volfrac=0.62,       # the pockets' liners alone are 0.44 of the space; the hand-drawn tray fills 0.85
        extra={"blender": {"subdivide": 0}})                 # mostly flat walls: nothing to gain from a finer skin


PROBLEMS = {"thigh": thigh, "shank": shank, "tray": tray}
