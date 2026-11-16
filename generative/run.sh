#!/bin/sh
# The whole pipeline for one part or more:  sh generative/run.sh thigh shank tray
#
# PY is a Python with pytopo3d, pypardiso, scipy, scikit-image, trimesh and rtree (default: python).
# `cad` is text-to-cad's CLI: it runs the Blender step and the printability check.
set -eu
cd "$(dirname "$0")"
PY=${PY:-python}
for part in "$@"; do
  "$PY" optimize.py "$part" > "out/${part}_optimize.log" 2>&1
  tail -n 1 "out/${part}_optimize.log"
  "$PY" cleanup.py "$part" 2>/dev/null | tail -n 1
  cad run finish_blender.py "$part" 2>&1 | grep -E "wrote|rror" || true
  cad stl dfm "out/${part}.stl" --process printing --technology fdm --material pla 2>&1 | grep -E "^(OK|FAILED|error)" || true
  "$PY" check_mesh.py "out/${part}.stl" 2>/dev/null
  "$PY" evaluate.py "$part" 2>/dev/null | tail -n 5
done
