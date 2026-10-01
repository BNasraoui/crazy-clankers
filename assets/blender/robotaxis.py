"""Parody robotaxis built from Sketchfab source models (see docs/CREDITS.md).

    blender --background --factory-startup --python robotaxis.py -- wayfarer|cybercab|lineup|style

Run fetch_sources.py first; the raw downloads live in sources/ and are not committed.

The cars keep the real shapes of their sources at real size; only the rendering is ours:
flat role colours with straight colour borders, normals split at real creases (about
38 degrees) so the game's two-tone shader puts hard shadow shapes on flat panels, and a
few thin ink lines along the seams an artist would draw.

- wayfarer: a Waymo-style cab from a Jaguar I-PACE. The interior, brakes, lamp internals,
  badges, script and plate are dropped and every other part is decimated and recoloured
  by role, so its colour borders are the source's own panel edges. The mesh grille becomes
  a plain panel of the same outline, the wheels are the source's (scaled to the real
  20-inch size), and our own sensor kit (roof tower with a spinning lidar, fender, nose
  and rear-corner sensors) and teal swoosh are added.
  Nodes: wayfarer > body, lidar, wheel_FL/FR/RL/RR.
- cybercab: a Cybercab-style two-seater from a single fused, textured (AI-generated) mesh.
  The texture is not used: the mesh is made symmetric, the mirrors, plate recess and
  baked-in wheels are ironed away, it is decimated, then the colour borders (glass
  canopy, light bars, cladding) are cut into it along planes, so they come out straight.
  Nodes: cybercab > body, wheel_FL/FR/RL/RR.
- lineup: both side on next to the current cab.glb at the same scale.
- style: the robotaxi from docs/art/scene-target.jpg next to both cars at a similar
  front 3/4 view.

Both follow cab.py's conventions: metres, the car faces -Y in Blender (+Z in the game),
origin on the ground midway between the axles, left (wheel_FL, wheel_RL) at +X.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import common as C  # noqa: E402

SOURCES = Path(__file__).resolve().parent / "sources"
TRI_RANGE = (8000, 16000)
SMOOTH_ANGLE = 38  # normals split at creases sharper than this
TEAL = 0x2FD6BF


# Frames whose local XY is the game's side plane (z, y) and Blender's plan (x, y), for
# laying ink and decals onto the body.
SIDE = Matrix(((0, 0, 1, 0), (-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def side_frame(sx):
    return Matrix.Translation((sx * 3.0, 0, 0)) @ SIDE


def top_frame():
    return Matrix.Translation((0, 0, 4.0))


# Ray directions into the body from the front, the back and the top.
FORWARD, BACKWARD, DOWN = Vector((0, 1, 0)), Vector((0, -1, 0)), Vector((0, 0, -1))


def inward(sx):
    return Vector((-sx, 0, 0))


# --- source import and cleanup -------------------------------------------------

def import_source(name):
    """Import sources/<name>/scene.gltf; returns its meshes with transforms baked in."""
    path = SOURCES / name / "scene.gltf"
    if not path.exists():
        sys.exit(f"missing {path}: run assets/blender/fetch_sources.py first")
    bpy.ops.import_scene.gltf(filepath=str(path))
    meshes = []
    for o in list(bpy.context.scene.objects):
        if o.type == "MESH":
            o.data.transform(o.matrix_world)
            o.parent = None
            o.matrix_world = Matrix()
            meshes.append(o)
    for o in list(bpy.context.scene.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    return sorted(meshes, key=lambda o: o.name)


def mesh_co(o):
    co = np.empty(len(o.data.vertices) * 3, dtype=np.float64)
    o.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def bounds(objs):
    pts = np.concatenate([mesh_co(o) for o in objs])
    return pts.min(axis=0), pts.max(axis=0)


def transform_all(objs, m):
    for o in objs:
        o.data.transform(m)


def edit(obj, fn):
    """Run fn(bm) on the object's mesh."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    out = fn(bm)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return out


def islands(bm):
    """Connected face sets, in a deterministic order."""
    bm.faces.ensure_lookup_table()
    seen, out = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        island, stack = [], [f]
        seen.add(f.index)
        while stack:
            cur = stack.pop()
            island.append(cur)
            for e in cur.edges:
                for nb in e.link_faces:
                    if nb.index not in seen:
                        seen.add(nb.index)
                        stack.append(nb)
        out.append(island)
    return out


def drop_small_islands(obj, min_size):
    """Delete loose parts whose bounding-box diagonal is under `min_size` (bolts, letters)."""
    def run(bm):
        doomed = []
        for island in islands(bm):
            co = np.array([v.co[:] for f in island for v in f.verts])
            if np.linalg.norm(co.max(axis=0) - co.min(axis=0)) < min_size:
                doomed += island
        bmesh.ops.delete(bm, geom=doomed, context="FACES")
    edit(obj, run)


def delete_faces(obj, pred):
    """Delete faces whose centre satisfies pred(Vector)."""
    edit(obj, lambda bm: bmesh.ops.delete(
        bm, geom=[f for f in bm.faces if pred(f.calc_center_median())], context="FACES"))


def weld(obj, dist):
    edit(obj, lambda bm: bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist))


def decimate(obj, target_tris):
    tris = C.triangle_count([obj])
    if tris <= target_tris:
        return
    mod = obj.modifiers.new("dec", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = target_tris / tris
    mod.use_collapse_triangulate = True
    C.apply_modifiers(obj)


def set_role(obj, role, mats):
    obj.data.materials.clear()
    obj.data.materials.append(mats[role])
    obj.data.polygons.foreach_set("material_index", [0] * len(obj.data.polygons))


def join_into(builder, objs):
    for o in objs:
        builder.merge_mesh(o.data, [m.name for m in o.data.materials])
        bpy.data.objects.remove(o)


def iron(bm, axis, zone, pad, keep=lambda v, fit: True):
    """Replace a bump or hollow with the surrounding skin: fit the `axis` coordinate as a
    quadratic in the other two over the ring of verts within `pad` of the zone, then move
    every vert in zone(co, 0) with keep(v, fit) onto the fit."""
    a, b = [i for i in range(3) if i != axis]

    def terms(c):
        return [1, c[a], c[b], c[a] * c[a], c[a] * c[b], c[b] * c[b]]
    ring = [v for v in bm.verts if zone(v.co, pad) and not zone(v.co, 0.0)]
    coef = np.linalg.lstsq(np.array([terms(v.co) for v in ring]),
                           np.array([v.co[axis] for v in ring]), rcond=None)[0]
    for v in bm.verts:
        if zone(v.co, 0.0):
            fit = float(np.dot(terms(v.co), coef))
            if keep(v, fit):
                v.co[axis] = fit


# --- plane-cut colour regions ----------------------------------------------------

def plane3(a, b, c, up):
    """Plane through three points as (point, unit normal), the normal on the side of `up`."""
    a, b, c = Vector(a), Vector(b), Vector(c)
    n = (b - a).cross(c - a).normalized()
    if n.dot(Vector(up)) < 0:
        n = -n
    return a, n


def plane2(a, b, up):
    """Plane through two (y, z) side-view points, extended across the car (along X)."""
    pa, pb = Vector((0, *a)), Vector((0, *b))
    return plane3(pa, pb, pa + Vector((1, 0, 0)), up)


def plane_axis(axis, value, up):
    """Plane `axis` = value; `up` (+1/-1) picks the side the region is on."""
    n = Vector((0, 0, 0))
    n[axis] = up
    co = Vector((0, 0, 0))
    co[axis] = value
    return co, n


def inside(c, planes, margin=0.0):
    return all((c - co).dot(n) >= -margin for co, n in planes)


def cut_region(bm, planes, margin=0.12, snap=0.008):
    """Cut every plane of the convex region into the faces near the region, so the faces
    inside it can be picked exactly by their centres afterwards."""
    for co, n in planes:
        others = [p for p in planes if p[0] is not co]
        faces = [f for f in bm.faces if inside(f.calc_center_median(), others, margin)
                 and abs((f.calc_center_median() - co).dot(n)) < margin]
        if not faces:
            continue
        # Snap verts lying almost on the plane onto it, so the cut leaves no slivers.
        for v in {v for f in faces for v in f.verts}:
            d = (v.co - co).dot(n)
            if abs(d) < snap:
                v.co -= n * d
        geom = faces + list({e for f in faces for e in f.edges}) + list({v for f in faces for v in f.verts})
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=co, plane_no=n)


def paint_region(bm, planes, mat_index, where=lambda f: True):
    for f in bm.faces:
        if inside(f.calc_center_median(), planes) and where(f):
            f.material_index = mat_index


def calm_normals(obj, iterations):
    """Shade the generated mesh's small lumps away without moving it: vertex normals are
    averaged with their neighbours' across smooth edges a few times, so the two-tone
    shadow edge runs in a clean curve; corners at sharp edges keep their split normals."""
    me = obj.data
    n_v = len(me.vertices)
    vn = np.empty(n_v * 3)
    me.vertices.foreach_get("normal", vn)
    vn = vn.reshape(-1, 3)
    ev = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", ev)
    ev = ev.reshape(-1, 2)
    sharp = np.array([e.use_edge_sharp for e in me.edges], dtype=bool)
    creased = np.zeros(n_v, dtype=bool)
    creased[ev[sharp].ravel()] = True
    soft = ev[~sharp]
    for _ in range(iterations):
        acc = vn.copy()
        np.add.at(acc, soft[:, 0], vn[soft[:, 1]])
        np.add.at(acc, soft[:, 1], vn[soft[:, 0]])
        acc /= np.linalg.norm(acc, axis=1, keepdims=True)
        vn = np.where(creased[:, None], vn, acc)
    normals = []
    for i, cn in enumerate(me.corner_normals):
        v = me.loops[i].vertex_index
        normals.append(cn.vector[:] if creased[v] else tuple(vn[v]))
    me.normals_split_custom_set(normals)


# --- surface details ---------------------------------------------------------------

def rim_bands(bm, width, lift=0.003):
    """Ink round a lamp: a band `width` wide lying on the surface just outside each open
    edge of the lamp glass, as quads (lists of points)."""
    bm.normal_update()
    out = []
    for e in bm.edges:
        if not e.is_boundary:
            continue
        f = e.link_faces[0]
        v0, v1 = e.verts
        d = (v1.co - v0.co).normalized()
        t = d.cross(f.normal).normalized()
        if t.dot(f.calc_center_median() - v0.co) > 0:
            t = -t
        quad = [v0.co + v0.normal * lift, v1.co + v1.normal * lift,
                v1.co + v1.normal * lift + t * width, v0.co + v0.normal * lift + t * width]
        # Face the same way as the glass.
        if (quad[1] - quad[0]).cross(quad[3] - quad[0]).dot(f.normal) < 0:
            quad.reverse()
        out.append([p.copy() for p in quad])
    return out


def plate(b, mat, bvh, frame, pts, direction, depth=0.012, steps=(6, 2), sink=0.012):
    """A thin plate on the surface: the quad `pts` (a, b, c, d) in the local XY of
    `frame` is ray-cast along `direction` onto `bvh` on a grid; the plate stands `depth`
    proud of the surface (along the ray) and reaches `sink` below it."""
    a, b_, c, d = (Vector(p) for p in pts)
    nu, nv = steps
    direction = direction.normalized()
    top, bot = [], []
    for j in range(nv + 1):
        trow, brow = [], []
        for i in range(nu + 1):
            u, v = i / nu, j / nv
            p2 = a.lerp(b_, u).lerp(d.lerp(c, u), v)
            for nudge in (0.0, 0.012, -0.012, 0.024, -0.024):
                # A ray down a panel gap passes through; nudge it onto the panel beside.
                origin = frame @ Vector((p2.x + nudge, p2.y + nudge, 0))
                hit = bvh.ray_cast(origin, direction, 8.0)[0]
                if hit is not None:
                    break
            assert hit is not None, f"plate point {p2[:]} missed the body"
            # Offset along the ray, not the hit normal: face normals jump between faces
            # and would crease the plate.
            trow.append(b.bm.verts.new(hit - direction * depth))
            brow.append(b.bm.verts.new(hit + direction * sink))
        top.append(trow)
        bot.append(brow)
    before = b._begin()
    for j in range(nv):
        for i in range(nu):
            b.bm.faces.new((top[j][i], top[j][i + 1], top[j + 1][i + 1], top[j + 1][i]))
            b.bm.faces.new((bot[j][i], bot[j + 1][i], bot[j + 1][i + 1], bot[j][i + 1]))
    rim = ([(j, 0) for j in range(nv)] + [(nv, i) for i in range(nu)]
           + [(j, nu) for j in range(nv, 0, -1)] + [(0, i) for i in range(nu, 0, -1)])
    for (j0, i0), (j1, i1) in zip(rim, rim[1:] + rim[:1]):
        b.bm.faces.new((top[j0][i0], top[j1][i1], bot[j1][i1], bot[j0][i0]))
    new = [f for f in b.bm.faces if f not in before]
    bmesh.ops.recalc_face_normals(b.bm, faces=new)
    return b._assign(before, mat)


def ink(b, bvh, frame, pts, direction, width=0.016, depth=0.005, step=0.08):
    """A thin dark seam line along the polyline `pts` in the frame's local XY, laid on
    the body like a plate, each segment a little longer so the joints overlap."""
    for p0, p1 in zip(pts, pts[1:]):
        p0, p1 = Vector(p0), Vector(p1)
        d = (p1 - p0).normalized()
        p0, p1 = p0 - d * width / 2, p1 + d * width / 2
        n = Vector((-d.y, d.x)) * width / 2
        steps = (max(1, math.ceil((p1 - p0).length / step)), 1)
        plate(b, "trim", bvh, frame, [p0 - n, p1 - n, p1 + n, p0 + n], direction,
              depth=depth, steps=steps)


def to_object(b, *args, **kw):
    """Builder.to_object with coordinates snapped to 0.01 mm: some bmesh ops leave float
    noise that differs from run to run, and the build must be byte-identical."""
    for v in b.bm.verts:
        v.co = Vector(round(c, 5) for c in v.co)
    return b.to_object(*args, **kw)


def finish(name, root, parts):
    C.report(parts)
    tris = C.triangle_count(parts)
    assert TRI_RANGE[0] <= tris <= TRI_RANGE[1], f"{name} has {tris} triangles, outside {TRI_RANGE}"
    C.export_glb(name)
    C.render_contact_sheet(root, name, outline=0.02)


# --- Wayfarer (Waymo-style, from the Jaguar I-PACE) ----------------------------

WAYFARER_LENGTH = 4.68
WAYFARER_WHEEL_R = 0.38   # 245/50 R20; the source's tyres are about 10% oversize
WAYFARER_PALETTE = {
    "body": 0xF4F4F0,
    "glass": 0x1E2731,
    "trim": 0x1C1D20,
    "accent": TEAL,
    "light_head": 0xFFF6DE,
    "light_tail": 0xE0303A,
    "tyre": 0x232427,
    "hub": 0xB4B8BD,
}
# Source material -> (role, triangle budget). Anything not listed is dropped: the
# interior and seats, discs and calipers, lamp internals and chrome bezels, the mesh
# grille (replaced by a plain panel), the side repeaters, the "I-PACE" side script and
# the Jaguar badge (Ipace, Jaguar_bleu).
IPACE_PARTS = {
    "Body": ("body", 4300),
    "Body_noir": ("trim", 1000),
    "Body_blue": ("trim", 200),
    "Chrome": ("trim", 500),
    "Plastique_noir": ("trim", 900),
    "Partie_noir": ("trim", 300),
    "Dessous": ("trim", 200),
    "Miroir": ("trim", 40),
    "Vitre": ("glass", 420),
    "Vitre_noir": ("glass", 420),
    "Vitre_toit": ("glass", 80),
    "Phare_vitre": ("light_head", 200),
    "LED_blanc": ("trim", 80),  # bumper accent line, not a lamp
    "Feux_glass_red": ("light_tail", 280),
    "Feux_LED_red": ("light_tail", 40),
}
# The wheels: source material -> (role, triangle budget per wheel).
IPACE_WHEEL = {"Pneu": ("tyre", 260), "Jante": ("hub", 460), "Jante_noir": ("trim", 120)}


def build_wayfarer():
    C.reset_scene()
    mats = C.make_materials(WAYFARER_PALETTE)
    roles = list(WAYFARER_PALETTE)
    src = import_source("ipace")
    root = C.empty("wayfarer")
    by_mat = {o.data.materials[0].name: o for o in src}

    # Scale to the real car and put the origin on the ground midway between the axles.
    lo, hi = bounds([by_mat["Body"]])
    s = WAYFARER_LENGTH / (hi[1] - lo[1])
    tyre = mesh_co(by_mat["Pneu"])
    axle_y = [tyre[tyre[:, 1] < 0][:, 1].mean(), tyre[tyre[:, 1] > 0][:, 1].mean()]
    transform_all(src, Matrix.Diagonal((s, s, s, 1)) @ Matrix.Translation(
        (-(lo[0] + hi[0]) / 2, -(axle_y[0] + axle_y[1]) / 2, -tyre[:, 2].min())))
    tyre = mesh_co(by_mat["Pneu"])
    src_r = (tyre[:, 2].max() - tyre[:, 2].min()) / 2
    # Real-size wheels: shrink them about their axles and lower the car to stand on them.
    drop = src_r - WAYFARER_WHEEL_R
    transform_all(src, Matrix.Translation((0, 0, -drop)))
    axles = (tyre[tyre[:, 1] < 0][:, 1].mean(), tyre[tyre[:, 1] > 0][:, 1].mean())
    grille_lo, grille_hi = bounds([by_mat["Grille_calandre"]])
    badge_lo, badge_hi = bounds([by_mat["Jaguar_bleu"]])
    badge_lo, badge_hi = badge_lo - 0.03, badge_hi + 0.03

    def in_badge(c):
        return (badge_lo[0] < c.x < badge_hi[0] and badge_lo[2] < c.z < badge_hi[2]
                and c.y < badge_hi[1] + 0.06)

    wheel_parts = {m: by_mat.pop(m) for m in IPACE_WHEEL}
    kept, rims = [], []
    for o in src:
        m = o.data.materials[0].name
        if m in IPACE_WHEEL:
            continue
        if m not in IPACE_PARTS:
            bpy.data.objects.remove(o)
            continue
        role, budget = IPACE_PARTS[m]
        drop_small_islands(o, 0.03)
        delete_faces(o, in_badge)
        if m == "Body_blue":
            # The blank licence plate on the rear bumper.
            delete_faces(o, lambda c: abs(c.x) < 0.4 and c.y > 2.0 and 0.3 < c.z < 0.7)
        if m == "Chrome":
            # The leaper on the tailgate and the plate frame below it.
            delete_faces(o, lambda c: abs(c.x) < 0.4 and c.y > 2.0 and c.z > 0.2)
        weld(o, 1e-4)
        decimate(o, budget)
        set_role(o, role, mats)
        if m in ("Phare_vitre", "Feux_glass_red"):
            rims += edit(o, lambda bm: rim_bands(bm, 0.014))
        kept.append(o)

    b = C.Builder(roles)
    join_into(b, kept)
    before = b._begin()
    for quad in rims:
        b.bm.faces.new([b.bm.verts.new(p) for p in quad])
    b._assign(before, "trim")
    bvh = BVHTree.FromBMesh(b.bm)
    grille_panel(b, bvh, grille_lo, grille_hi)
    wayfarer_details(b, bvh)
    roof = wayfarer_sensors(b, bvh)
    body = to_object(b, "body", mats, parent=root, smooth_angle=SMOOTH_ANGLE)
    calm_normals(body, iterations=4)
    lidar = build_lidar(mats, roles, root, roof)
    wheels = source_wheels(root, mats, roles, wheel_parts, axles, src_r)
    return root, [body, lidar, *wheels]


def source_wheels(root, mats, roles, parts, axles, src_r):
    """Split the source's four wheels into nodes, scaled about their axles to the real
    size; the pivot is the axle centre."""
    k = WAYFARER_WHEEL_R / src_r
    out = []
    for name, sx, ay in (("wheel_FL", 1, axles[0]), ("wheel_FR", -1, axles[0]),
                         ("wheel_RL", 1, axles[1]), ("wheel_RR", -1, axles[1])):
        b = C.Builder(roles)
        centre = None
        for m, (role, budget) in IPACE_WHEEL.items():
            src = parts[m]
            me = src.data.copy()
            o = bpy.data.objects.new(f"{name}_{m}", me)
            bpy.context.scene.collection.objects.link(o)
            delete_faces(o, lambda c: c.x * sx < 0 or abs(c.y - ay) > 0.8)
            drop_small_islands(o, 0.03)
            if m == "Pneu":
                co = mesh_co(o)
                centre = Vector((co[:, 0].mean(), ay, (co[:, 2].max() + co[:, 2].min()) / 2))
            weld(o, 1e-4)
            decimate(o, budget)
            set_role(o, role, mats)
            # Scale about the axle, which the lowered car has put at the real radius.
            o.data.transform(Matrix.Translation(centre) @ Matrix.Diagonal((k, k, k, 1))
                             @ Matrix.Translation(-centre)
                             @ Matrix.Translation((0, 0, WAYFARER_WHEEL_R - centre.z)))
            join_into(b, [o])
        pivot = Vector((centre.x, ay, WAYFARER_WHEEL_R))
        # The hub caps carried the Jaguar badge: cover the centre with a plain cap.
        face = max(v.co.x * sx for v in b.bm.verts)
        b.tube("hub", Vector((sx * (face - 0.03), ay, pivot.z)), Vector((sx * (face - 0.005), ay, pivot.z)),
               0.055, 0.05, sides=10)
        out.append(to_object(b, name, mats, pivot=pivot, parent=root, smooth_angle=SMOOTH_ANGLE))
    for o in parts.values():
        bpy.data.objects.remove(o)
    return out


def grille_panel(b, bvh, lo, hi):
    """A plain black panel in the outline of the mesh grille: the outline is the grille's
    front silhouette, the panel follows its curve and sits just inside the surround."""
    lo, hi = Vector(lo), Vector(hi)
    cx, cz = (lo.x + hi.x) / 2, (lo.z + hi.z) / 2
    w, h = (hi.x - lo.x) / 2, (hi.z - lo.z) / 2
    # The I-PACE grille: a wide hexagon, its top edge straight, the lower corners cut.
    outline = [(-1.0, 1.0), (1.0, 1.0), (1.0, -0.25), (0.62, -1.0), (-0.62, -1.0), (-1.0, -0.25)]
    rings = (0.97, 0.6, 0.25)
    y_back = hi.y + 0.02

    def vert(u, v):
        x, z = cx + u * w, cz + v * h
        # The grille bows forward in plan: follow the bumper skin behind it.
        hit = bvh.ray_cast(Vector((x, lo.y - 1.0, z)), FORWARD, 3.0)[0]
        y = hit.y if hit is not None and hit.y < y_back else lo.y + (hi.y - lo.y) * abs(u) ** 2
        return Vector((x, y + 0.015, z))
    before = b._begin()
    loops = [[b.bm.verts.new(vert(u * s, v * s)) for u, v in outline] for s in rings]
    centre = b.bm.verts.new(vert(0, 0))
    n = len(outline)
    for r0, r1 in zip(loops, loops[1:]):
        for i in range(n):
            j = (i + 1) % n
            b.bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    for i in range(n):
        b.bm.faces.new((loops[-1][i], loops[-1][(i + 1) % n], centre))
    # Back it with a box so it closes.
    new = [f for f in b.bm.faces if f not in before]
    bmesh.ops.recalc_face_normals(b.bm, faces=new)
    for f in new:
        if f.normal.y > 0:
            f.normal_flip()
    b._assign(before, "trim")
    # Two horizontal bars across it, as the artist draws a grille.
    for v in (0.35, -0.25):
        z = cz + v * h
        b.box("hub", (w * 1.7 * (1 - abs(v) * 0.4), 0.02, 0.016), Vector((cx, vert(0, v).y - 0.01, z)), bevel=0.006)


# Seams an artist would draw, in the side frame (forward, up) in metres, laid over the
# source's own panel gaps (its open edges).
WF_SEAMS = [
    [(0.92, 1.12), (1.0, 0.9), (1.0, 0.62), (1.02, 0.4)],              # front door, front edge
    [(-0.2, 1.12), (-0.2, 0.6), (-0.18, 0.4)],                         # B-pillar shut line
    [(-1.42, 1.12), (-1.28, 0.96), (-1.2, 0.8), (-1.16, 0.6)],         # rear door, rear edge
]


def wayfarer_details(b, bvh):
    """Door seams, the hood shut lines and the teal swoosh."""
    for sx in (1, -1):
        s = side_frame(sx)
        for pts in WF_SEAMS:
            ink(b, bvh, s, pts, inward(sx))
        # Teal swoosh: a wide band leaning forward across the front door, like the concept.
        plate(b, "accent", bvh, s, [(0.12, 0.56), (0.38, 0.56), (0.86, 1.04), (0.6, 1.04)],
              inward(sx), steps=(4, 6), depth=0.006)
    # Clamshell hood: shut lines along the tops of the wings.
    for sx in (1, -1):
        ink(b, bvh, top_frame(), [(sx * 0.8, -2.08), (sx * 0.8, -1.15)], DOWN)


def roof_hit(bvh, x, y):
    return bvh.ray_cast(Vector((x, y, 4.0)), DOWN, 6.0)[0]


WF_TOWER_Y = 0.15   # Blender y of the roof tower, over the B-pillars


def wayfarer_sensors(b, bvh):
    """A Waymo-style sensor kit: the roof tower (a white plinth, a black camera ring with
    a teal band; the lidar dome on top is its own node), fender sensors ahead of the
    mirrors, a nose lidar and rear-corner sensors, each with a teal ring."""
    y = WF_TOWER_Y
    # Rounded so float noise in the ray casts cannot change the build.
    roof = round(max(roof_hit(bvh, x, y + dy).z for x in (-0.3, 0, 0.3) for dy in (-0.3, 0, 0.3)), 3)
    # Plinth: a low white block, its sides raked, sunk into the curved roof.
    b.box("body", (0.8, 0.9, 0.16), Vector((0, y, roof + 0.02)), bevel=0.035, seg=2, taper=(0.86, 0.84))
    # Small camera bumps at the plinth's corners.
    for sx in (1, -1):
        for dy in (-0.38, 0.38):
            b.box("trim", (0.07, 0.09, 0.06), Vector((sx * 0.36, y + dy, roof + 0.08)), bevel=0.012)
    top = roof + 0.1
    b.tube("trim", Vector((0, y, top)), Vector((0, y, top + 0.11)), 0.3, 0.28, sides=16, bevel=0.012)
    b.tube("accent", Vector((0, y, top + 0.11)), Vector((0, y, top + 0.135)), 0.28, 0.28, sides=16)
    b.tube("trim", Vector((0, y, top + 0.135)), Vector((0, y, top + 0.15)), 0.25, 0.25, sides=16)
    for sx in (1, -1):
        # Fender sensors on the wings, ahead of the A-pillars.
        fx, fy = sx * 0.76, -1.12
        h = roof_hit(bvh, fx, fy).z
        b.box("body", (0.12, 0.16, 0.08), Vector((fx, fy, h + 0.02)), bevel=0.02, taper=(0.85, 0.85))
        b.tube("trim", Vector((fx, fy, h + 0.05)), Vector((fx, fy, h + 0.15)), 0.055, 0.05, sides=12, bevel=0.008)
        b.tube("accent", Vector((fx, fy, h + 0.105)), Vector((fx, fy, h + 0.12)), 0.057, 0.057, sides=12)
        # Rear-corner sensors on the bumper corners.
        hit = bvh.ray_cast(Vector((sx * 0.84, 4.0, 0.62)), BACKWARD, 4.0)[0]
        c = hit + Vector((0, 0.01, 0))
        b.box("trim", (0.12, 0.08, 0.14), c, bevel=0.02)
        b.tube("accent", c + Vector((0, 0.035, 0.03)), c + Vector((0, 0.045, 0.03)), 0.022, 0.022, sides=8)
    # Nose lidar under the grille.
    hit = bvh.ray_cast(Vector((0, -4.0, 0.42)), FORWARD, 4.0)[0]
    b.tube("trim", hit + Vector((0, 0.03, 0)), hit + Vector((0, -0.06, 0)), 0.07, 0.065, sides=12, bevel=0.01)
    return top + 0.15


def build_lidar(mats, roles, root, base):
    """The spinning lidar dome on the tower; pivot on its axis so it spins about the
    game's Y."""
    y = WF_TOWER_Y
    b = C.Builder(roles)
    b.tube("trim", Vector((0, y, base)), Vector((0, y, base + 0.2)), 0.2, 0.19, sides=20, bevel=0.01)
    b.tube("accent", Vector((0, y, base + 0.13)), Vector((0, y, base + 0.155)), 0.197, 0.196, sides=20)
    b.sphere("trim", Vector((0, y, base + 0.2)), (0.19, 0.19, 0.07), u=20, v=6)
    return to_object(b, "lidar", mats, pivot=Vector((0, y, base + 0.12)), parent=root, smooth_angle=50)


# --- Cyber Cab (Cybercab-style, from a fused AI mesh) --------------------------

CYBERCAB_LENGTH = 4.4
CYBERCAB_PALETTE = {
    "body": 0xC8B48C,       # champagne gold
    "glass": 0x1E2731,
    "trim": 0x141518,
    "light_head": 0xF6F7F2,
    "light_tail": 0xE0303A,
    "tyre": 0x232427,
    "hub": 0xC4C7CB,        # silver aero covers
}
CC_WHEEL_R = 0.37      # measured off the source's baked-in wheels
CC_WHEEL_X = 0.84      # tyre centre, half track
CC_TYRE_W = 0.24
CC_HALF_TRIS = 4300
CC_ARCH_R = CC_WHEEL_R + 0.06
CC_ARCH_IN = 0.5      # the arch liners reach in to this half width
CC_LINER_Z = 0.2      # and down to this height


def band(plane, half):
    """The slab within `half` of a plane, as two planes."""
    co, n = plane
    return [(co - n * half, n), (co + n * half, -n)]


def cc_regions():
    """The colour regions of the right half (x >= 0), each a convex set of planes
    (point, normal pointing inside). Read off the source's texture in orthographic views."""
    belt = plane2((-1.35, 0.9), (1.25, 1.22), (0, 0, 1))
    cowl = plane3((0, -1.2, 0.95), (0.62, -1.06, 0.98), (0.62, -0.7, 1.4), (0, 1, 0))
    tail = plane3((0, 0.98, 1.4), (0.74, 1.24, 1.2), (0.74, 1.24, 0.6), (0, -1, 0))
    return {
        "glass": [[belt, cowl, tail]],
        # Front light bar: a slim band across the nose, wrapping a little round the corners.
        "light_head": [[plane_axis(2, 0.655, 1), plane_axis(2, 0.705, -1),
                        plane_axis(1, -1.62, -1), plane_axis(0, 0.9, -1)]],
        # Rear light bar across the full width of the tail.
        "light_tail": [[plane_axis(2, 0.885, 1), plane_axis(2, 0.945, -1),
                        plane_axis(1, 1.86, 1), plane_axis(0, 0.95, -1)]],
        "trim": [
            [plane_axis(2, 0.27, -1)],                                        # sills, underside
            [plane_axis(2, 0.42, -1), plane_axis(1, 1.86, 1)],                # rear diffuser
            # Window frames on the canopy: the A-pillar running into the roof rail ...
            [belt, cowl, tail, *band(plane3((0.66, -1.1, 0), (0.57, 1.0, 0), (0.57, 1.0, 1), (1, 0, 0)), 0.035)],
            # ... and the B-pillar between the door glass and the rear quarter glass.
            [belt, tail, plane_axis(0, 0.6, 1), *band(plane2((0.44, 1.0), (0.54, 1.5), (0, -1, 0)), 0.028)],
        ],
    }


def build_cybercab():
    C.reset_scene()
    mats = C.make_materials(CYBERCAB_PALETTE)
    roles = list(CYBERCAB_PALETTE)
    (src,) = import_source("cybercab")
    root = C.empty("cybercab")
    lo, hi = bounds([src])
    s = CYBERCAB_LENGTH / (hi[1] - lo[1])
    transform_all([src], Matrix.Diagonal((s, s, s, 1)) @ Matrix.Translation(
        (-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])))
    # Axles from the tyre contact patches (the lowest vertices, front and back).
    co = mesh_co(src)
    low = co[co[:, 2] < 0.02]
    axles = [low[low[:, 1] < 0][:, 1].mean(), low[low[:, 1] > 0][:, 1].mean()]
    mid = (axles[0] + axles[1]) / 2
    transform_all([src], Matrix.Translation((0, -mid, 0)))
    axles = [a - mid for a in axles]

    # Work on the right half and mirror it: the generated mesh is not quite symmetric.
    edit(src, keep_right)
    edit(src, lambda bm: cc_iron(bm, axles))
    edit(src, mirror_x)
    # Rebuild its tangled topology (folds, slivers, stray inner shells) as one clean
    # watertight surface on a 1 cm grid; the shape does not change.
    mod = src.modifiers.new("remesh", "REMESH")
    mod.mode = "VOXEL"
    mod.voxel_size = 0.01
    C.apply_modifiers(src)
    edit(src, keep_right)
    edit(src, cc_relax)
    decimate(src, CC_HALF_TRIS)
    weld(src, 0.004)
    src.data.materials.clear()
    for n in roles:
        src.data.materials.append(mats[n])
    skin = edit(src, lambda bm: BVHTree.FromBMesh(bm))
    edit(src, lambda bm: cc_arches(bm, axles))
    edit(src, cc_paint)

    edit(src, mirror_x)

    b = C.Builder(roles)
    join_into(b, [src])
    bvh = BVHTree.FromBMesh(b.bm)
    arch_liners(b, axles, skin)
    cybercab_seams(b, bvh)
    body = to_object(b, "body", mats, parent=root, smooth_angle=SMOOTH_ANGLE)
    calm_normals(body, iterations=10)
    wheels = cc_wheels(root, mats, roles, axles)
    return root, [body, *wheels]


def keep_right(bm):
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6,
                           plane_co=(0, 0, 0), plane_no=(1, 0, 0), clear_inner=True)


def mirror_x(bm):
    """Mirror the right half into the left and weld the centre line."""
    bmesh.ops.mirror(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], axis="X",
                     matrix=Matrix(), merge_dist=0.002)


def cc_relax(bm):
    """Relax the skin where the mirror was ironed off, so no dent is left."""
    zone = [v for v in bm.verts if -0.95 < v.co.y < -0.25 and 0.78 < v.co.z < 1.2 and v.co.x > 0.6]
    for _ in range(80):
        bmesh.ops.smooth_vert(bm, verts=zone, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)


def cc_iron(bm, axles):
    """Iron away what the real car hasn't, or what we rebuild: the mirrors, the plate
    recess in the tail, and the baked-in wheels (pressed into flat wells)."""
    # Mirrors: everything standing proud of the door skin around the mirror.
    def mirror_zone(c, pad):
        return -0.9 - pad < c.y < -0.3 + pad and 0.8 - pad < c.z < 1.18 + pad and c.x > 0.5
    iron(bm, 0, mirror_zone, 0.12, keep=lambda v, fit: v.co.x > fit - 0.08)
    # Plate recess: the tail skin, flat across.
    rear = max(v.co.y for v in bm.verts)

    def plate_zone(c, pad):
        return c.x < 0.5 + pad and c.y > rear - 0.45 and 0.5 - pad < c.z < 0.86 + pad
    iron(bm, 1, plate_zone, 0.12, keep=lambda v, fit: abs(v.co.y - fit) < 0.15)
    # The lumpy diffuser "tips" below it.
    def diffuser_zone(c, pad):
        return c.x < 0.75 + pad and c.y > rear - 0.4 and 0.12 - pad < c.z < 0.48 + pad
    iron(bm, 1, diffuser_zone, 0.06, keep=lambda v, fit: abs(v.co.y - fit) < 0.2)


def cc_paint(bm):
    """Cut the colour regions along their planes and paint them: straight borders."""
    names = list(CYBERCAB_PALETTE)
    regions = cc_regions()
    for role in ("trim", "glass", "light_head", "light_tail"):
        for planes in regions[role]:
            cut_region(bm, planes)
    for f in bm.faces:
        f.material_index = names.index("body")
    for role in ("glass", "trim", "light_head", "light_tail"):
        for planes in regions[role]:
            where = (lambda f: f.normal.y < -0.25) if role == "light_head" else (
                (lambda f: f.normal.y > 0.25) if role == "light_tail" else (lambda f: True))
            paint_region(bm, planes, names.index(role), where)


ARCH_SIDES = 24


def arch_planes(ay):
    """The wheel arch as a convex region: a 24-sided cylinder about the axle (along X),
    outboard of the liner."""
    planes = [plane_axis(0, CC_ARCH_IN, 1)]
    for i in range(ARCH_SIDES):
        a = 2 * math.pi * (i + 0.5) / ARCH_SIDES
        d = Vector((0, math.cos(a), math.sin(a)))
        planes.append((Vector((0, ay, CC_WHEEL_R)) + d * CC_ARCH_R, -d))
    return planes


def cc_arches(bm, axles):
    """Cut round wheel arches through the body and the baked-in wheels."""
    for ay in axles:
        planes = arch_planes(ay)
        cut_region(bm, planes, margin=0.08)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if inside(f.calc_center_median(), planes)],
                         context="FACES")


def arch_liners(b, axles, skin):
    """Dark liners inside the arches, reaching out to the uncut body skin (`skin`, the
    right half), and a wall closing each at the inboard end."""
    for sx in (1, -1):
        for ay in axles:
            before = b._begin()
            ring = []
            # The arc above the sill line; below it there is no body to line.
            a0 = math.asin((CC_LINER_Z - CC_WHEEL_R) / CC_ARCH_R)
            n = ARCH_SIDES // 2 + 2
            for i in range(n + 1):
                a = -a0 + (math.pi + 2 * a0) * i / n
                p = Vector((0, ay + math.cos(a) * CC_ARCH_R, CC_WHEEL_R + math.sin(a) * CC_ARCH_R))
                hit = skin.ray_cast(Vector((2.0, p.y, p.z)), Vector((-1, 0, 0)), 2.0 - CC_ARCH_IN)[0]
                x_out = hit.x - 0.004 if hit is not None else CC_WHEEL_X
                ring.append((b.bm.verts.new((sx * CC_ARCH_IN, p.y, p.z)),
                             b.bm.verts.new((sx * x_out, p.y, p.z))))
            for (p0, p1), (q0, q1) in zip(ring, ring[1:]):
                b.bm.faces.new((p0, p1, q1, q0))
            b.bm.faces.new([r[0] for r in ring])
            new = [f for f in b.bm.faces if f not in before]
            centre = Vector((sx * 0.8, ay, CC_WHEEL_R))
            for f in new:
                f.normal_update()
                c = f.calc_center_median()
                inner = (centre - c).dot(f.normal) < 0 if len(f.verts) == 4 else f.normal.x * sx < 0
                if inner:
                    f.normal_flip()
            b._assign(before, "trim")


def cybercab_seams(b, bvh):
    """Butterfly-door shut lines."""
    for sx in (1, -1):
        s = side_frame(sx)
        ink(b, bvh, s, [(0.8, 0.3), (0.84, 0.62), (0.86, 0.94)], inward(sx))         # door front
        ink(b, bvh, s, [(-0.3, 0.29), (-0.38, 0.7), (-0.47, 1.08)], inward(sx))      # door rear


def cc_wheels(root, mats, roles, axles):
    """Aero-covered wheels like the real car's: a tyre with a rounded shoulder, a flat
    cover with a dark ring and a small cap; pivot at the axle centre."""
    out = []
    for name, sx, ay in (("wheel_FL", 1, axles[0]), ("wheel_FR", -1, axles[0]),
                         ("wheel_RL", 1, axles[1]), ("wheel_RR", -1, axles[1])):
        b = C.Builder(roles)
        c = Vector((sx * CC_WHEEL_X, ay, CC_WHEEL_R))
        ax = Vector((sx, 0, 0))
        w, r = CC_TYRE_W, CC_WHEEL_R
        b.tube("tyre", c - ax * w / 2, c + ax * w / 2, r, r, sides=20, bevel=0.045)
        face = w / 2 + 0.006
        rim = r * 0.74
        b.tube("hub", c + ax * (w / 2 - 0.04), c + ax * face, rim, rim * 0.97, sides=20, bevel=0.01)
        b.tube("trim", c + ax * (face - 0.004), c + ax * (face + 0.004), rim * 0.82, rim * 0.82, sides=20)
        b.tube("hub", c + ax * (face - 0.002), c + ax * (face + 0.008), rim * 0.78, rim * 0.6, sides=20)
        b.tube("trim", c + ax * (face + 0.006), c + ax * (face + 0.014), rim * 0.12, rim * 0.1, sides=10)
        out.append(to_object(b, name, mats, pivot=c, parent=root, smooth_angle=SMOOTH_ANGLE))
    return out


# --- lineup and style sheets -------------------------------------------------------

def import_cab(name, root, offset, smooth=SMOOTH_ANGLE):
    bpy.ops.import_scene.gltf(filepath=str(C.MODELS_DIR / f"{name}.glb"))
    for o in bpy.context.selected_objects:
        if o.parent is None:
            o.parent = root
            o.location.y += offset
        if o.type == "MESH":
            # glTF splits vertices per face; weld so the outline hulls stay closed.
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
            bm.to_mesh(o.data)
            bm.free()
            o.data.shade_smooth()
            o.data.set_sharp_from_angle(angle=math.radians(1 if name == "cab" else smooth))


def build_lineup():
    """The two robotaxis nose to tail with the current cab, side on, at export scale."""
    C.reset_scene()
    root = C.empty("lineup")
    for name, y in (("wayfarer", -5.2), ("cab", 0.0), ("cybercab", 5.0)):
        import_cab(name, root, y)
    C.render_contact_sheet(root, "robotaxis-lineup", outline=0.02, size=1800, fill=1.0,
                           elevation=6.0, views=(("side", -90),))
    crop_to_content(C.RENDERS_DIR / "robotaxis-lineup.png", margin=40)


# The robotaxi in docs/art/scene-target.jpg (x0, y0, x1, y1 in pixels).
CONCEPT = Path(__file__).resolve().parents[2] / "docs" / "art" / "scene-target.jpg"
CONCEPT_CROP = (752, 205, 1218, 612)


def build_style():
    """Concept-art robotaxi, then each robotaxi from a similar front 3/4 view, from above."""
    tiles = []
    for name in ("wayfarer", "cybercab"):
        C.reset_scene()
        root = C.empty("style")
        import_cab(name, root, 0.0)
        C.render_contact_sheet(root, f".style-{name}", outline=0.02, size=800, fill=0.78,
                               elevation=4.0, views=(("3/4 front", 32),))
        path = C.RENDERS_DIR / f".style-{name}.png"
        tiles.append(load_rgb(path))
        path.unlink()
    concept = load_rgb(CONCEPT)
    x0, y0, x1, y1 = CONCEPT_CROP
    h = concept.shape[0]
    concept = concept[h - y1:h - y0, x0:x1]  # Blender images are stored bottom-up
    concept = resize(concept, tiles[0].shape[0])
    gap = np.ones((tiles[0].shape[0], 12, 3), np.float32) * np.array(C.BG, np.float32)
    row = [concept]
    for t in tiles:
        row += [gap, t]
    save_rgb(np.concatenate(row, axis=1), C.RENDERS_DIR / "robotaxis-style.png")


def load_rgb(path):
    img = bpy.data.images.load(str(path))
    img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[..., :3].copy()


def resize(px, height):
    """Nearest-neighbour resize to `height`, keeping the aspect ratio."""
    h, w = px.shape[:2]
    width = round(w * height / h)
    ys = (np.arange(height) * h / height).astype(int)
    xs = (np.arange(width) * w / width).astype(int)
    return px[ys][:, xs]


def save_rgb(px, path):
    h, w = px.shape[:2]
    out = bpy.data.images.new(path.stem, w, h, alpha=False)
    out.colorspace_settings.name = "Non-Color"
    out.pixels.foreach_set(np.concatenate([px, np.ones((h, w, 1), np.float32)], axis=2).ravel())
    out.filepath_raw = str(path)
    out.file_format = "PNG"
    out.save()
    print(f"rendered {path}")


def crop_to_content(path, margin):
    px = load_rgb(path)
    ink_px = np.abs(px - np.array(C.BG, dtype=np.float32)).sum(axis=2) > 0.02
    rows = np.where(ink_px.any(axis=1))[0]
    lo, hi = max(rows.min() - margin, 0), min(rows.max() + margin, px.shape[0] - 1)
    save_rgb(px[lo:hi + 1], path)


def main():
    car = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "wayfarer"
    if car == "lineup":
        build_lineup()
    elif car == "style":
        build_style()
    else:
        root, parts = {"wayfarer": build_wayfarer, "cybercab": build_cybercab}[car]()
        finish(car, root, parts)


main()
