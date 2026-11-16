#!/bin/sh
# A Python environment for the pipeline:  sh setup_env.sh [folder]   (default: ~/.cache/generative-part/venv)
# Prints the interpreter to hand to run.sh as PY. Safe to run again.
set -eu
target=${1:-"$HOME/.cache/generative-part/venv"}
# pytopo3d is pinned: optimize.py swaps two of its internals (the compliance evaluator and the density update).
packages="pytopo3d==0.3.0 pypardiso scikit-image trimesh rtree matplotlib"
if [ ! -x "$target/bin/python" ]; then
  if command -v uv >/dev/null 2>&1; then uv venv --quiet "$target"; else python3 -m venv "$target"; fi
fi
if ! "$target/bin/python" -c "import pytopo3d, pypardiso, skimage, trimesh, rtree" 2>/dev/null; then
  if command -v uv >/dev/null 2>&1; then uv pip install --quiet --python "$target/bin/python" $packages
  else "$target/bin/python" -m pip install --quiet $packages; fi
fi
"$target/bin/python" -c "import pytopo3d, pypardiso, skimage, trimesh, rtree"
echo "$target/bin/python"
