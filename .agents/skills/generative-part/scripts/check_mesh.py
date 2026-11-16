"""Is a finished mesh one closed body?  python check_mesh.py out/part.stl ...

A boolean can leave a few triangles of no volume beside the part: they are counted apart, and a slicer ignores them.
"""
import sys

import trimesh

for path in sys.argv[1:]:
    mesh = trimesh.load(path)
    bodies = sorted(mesh.split(only_watertight=False), key=lambda b: -abs(b.volume))
    main, rest = bodies[0], bodies[1:]
    slivers = [b for b in rest if abs(b.volume) < 1e-3]
    others = len(rest) - len(slivers)
    verdict = "OK" if main.is_watertight and not others and mesh.volume > 0 else "CHECK"
    print(f"{verdict} {path}: {abs(mesh.volume):.1f} mm3, main body {'closed' if main.is_watertight else 'OPEN'}, "
          f"{others} other bodies, {len(slivers)} slivers of no volume, "
          f"{'facing outward' if mesh.volume > 0 else 'INSIDE OUT'}, bounds {mesh.bounds.round(2).tolist()}")
