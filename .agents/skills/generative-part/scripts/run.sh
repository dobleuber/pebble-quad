#!/bin/sh
# The pipeline for one part or more:  sh run.sh <problems.py> <part> [<part> ...]
#
# PY       a Python with the packages setup_env.sh installs (default: the environment it makes, else python3)
# BLENDER  how to run a script in Blender's Python: "cad run" (text-to-cad, the default when `cad` is there),
#          or "blender" for a Blender 4.5 or later on PATH
# STEPS    which steps to run, default "optimize cleanup finish check evaluate" (to redo the cheap ones on a density
#          field that is already there: STEPS="cleanup finish check evaluate")
set -eu
here=$(cd "$(dirname "$0")" && pwd)
problems=$1; shift
folder=$(cd "$(dirname "$problems")" && pwd)
PY=${PY:-"$HOME/.cache/generative-part/venv/bin/python"}
[ -x "$PY" ] || PY=python3
STEPS=${STEPS:-"optimize cleanup finish check evaluate"}
if [ -z "${BLENDER:-}" ]; then
  if command -v cad >/dev/null 2>&1; then BLENDER="cad run"; else BLENDER="blender"; fi
fi
in_blender() {   # script, then its arguments
  script=$1; shift
  if [ "$BLENDER" = "cad run" ]; then cad run "$here/$script" "$@"; else "$BLENDER" -b -P "$here/$script" -- "$@"; fi
}
mkdir -p "$folder/out"
for part in "$@"; do
  for step in $STEPS; do
    case $step in
      optimize) "$PY" "$here/optimize.py" "$problems" "$part" > "$folder/out/${part}_optimize.log" 2>&1 \
                  || { tail -n 3 "$folder/out/${part}_optimize.log"; exit 1; }
                grep -E "^$part: " "$folder/out/${part}_optimize.log" ;;
      cleanup)  "$PY" "$here/cleanup.py" "$problems" "$part" 2>/dev/null | tail -n 3 ;;
      finish)   in_blender finish_blender.py "$problems" "$part" 2>&1 | grep -E "^wrote|^skin of|no closed surface|Error|error:" || true
                [ -f "$folder/out/$part.stl" ] || { echo "$part: the finishing step wrote no mesh"; exit 1; } ;;
      check)    "$PY" "$here/check_mesh.py" "$folder/out/$part.stl" 2>/dev/null
                if command -v cad >/dev/null 2>&1; then   # a printability check, when text-to-cad is there
                  cad stl dfm "$folder/out/$part.stl" --process printing --technology fdm --material pla 2>&1 | grep -E "^(OK|FAILED|error)" || true
                fi ;;
      evaluate) "$PY" "$here/evaluate.py" "$problems" "$part" 2>/dev/null | tail -n 12 ;;
      lite)     in_blender lite.py "$problems" "$part" 2>&1 | grep -E "^wrote|Error|error:" || true ;;
      *) echo "unknown step: $step"; exit 2 ;;
    esac
  done
done
