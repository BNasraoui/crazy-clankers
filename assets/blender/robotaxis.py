"""Parody robotaxis built from Sketchfab source models (see docs/CREDITS.md).

    blender --background --factory-startup --python robotaxis.py -- wayfarer|cybercab|lineup

Run fetch_sources.py first; the raw downloads live in sources/ and are not committed.

- wayfarer: a Waymo-style cab from a Jaguar I-PACE. Interior, wheels, brakes, badges and
  the mesh grille are dropped, every part is decimated and recoloured by role, and our own
  sensor kit (roof pod with a spinning lidar dome, fender and rear-corner pods) and teal
  stripe are added. Nodes: wayfarer > body, lidar, wheel_FL/FR/RL/RR.
- cybercab: a Cybercab-style two-seater from a single fused (AI-generated) mesh. Faces are
  sorted into roles by sampling the source texture, the texture is then discarded, the
  baked-in wheels are pressed into wells and replaced, and door seams and light bars are
  laid onto the surface. Nodes: cybercab > body, wheel_FL/FR/RL/RR.
- lineup: both next to the current cab.glb at the same scale.

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
MAX_TRIS = 12000


def g(x, y, z):
    """Game coordinates (Y up, +Z forward) to Blender (Z up, -Y forward)."""
    return Vector((x, -z, y))


def gsize(w, h, d):
    return (w, d, h)


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


def bounds(objs):
    pts = np.concatenate([mesh_co(o) for o in objs])
    return pts.min(axis=0), pts.max(axis=0)


def mesh_co(o):
    co = np.empty(len(o.data.vertices) * 3, dtype=np.float64)
    o.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def transform_all(objs, m):
    for o in objs:
        o.data.transform(m)


def drop_small_islands(obj, min_size):
    """Delete loose parts whose bounding-box diagonal is under `min_size` (bolts, letters)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    seen, doomed = set(), []
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
        co = np.array([v.co[:] for q in island for v in q.verts])
        if np.linalg.norm(co.max(axis=0) - co.min(axis=0)) < min_size:
            doomed += island
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    return len(doomed)


def delete_faces(obj, pred):
    """Delete faces whose centre satisfies pred(Vector)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if pred(f.calc_center_median())], context="FACES")
    bm.to_mesh(obj.data)
    bm.free()


def weld(obj, dist):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.to_mesh(obj.data)
    bm.free()


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


def decal(builder, mat, bvh, frame, pts, direction, lift=0.012, steps=(6, 2)):
    """Lay a flat quad strip onto a surface: `pts` is a 4-point quad (a, b, c, d) in the
    local XY of `frame`; each grid point is ray-cast along `direction` (model space) onto
    `bvh` and lifted off the hit along its normal. Points that miss are dropped."""
    a, b, c, d = (Vector(p) for p in pts)
    nu, nv = steps
    grid = []
    for j in range(nv + 1):
        row = []
        for i in range(nu + 1):
            u, v = i / nu, j / nv
            p2 = (a.lerp(b, u)).lerp(d.lerp(c, u), v)
            origin = frame @ Vector((p2.x, p2.y, 0)) - direction.normalized() * 2.0
            hit, n, _, _ = bvh.ray_cast(origin, direction.normalized(), 5.0)
            row.append(None if hit is None else builder.bm.verts.new(hit + n * lift))
        grid.append(row)
    before = builder._begin()
    for j in range(nv):
        for i in range(nu):
            q = [grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]]
            if all(q):
                f = builder.bm.faces.new(q)
                f.normal_update()
                if f.normal.dot(direction) > 0:
                    f.normal_flip()
    loose = [v for row in grid for v in row if v is not None and not v.link_faces]
    bmesh.ops.delete(builder.bm, geom=loose, context="VERTS")
    return builder._assign(before, mat)


def wheel(name, mats_list, mats, root, x, z, r, width, hub_r, cap=False, sides=14):
    """Tyre + hub disc in the cab.py style; pivot at the axle centre."""
    b = C.Builder(mats_list)
    sx = 1 if x > 0 else -1
    y = r
    b.tube("tyre", g(x - sx * width / 2, y, z), g(x + sx * width / 2, y, z), r, r, sides=sides, bevel=0.04)
    b.tube("hub", g(x + sx * (width / 2 - 0.02), y, z), g(x + sx * (width / 2 + 0.012), y, z),
           hub_r, hub_r * 0.93, sides=sides if cap else 8)
    b.tube("trim", g(x + sx * (width / 2 + 0.008), y, z), g(x + sx * (width / 2 + 0.025), y, z),
           0.07, 0.05, sides=8)
    return b.to_object(name, mats, pivot=g(x, y, z), parent=root)


def build_wheels(root, mats_list, mats, track_x, front_z, rear_z, r, width, hub_r, cap=False):
    out = []
    for name, x, z in (("wheel_FL", track_x, front_z), ("wheel_FR", -track_x, front_z),
                       ("wheel_RL", track_x, rear_z), ("wheel_RR", -track_x, rear_z)):
        out.append(wheel(name, mats_list, mats, root, x, z, r, width, hub_r, cap))
    return out


def finish(name, root, parts, outline=0.03):
    C.report(parts)
    tris = C.triangle_count(parts)
    assert tris <= MAX_TRIS, f"{name} has {tris} triangles, over {MAX_TRIS}"
    C.export_glb(name)
    C.render_contact_sheet(root, name, outline=outline)


# --- Wayfarer (Waymo-style, from the Jaguar I-PACE) ----------------------------

WAYFARER_LENGTH = 4.68
WAYFARER_PALETTE = {
    "body": 0xF2F2EE,
    "glass": 0x1E2731,
    "trim": 0x1C1D20,
    "accent": 0x2FCDB8,
    "tyre": 0x232427,
    "hub": 0xA6AAAF,
    "light_head": 0xFFF4D6,
    "light_tail": 0xE0303A,
}
# Source material -> (role, triangle budget). Anything not listed is dropped: the
# interior and seats, wheels, discs and calipers (replaced), lamp internals, chrome
# lamp bezels, the mesh grille (replaced by a plain panel), side repeaters, and the
# "I-PACE" side script and Jaguar badge (Ipace, Jaguar_bleu).
IPACE_PARTS = {
    "Body": ("body", 5200),
    "Body_noir": ("trim", 1100),
    "Body_blue": ("trim", 160),
    "Chrome": ("trim", 600),
    "Plastique_noir": ("trim", 800),
    "Partie_noir": ("trim", 300),
    "Dessous": ("trim", 220),
    "Miroir": ("trim", 40),
    "Vitre": ("glass", 420),
    "Vitre_noir": ("glass", 380),
    "Vitre_toit": ("glass", 80),
    "Phare_vitre": ("light_head", 160),
    "LED_blanc": ("trim", 80),  # bumper accent line, not a lamp
    "Feux_glass_red": ("light_tail", 260),
    "Feux_LED_red": ("light_tail", 40),
}


def build_wayfarer():
    C.reset_scene()
    mats = C.make_materials(WAYFARER_PALETTE)
    mats_list = list(WAYFARER_PALETTE)
    src = import_source("ipace")
    global ROOT
    ROOT = C.empty("wayfarer")
    by_mat = {o.data.materials[0].name: o for o in src}

    # Measure from the source tyres, then scale to the real car and put the origin on
    # the ground midway between the axles.
    lo, hi = bounds([by_mat["Body"]])
    s = WAYFARER_LENGTH / (hi[1] - lo[1])
    tyre = mesh_co(by_mat["Pneu"])
    ground = tyre[:, 2].min()
    axle_y = [tyre[tyre[:, 1] < 0][:, 1].mean(), tyre[tyre[:, 1] > 0][:, 1].mean()]
    fit = Matrix.Diagonal((s, s, s, 1)) @ Matrix.Translation(
        (-(lo[0] + hi[0]) / 2, -(axle_y[0] + axle_y[1]) / 2, -ground))
    transform_all(src, fit)
    tyre = mesh_co(by_mat["Pneu"])
    front = tyre[tyre[:, 1] < 0]
    wheel_r = (front[:, 2].max() - front[:, 2].min()) / 2
    wheel_x = (np.abs(front[:, 0]).max() + np.abs(front[:, 0]).min()) / 2
    tyre_w = np.abs(front[:, 0]).max() - np.abs(front[:, 0]).min()
    front_z = -front[:, 1].mean()
    grille_lo, grille_hi = bounds([by_mat["Grille_calandre"]])
    # The grille badge and its ring sit in front of the grille, around the blue badge.
    badge_lo, badge_hi = bounds([by_mat["Jaguar_bleu"]])
    badge_lo, badge_hi = badge_lo - 0.09, badge_hi + 0.09

    def in_badge(c):
        return (badge_lo[0] < c.x < badge_hi[0] and badge_lo[2] < c.z < badge_hi[2]
                and c.y < badge_hi[1] + 0.15)

    kept = []
    for o in src:
        m = o.data.materials[0].name
        if m not in IPACE_PARTS:
            bpy.data.objects.remove(o)
            continue
        role, budget = IPACE_PARTS[m]
        drop_small_islands(o, 0.06)
        if m != "Body":
            delete_faces(o, in_badge)
        if m == "Body_blue":
            # The blank licence plate on the rear bumper.
            delete_faces(o, lambda c: abs(c.x) < 0.4 and c.y > 2.0 and 0.4 < c.z < 0.7)
        if m == "Chrome":
            # The leaper badge on the tailgate and the licence-plate frame below it.
            delete_faces(o, lambda c: abs(c.x) < 0.4 and c.y > 2.0 and c.z > 0.3)
        weld(o, 1e-4)
        decimate(o, budget)
        set_role(o, role, mats)
        kept.append(o)

    b = C.Builder(mats_list)
    join_into(b, kept)
    body_bvh = surface_bvh_from_builder(b)

    # Plain black panel where the mesh grille was.
    gc = (Vector(grille_lo) + Vector(grille_hi)) / 2
    gs = Vector(grille_hi) - Vector(grille_lo)
    b.box("trim", (gs.x * 0.98, gs.y, gs.z * 0.95), gc, bevel=0.02)

    sensors(b, body_bvh)
    body = b.to_object("body", mats, parent=ROOT, smooth_angle=40)
    lidar = build_lidar(mats_list, mats)
    wheels = build_wheels(ROOT, mats_list, mats, wheel_x, front_z, -front_z,
                          wheel_r, tyre_w, wheel_r * 0.62)
    print(f"WHEELS wayfarer r={wheel_r:.3f} x=±{wheel_x:.3f} axles z=±{front_z:.3f} width={tyre_w:.3f}")
    return [body, lidar, *wheels]


def surface_bvh_from_builder(b):
    return BVHTree.FromBMesh(b.bm)


# Roof pod and lidar, in game coordinates (z forward, y up). Placed against the
# measured roof in sensors().
LIDAR = {"z": -0.15, "y": None}
ROOT = None  # the car's root empty, made after the source import


def roof_height(bvh, x, z):
    hit = bvh.ray_cast(g(x, 4.0, z), Vector((0, 0, -1)), 6.0)[0]
    return hit.z


def sensors(b, bvh):
    """Our own Waymo-ish kit: roof pod with a lidar dome, fender pods, rear-corner pods,
    a front 'nose' sensor and a teal stripe on the doors and tailgate."""
    lz = LIDAR["z"]
    roof = roof_height(bvh, 0, lz)
    # Roof pod: a low rounded plinth that reaches down into the roof.
    b.box("body", gsize(0.62, 0.22, 0.78), g(0, roof + 0.05, lz), bevel=0.05, seg=2, taper=(0.8, 0.8))
    b.tube("trim", g(0, roof + 0.15, lz), g(0, roof + 0.2, lz), 0.25, 0.24, sides=14)
    LIDAR["y"] = roof + 0.2
    for sx in (1, -1):
        # Fender pods just ahead of the A-pillars, on top of the front wings.
        fz = 1.25
        fx = sx * 0.78
        fy = roof_height(bvh, fx, fz)
        b.box("trim", gsize(0.13, 0.16, 0.24), g(fx, fy + 0.06, fz), bevel=0.03)
        b.tube("trim", g(fx, fy + 0.13, fz), g(fx, fy + 0.2, fz), 0.07, 0.06, sides=8)
        # Rear-corner pods, sunk into the bumper corners.
        hit = bvh.ray_cast(g(sx * 0.8, 0.8, -4.0), Vector((0, -1, 0)), 4.0)[0]
        b.box("trim", gsize(0.12, 0.2, 0.16), hit + Vector((0, -0.02, 0)), bevel=0.03)
        # Teal swoosh on the front door, leaning forward.
        side = side_frame(sx * 1.4)
        decal(b, "accent", bvh, side, [(0.08, 0.56), (0.38, 0.56), (0.72, 0.98), (0.42, 0.98)],
              Vector((-sx, 0, 0)), steps=(4, 3))
    # Nose sensor under the grille.
    b.box("trim", gsize(0.26, 0.09, 0.08), g(0, 0.36, 2.33), bevel=0.02)
    # Teal slash on the tailgate.
    rear = Matrix.Translation(g(0, 0, -3.0)) @ FACING
    decal(b, "accent", bvh, rear, [(-0.3, 0.8), (-0.44, 0.8), (-0.62, 1.0), (-0.48, 1.0)],
          Vector((0, -1, 0)), steps=(3, 2))


# Frame whose local XY is the game's front/back plane (x, y).
FACING = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
SIDE = Matrix(((0, 0, 1, 0), (-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def side_frame(x):
    """Frame whose local XY is the game's side plane (z, y) at game x."""
    return Matrix.Translation((x, 0, 0)) @ SIDE


def build_lidar(mats_list, mats):
    """Rounded spinning dome; pivot at the dome centre so it spins about the game's Y."""
    lz, ly = LIDAR["z"], LIDAR["y"]
    b = C.Builder(mats_list)
    b.tube("trim", g(0, ly, lz), g(0, ly + 0.16, lz), 0.22, 0.22, sides=16)
    b.tube("accent", g(0, ly + 0.05, lz), g(0, ly + 0.09, lz), 0.228, 0.228, sides=16)
    b.sphere("trim", g(0, ly + 0.16, lz), (0.22, 0.22, 0.13), u=16, v=8)
    centre = g(0, ly + 0.12, lz)
    return b.to_object("lidar", mats, pivot=centre, parent=ROOT, smooth_angle=50)


# --- Cyber Cab (Cybercab-style, from a fused AI mesh) --------------------------

CYBERCAB_LENGTH = 4.4
CYBERCAB_PALETTE = {
    "body": 0xB8BCC0,
    "glass": 0x141619,
    "trim": 0x1C1D20,
    "tyre": 0x232427,
    "hub": 0xC9CCD0,
    "light_head": 0xF6F7F2,
    "light_tail": 0xE0303A,
}
CC_WHEEL_R = 0.37      # measured off the source's baked-in wheels
CC_WHEEL_X = 0.84      # tyre centre, half track
CC_TYRE_W = 0.22
CC_WELL_X = 0.70       # wheel wells are pressed in to this half width
CC_BELT_Y = 0.92       # glass only above this height
CC_TRIM_Y = 0.45       # black trim only below this height


def classify_cybercab(obj, mats):
    """Give each face a role from the source texture at its UV centre and its position."""
    me = obj.data
    img = None
    for n in me.materials[0].node_tree.nodes:
        if n.type == "TEX_IMAGE" and "baseColor" in n.image.name:
            img = n.image
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)[..., :3]
    n_loops, n_polys = len(me.loops), len(me.polygons)
    uv = np.empty(n_loops * 2, dtype=np.float32)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    start = np.empty(n_polys, dtype=np.int32)
    total = np.empty(n_polys, dtype=np.int32)
    me.polygons.foreach_get("loop_start", start)
    me.polygons.foreach_get("loop_total", total)
    centre_uv = np.add.reduceat(uv, start) / total[:, None]
    ix = np.clip((centre_uv[:, 0] % 1) * w, 0, w - 1).astype(int)
    iy = np.clip((centre_uv[:, 1] % 1) * h, 0, h - 1).astype(int)
    col = px[iy, ix]
    centre = np.empty(n_polys * 3, dtype=np.float32)
    me.polygons.foreach_get("center", centre)
    centre = centre.reshape(-1, 3)
    normal = np.empty(n_polys * 3, dtype=np.float32)
    me.polygons.foreach_get("normal", normal)
    normal = normal.reshape(-1, 3)

    r, gg, bb = col[:, 0], col[:, 1], col[:, 2]
    luma = 0.3 * r + 0.59 * gg + 0.11 * bb
    z = centre[:, 2]
    roles = np.full(n_polys, "body", dtype=object)
    # The texture has baked shadows, so dark only means trim in the lower band (intakes,
    # sills, diffuser) and glass in the greenhouse; in between everything is paint.
    dark = luma < 0.22
    roles[dark & (z < CC_TRIM_Y)] = "trim"
    roles[dark & (z > CC_BELT_Y)] = "glass"
    # Red tail lamps in the texture become paint; cyber_details() lays a crisp bar instead.
    roles[z < 0.24] = "trim"  # sills and underside
    roles[normal[:, 2] < -0.5] = "trim"

    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    nbrs = [[nb.index for e in f.edges for nb in e.link_faces if nb is not f] for f in bm.faces]
    area = np.array([f.calc_area() for f in bm.faces])
    bm.free()
    roles = majority_filter(roles, nbrs, 4)
    roles = absorb_islands(roles, nbrs, area, 0.006)

    names = list(CYBERCAB_PALETTE)
    me.materials.clear()
    for n in names:
        me.materials.append(mats[n])
    me.polygons.foreach_set("material_index", [names.index(x) for x in roles])


def majority_filter(roles, nbrs, passes):
    for _ in range(passes):
        new = roles.copy()
        for i, nb in enumerate(nbrs):
            if nb:
                vals, counts = np.unique(np.array([roles[j] for j in nb]), return_counts=True)
                if counts.max() > len(nb) / 2:
                    new[i] = vals[counts.argmax()]
        roles = new
    return roles


def absorb_islands(roles, nbrs, area, min_area):
    """Repaint connected same-role patches smaller than `min_area` (m^2) with the role
    that borders them most."""
    roles = roles.copy()
    seen = np.zeros(len(roles), dtype=bool)
    for start in range(len(roles)):
        if seen[start]:
            continue
        patch, stack, border = [], [start], []
        seen[start] = True
        while stack:
            i = stack.pop()
            patch.append(i)
            for j in nbrs[i]:
                if roles[j] == roles[start]:
                    if not seen[j]:
                        seen[j] = True
                        stack.append(j)
                else:
                    border.append(roles[j])
        if border and area[patch].sum() < min_area:
            vals, counts = np.unique(np.array(border), return_counts=True)
            for i in patch:
                roles[i] = vals[counts.argmax()]
    return roles


def press_wheel_wells(obj, axles):
    """Push the baked-in wheels into flat wells so the real wheels can sit in them."""
    names = [m.name for m in obj.data.materials]
    trim = names.index("trim")
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    well_r = CC_WHEEL_R + 0.05
    for v in bm.verts:
        for ay in axles:
            d = math.hypot(v.co.y - ay, v.co.z - CC_WHEEL_R)
            if d < well_r and abs(v.co.x) > CC_WELL_X:
                v.co.x = math.copysign(CC_WELL_X, v.co.x)
    for f in bm.faces:
        c = f.calc_center_median()
        for ay in axles:
            if math.hypot(c.y - ay, c.z - CC_WHEEL_R) < well_r + 0.01 and abs(c.x) > CC_WELL_X - 0.15:
                f.material_index = trim
    bm.to_mesh(obj.data)
    bm.free()


def smooth_surface(obj, rear_y):
    """Even out the generated mesh's lumps, then iron the licence-plate slot in the
    tail flat."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.smooth_laplacian_vert(bm, verts=bm.verts, lambda_factor=0.4, lambda_border=0.0,
                                    use_x=True, use_y=True, use_z=True, preserve_volume=True)
    # Fit y = f(x, z) to the rear-facing skin around the slot and project the slot onto it.
    bm.normal_update()

    def zone(v, pad):
        return abs(v.co.x) < 0.5 + pad and v.co.y > rear_y - 0.4 and 0.36 - pad < v.co.z < 0.88 + pad

    def terms(x, z):
        return [1, x, z, x * x, x * z, z * z]
    ring = [v for v in bm.verts if zone(v, 0.15) and not zone(v, 0.0) and v.normal.y > 0.3]
    a = np.array([terms(v.co.x, v.co.z) for v in ring])
    coef = np.linalg.lstsq(a, np.array([v.co.y for v in ring]), rcond=None)[0]
    skin_max = max(v.co.y for v in ring)
    for v in bm.verts:
        if zone(v, 0.0):
            skin = min(float(np.dot(terms(v.co.x, v.co.z), coef)), skin_max)
            if abs(v.co.y - skin) < 0.15:  # the slot, not the far side of the car
                v.co.y = skin
    bm.to_mesh(obj.data)
    bm.free()


def split_by_material(obj):
    """Split edges between different materials so decimation keeps the colour borders."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    edges = [e for e in bm.edges if len(e.link_faces) == 2
             and e.link_faces[0].material_index != e.link_faces[1].material_index]
    bmesh.ops.split_edges(bm, edges=edges)
    bm.to_mesh(obj.data)
    bm.free()


def build_cybercab():
    C.reset_scene()
    mats = C.make_materials(CYBERCAB_PALETTE)
    mats_list = list(CYBERCAB_PALETTE)
    (src,) = import_source("cybercab")
    global ROOT
    ROOT = C.empty("cybercab")

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

    smooth_surface(src, mesh_co(src)[:, 1].max())
    classify_cybercab(src, mats)
    press_wheel_wells(src, axles)
    split_by_material(src)
    decimate(src, 9800)
    weld(src, 0.006)

    b = C.Builder(mats_list)
    join_into(b, [src])
    bvh = surface_bvh_from_builder(b)
    cyber_details(b, bvh, axles)
    body = b.to_object("body", mats, parent=ROOT, smooth_angle=40)
    front_z = -axles[0]
    wheels = build_wheels(ROOT, mats_list, mats, CC_WHEEL_X, front_z, -axles[1],
                          CC_WHEEL_R, CC_TYRE_W, CC_WHEEL_R * 0.86, cap=True)
    print(f"WHEELS cybercab r={CC_WHEEL_R:.3f} x=±{CC_WHEEL_X:.3f} axles z={front_z:.3f},{-axles[1]:.3f}")
    return [body, *wheels]


def cyber_details(b, bvh, axles):
    """Butterfly-door seams, a thin white light bar on the nose and a red one at the back."""
    front_z = -axles[0]
    for sx in (1, -1):
        side = side_frame(sx * 1.5)
        inward = Vector((-sx, 0, 0))
        seam = 0.018
        # Front edge of the door, just behind the front wheel arch.
        z0 = front_z - 0.42
        decal(b, "trim", bvh, side, [(z0, 0.3), (z0 + seam, 0.3), (z0 + 0.06 + seam, 0.95), (z0 + 0.06, 0.95)],
              inward, steps=(1, 6))
        # Rear edge, leaning back as it climbs to the roof.
        decal(b, "trim", bvh, side, [(-0.24, 0.27), (-0.24 + seam, 0.27), (-0.44 + seam, 1.1), (-0.44, 1.1)],
              inward, steps=(1, 8))
    # Butterfly hinge seams along the roof.
    top = Matrix.Translation((0, 0, 3.0))
    for sx in (1, -1):
        x = sx * 0.3
        decal(b, "trim", bvh, top, [(x, 0.5), (x + 0.015, 0.5), (x + 0.015, -0.55), (x, -0.55)],
              Vector((0, 0, -1)), steps=(1, 8))
    # Light bars, ray-cast onto the nose and tail.
    front = Matrix.Translation((0, -3.0, 0)) @ FACING
    decal(b, "light_head", bvh, front, [(-0.82, 0.66), (0.82, 0.66), (0.82, 0.69), (-0.82, 0.69)],
          Vector((0, 1, 0)), steps=(12, 1))
    rear = Matrix.Translation((0, 3.0, 0)) @ FACING
    decal(b, "light_tail", bvh, rear, [(-0.88, 0.9), (0.88, 0.9), (0.88, 0.94), (-0.88, 0.94)],
          Vector((0, -1, 0)), steps=(12, 1))


# --- lineup --------------------------------------------------------------------

def build_lineup():
    """The two robotaxis nose to tail with the current cab, side on, at export scale."""
    C.reset_scene()
    root = C.empty("lineup")
    for name, y in (("wayfarer", -5.4), ("cab", 0.0), ("cybercab", 5.2)):
        bpy.ops.import_scene.gltf(filepath=str(C.MODELS_DIR / f"{name}.glb"))
        for o in bpy.context.selected_objects:
            if o.parent is None:
                o.parent = root
                o.location.y += y
            if o.type == "MESH":
                # glTF splits vertices per face; weld so the outline hulls stay closed.
                weld(o, 1e-5)
                o.data.shade_smooth()
                o.data.set_sharp_from_angle(angle=math.radians(1 if name == "cab" else 40))
    C.render_contact_sheet(root, "robotaxis-lineup", outline=0.03, size=1800, fill=1.0,
                           elevation=6.0, views=(("side", -90),))
    crop_to_content(C.RENDERS_DIR / "robotaxis-lineup.png", margin=40)


def crop_to_content(path, margin):
    img = bpy.data.images.load(str(path))
    img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    ink = np.abs(px[..., :3] - np.array(C.BG, dtype=np.float32)).sum(axis=2) > 0.02
    rows = np.where(ink.any(axis=1))[0]
    lo, hi = max(rows.min() - margin, 0), min(rows.max() + margin, h - 1)
    crop = px[lo:hi + 1]
    out = bpy.data.images.new("crop", w, crop.shape[0], alpha=False)
    out.colorspace_settings.name = "Non-Color"
    out.pixels.foreach_set(crop.ravel())
    out.filepath_raw = str(path)
    out.file_format = "PNG"
    out.save()


def main():
    car = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "wayfarer"
    if car == "lineup":
        build_lineup()
        return
    parts = {"wayfarer": build_wayfarer, "cybercab": build_cybercab}[car]()
    finish(car, ROOT, parts)


main()
