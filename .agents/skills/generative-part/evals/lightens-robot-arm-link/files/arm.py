"""A hand-drawn forearm link of a small robot arm, and the servo it carries (the fixture for the skill's test)."""
import build123d as bd
from cad import model


@model
def forearm():
    """Frame: origin on the elbow screw's axis at the underside; x along the link; z up from the print bed."""
    body = bd.Pos(27.5, 0, 2) * bd.Box(69, 14, 4)
    body += bd.Pos(0, 0, 2) * bd.Cylinder(7, 4)
    for x in (37.5, 62.5):                                   # posts under the wrist servo's tabs
        body += bd.Pos(x, 0, 9) * bd.Box(3, 9, 10)
    body -= bd.Pos(0, 0, 2) * bd.Cylinder(1.7, 10)           # M3 at the elbow
    for x in (37.5, 62.5):
        body -= bd.Pos(x, 0, 11) * bd.Cylinder(0.6, 8)       # tab screw pilots
    return body


@model
def wrist_servo():
    """The wrist servo's envelope, where it sits on the forearm (same frame)."""
    return bd.Pos(50, 0, 13.5) * bd.Box(22, 9, 19) + bd.Pos(50, 0, 14.6) * bd.Box(31, 9, 1.2)


if __name__ == "__main__":
    forearm()
    wrist_servo()
