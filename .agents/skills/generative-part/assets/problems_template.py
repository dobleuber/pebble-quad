"""A design problem to copy and edit: a small wall bracket. Run it as it is to see the pipeline work (about two
minutes):   sh <skill>/scripts/run.sh problems.py bracket

Frame: x along the arm from the wall screw, y across, z up from the print bed (mm, N).
The bracket is screwed to a wall through a boss at the origin and carries a load on a pad at its tip.
"""
from genpart import Problem, RemoteLoad, box, zcyl


def bracket():
    pad = box(34, 40, -5, 5, 8, 12)                    # the flat the load sits on, at the top of the tip
    return Problem(
        name="bracket",
        bounds=(-8, 40, -8, 8, 0, 12),                 # the box the part may fill; z0 is the print bed
        keepout=[zcyl(0, 0, 3.5, 4, 99),               # the screw's head, and the driver's path to it
                 box(12, 28, -99, 99, 0, 3)],          # a cable passes under the arm
        preserve=[zcyl(0, 0, 6.0, 0, 4), pad],         # crisp features: the boss under the screw head, the load's pad
        holes=[zcyl(0, 0, 1.7, -9, 99)],               # the screw (M3 clearance)
        support=[zcyl(0, 0, 6.0, -1, 2)],              # held where the boss sits on the wall
        cases={                                        # every load the part must take, not only the worst one
            "down": [RemoteLoad([pad], (37, 0, 12), (0, 0, -20))],
            "down + sideways": [RemoteLoad([pad], (37, 0, 12), (0, 8, -20))],
            "pulled along": [RemoteLoad([pad], (37, 0, 12), (15, 0, -5))],
        },
        round=3.0, voxel=1.0, volfrac=0.30, rmin=2.5, min_wall=1.2,
        baseline="",                                   # "baselines/bracket.stl": the part this replaces, same frame, to compare with
    )


PROBLEMS = {"bracket": bracket}
