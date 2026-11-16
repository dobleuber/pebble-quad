---
name: generative-part
description: Grows a lighter or stiffer version of a structural part by generative design (topology optimization), the way Fusion 360's generative design does, with free tools - PyTopo3D for several load cases at once, distance-field cleanup, Blender finishing - and measures it against the part it replaces. Use it whenever someone wants to lighten, stiffen, optimize or "make organic" a bracket, arm, leg, link, mount, chassis or frame of a robot or any 3D-printed mechanism, asks for generative design, topology optimization, organic or bionic structures, or wants to improve the parts of an existing design (build123d / text-to-cad, OpenSCAD, STEP or STL), also when they say it in other words or another language ("diseño generativo", "optimización topológica", "aligerar esta pieza", "piezas orgánicas"). Not for drawing a part from scratch (the cad skill), nor for a stress analysis with safety factors (the fea skill).
---

# Generative part

Grow a structural part from a description of its job - where it may be, what it must leave alone, what must stay
exact, where it is held, what loads it - and say with numbers whether the result beats the part it replaces.

What comes out: a mesh to print (`parts/<part>.stl`), a comparison with the original on the same loads, and a
light copy that a CAD assembly can check. What does not come out: an editable CAD solid, or a safety factor.

The scripts are in `scripts/` beside this file; below, `$SKILL` is this folder. Each step takes the project's
problems file and a part's name, and writes beside that file: `out/` (working files) and `parts/` (results).

## 1. Set up, once per machine

```bash
PY=$(sh $SKILL/scripts/setup_env.sh)
```

That makes a Python environment (PyTopo3D pinned at 0.3.0, because the optimizer step reaches into it) and
prints its interpreter; `run.sh` finds it there by itself afterwards. The finishing step needs Blender's Python:
text-to-cad's `cad run` brings it, and so does a Blender 4.5 or later on PATH (`BLENDER=blender`).

Run one heavy job at a time. The optimizer and Blender each take gigabytes; two together get killed.

## 2. Choose the parts worth growing

Not every part gains. Before any work, sort the design's printed parts into three groups and tell the user:

- **Worth it**: carries load between a few interfaces, with free space around it - arms, legs, brackets,
  motor cradles. This is where the pipeline has given a thigh 13 % lighter and 1.5 to 5 times stiffer.
- **A little**: mostly walls that must exist (pockets, trays, housings). Expect the same stiffness for
  10 to 15 % less mass, no more.
- **Not worth it**: small parts that are almost all mandatory features (a hub, two screw bosses and a peg),
  covers and shells, anything that must stay easy to edit or print without supports. The pipeline has made
  such a part 3 to 7 times *less* stiff than a plain hand-drawn one of the same mass.

`references/judgement.md` has the reasoning and the numbers behind this.

## 3. Bring the part and its neighbours into one frame

The optimizer needs the existing part as a mesh to compare with, and its surroundings to know what to avoid.
Export each as STL in millimetres, **in the part's own frame**: Z up from the face it prints on, the main
interface (a shaft, a mounting screw) at the origin when there is one. Holes and screws should run along Z,
because the problem's primitives are boxes and cylinders along Z only.

- text-to-cad model: `cad model export <id> baselines/<part>.stl --tolerance 0.02` (a part's own model is
  already in its frame); a STEP: `cad step export part.step baselines/<part>.stl`.
- OpenSCAD: `openscad -o baselines/<part>.stl -D 'part="<name>"' design.scad`, or a small `.scad` that calls
  the module with its transform undone.
- Only an STL of the whole assembly: split it by body first, and say what could not be separated.

Then measure what you have:

```bash
$PY $SKILL/scripts/measure.py baselines/<part>.stl neighbour1.stl neighbour2.stl
```

It prints the part's box, volume and mass, and each neighbour's box as a keep-out line to start from.

## 4. Describe the problem

Copy `assets/problems_template.py` to the project (for example `generative/problems.py`) and write one function
per part. Read `references/problem.md` first: it explains each field, how to get loads when nobody measured
them, and the mistakes that cost a run.

The loads decide everything, and they are the user's to give. If they are not known, derive them from something
real (a motor's stall torque over its lever arm, the weight carried times 2 or 3 for dynamics, a simulation's
peak) and state the assumption in the problem's docstring and in the report. Give at least three cases that
push in different directions: a part grown for one load is strong in that direction and weak in the others.

## 5. Look before you run

```bash
$PY $SKILL/scripts/preview.py generative/problems.py <part>
```

It draws `out/<part>_problem.png`: design space, keep-outs, crisp features, supports and loads in three views,
with the original part's edges on top. Open the picture. A keep-out off by a sign, a support inside a
keep-out or a load patch in thin air is obvious here and costs minutes to find later. It also prints any
`PROBLEM:` it can detect; fix those first.

## 6. Run

```bash
sh $SKILL/scripts/run.sh generative/problems.py <part>
```

Steps, in order: `optimize` (minutes: the log is `out/<part>_optimize.log`), `cleanup`, `finish` (Blender),
`check` (is the mesh one closed body; a printability check too when text-to-cad is there) and `evaluate`.
`STEPS="cleanup finish check evaluate"` redoes the cheap ones on a density field that is already there.
For a run longer than a few minutes, start it in the background and read the log.

A grid of 30 000 cells takes about 4 s an iteration and 80 iterations; 80 000 cells is where it stops being
practical here. Coarsen the voxel before anything else.

## 7. Read the result and decide

`evaluate` prints, per load case, stiffness and indicative stress against the original, and the mass.
Look at the mesh too (`cad stl snapshot out/<part>.stl out/<part>.png`, or any viewer): a number does not show
a stub, a blob or a neck.

- Lighter and at least as stiff in **every** case: adopt it.
- Stiffer in some cases and weaker in others: the cases or the space are wrong, not the tool. See
  `references/judgement.md` for what to change (it lists each symptom and its usual cause).
- No better than the original at the same mass: say so and keep the original. That is a result, and an honest
  one is worth more than a pretty mesh.

Change one thing at a time between runs (volume fraction, member size, a keep-out), and keep the numbers of
each attempt for the report.

## 8. Hand it over

```bash
STEPS=lite sh $SKILL/scripts/run.sh generative/problems.py <part>
```

writes `parts/<part>.stl` to print (and `<part>_b.stl`, its mirror image, for `mirrored=True`) and
`parts/<part>_lite.stl`, a few thousand triangles. `references/assembly.md` shows how to put the light copy in a
text-to-cad assembly as a solid, so the design's own checks (interference, joint travel, simulation) run with
the new part, and how to show the full mesh in MuJoCo and in renders.

Then report, in the user's language, with this table per part (and the picture of both parts):

| | Original | Generative |
|---|---|---|
| Mass | | |
| Stiffness, per load case | 1 | ×… , ×… |
| Indicative stress, per load case | 1 | ×… , ×… |
| Printing | supports? warnings? | thinnest wall, supports needed |
| Verdict | | adopt / keep the original, and why |

Under it, always say: which loads were assumed and where they came from; that stiffness and stress are ratios on
a voxel model and not safety factors (a part that matters gets the fea skill, or a test print); what was not
checked; and which parts were tried and not adopted.

## Files

```
scripts/setup_env.sh      the Python environment
scripts/measure.py        an existing part's box, mass and neighbours
scripts/preview.py        step 0: the problem as a picture
scripts/run.sh            the pipeline: optimize, cleanup, finish, check, evaluate, lite
scripts/optimize.py       topology optimization for all load cases at once (PyTopo3D)
scripts/cleanup.py        makes the density field buildable; prunes material no load passes through
scripts/finish_blender.py smooth skin, then exact crisp features and cuts
scripts/evaluate.py       original against generative on the same voxels
scripts/lite.py           meshes to print and light copies for an assembly
scripts/genpart.py        what a problem is (Problem, RemoteLoad, box, zcyl); fe.py, blender_ops.py: shared
assets/problems_template.py   a bracket to copy: runs as it is in about two minutes
references/problem.md     every field of a problem, loads, and the mistakes that cost a run
references/judgement.md   which parts gain, how to read results, symptom -> cause
references/assembly.md    the grown part in a CAD assembly, in MuJoCo and in renders
```
