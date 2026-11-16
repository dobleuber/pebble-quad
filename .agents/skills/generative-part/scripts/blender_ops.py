"""Blender operations the finishing and the light-copy steps share (Blender 4.5 or later: the Manifold solver)."""
import bpy
import bmesh  # noqa: I001  (bpy brings it: it cannot come first)


def load(path):
    """An empty scene holding one STL; returns its object, active."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.stl_import(filepath=str(path))
    part = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = part
    return part


def modifier(part, kind, **values):
    bpy.context.view_layer.objects.active = part
    m = part.modifiers.new(kind.lower(), kind)
    for key, value in values.items():
        setattr(m, key, value)
    bpy.ops.object.modifier_apply(modifier=m.name)


def limits(bounds, reach=20.0):
    """Where "to infinity" stops: a little past the problem's box."""
    x0, x1, y0, y1, z0, z1 = bounds
    return ((x0 - reach, x1 + reach), (y0 - reach, y1 + reach), (z0 - reach, z1 + reach))


def tool(prim, within):
    """A primitive of a problem (problems.box, problems.zcyl) as a mesh object, clamped to `within`."""
    clamp = lambda value, axis: max(within[axis][0], min(within[axis][1], value))  # noqa: E731
    kind, *v = prim
    if kind == "box":
        a = [clamp(v[0], 0), clamp(v[1], 0), clamp(v[2], 1), clamp(v[3], 1), clamp(v[4], 2), clamp(v[5], 2)]
        bpy.ops.mesh.primitive_cube_add(size=1, location=((a[0] + a[1]) / 2, (a[2] + a[3]) / 2, (a[4] + a[5]) / 2))
        bpy.context.active_object.scale = (a[1] - a[0], a[3] - a[2], a[5] - a[4])
    else:
        cx, cy, r, za, zb = v
        za, zb = clamp(za, 2), clamp(zb, 2)
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=r, depth=zb - za, location=(cx, cy, (za + zb) / 2))
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)     # its vertices where they are
    return bpy.context.active_object


def boolean(part, other, operation, solver="EXACT"):
    """A boolean of the part with another object (UNION, INTERSECT or DIFFERENCE); the other is used up.
    EXACT copes with faces that coincide, as primitives' do; MANIFOLD is the sturdy one between closed surfaces."""
    bpy.context.view_layer.objects.active = part
    m = part.modifiers.new("bool", "BOOLEAN")
    m.operation, m.solver, m.object = operation, solver, other
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(other, do_unlink=True)


def combine(prims, within):
    """The union of primitives as one object. Boxes and cylinders join cleanly with each other whatever faces they
    share, so the fine mesh then meets one tool once instead of many tools one after the other."""
    whole = tool(prims[0], within)
    for prim in prims[1:]:
        boolean(whole, tool(prim, within), "UNION")
    return whole


def outside(bounds):
    """Everything outside a box, as six slabs: cut with the keep-outs, they trim a part to the box in the same boolean."""
    x0, x1, y0, y1, z0, z1 = bounds
    far = 999.0
    return [("box", -far, x0, -far, far, -far, far), ("box", x1, far, -far, far, -far, far),
            ("box", -far, far, -far, y0, -far, far), ("box", -far, far, y1, far, -far, far),
            ("box", -far, far, -far, far, -far, z0), ("box", -far, far, -far, far, z1, far)]


def weld(part, distance):
    """Merge vertices closer than `distance` and drop the faces that leaves without area."""
    mesh = bmesh.new()
    mesh.from_mesh(part.data)
    bmesh.ops.remove_doubles(mesh, verts=mesh.verts, dist=distance)
    bmesh.ops.dissolve_degenerate(mesh, edges=mesh.edges, dist=distance)
    mesh.to_mesh(part.data)
    mesh.free()


def tidy(part):
    """Triangles only, no face doubled back on itself, one body. Returns the crumbs and the doubled faces dropped,
    and the edges left on a hole's rim (0 for a closed surface)."""
    mesh = bmesh.new()
    mesh.from_mesh(part.data)
    bmesh.ops.triangulate(mesh, faces=mesh.faces)               # as the export would, so what it makes can be checked
    seen = {}                                                    # a cut can leave a sliver flat against its own wall:
    for face in mesh.faces:                                      # two faces on the same vertices, back to back
        seen.setdefault(frozenset(v.index for v in face.verts), []).append(face)
    doubles = [face for faces in seen.values() if len(faces) > 1 for face in faces]
    bmesh.ops.delete(mesh, geom=doubles, context="FACES")
    mesh.faces.ensure_lookup_table()
    island = [-1] * len(mesh.faces)                              # crumbs (some hang on by one vertex) and sealed bubbles
    sizes = []                                                   # are bodies of their own: keep the largest set of
    for seed in mesh.faces:                                      # faces joined across edges
        if island[seed.index] >= 0:
            continue
        island[seed.index] = len(sizes)
        stack, count = [seed], 0
        while stack:
            face = stack.pop()
            count += 1
            for edge in face.edges:
                for other in edge.link_faces:
                    if island[other.index] < 0:
                        island[other.index] = len(sizes)
                        stack.append(other)
        sizes.append(count)
    keep = sizes.index(max(sizes))
    bmesh.ops.delete(mesh, geom=[f for f in mesh.faces if island[f.index] != keep], context="FACES")
    rims = [edge for edge in mesh.edges if len(edge.link_faces) < 2]             # a boolean can drop a triangle or two:
    if rims:                                                                     # close holes of a few edges
        bmesh.ops.holes_fill(mesh, edges=rims, sides=8)
        bmesh.ops.triangulate(mesh, faces=mesh.faces)
    open_edges = sum(1 for edge in mesh.edges if len(edge.link_faces) < 2)      # a hole's rim (an edge of four faces is closed)
    mesh.to_mesh(part.data)
    mesh.free()
    return len(sizes) - 1, len(doubles), open_edges


def mirror_y(part):
    """Turn the part into its mirror image in y, facing outward."""
    part.scale = (1, -1, 1)
    bpy.ops.object.select_all(action="DESELECT")
    part.select_set(True)
    bpy.context.view_layer.objects.active = part
    bpy.ops.object.transform_apply(scale=True)
    mesh = bmesh.new()
    mesh.from_mesh(part.data)
    bmesh.ops.recalc_face_normals(mesh, faces=mesh.faces)        # a mirror image is inside out
    mesh.to_mesh(part.data)
    mesh.free()


def export(part, path):
    bpy.ops.object.select_all(action="DESELECT")
    part.select_set(True)
    bpy.context.view_layer.objects.active = part
    bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True)
    return len(part.data.polygons)
