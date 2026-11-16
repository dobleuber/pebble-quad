# Pebble Quad

- Everything in this repository is written in English: code, comments, documentation, commit messages
  and pull requests. Chat with the owner may be in Spanish; the repository is not.
- The model is the source of truth. `sim/` is generated from it (`cad run src/quad_mujoco.py`) and is
  never edited by hand, except `sim/scene.xml`.
- After a change to the geometry or the moves, rerun the checks listed under "Checks made" in the
  README and update its numbers.
- `generative/` is a second build of the robot, with parts grown by the `generative-part` skill
  (`.agents/skills/generative-part`, linked from `.claude/skills/`). Its `parts/` and `sim/` are generated:
  the parts by the skill's `run.sh` from `generative/problems.py`, the rest by `sh generative/checks.sh`.
  If a hand-drawn part a problem describes changes, export its baseline again and rerun both; the numbers
  live in `generative/README.md` and in the README's "A generative build" table.
- The skill's scripts must keep reproducing `generative/parts/` (the problems there state `balance="sum"`):
  after changing them, rerun the thigh and compare its volume and stiffness ratios with the README's.
