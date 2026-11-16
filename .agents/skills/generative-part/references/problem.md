# Describing a part as a problem

A problems file is ordinary Python that the pipeline loads. It imports the vocabulary from `genpart` (the
pipeline puts it on the path), may import the project's own modules (its folder is on the path too: take
dimensions from the design's parameters rather than retyping them), and ends with
`PROBLEMS = {"name": function, ...}`. Each function returns a `Problem`.

## Contents

- [The frame](#the-frame)
- [Primitives](#primitives)
- [The fields](#the-fields)
- [Loads](#loads)
- [Sizing the run](#sizing-the-run)
- [Mistakes that cost a run](#mistakes-that-cost-a-run)

## The frame

Millimetres and newtons, in the part's own frame. `bounds[4]` (z0) is the print bed: the part is trimmed flat
there. Put the origin on the main interface. Write the frame in the function's docstring ("x along the arm from
the hip axis, y across, z outward from the horn's face"): every number below depends on it, and the next
reader has nothing else to go by.

The original part's STL (`baseline`), the neighbours you measure and the problem must all be in this frame.
`preview.py` draws the baseline over the problem: if they do not line up, the frame is wrong.

## Primitives

Two shapes, both closed solids:

- `box(x0, x1, y0, y1, z0, z1)`
- `zcyl(cx, cy, r, z0, z1)`: a cylinder along Z

Use `99` or `-99` for "to infinity" (through the top, through the bed). A round motor on its side, a sloped
face or a sphere is approximated by a few boxes; err on the side of a larger keep-out. If the part's important
holes do not run along Z, turn the frame until they do.

## The fields

| Field | What it says | Notes |
|---|---|---|
| `name` | the part, and its files' names | |
| `bounds` | the box the part may fill | Start from the original's box (`measure.py`) and widen it wherever there is free room: room is what the optimizer turns into stiffness. Keep every number a multiple of 0.25 mm (the cleanup's grid), or a face lands up to 0.25 mm short |
| `keepout` | volumes that must stay empty | Neighbours with their clearance (0.3 mm around a part that sits in a printed pocket), **screw heads and the driver's path to them**, cables, the swept volume of anything that moves past |
| `preserve` | crisp solid features | Bosses under screw heads, seats, flat mating faces, walls around pockets ("liners"), pegs. They come out exact, with sharp edges. Give every screw hole a boss with at least 1.4 mm of wall around it |
| `holes` | exact cuts made last | Screws and pilots. Cut through everything, including `preserve` |
| `support` | where the part is held | A volume overlapping material: usually the lower part of the boss it is screwed through, or its mating face |
| `cases` | name → list of `RemoteLoad` | See below. The first three or four that push in different directions |
| `round`, `round_top` | the envelope's corner radius; whether the top edges are rounded too | `round_top=False` when the top is a flat mating face |
| `voxel` | the optimizer's cell, mm | See sizing |
| `volfrac` | share of the design space to fill | Counts the preserved features. See sizing |
| `rmin` | smallest member, in voxels | 3 is a good start; a small part wants fewer, thicker members (5) |
| `min_wall` | thinnest wall to keep, mm | 1.2 for a 0.4 mm nozzle |
| `baseline` | the original's STL, path relative to the problems file | Without it there is nothing to compare with: only leave it empty for a part that does not exist yet |
| `mirrored` | also write the mirror image in y | Left and right hands of a leg or an arm |
| `youngs`, `poisson`, `density` | material | PLA by default (3500 MPa, 0.3, 1.24e-3 g/mm³). They scale the absolute numbers, not the comparison |
| `extra` | `{"blender": {"subdivide": 0}}` for a part that is mostly flat walls; `{"lite": 3000}` triangles of the light copy | |

## Loads

A `RemoteLoad(patches, point, force)` is a force (N, in the part's frame) acting at a point, carried by patches
of the part:

- One patch, the force acting at it: `RemoteLoad([pad], centre_of_pad, (0, 0, -20))`.
- A force acting somewhere off the part (at a foot, a wheel, a gripper's tip) that reaches the part through an
  interface: list the patches of that interface (the four corners of a motor's seat) and give the real point
  of action. The patches share the force **and the moment** it has about them. This is how a leg's link gets
  the bending its foot causes, without modelling the rest of the leg.

Every patch must overlap material that will exist: make patches out of the `preserve` features (a seat, a pad).

Where to get the numbers, best first:

1. A simulation or a measurement: the peak force at the foot or the tip over the design's moves and a drop.
2. The actuator: stall torque divided by the lever arm is the most the mechanism can push with.
3. Weight: the mass carried times g, times 2 or 3 for a walking or moving machine.

Then the directions. The governing case alone is not enough; add what the part meets in use:

- the main load;
- the main load with a sideways component each way (a quarter to a half of it);
- the main load with friction along the direction of travel (the friction coefficient times the normal force);
- for a chassis: all supports loaded, and a diagonal pair only.

The objective weighs the cases equally (each as a share of its own starting compliance), so a case the part
resists easily counts as much as the hard one. Do not add cases that cannot happen.

## Sizing the run

- **Voxel**: the largest that still shows the features that matter, with at least 3 cells across the thinnest
  preserved wall you care about and the grid under about 40 000 cells (`preview.py` prints the count). Typical:
  0.75 mm for a 50 mm part, 1.0 mm for a 100 mm one, 0.5 mm only for something under 40 mm.
- **Volume fraction**: target volume ÷ design space. `preview.py` prints the design space and what the fraction
  comes to in grams. The cleanup and the finishing add 10 to 20 % to what the optimizer leaves, so to match the
  original's mass aim about 15 % under it. The preserved features are inside the fraction: `optimize.py` refuses
  to start when they alone exceed it.
- **First run**: aim for the original's mass. A lighter part comes second, once this one is known to be stiffer.

## Mistakes that cost a run

Each of these happened, and the remedy is in the description, not in the tool:

- **No keep-out for a screw's head and driver.** The optimizer builds over the screw. Add a `zcyl` from the
  seat upward, as wide as the head plus clearance.
- **A hole with no wall around it.** The cut leaves a web thinner than a nozzle. Preserve a boss around every hole.
- **Two keep-outs that only touch.** A pocket from z = 5 up and a window from z = 5 down leave a skin of no
  thickness between them. Make one reach 1 mm into the other.
- **Crisp features that eat the budget.** A tray whose pocket walls were 44 % of the space was given a volume
  fraction of 22 %: nothing grew. Check the share `preview.py` prints.
- **A support or a load patch inside a keep-out.** It holds no material; `preview.py` says so.
- **One load case.** Stiff in that direction, 30 % weaker than the original in two others.
- **Bounds off the 0.25 mm grid.** A mating face ends up to 0.25 mm short of where it should be.
- **A part that is nothing but mandatory features.** See `judgement.md`: do not grow it.
