"""Is a finished mesh one closed, outward-facing body?  python generative/check_mesh.py out/thigh.stl ..."""
import sys

import trimesh

for path in sys.argv[1:]:
    m = trimesh.load(path)
    print(f"{path}: watertight {m.is_watertight}, volume {m.volume:.1f} mm3, bodies {len(m.split(only_watertight=False))}, "
          f"bounds {m.bounds.round(2).tolist()}")
