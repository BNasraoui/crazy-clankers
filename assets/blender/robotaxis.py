"""Parody robotaxis, restyled to sit next to the Clanker Cab (see docs/CREDITS.md).

    blender --background --factory-startup --python robotaxis.py -- wayfarer|cybercab|lineup|style

Run fetch_sources.py first; the raw downloads live in sources/ and are not committed.

The Sketchfab sources are only used for their shape. A low-res capsule is wrapped around
each source and every vertex is ray-cast inwards onto the outermost surface, so the
result is one clean, closed hull that keeps the car's silhouette but none of its panel
gaps, vents, handles or mirrors. The hull is then smoothed, given a little cartoon
exaggeration (shorter overhangs, more height, bigger wheels), its wheel arches are cut
with clean cylinders, and its colour blocks are cut with planes, so every colour border
is a straight crisp edge. Lights, grille, stripes and sensors are chunky solid plates
and primitives laid on top, in the cab.py style.

- wayfarer: a Waymo-style cab from a Jaguar I-PACE, with our sensor kit (roof plinth
  and lidar puck, fender and rear-corner pods) and teal stripes.
  Nodes: wayfarer > body, lidar, wheel_FL/FR/RL/RR.
- cybercab: a Cybercab-style two-seat teardrop from a fused (AI-generated) mesh, no
  mirrors. Nodes: cybercab > body, wheel_FL/FR/RL/RR.
- lineup: both side on next to the current cab.glb at the same scale.
- style: each cab in a 3/4 view next to the robotaxi from docs/art/scene-target.jpg.

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
TRI_RANGE = (4000, 8000)
TEAL = 0x2FD6BF

# Shared role palette: white or steel paint, near-black glass and trim, teal accent.
PALETTE = {
    "body": 0xF2F2EE,
    "glass": 0x1E2731,
    "trim": 0x1C1D20,
    "accent": TEAL,
    "hub": 0xA6AAAF,
    "light_head": 0xFFF4D6,
    "light_tail": 0xE0303A,
}
ROLES = list(PALETTE)


# Frames whose local XY is the game's front/back plane (x, y) and side plane (z, y).
FACING = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
SIDE = Matrix(((0, 0, 1, 0), (-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def front_frame():
    return Matrix.Translation((0, -4.0, 0)) @ FACING


def rear_frame():
    return Matrix.Translation((0, 4.0, 0)) @ FACING


def side_frame(sx):
    return Matrix.Translation((sx * 3.0, 0, 0)) @ SIDE


FORWARD, BACKWARD, DOWN = Vector((0, 1, 0)), Vector((0, -1, 0)), Vector((0, 0, -1))


def inward(sx):
    return Vector((-sx, 0, 0))


# --- source import -------------------------------------------------------------

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


def source_bvh(objs, drop=None):
    """One BVH over `objs`, minus faces whose centre satisfies drop(Vector)."""
    bm = bmesh.new()
    for o in objs:
        bm.from_mesh(o.data)
    if drop:
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if drop(f.calc_center_median())], context="FACES")
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    return bvh


# --- hull ----------------------------------------------------------------------

def shrink_hull(bvh, y0, y1, zc, slab, n_around=32, n_cap=7, n_body=26, reach=6.0):
    """Wrap a capsule around the axis from (0, y0, zc) to (0, y1, zc) and pull each of
    its vertices in along a ray onto the outermost source surface. Rings run front to
    back, each starting at the bottom; vertex j mirrors vertex n_around - j.

    slab = (z_lo, z_hi): between these heights the sides are pushed out to each ring's
    widest point, so the doors read as one flat slab like the Clanker Cab's."""
    phis = [-math.pi / 2 + 2 * math.pi * j / n_around for j in range(n_around)]
    misses = 0

    def cast(q, d):
        nonlocal misses
        hit = bvh.ray_cast(q + d * reach, -d, reach * 1.5)[0]
        if hit is None:
            misses += 1
            return q
        return hit

    def ring(q, a, ahead):
        return [cast(q, Vector((math.sin(a) * math.cos(p), ahead * math.cos(a), math.sin(a) * math.sin(p))))
                for p in phis]

    front, rear = Vector((0, y0, zc)), Vector((0, y1, zc))
    rings = [ring(front, math.pi / 2 * k / n_cap, -1) for k in range(1, n_cap + 1)]
    rings += [ring(front.lerp(rear, i / n_body), math.pi / 2, 0) for i in range(1, n_body)]
    rings += [ring(rear, math.pi / 2 * k / n_cap, 1) for k in range(n_cap, 0, -1)]
    assert misses == 0, f"{misses} hull rays missed the source"

    p = np.array([[v[:] for v in r] for r in rings])
    mirror = p[:, (-np.arange(n_around)) % n_around] * np.array([-1, 1, 1])
    p = (p + mirror) / 2
    alphas = [k / n_cap for k in range(1, n_cap + 1)]
    weights = np.array(alphas + [1.0] * (n_body - 1) + alphas[::-1]) ** 6
    z_lo, z_hi = slab
    lateral = np.abs(np.cos(phis)) > 0.55  # only rays that come in from the side
    for r, w in zip(p, weights):
        side = (r[:, 2] > z_lo) & (r[:, 2] < z_hi) & lateral
        if side.any():
            widest = np.abs(r[side, 0]).max()
            r[side, 0] += (np.sign(r[side, 0]) * widest - r[side, 0]) * w

    bm = bmesh.new()
    verts = [[bm.verts.new(c) for c in r] for r in p]
    n = n_around
    caps = [(bm.faces.new(verts[0][::-1]), verts[0], verts[1]),
            (bm.faces.new(verts[-1]), verts[-1], verts[-2])]
    for i in range(len(verts) - 1):
        for j in range(n):
            bm.faces.new((verts[i][j], verts[i][(j + 1) % n], verts[i + 1][(j + 1) % n], verts[i + 1][j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm, caps


def close_caps(bm, caps):
    """Fan each end ring into a centre vertex set on the dome the last two rings imply
    (y = y0 + k r^2, a little short of its tip), so the cap stays convex; a centre left on the ring's own plane
    dimples and shows its ink outline."""
    for face, ring, nxt in caps:
        centre = sum((v.co for v in ring), Vector()) / len(ring)
        def mean_r2_y(vs):
            return (sum((v.co.x ** 2 + (v.co.z - centre.z) ** 2) for v in vs) / len(vs),
                    sum(v.co.y for v in vs) / len(vs))
        r1, y1 = mean_r2_y(ring)
        r2, y2 = mean_r2_y(nxt)
        k = (y2 - y1) / (r2 - r1)
        res = bmesh.ops.poke(bm, faces=[face])
        res["verts"][0].co = Vector((0.0, y1 - 0.6 * k * r1, centre.z))


def taubin(bm, iterations, lam=0.5, mu=-0.53, keep=None):
    """Shrink-free Laplacian smoothing: irons out the source's panel lines and lumps."""
    bm.verts.index_update()
    co = np.array([v.co[:] for v in bm.verts])
    nbrs = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
    fixed = np.array([keep(v) for v in bm.verts]) if keep else np.zeros(len(co), bool)
    for _ in range(iterations):
        for f in (lam, mu):
            avg = np.array([co[nb].mean(axis=0) for nb in nbrs])
            step = f * (avg - co)
            step[fixed] = 0
            co = co + step
    for v, c in zip(bm.verts, co):
        v.co = c
    # Keep the two halves exact mirrors after smoothing.
    for v in bm.verts:
        if abs(v.co.x) < 1e-4:
            v.co.x = 0.0


def exaggerate(bm, axle, overhang, height, lift, nose=0.0):
    """Cartoon proportions: overhangs past the axles shrink, the body grows taller and
    sits a touch higher on its bigger wheels; `nose` raises the bonnet towards the front
    for a blunter, friendlier face."""
    for v in bm.verts:
        y = v.co.y
        if abs(y) > axle:
            v.co.y = math.copysign(axle + (abs(y) - axle) * overhang, y)
        front = min(max((-v.co.y - 0.6) / 1.0, 0.0), 1.0)
        rise = nose * front * min(max((v.co.z - 0.5) / 0.6, 0.0), 1.0)
        v.co.z = v.co.z * height + lift + rise


def body_object(bm, name):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def cut_arches(body, axles, r, inner):
    """Boolean four clean cylindrical wheel wells into the hull."""
    cutter = C.Builder(["trim"])
    for ay in axles:
        for sx in (1, -1):
            cutter.tube("trim", Vector((sx * inner, ay, r[1])), Vector((sx * 3.0, ay, r[1])), r[0], r[0], sides=28)
    cut = body_object(cutter.bm, "_arch_cutter")
    mod = body.modifiers.new("arches", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cut
    C.apply_modifiers(body)
    bpy.data.objects.remove(cut)


def colour_block(body, planes, role):
    """Cut the hull along `planes` [(point, normal)] so colour borders are crisp edges,
    then give each face the role role(centre, normal) picks for it."""
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bpy.data.objects.remove(body)
    for co, no in planes:
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges)
    bm.normal_update()
    for f in bm.faces:
        f.material_index = ROLES.index(role(f.calc_center_median(), f.normal, f))
    return bm


def in_arch(f, axles, r, inner):
    """True for faces the arch cutter left behind: the well's cylinder and inner wall."""
    lo = r[0] * math.cos(math.pi / 28) - 1e-3
    for ay in axles:
        d = [math.hypot(v.co.y - ay, v.co.z - r[1]) for v in f.verts]
        if all(lo <= x <= r[0] + 1e-3 for x in d) or (
                all(abs(abs(v.co.x) - inner) < 1e-4 for v in f.verts) and max(d) <= r[0] + 1e-3):
            return True
    return False


def plane_z(z, tilt=0.0):
    """Plane z = z + tilt * y (Blender), for belt and roof lines."""
    return Vector((0, 0, z)), Vector((0, -tilt, 1)).normalized()


def above(c, plane):
    co, no = plane
    return (c - co).dot(no) > 0


def plate(b, mat, bvh, frame, pts, direction, depth=0.03, steps=(6, 2), sink=0.01):
    """A solid plate on the surface: the quad `pts` (a, b, c, d) in the local XY of
    `frame` is ray-cast along `direction` onto `bvh` on a grid; the plate stands `depth`
    proud of the surface (along the ray) and reaches `sink` below it, so it gets its own ink outline."""
    a, b_, c, d = (Vector(p) for p in pts)
    nu, nv = steps
    direction = direction.normalized()
    top, bot = [], []
    for j in range(nv + 1):
        trow, brow = [], []
        for i in range(nu + 1):
            u, v = i / nu, j / nv
            p2 = a.lerp(b_, u).lerp(d.lerp(c, u), v)
            origin = frame @ Vector((p2.x, p2.y, 0))
            hit = bvh.ray_cast(origin, direction, 8.0)[0]
            assert hit is not None, f"plate point {p2[:]} missed the body"
            # Offset along the ray, not the hit normal: flat face normals jump between
            # faces and would crease the plate.
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
    rim_next = rim[1:] + rim[:1]
    for (j0, i0), (j1, i1) in zip(rim, rim_next):
        b.bm.faces.new((top[j0][i0], top[j1][i1], bot[j1][i1], bot[j0][i0]))
    new = [f for f in b.bm.faces if f not in before]
    bmesh.ops.recalc_face_normals(b.bm, faces=new)
    return b._assign(before, mat)


def mirrored(pts):
    return [(-x, y) for x, y in reversed(pts)]


# --- wheels ----------------------------------------------------------------------

def wheel(name, mats, root, x, y, r, width, hub_r):
    """Chunky tyre and hub disc in the cab.py style; pivot at the axle centre."""
    b = C.Builder(ROLES)
    sx = 1 if x > 0 else -1
    c = Vector((x, y, r))
    ax = Vector((sx, 0, 0))
    b.tube("trim", c - ax * width / 2, c + ax * width / 2, r, r, sides=12, bevel=0.05)
    b.tube("hub", c + ax * (width / 2 - 0.02), c + ax * (width / 2 + 0.018), hub_r, hub_r * 0.92, sides=8)
    b.tube("trim", c + ax * (width / 2 + 0.01), c + ax * (width / 2 + 0.035), hub_r * 0.34, hub_r * 0.24, sides=8)
    return b.to_object(name, mats, pivot=c, parent=root)


def build_wheels(root, mats, track_x, axles, r, width, hub_r):
    """axles = (front_y, rear_y) in Blender; FL at +X."""
    out = []
    for name, x, y in (("wheel_FL", track_x, axles[0]), ("wheel_FR", -track_x, axles[0]),
                       ("wheel_RL", track_x, axles[1]), ("wheel_RR", -track_x, axles[1])):
        out.append(wheel(name, mats, root, x, y, r, width, hub_r))
    return out


def finish(name, root, parts):
    C.report(parts)
    tris = C.triangle_count(parts)
    assert TRI_RANGE[0] <= tris <= TRI_RANGE[1], f"{name} has {tris} triangles, outside {TRI_RANGE}"
    C.export_glb(name)
    C.render_contact_sheet(root, name, outline=0.03)


# --- Wayfarer (Waymo-style, from the Jaguar I-PACE) ----------------------------

WAYFARER_LENGTH = 4.68
# Source parts that make up the outer skin; wheels, brakes, interior, mirrors and
# indicator repeaters are left out so the hull rays pass straight through them.
IPACE_SKIN = ("Body", "Body_noir", "Body_blue", "Chrome", "Plastique_noir", "Partie_noir",
              "Dessous", "Vitre", "Vitre_noir", "Vitre_toit", "Phare_vitre", "Phare_chrome",
              "Phare_plastique", "Feux_glass_red", "Feux_rouge", "Grille_calandre", "LED_blanc")
WF_AXLE = 1.5          # half wheelbase, measured
WF_WHEEL_R = 0.418 * 1.13
WF_TYRE_W = 0.34
WF_TRACK = 0.83        # tyre centre, half track
WF_ARCH_R = WF_WHEEL_R + 0.07
WF_ARCH_INNER = 0.4    # wheel wells reach in to this half width
WF_LIFT = 0.04
WF_HEIGHT = 1.1
WF_CLAD = 0.6          # black cladding below
WF_BELT = plane_z(1.22, tilt=0.04)
WF_ROOF = plane_z(1.64)
WF_COWL = -1.42        # windscreen base, Blender y
WF_TAIL_GLASS = 2.15   # no glass behind this (the spoiler lip)


def wf_role(c, n, f):
    if in_arch(f, (-WF_AXLE, WF_AXLE), (WF_ARCH_R, WF_WHEEL_R), WF_ARCH_INNER):
        return "trim"
    if c.z < WF_CLAD or n.z < -0.6:
        return "trim"
    if above(c, WF_BELT) and not above(c, WF_ROOF) and WF_COWL < c.y < WF_TAIL_GLASS:
        return "glass"
    return "body"


def build_wayfarer():
    C.reset_scene()
    mats = C.make_materials(PALETTE)
    src = import_source("ipace")
    root = C.empty("wayfarer")
    by_mat = {o.data.materials[0].name: o for o in src}

    # Scale to the real car, origin on the ground midway between the axles.
    lo, hi = bounds([by_mat["Body"]])
    s = WAYFARER_LENGTH / (hi[1] - lo[1])
    tyre = mesh_co(by_mat["Pneu"])
    axle_y = [tyre[tyre[:, 1] < 0][:, 1].mean(), tyre[tyre[:, 1] > 0][:, 1].mean()]
    transform_all(src, Matrix.Diagonal((s, s, s, 1)) @ Matrix.Translation(
        (-(lo[0] + hi[0]) / 2, -(axle_y[0] + axle_y[1]) / 2, -tyre[:, 2].min())))
    mlo, mhi = bounds([by_mat["Miroir"]])

    def mirror_housing(c):
        return (abs(c.x) > 0.88 and mlo[1] - 0.1 < c.y < mhi[1] + 0.1 and mlo[2] - 0.12 < c.z < mhi[2] + 0.1)

    bvh = source_bvh([by_mat[m] for m in IPACE_SKIN], drop=mirror_housing)
    for o in src:
        bpy.data.objects.remove(o)

    bm, caps = shrink_hull(bvh, -1.85, 1.85, 0.78, slab=(0.3, 1.0))
    taubin(bm, 40)
    taubin(bm, 60, keep=lambda v: abs(v.co.y) < 1.7)  # iron the bumpers' plate recesses
    close_caps(bm, caps)
    exaggerate(bm, WF_AXLE, overhang=0.8, height=WF_HEIGHT, lift=WF_LIFT, nose=0.08)
    body = body_object(bm, "_hull")
    cut_arches(body, (-WF_AXLE, WF_AXLE), (WF_ARCH_R, WF_WHEEL_R), WF_ARCH_INNER)
    bm = colour_block(body, [WF_BELT, WF_ROOF, plane_z(WF_CLAD),
                             (Vector((0, WF_COWL, 0)), Vector((0, 1, 0))),
                             (Vector((0, WF_TAIL_GLASS, 0)), Vector((0, 1, 0)))], wf_role)
    b = C.Builder(ROLES)
    b.bm = bm
    bvh = BVHTree.FromBMesh(bm)
    wayfarer_details(b, bvh)
    roof = bvh.ray_cast(Vector((0, WF_LIDAR_Y, 4)), DOWN, 8)[0].z
    wayfarer_sensors(b, bvh, roof)
    body = b.to_object("body", mats, parent=root, smooth_angle=45)
    lidar = build_lidar(mats, root, roof)
    wheels = build_wheels(root, mats, WF_TRACK, (-WF_AXLE, WF_AXLE), WF_WHEEL_R, WF_TYRE_W, WF_WHEEL_R * 0.6)
    return root, [body, lidar, *wheels]


def wayfarer_details(b, bvh):
    """Big readable shapes: headlights, grille, tail lights, teal swooshes."""
    f, r = front_frame(), rear_frame()
    # The game's front plane, seen from the front: +x is the car's left.
    for sx in (1, -1):
        head = [(0.46, 0.9), (0.82, 0.92), (0.8, 1.06), (0.46, 1.06)]
        pts = head if sx > 0 else mirrored(head)
        plate(b, "light_head", bvh, f, pts, FORWARD, steps=(4, 1))
        tail = [(0.42, 1.14), (0.76, 1.14), (0.76, 1.26), (0.42, 1.26)]
        plate(b, "light_tail", bvh, r, tail if sx > 0 else mirrored(tail), BACKWARD, steps=(4, 1))
    # One big dark grille, like the cab's.
    plate(b, "trim", bvh, f, [(-0.56, 0.56), (0.56, 0.56), (0.52, 0.84), (-0.52, 0.84)], FORWARD, steps=(6, 2))
    # Teal swoosh on each front door, leaning forward (side frame: x = game z forward).
    for sx in (1, -1):
        plate(b, "accent", bvh, side_frame(sx), [(0.1, 0.5), (0.44, 0.5), (0.86, 1.12), (0.52, 1.12)],
              inward(sx), steps=(4, 4))
    # Teal slash on the tailgate, the cab's motif.
    plate(b, "accent", bvh, r, [(-0.24, 0.62), (-0.44, 0.62), (-0.7, 1.04), (-0.5, 1.04)], BACKWARD, steps=(2, 3))


WF_LIDAR_Y = 0.25  # Blender y of the roof puck (behind the windscreen header)


def wayfarer_sensors(b, bvh, roof):
    """Clanker Cab-sized kit: a white roof plinth, chunky fender and rear-corner pods."""
    ly = WF_LIDAR_Y
    b.box("body", (0.86, 0.92, 0.2), Vector((0, ly, roof + 0.06)), bevel=0.04, seg=2, taper=(0.82, 0.82))
    for sx in (1, -1):
        # Fender pods on the front wings, ahead of the A-pillars.
        fx, fy = sx * 0.74, -1.25
        fz = bvh.ray_cast(Vector((fx, fy, 4)), DOWN, 8)[0].z
        b.box("trim", (0.18, 0.3, 0.2), Vector((fx, fy, fz + 0.07)), bevel=0.04, seg=2, taper=(0.85, 0.85))
        b.tube("trim", Vector((fx, fy, fz + 0.16)), Vector((fx, fy, fz + 0.26)), 0.085, 0.075, sides=10)
        b.tube("accent", Vector((fx, fy, fz + 0.2)), Vector((fx, fy, fz + 0.23)), 0.09, 0.09, sides=10)
        # Rear-corner pods, sunk into the bumper corners.
        hit = bvh.ray_cast(Vector((sx * 0.8, 4.0, 0.82)), BACKWARD, 8)[0]
        b.box("trim", (0.16, 0.2, 0.22), hit + Vector((0, -0.04, 0)), bevel=0.04, seg=2)


def build_lidar(mats, root, roof):
    """The Clanker Cab's puck: pivot on its axis so it spins about the game's Y."""
    y, z0 = WF_LIDAR_Y, roof + 0.16
    b = C.Builder(ROLES)
    b.tube("trim", Vector((0, y, z0)), Vector((0, y, z0 + 0.42)), 0.3, 0.27, sides=14, bevel=0.02)
    b.tube("accent", Vector((0, y, z0 + 0.14)), Vector((0, y, z0 + 0.22)), 0.315, 0.31, sides=14)
    b.tube("trim", Vector((0, y, z0 + 0.42)), Vector((0, y, z0 + 0.48)), 0.21, 0.12, sides=14)
    return b.to_object("lidar", mats, pivot=Vector((0, y, z0 + 0.24)), parent=root)


# --- Cyber Cab (Cybercab-style, from a fused AI mesh) --------------------------

CYBERCAB_LENGTH = 4.4
CC_AXLE = 1.27          # half wheelbase, measured off the baked-in wheels
CC_WHEEL_R = 0.37 * 1.13
CC_TYRE_W = 0.3
CC_TRACK = 0.82
CC_ARCH_R = CC_WHEEL_R + 0.06
CC_ARCH_INNER = 0.4
CC_LIFT = 0.04
CC_HEIGHT = 1.06
CC_CLAD = 0.46
CC_BELT = plane_z(1.0, tilt=0.07)
CC_ROOF = plane_z(1.5)
CC_COWL = -1.12
CC_CPILLAR = (Vector((0, 0.75, 1.4)), Vector((0, 0.62, 0.78)).normalized())  # glass ahead of it
CC_STEEL = 0xC4C9CE


def cc_role(c, n, f):
    if in_arch(f, (-CC_AXLE, CC_AXLE), (CC_ARCH_R, CC_WHEEL_R), CC_ARCH_INNER):
        return "trim"
    if c.z < CC_CLAD or n.z < -0.6:
        return "trim"
    if above(c, CC_BELT) and not above(c, CC_ROOF) and c.y > CC_COWL and not above(c, CC_CPILLAR):
        return "glass"
    return "body"


def build_cybercab():
    C.reset_scene()
    mats = C.make_materials({**PALETTE, "body": CC_STEEL})
    (src,) = import_source("cybercab")
    root = C.empty("cybercab")

    lo, hi = bounds([src])
    s = CYBERCAB_LENGTH / (hi[1] - lo[1])
    transform_all([src], Matrix.Diagonal((s, s, s, 1)) @ Matrix.Translation(
        (-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])))
    # Axles from the tyre contact patches (the lowest vertices, front and back).
    co = mesh_co(src)
    low = co[co[:, 2] < 0.02]
    mid = (low[low[:, 1] < 0][:, 1].mean() + low[low[:, 1] > 0][:, 1].mean()) / 2
    transform_all([src], Matrix.Translation((0, -mid, 0)))

    def mirror(c):
        return abs(c.x) > 0.92 and -0.9 < c.y < -0.5 and 0.86 < c.z < 1.16

    bvh = source_bvh([src], drop=mirror)
    bpy.data.objects.remove(src)

    bm, caps = shrink_hull(bvh, -1.55, 1.6, 0.52, slab=(0.2, 0.86))
    taubin(bm, 40)
    taubin(bm, 60, keep=lambda v: abs(v.co.y) < 1.45)
    close_caps(bm, caps)
    exaggerate(bm, CC_AXLE, overhang=0.82, height=CC_HEIGHT, lift=CC_LIFT)
    body = body_object(bm, "_hull")
    cut_arches(body, (-CC_AXLE, CC_AXLE), (CC_ARCH_R, CC_WHEEL_R), CC_ARCH_INNER)
    bm = colour_block(body, [CC_BELT, CC_ROOF, plane_z(CC_CLAD), CC_CPILLAR,
                             (Vector((0, CC_COWL, 0)), Vector((0, 1, 0)))], cc_role)
    b = C.Builder(ROLES)
    b.bm = bm
    bvh = BVHTree.FromBMesh(bm)
    cybercab_details(b, bvh)
    body = b.to_object("body", mats, parent=root, smooth_angle=45)
    wheels = build_wheels(root, mats, CC_TRACK, (-CC_AXLE, CC_AXLE), CC_WHEEL_R, CC_TYRE_W, CC_WHEEL_R * 0.78)
    return root, [body, *wheels]


def cybercab_details(b, bvh):
    """Full-width light bars front and back, and the teal accent along the doors."""
    plate(b, "light_head", bvh, front_frame(), [(-0.8, 0.72), (0.8, 0.72), (0.8, 0.8), (-0.8, 0.8)],
          FORWARD, steps=(12, 1))
    plate(b, "light_tail", bvh, rear_frame(), [(-0.74, 0.98), (0.74, 0.98), (0.74, 1.07), (-0.74, 1.07)],
          BACKWARD, steps=(12, 1))
    for sx in (1, -1):
        plate(b, "accent", bvh, side_frame(sx), [(0.48, 0.47), (0.86, 0.47), (0.46, 1.0), (0.08, 1.0)],
              inward(sx), steps=(4, 4))


# --- lineup and style sheet ------------------------------------------------------

def import_cab(name, root, offset):
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
            o.data.set_sharp_from_angle(angle=math.radians(1 if name == "cab" else 45))


def build_lineup():
    """The two robotaxis nose to tail with the current cab, side on, at export scale."""
    C.reset_scene()
    root = C.empty("lineup")
    for name, y in (("wayfarer", -5.2), ("cab", 0.0), ("cybercab", 5.0)):
        import_cab(name, root, y)
    C.render_contact_sheet(root, "robotaxis-lineup", outline=0.03, size=1800, fill=1.0,
                           elevation=6.0, views=(("side", -90),))
    crop_to_content(C.RENDERS_DIR / "robotaxis-lineup.png", margin=40)


# The robotaxi in docs/art/scene-target.jpg (x0, y0, x1, y1 in pixels).
CONCEPT = Path(__file__).resolve().parents[2] / "docs" / "art" / "scene-target.jpg"
CONCEPT_CROP = (752, 205, 1218, 612)


def build_style():
    """Concept-art robotaxi, then each cab from a similar front 3/4 view."""
    tiles = []
    for name in ("wayfarer", "cybercab", "cab"):
        C.reset_scene()
        root = C.empty("style")
        import_cab(name, root, 0.0)
        C.render_contact_sheet(root, f".style-{name}", outline=0.03, size=700, fill=0.85,
                               elevation=16.0, views=(("3/4 front", 35),))
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
    ink = np.abs(px - np.array(C.BG, dtype=np.float32)).sum(axis=2) > 0.02
    rows = np.where(ink.any(axis=1))[0]
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
