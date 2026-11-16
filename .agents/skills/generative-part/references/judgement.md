# Which parts gain, and how to read a result

## What the numbers mean

`evaluate.py` samples the original and the generative part on the same voxels and solves both with the same
supports and loads.

- **Mass** comes from the meshes themselves and is exact for a solid print.
- **Stiffness ×** is the original's compliance over the new part's, per load case. Above 1 is stiffer. It is
  reliable as a ratio: both parts see the same crude model.
- **Indicative stress ×** is the ratio of the 99th-percentile energy-equivalent stress, away from supports and
  load patches. Voxel stairs exaggerate stress, so read only the ratio, and only as "more" or "less".
- Neither is a safety factor. A part someone's safety or money rides on gets a real stress analysis (the fea
  skill, on the original; a mesh cannot go through it) or a test print loaded until it breaks.

A layered print is weaker across its layers than the model's uniform material. Members that rise steeply from
the bed carry their load across layers: say so when the result has them.

## Which parts gain

What was measured on a 100 g quadruped with 4 g servos, in PLA, each part against its hand-drawn original:

| Part | Kind | Mass | Stiffness over the load cases | Verdict |
|---|---|---|---|---|
| Thigh: a plate carrying a servo, 48 mm | load path with free room around it | −13 % | ×4.3, ×5.1, ×1.5, ×2.0 | adopted |
| Chassis tray: four pockets and a battery bay, 98 mm | mostly mandatory walls | −13 % | ×0.99, ×1.00 | adopted |
| Lower leg: hub, two screw bosses, a peg, 37 mm | almost all mandatory features | same | ×0.26, ×0.24, ×0.14, ×0.14 | rejected |

And on a 72 mm forearm link of a small arm (a 4 mm plate with two posts carrying a servo), in the original's own
box, with the same three cases and the same budget:

| Objective | Mass | Stiffness: down, sideways, along |
|---|---|---|
| `balance="sum"` | −9 % | ×8.3, **×0.48**, ×21 |
| `balance="worst"` (the default with a baseline) | −4 % | ×2.2, ×1.4, ×3.7 |

The pattern behind it:

- The gain comes from **room**. The thigh's optimizer found that a servo is better held in a cradle with rails
  than on a plate, because it had 3 mm more width and the full height to build in. A part already as deep as
  its space allows has nothing to find.
- **Mandatory features are not optimized.** If bosses, seats and pocket walls are more than about 40 % of the
  target volume, what is left is too little to rearrange. A tapered plate drawn by hand is already close to
  the best beam.
- **A flat plate is already the best shape for a load in its own plane.** Left to add up all cases, the
  optimizer trades that plate for depth, wins hugely in bending and loses sideways. Measuring each case against
  the original and following the worst one (`"worst"`) keeps what the original was good at.
- **A robot does not feel 4 %.** Taking 4 g off a 104 g walker changed nothing in its gait or servo load. Mass
  matters at the end of a moving limb, or when it adds up over many parts; stiffness matters where a mechanism
  loses accuracy or where the original was marginal in its stress analysis.

Costs to tell the user before they ask:

- Grown parts need **supports** to print (the thigh, half its own volume), where the original needed none.
- They are **meshes**. Changing a dimension means running the pipeline again: two to ten minutes a part.
- The original stays the reference: keep it in the design and offer the grown part as a second build.

## When a result is wrong

| What you see | Usual cause | What to change |
|---|---|---|
| Much stiffer in one case, weaker than the original in a case that is missing from the set | the cases do not span what the part meets | add the missing directions; never fewer than three |
| Weaker than the original in a case that is in the set | the original is already the best shape for that load (a plate loaded in its plane), and the space or the budget cannot match it and the other cases too | check `balance` is `"worst"`; then more room (`bounds`), then more material (`volfrac`), then that case's `weights`; if the original's plate is what works, preserve a thinner one as a floor |
| A thin neck between two blobs | the crisp features take most of the volume fraction | raise `volfrac`, shrink `preserve`, or drop the part |
| A member that ends in the air | a strut the optimizer left half-formed | `cleanup.py` prunes these; if one survives, raise `rmin` |
| Heavier or lighter than aimed | cleanup and finishing add 5 to 20 % to the optimizer's volume | correct `volfrac` by the ratio, once |
| The printability check finds a wall under 0.8 mm | a skin beside a pocket or a hole | preserve a wall there (a liner or a boss); do not raise `min_wall` for the whole part, it inflates everything |
| `optimize` refuses to start | preserved share above the volume fraction, or nothing held | read its message and `preview.py`'s |
| `finish` reports open edges on every skin | a keep-out that only touches another | overlap them by 1 mm |
| The run is killed | memory: too many cells, or two heavy jobs at once | coarser `voxel`; one job at a time |
| Stiffness ratios near 1 and the mass down 10 to 15 % | a part of mandatory walls | that is its ceiling: adopt it or not, but stop iterating |

Change one thing between runs, and keep each attempt's numbers. Three attempts without improvement over the
original at equal mass is the answer: the original is good.
