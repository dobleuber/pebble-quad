# Pebble Quad

- Everything in this repository is written in English: code, comments, documentation, commit messages
  and pull requests. Chat with the owner may be in Spanish; the repository is not.
- The model is the source of truth. `sim/` is generated from it (`cad run src/quad_mujoco.py`) and is
  never edited by hand, except `sim/scene.xml`.
- After a change to the geometry or the moves, rerun the checks listed under "Checks made" in the
  README and update its numbers.
