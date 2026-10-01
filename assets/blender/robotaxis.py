"""Parody robotaxis, built hard-surface to sit next to the Clanker Cab (see docs/CREDITS.md).

    blender --background --factory-startup --python robotaxis.py -- wayfarer|cybercab|lineup|style|silhouettes|trace

Each body is built like cab.py, from flat planes: a side profile polygon (traced from the
Sketchfab source, see `trace`, then given toy proportions: shorter overhangs, more height,
bigger wheels) is extruded across the car and cut by a handful of planes that set the
front section (tuck-under, flat side, shoulder crease, tumblehome, roof edge), the plan
(nose and tail corners) and the corner facets around the lights. Every edge between
two planes gets a one-segment chamfer and the body is flat shaded, so it reads as hard
panels with crisp creases. Wheel arches are octagonal cuts with a lip; colour blocks are
cut along planes, and the chamfers framing the glass stay paint, so the glass reads as
real windows. Seams inside the silhouette (door cuts, hood and bumper lines, tailgate)
get thin dark ink strips laid on the panels, since the game's outline only draws the
silhouette. Lights, grille, stripes and sensors are chunky plates and primitives on top.

- wayfarer: a Waymo-style cab with the Jaguar I-PACE's profile, our sensor kit (roof
  plinth and lidar puck, fender and rear-corner pods) and teal stripes.
  Nodes: wayfarer > body, lidar, wheel_FL/FR/RL/RR.
- cybercab: a Cybercab-style two-seat teardrop, no mirrors.
  Nodes: cybercab > body, wheel_FL/FR/RL/RR.
- lineup: both side on next to the current cab.glb at the same scale.
- style: each cab in a 3/4 view next to the robotaxi from docs/art/scene-target.jpg.
- silhouettes: each car in black next to its previous (soft) version from sources/prev/.
- trace: print the source measurements the profiles and sections were traced from
  (needs fetch_sources.py).

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


# Frames whose local XY is the game's front/back plane (x, y), side plane (z, y) and
# Blender's plan (x, y), for laying plates onto the body.
FACING = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
SIDE = Matrix(((0, 0, 1, 0), (-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def front_frame():
    return Matrix.Translation((0, -4.0, 0)) @ FACING


def rear_frame():
    return Matrix.Translation((0, 4.0, 0)) @ FACING


def side_frame(sx):
    return Matrix.Translation((sx * 3.0, 0, 0)) @ SIDE


def top_frame():
    return Matrix.Translation((0, 0, 4.0))


FORWARD, BACKWARD, DOWN = Vector((0, 1, 0)), Vector((0, -1, 0)), Vector((0, 0, -1))


def inward(sx):
    return Vector((-sx, 0, 0))


def mirrored(pts):
    return [(-x, y) for x, y in reversed(pts)]


# --- sources (only for `trace`) ----------------------------------------------------

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


WAYFARER_LENGTH = 4.68
IPACE_SKIN = ("Body", "Body_noir", "Body_blue", "Chrome", "Plastique_noir", "Partie_noir",
              "Dessous", "Vitre", "Vitre_noir", "Vitre_toit", "Phare_vitre", "Phare_chrome",
              "Phare_plastique", "Feux_glass_red", "Feux_rouge", "Grille_calandre", "LED_blanc")
CYBERCAB_LENGTH = 4.4


def ipace_bvh():
    """The I-PACE's outer skin at real size, origin on the ground midway between the axles."""
    src = import_source("ipace")
    by_mat = {o.data.materials[0].name: o for o in src}
    lo, hi = bounds([by_mat["Body"]])
    s = WAYFARER_LENGTH / (hi[1] - lo[1])
    tyre = mesh_co(by_mat["Pneu"])
    axle_y = [tyre[tyre[:, 1] < 0][:, 1].mean(), tyre[tyre[:, 1] > 0][:, 1].mean()]
    transform_all(src, Matrix.Diagonal((s, s, s, 1)) @ Matrix.Translation(
        (-(lo[0] + hi[0]) / 2, -(axle_y[0] + axle_y[1]) / 2, -tyre[:, 2].min())))
    mlo, mhi = bounds([by_mat["Miroir"]])

    def mirror_housing(c):
        return abs(c.x) > 0.88 and mlo[1] - 0.1 < c.y < mhi[1] + 0.1 and mlo[2] - 0.12 < c.z < mhi[2] + 0.1

    return source_bvh([by_mat[m] for m in IPACE_SKIN], drop=mirror_housing)


def cybercab_bvh():
    (src,) = import_source("cybercab")
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

    return source_bvh([src], drop=mirror)


def trace():
    """Print each source's roof line and half widths per station, and its nose and tail
    per height: the numbers the profiles and sections below were read from (before the
    toy proportions: overhangs x0.8, heights x1.1 + 0.04)."""
    for name, make in (("ipace", ipace_bvh), ("cybercab", cybercab_bvh)):
        C.reset_scene()
        bvh = make()
        print(f"== {name}: y, roof z, half width at z = 0.3 .. 1.5")
        for y in np.arange(-2.4, 2.45, 0.1):
            top = bvh.ray_cast(Vector((0, y, 5)), DOWN, 10)[0]
            if top is None:
                continue
            ws = []
            for z in np.arange(0.3, 1.55, 0.2):
                hit = bvh.ray_cast(Vector((3, y, z)), Vector((-1, 0, 0)), 6)[0]
                ws.append(f"{hit.x:.2f}" if hit else "  - ")
            print(f"  y={y:5.2f} roof={top.z:.2f} w=[{' '.join(ws)}]")
        for z in np.arange(0.3, 1.65, 0.1):
            f = bvh.ray_cast(Vector((0, -4, z)), FORWARD, 8)[0]
            r = bvh.ray_cast(Vector((0, 4, z)), BACKWARD, 8)[0]
            print(f"  z={z:.1f} nose={f.y if f else float('nan'):.2f} tail={r.y if r else float('nan'):.2f}")


# --- hard-surface body ---------------------------------------------------------------

INSIDE = Vector((0, 0, 0.8))  # a point inside every body, to orient the cutting planes


def plane3(a, b, c):
    """The plane through points a, b, c, its normal facing away from INSIDE."""
    a, b, c = Vector(a), Vector(b), Vector(c)
    n = (b - a).cross(c - a).normalized()
    if (INSIDE - a).dot(n) > 0:
        n = -n
    return a, n


def section(x0, z0, x1, z1, rise=0.0):
    """A cut along the whole car through the front-section edge (x0, z0)-(x1, z1) on the
    left side (mirrored to the right); `rise` tilts it up towards the back, per metre."""
    return plane3((x0, 0, z0), (x1, 0, z1), (x0, 1, z0 + rise))


def plan(x0, y0, x1, y1):
    """A vertical cut through the plan edge (x0, y0)-(x1, y1), mirrored."""
    return plane3((x0, y0, 0), (x1, y1, 0), (x0, y0, 1))


def clip(bm, co, no):
    """Keep the part of bm behind the plane and close the cut with a flat face."""
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=True, dist=1e-6)
    edges = [e for e in bm.edges if e.is_boundary]
    if edges:
        bmesh.ops.holes_fill(bm, edges=edges, sides=0)


def hull(profile, cuts, chamfer, crease=10.0):
    """Extrude the side `profile` [(y, z)] across the car, clip it by each of `cuts`
    (and its mirror) and chamfer every crease sharper than `crease` degrees with one
    segment. Returns the bmesh and its int face layer marking the chamfers."""
    b = C.Builder(ROLES)
    b.prism("body", [(-y, z) for y, z in profile], 2.6, SIDE)
    bm = b.bm
    for co, no in cuts:
        clip(bm, co, no)
        if abs(no.x) > 1e-6:
            clip(bm, Vector((-co.x, co.y, co.z)), Vector((-no.x, no.y, no.z)))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    layer = bm.faces.layers.int.new("chamfer")
    bm.edges.index_update()
    edges = sorted((e for e in bm.edges if not e.is_boundary and e.calc_face_angle(0) > math.radians(crease)),
                   key=lambda e: e.index)
    res = bmesh.ops.bevel(bm, geom=edges, offset=chamfer, offset_type="OFFSET", segments=1,
                          profile=0.5, affect="EDGES", clamp_overlap=True)
    for f in res["faces"]:
        f[layer] = 1
    return bm, layer


def colour_block(bm, layer, planes, role):
    """Cut along `planes` [(point, normal)] so colour borders are crisp edges, then give
    each face the role role(centre, normal, is_chamfer) picks for it."""
    for co, no in planes:
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges)
    bm.normal_update()
    for f in bm.faces:
        f.material_index = ROLES.index(role(f.calc_center_median(), f.normal, f[layer] == 1))


def on_facet(c, n, plane):
    """True for a face lying on `plane` or its mirror."""
    co, no = plane
    m = Vector((math.copysign(1, c.x) * math.copysign(1, co.x), 1, 1))
    co, no = co * m, no * m
    return n.dot(no) > 0.995 and abs((c - co).dot(no)) < 1e-3


def facet_frame(plane, centre, up=Vector((0, 0, 1))):
    """A frame on `plane` at `centre`, a metre out along its normal: local x runs level
    across the facet, local y up it, so plates can be laid on it casting along -normal."""
    no = plane[1]
    co = Vector(centre) - no * (Vector(centre) - plane[0]).dot(no)
    u = up.cross(no).normalized()
    v = no.cross(u)
    basis = Matrix((u, v, no)).transposed().to_4x4()
    return Matrix.Translation(co + no) @ basis


def mirror_plane(plane):
    co, no = plane
    return Vector((-co.x, co.y, co.z)), Vector((-no.x, no.y, no.z))


def body_object(bm, name, mats):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for n in ROLES:
        me.materials.append(mats[n])
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def arch_outline(cy, cz, r, bottom):
    """Octagonal arch (flat top, flat sides) of circumradius r about (cy, cz), in the
    side plane (y, z), run from the bottom at the front round to the bottom at the back."""
    k = math.cos(math.pi / 8)
    pts = [(cy - r * k, bottom)]
    for i in range(4):
        a = math.pi * (7 - 2 * i) / 8
        pts.append((cy + r * math.cos(a), cz + r * math.sin(a)))
    return pts + [(cy + r * k, bottom)]


def cut_arches(bm, mats, axles, r, cz, inner):
    """Boolean four octagonal wheel wells into the body; the wells come out as trim."""
    body = body_object(bm, "_hull", mats)
    cutter = C.Builder(ROLES)
    for ay in axles:
        for sx in (1, -1):
            cutter.tube("trim", Vector((sx * inner, ay, cz)), Vector((sx * 3.0, ay, cz)), r, r,
                        sides=8, spin=math.pi / 8)
    cut = body_object(cutter.bm, "_arch_cutter", mats)
    mod = body.modifiers.new("arches", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.material_mode = "TRANSFER"
    mod.object = cut
    C.apply_modifiers(body)
    bpy.data.objects.remove(cut)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bpy.data.objects.remove(body)
    return bm


def arch_lips(b, mat, axles, r, cz, bottom, width, x_in, x_out):
    """A flat octagonal lip round each arch, from x_in to x_out (proud of the side)."""
    for ay in axles:
        outer = arch_outline(-ay, cz, r + width, bottom)
        inner = arch_outline(-ay, cz, r, bottom)
        ring = outer + inner[::-1]
        for sx in (1, -1):
            x0, x1 = sx * x_in, sx * x_out
            frame = Matrix.Translation(((x0 + x1) / 2, 0, 0)) @ SIDE
            b.prism(mat, ring, abs(x1 - x0), frame)


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


def ink(b, bvh, frame, pts, direction, width=0.024, depth=0.008, step=0.06):
    """A thin dark seam line along the polyline `pts` in the frame's local XY, laid on
    the body like a plate, each segment a little longer so the joints overlap."""
    for p0, p1 in zip(pts, pts[1:]):
        p0, p1 = Vector(p0), Vector(p1)
        d = (p1 - p0).normalized()
        p0, p1 = p0 - d * width / 2, p1 + d * width / 2
        n = Vector((-d.y, d.x)) * width / 2
        steps = (max(1, math.ceil((p1 - p0).length / step)), 1)
        plate(b, "trim", bvh, frame, [p0 - n, p1 - n, p1 + n, p0 + n], direction,
              depth=depth, steps=steps, sink=0.012)


# --- wheels ----------------------------------------------------------------------

def wheel(name, mats, root, x, y, r, width, rim_r):
    """Chamfered tyre, flat rim face with five dark spoke gaps and a cap; pivot at the
    axle centre."""
    b = C.Builder(ROLES)
    sx = 1 if x > 0 else -1
    c = Vector((x, y, r))
    ax = Vector((sx, 0, 0))
    b.tube("trim", c - ax * width / 2, c + ax * width / 2, r, r, sides=18, bevel=0.05)
    face = width / 2 + 0.012
    b.tube("hub", c + ax * (width / 2 - 0.03), c + ax * face, rim_r, rim_r * 0.94, sides=10, bevel=0.012)
    # Spoke gaps: dark trapezoids between five spokes, on the rim face.
    frame = Matrix.Translation(c + ax * (face + 0.004)) @ Matrix(((0, 0, sx, 0), (-sx, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    for i in range(5):
        a0 = 2 * math.pi * i / 5 + 0.3
        a1 = a0 + 2 * math.pi / 5 - 0.42
        r0, r1 = rim_r * 0.36, rim_r * 0.8
        quad = [(r0 * math.cos(a0 + 0.12), r0 * math.sin(a0 + 0.12)), (r1 * math.cos(a0), r1 * math.sin(a0)),
                (r1 * math.cos(a1), r1 * math.sin(a1)), (r0 * math.cos(a1 - 0.12), r0 * math.sin(a1 - 0.12))]
        b.prism("trim", quad, 0.012, frame)
    b.tube("trim", c + ax * (face - 0.004), c + ax * (face + 0.022), rim_r * 0.24, rim_r * 0.18, sides=8)
    return b.to_object(name, mats, pivot=c, parent=root)


def build_wheels(root, mats, track_x, axles, r, width, rim_r):
    """axles = (front_y, rear_y) in Blender; FL at +X."""
    out = []
    for name, x, y in (("wheel_FL", track_x, axles[0]), ("wheel_FR", -track_x, axles[0]),
                       ("wheel_RL", track_x, axles[1]), ("wheel_RR", -track_x, axles[1])):
        out.append(wheel(name, mats, root, x, y, r, width, rim_r))
    return out


def finish(name, root, parts):
    C.report(parts)
    tris = C.triangle_count(parts)
    assert TRI_RANGE[0] <= tris <= TRI_RANGE[1], f"{name} has {tris} triangles, outside {TRI_RANGE}"
    C.export_glb(name)
    C.render_contact_sheet(root, name, outline=0.03)


# --- Wayfarer (Waymo-style, the Jaguar I-PACE's profile) ------------------------

WF_AXLE = 1.5          # half wheelbase, measured
WF_WHEEL_R = 0.418 * 1.13
WF_TYRE_W = 0.34
WF_TRACK = 0.83        # tyre centre, half track
WF_ARCH_R = WF_WHEEL_R + 0.09
WF_ARCH_INNER = 0.45   # wheel wells reach in to this half width
WF_SILL = 0.3
# Side profile, front bumper chin round over the roof to the rear bumper (Blender y, z):
# a short hood rising into a steep, fast windscreen, a coupe roof sloping into a
# cut-off tail. Traced from the I-PACE (hood 1.11 at the cowl, roof 1.61, tail 1.21).
WF_PROFILE = [(-2.12, WF_SILL), (-2.2, 0.44), (-2.2, 0.94), (-2.07, 1.07), (-1.42, 1.23),
              (-0.5, 1.72), (0.62, 1.8), (1.5, 1.68), (2.0, 1.44), (2.14, 1.32),
              (2.17, 0.46), (2.1, WF_SILL)]
WF_BELT = 1.26         # shoulder crease at the front; it rises towards the back
# The corner facets that carry the head and tail lights.
WF_HEAD_FACET = plane3((0.95, -1.5, 1.24), (0.95, -2.0, 0.78), (0.35, -2.2, 1.04))
WF_TAIL_FACET = plane3((0.89, 1.88, 1.38), (0.95, 2.06, 1.06), (0.62, 2.15, 1.3))
WF_RISE = 0.025
WF_CUTS = [
    section(0.84, WF_SILL, 0.95, 0.56),                        # tuck-under
    section(0.95, 0.56, 0.95, 1.12),                           # flat door sides
    section(0.95, 1.12, 0.89, WF_BELT, rise=WF_RISE),          # shoulder
    section(0.89, WF_BELT, 0.69, 1.74, rise=WF_RISE),          # tumblehome
    section(0.69, 1.74, 0.5, 1.86),                            # roof edge
    plan(0.95, -1.88, 0.7, -2.2),                              # nose corners
    plan(0.95, 1.92, 0.74, 2.17),                              # tail corners
    WF_HEAD_FACET,
    WF_TAIL_FACET,
]
WF_CLAD = 0.58         # black cladding below, on the sides
WF_BUMPER = 0.4        # and on the bumper faces
WF_COWL = -1.42        # windscreen base, Blender y
WF_B = 0.1             # B-pillar centre, Blender y at the ground
WF_B_LEAN = 0.12       # it leans back this much per metre up
WF_C = ((1.62, 1.3), (1.3, 1.76))   # the side glass ends ahead of this line (y, z)


def wf_planes():
    c0, c1 = WF_C
    return [
        (Vector((0, 0, WF_CLAD)), Vector((0, 0, 1))),
        (Vector((0, 0, WF_BUMPER)), Vector((0, 0, 1))),
        (Vector((0, WF_B - 0.07, 0)), Vector((0, 1, -WF_B_LEAN)).normalized()),
        (Vector((0, WF_B + 0.07, 0)), Vector((0, 1, -WF_B_LEAN)).normalized()),
        plane3((0, *c0), (0, *c1), (1, *c0)),
    ]


def wf_role(c, n, chamfer):
    if on_facet(c, n, WF_HEAD_FACET):
        return "trim"
    if on_facet(c, n, WF_TAIL_FACET):
        return "light_tail"
    if c.z < (WF_BUMPER if abs(n.y) > 0.9 else WF_CLAD) or n.z < -0.6:
        return "trim"
    if chamfer or n.z > 0.92:
        return "body"
    belt = WF_BELT + WF_RISE * c.y
    if n.y < -0.25 and n.z > 0.3 and c.z > 1.24 and c.y < 0:
        return "glass"                                         # windscreen
    if n.y > 0.3 and n.z > 0.3 and c.y > 1.4 and abs(n.x) < 0.4:
        return "glass"                                         # rear window
    c0, c1 = WF_C
    ahead = (c.y - c0[0]) * (c1[1] - c0[1]) - (c.z - c0[1]) * (c1[0] - c0[0]) < 0
    if abs(n.x) > 0.5 and c.z > belt + 0.02 and WF_COWL < c.y and ahead and abs(c.y - WF_B_LEAN * c.z - WF_B) > 0.07:
        return "glass"                                         # side windows
    return "body"


def build_wayfarer():
    C.reset_scene()
    mats = C.make_materials(PALETTE)
    root = C.empty("wayfarer")
    bm, layer = hull(WF_PROFILE, WF_CUTS, chamfer=0.045)
    colour_block(bm, layer, wf_planes(), wf_role)
    bm = cut_arches(bm, mats, (-WF_AXLE, WF_AXLE), WF_ARCH_R, WF_WHEEL_R, WF_ARCH_INNER)
    b = C.Builder(ROLES)
    b.bm = bm
    bvh = BVHTree.FromBMesh(bm)
    arch_lips(b, "trim", (-WF_AXLE, WF_AXLE), WF_ARCH_R, WF_WHEEL_R, WF_SILL + 0.06, 0.08, 0.8, 0.985)
    wayfarer_details(b, bvh)
    wayfarer_seams(b, bvh)
    roof = bvh.ray_cast(Vector((0, WF_LIDAR_Y, 4)), DOWN, 8)[0].z
    wayfarer_sensors(b, bvh, roof)
    body = b.to_object("body", mats, parent=root)
    lidar = build_lidar(mats, root, roof)
    wheels = build_wheels(root, mats, WF_TRACK, (-WF_AXLE, WF_AXLE), WF_WHEEL_R, WF_TYRE_W, WF_WHEEL_R * 0.62)
    return root, [body, lidar, *wheels]


def wayfarer_details(b, bvh):
    """Big readable shapes: angular headlights, grille, tail lights, teal swooshes."""
    f, r = front_frame(), rear_frame()
    # The game's front plane, seen from the front: +x is the car's left.
    # Headlights: a slim angular lamp on each black corner facet.
    for sx in (1, -1):
        plane = WF_HEAD_FACET if sx > 0 else mirror_plane(WF_HEAD_FACET)
        fr = facet_frame(plane, (sx * 0.74, -1.92, 1.0))
        lamp = [(-0.24, -0.02), (0.16, -0.12), (0.24, 0.0), (-0.18, 0.07)]
        if sx < 0:
            lamp = mirrored(lamp)
        plate(b, "light_head", bvh, fr, lamp, -plane[1], depth=0.02, steps=(3, 1))
    # One big dark grille with a cut-off top corner each side.
    plate(b, "trim", bvh, f, [(-0.6, 0.5), (0.6, 0.5), (0.56, 0.78), (-0.56, 0.78)], FORWARD, steps=(6, 2))
    # Teal swoosh on each front door, leaning forward (side frame: x = game z forward).
    for sx in (1, -1):
        plate(b, "accent", bvh, side_frame(sx), [(0.12, 0.6), (0.44, 0.6), (0.86, 1.18), (0.54, 1.18)],
              inward(sx), steps=(4, 4))
    # Teal slash on the tailgate, the cab's motif.
    plate(b, "accent", bvh, r, [(-0.14, 0.8), (-0.34, 0.8), (-0.56, 1.16), (-0.36, 1.16)], BACKWARD, steps=(2, 3))


def wayfarer_seams(b, bvh):
    """Ink lines on the panel seams: doors, hood, bumpers, tailgate."""
    for sx in (1, -1):
        s = side_frame(sx)
        # Side frame x = forward (= -Blender y).
        ink(b, bvh, s, [(0.8, WF_CLAD + 0.02), (0.82, 1.22)], inward(sx))                  # front door, front
        ink(b, bvh, s, [(-WF_B - WF_B_LEAN * 0.6, WF_CLAD + 0.02), (-WF_B - WF_B_LEAN * 1.26, 1.26)],
            inward(sx))                                                                     # B-pillar door cut
        ink(b, bvh, s, [(-0.82, WF_CLAD + 0.02), (-0.82, 1.0), (-1.1, 1.27)], inward(sx))   # rear door, rear
    # Hood shut lines along the fenders and across the nose.
    top = top_frame()
    for sx in (1, -1):
        ink(b, bvh, top, [(sx * 0.74, WF_COWL + 0.04), (sx * 0.7, -2.0)], DOWN)
    f = front_frame()
    ink(b, bvh, f, [(-0.44, 1.04), (0.44, 1.04)], FORWARD)                                 # hood front
    r = rear_frame()
    ink(b, bvh, r, [(-0.66, 0.74), (-0.66, 1.34)], BACKWARD)                               # tailgate
    ink(b, bvh, r, [(0.66, 0.74), (0.66, 1.34)], BACKWARD)
    ink(b, bvh, r, [(-0.66, 0.74), (0.66, 0.74)], BACKWARD)


WF_LIDAR_Y = 0.25  # Blender y of the roof puck (behind the windscreen header)


def wayfarer_sensors(b, bvh, roof):
    """Clanker Cab-sized kit: a white roof plinth, chunky fender and rear-corner pods."""
    ly = WF_LIDAR_Y
    b.box("body", (0.86, 0.92, 0.2), Vector((0, ly, roof + 0.06)), bevel=0.04, seg=1, taper=(0.82, 0.82))
    for sx in (1, -1):
        # Fender pods on the front wings, ahead of the A-pillars.
        fx, fy = sx * 0.74, -1.25
        fz = bvh.ray_cast(Vector((fx, fy, 4)), DOWN, 8)[0].z
        b.box("trim", (0.18, 0.3, 0.2), Vector((fx, fy, fz + 0.07)), bevel=0.03, seg=1, taper=(0.85, 0.85))
        b.tube("trim", Vector((fx, fy, fz + 0.16)), Vector((fx, fy, fz + 0.26)), 0.085, 0.075, sides=10)
        b.tube("accent", Vector((fx, fy, fz + 0.2)), Vector((fx, fy, fz + 0.23)), 0.09, 0.09, sides=10)
        # Rear-corner pods, sunk into the bumper corners.
        hit = bvh.ray_cast(Vector((sx * 0.8, 4.0, 0.84)), BACKWARD, 8)[0]
        b.box("trim", (0.16, 0.2, 0.22), hit + Vector((0, -0.04, 0)), bevel=0.03, seg=1)


def build_lidar(mats, root, roof):
    """The Clanker Cab's puck: pivot on its axis so it spins about the game's Y."""
    y, z0 = WF_LIDAR_Y, roof + 0.16
    b = C.Builder(ROLES)
    b.tube("trim", Vector((0, y, z0)), Vector((0, y, z0 + 0.42)), 0.3, 0.27, sides=14, bevel=0.02)
    b.tube("accent", Vector((0, y, z0 + 0.14)), Vector((0, y, z0 + 0.22)), 0.315, 0.31, sides=14)
    b.tube("trim", Vector((0, y, z0 + 0.42)), Vector((0, y, z0 + 0.48)), 0.21, 0.12, sides=14)
    return b.to_object("lidar", mats, pivot=Vector((0, y, z0 + 0.24)), parent=root)


# --- Cyber Cab (Cybercab-style teardrop) -----------------------------------------

CC_AXLE = 1.27          # half wheelbase, measured off the source's baked-in wheels
CC_WHEEL_R = 0.37 * 1.13
CC_TYRE_W = 0.3
CC_TRACK = 0.82
CC_ARCH_R = CC_WHEEL_R + 0.08
CC_ARCH_INNER = 0.45
CC_SILL = 0.26
# Teardrop side profile, faceted: flat nose face, hood, windscreen, a long roof that
# sweeps down into a short cut-off tail. Traced from the source (hood 0.95, roof 1.51,
# tail 1.03).
CC_PROFILE = [(-1.92, CC_SILL), (-1.99, 0.4), (-1.99, 0.78), (-1.88, 0.88), (-1.06, 1.06),
              (-0.36, 1.53), (0.22, 1.63), (1.0, 1.53), (1.6, 1.3), (1.95, 1.13), (2.03, 1.02),
              (2.03, 0.42), (1.95, CC_SILL)]
CC_BELT = 1.02
CC_RISE = 0.05
CC_CUTS = [
    section(0.84, CC_SILL, 0.94, 0.46),
    section(0.94, 0.46, 0.94, 0.9, rise=CC_RISE),
    section(0.94, 0.9, 0.82, CC_BELT, rise=CC_RISE),           # the sharp shoulder
    section(0.82, CC_BELT, 0.66, 1.52, rise=CC_RISE),
    section(0.66, 1.52, 0.46, 1.66),
    plan(0.94, -1.45, 0.8, -1.86),                             # two facets round the nose
    plan(0.86, -1.72, 0.52, -1.99),
    plan(0.94, 1.36, 0.72, 2.03),                              # the teardrop tail
    plane3((0.66, 0.9, 1.53), (0.66, 1.5, 1.32), (0.4, 1.8, 1.25)),  # greenhouse tapers to the tail
]
CC_CLAD = 0.44
CC_COWL = -1.06
CC_STEEL = 0xC4C9CE
CC_C = ((1.5, 1.08), (1.08, 1.5))   # side glass ends ahead of this line (y, z)


def cc_planes():
    c0, c1 = CC_C
    return [(Vector((0, 0, CC_CLAD)), Vector((0, 0, 1))), plane3((0, *c0), (0, *c1), (1, *c0))]


def cc_role(c, n, chamfer):
    if c.z < CC_CLAD or n.z < -0.6:
        return "trim"
    if chamfer or n.z > 0.95:
        return "body"
    belt = CC_BELT + CC_RISE * c.y
    if n.y < -0.25 and n.z > 0.3 and c.z > 1.08 and c.y < 0:
        return "glass"                                         # windscreen
    c0, c1 = CC_C
    ahead = (c.y - c0[0]) * (c1[1] - c0[1]) - (c.z - c0[1]) * (c1[0] - c0[0]) < 0
    if abs(n.x) > 0.45 and c.z > belt + 0.02 and CC_COWL < c.y and ahead:
        return "glass"                                         # side glass
    if n.y > 0.25 and 0.3 < n.z < 0.95 and 1.0 < c.y < 1.75 and abs(n.x) < 0.45:
        return "glass"                                         # rear glass on the fastback
    return "body"


def build_cybercab():
    C.reset_scene()
    mats = C.make_materials({**PALETTE, "body": CC_STEEL})
    root = C.empty("cybercab")
    bm, layer = hull(CC_PROFILE, CC_CUTS, chamfer=0.045)
    colour_block(bm, layer, cc_planes(), cc_role)
    bm = cut_arches(bm, mats, (-CC_AXLE, CC_AXLE), CC_ARCH_R, CC_WHEEL_R, CC_ARCH_INNER)
    b = C.Builder(ROLES)
    b.bm = bm
    bvh = BVHTree.FromBMesh(bm)
    arch_lips(b, "trim", (-CC_AXLE, CC_AXLE), CC_ARCH_R, CC_WHEEL_R, CC_SILL + 0.06, 0.035, 0.85, 0.955)
    cybercab_details(b, bvh)
    cybercab_seams(b, bvh)
    body = b.to_object("body", mats, parent=root)
    wheels = build_wheels(root, mats, CC_TRACK, (-CC_AXLE, CC_AXLE), CC_WHEEL_R, CC_TYRE_W, CC_WHEEL_R * 0.74)
    return root, [body, *wheels]


def cybercab_details(b, bvh):
    """Full-width light bars set in black recesses front and back, teal door accents."""
    f, r = front_frame(), rear_frame()
    plate(b, "trim", bvh, f, [(-0.9, 0.62), (0.9, 0.62), (0.9, 0.78), (-0.9, 0.78)], FORWARD,
          depth=0.012, steps=(14, 1))
    plate(b, "light_head", bvh, f, [(-0.86, 0.66), (0.86, 0.66), (0.86, 0.74), (-0.86, 0.74)], FORWARD,
          depth=0.024, steps=(14, 1))
    plate(b, "trim", bvh, r, [(-0.8, 0.94), (0.8, 0.94), (0.8, 1.08), (-0.8, 1.08)], BACKWARD,
          depth=0.012, steps=(12, 1))
    plate(b, "light_tail", bvh, r, [(-0.76, 0.97), (0.76, 0.97), (0.76, 1.05), (-0.76, 1.05)], BACKWARD,
          depth=0.024, steps=(12, 1))
    for sx in (1, -1):
        plate(b, "accent", bvh, side_frame(sx), [(0.26, 0.47), (0.58, 0.47), (0.24, 0.98), (-0.08, 0.98)],
              inward(sx), steps=(4, 4))


def cybercab_seams(b, bvh):
    for sx in (1, -1):
        s = side_frame(sx)
        ink(b, bvh, s, [(0.66, CC_CLAD + 0.02), (0.68, 0.96)], inward(sx))                 # door, front
        ink(b, bvh, s, [(-0.7, CC_CLAD + 0.02), (-0.7, 0.86), (-0.95, 1.1)], inward(sx))   # door, rear
    top = top_frame()
    ink(b, bvh, top, [(-0.6, -1.12), (0.6, -1.12)], DOWN)                                  # frunk lid
    for sx in (1, -1):
        ink(b, bvh, top, [(sx * 0.6, -1.12), (sx * 0.56, -1.84)], DOWN)
    f = front_frame()
    ink(b, bvh, f, [(-0.5, 0.52), (0.5, 0.52)], FORWARD)
    r = rear_frame()
    ink(b, bvh, r, [(-0.7, 0.62), (0.7, 0.62)], BACKWARD)                                  # bumper line
    ink(b, bvh, r, [(-0.7, 0.62), (-0.66, 1.12)], BACKWARD)                                # boot lid
    ink(b, bvh, r, [(0.7, 0.62), (0.66, 1.12)], BACKWARD)


# --- lineup, style and silhouette sheets -------------------------------------------

def import_cab(name, root, offset, path=None):
    bpy.ops.import_scene.gltf(filepath=str(path or C.MODELS_DIR / f"{name}.glb"))
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
            o.data.set_sharp_from_angle(angle=math.radians(1))  # flat panels, as exported


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


# The previous, shrink-wrapped versions (PR #16), for the silhouette comparison.
PREV = SOURCES / "prev"


def build_silhouettes():
    """Each car as a flat black shape, side on and front 3/4: previous version, then new."""
    rows = []
    for name in ("wayfarer", "cybercab"):
        row = []
        for label, path in (("prev", PREV / f"{name}.glb"), ("new", C.MODELS_DIR / f"{name}.glb")):
            if not path.exists():
                sys.exit(f"missing {path}: see build.sh robotaxis")
            C.reset_scene()
            root = C.empty("silhouette")
            import_cab(name, root, 0.0, path)
            for m in bpy.data.materials:
                m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0, 0, 0, 1)
            for o in bpy.context.scene.objects:
                o.visible_shadow = False
            tmp = f".silhouette-{name}-{label}"
            C.render_contact_sheet(root, tmp, outline=0.0, size=560, fill=0.95, elevation=8.0,
                                   views=(("side", -90), ("3/4 front", 35)))
            path = C.RENDERS_DIR / f"{tmp}.png"
            row.append(load_rgb(path))
            path.unlink()
        gap = np.ones((row[0].shape[0], 40, 3), np.float32) * 0.75
        rows.append(np.concatenate([row[0], gap, row[1]], axis=1))
    gap = np.ones((12, rows[0].shape[1], 3), np.float32) * np.array(C.BG, np.float32)
    # Blender images are bottom-up: the last row in the array is the top of the picture.
    save_rgb(np.concatenate([rows[1], gap, rows[0]], axis=0), C.RENDERS_DIR / "robotaxis-silhouettes.png")


def main():
    car = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "wayfarer"
    if car == "lineup":
        build_lineup()
    elif car == "style":
        build_style()
    elif car == "silhouettes":
        build_silhouettes()
    elif car == "trace":
        trace()
    else:
        root, parts = {"wayfarer": build_wayfarer, "cybercab": build_cybercab}[car]()
        finish(car, root, parts)


main()
