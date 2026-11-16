#!/bin/sh
# The generative build through the same checks as the hand-drawn robot (README.md, "Checks made"):
#
#   sh generative/checks.sh
#
# Needs text-to-cad's `cad` and python3. The parts' light copies must be there (generative/lite.py).
set -u
cd "$(dirname "$0")/.."
ID=$(cad run generative/quad_v2.py 2>&1 | awk '/^  id:/ {print $2}')
echo "quad_v2: $ID"

echo "== interference at 51 poses: as built, standing, crouched, and 12 along each move"
POSES="--pose stand --pose crouch"
for move in trot:0.5 crawl:1.0 wave:5.0 dance:6.0; do
  name=${move%%:*}; seconds=${move##*:}
  for i in 0 1 2 3 4 5 6 7 8 9 10 11; do
    POSES="$POSES --pose $name@$(python3 -c "print(round($seconds * $i / 12, 3))")"
  done
done
cad model interference "$ID" $POSES 2>&1 | tail -n 12

echo "== the leg-clearance guard against the CAD, 40 random poses"
python3 src/check_guard.py "$ID"

echo "== joint travel, each joint alone"
cad model ranges "$ID" 2>&1 | tail -n 12

echo "== simulation model"
cad run generative/quad_v2_mujoco.py 2>&1 | tail -n 3
cad mujoco check generative/sim/scene.xml 2>&1 | tail -n 3

echo "== walking tests"
cad run src/walk_sim.py --suite --scene generative/sim/scene.xml --results generative/results 2>&1 | tail -n 5
