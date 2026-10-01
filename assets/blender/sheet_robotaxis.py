"""Robotaxis modelled from scratch off our orthographic turnaround sheets (docs/art/vehicles).

    blender --background --factory-startup --python sheet_robotaxis.py -- zoox|apollo|fit-zoox|fit-apollo|four

There are no source models for these two, so they are planar hard-surface models: the
body is lofted through cross-section rings whose sizes are read off the sheet
(calibrations/<car>.json gives its scale and views), with edge loops placed on the
colour borders so the flat role colours meet in straight lines. Wheels, arches, sensor
kit, lamps and glass are built on top; ink panel lines are thin plates laid on the
surface with robotaxis.py's helpers, like the Wayfarer's.

- zoox: a Zoox-style bidirectional cab, identical at both ends. The body is lofted
  through horizontal rings (rounded rectangles in plan), so the tall end faces stay flat
  and lean as drawn. Nodes: zoox > body, lidar (front-left roof pod), wheel_FL/FR/RL/RR.
- apollo: an Apollo RT6-style minivan, lofted through horizontal rings too, with a round
  nose and a square tail: the rings step back over the short hood and up the windshield
  like contour lines. Nodes: apollo > body, lidar (the crown dome), wheel_FL/FR/RL/RR.
- fit-zoox / fit-apollo: reimport the exported glb, render its silhouette with the
  sheet's own orthographic cameras and score it against the sheet (sheets.py): IoU per
  view to reviews/<car>-fit.json and overlays to docs/renders/<car>-fit-<view>.png.
- four: the four robotaxis side on and from a front 3/4 view at one scale
  (docs/renders/robotaxis-four.png).

Conventions as cab.py and robotaxis.py: metres, the car faces -Y in Blender (+Z in the
game), origin on the ground midway between the axles, left (wheel_FL, wheel_RL) at +X.
"""
import json
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import common as C  # noqa: E402
import robotaxis as R  # noqa: E402

TRI_RANGE = (6000, 16000)
SMOOTH_ANGLE = R.SMOOTH_ANGLE
REVIEWS = Path(__file__).resolve().parent / "reviews"
DOWN, FORWARD, BACKWARD = R.DOWN, R.FORWARD, R.BACKWARD
SIDE, ARC, END = 0, 1, 2


# --- shared modelling ----------------------------------------------------------------

def end_frame(sy):
    """Local XY = (Blender X, up) on the end facing `sy` (-1 front, +1 back)."""
    return Matrix(((1, 0, 0, 0), (0, 0, sy, sy * 4.0), (0, 1, 0, 0), (0, 0, 0, 1)))


def corner_frame(cx, cy, theta):
    """Local XY = (along the corner, up) on a plan corner centred on (cx, cy), looking
    in along the direction `theta` (radians from +X); rays go along -corner_out."""
    out = Vector((math.cos(theta), math.sin(theta), 0))
    along = Vector((-out.y, out.x, 0))
    o = Vector((cx, cy, 0)) + out * 3.0
    return Matrix(((along.x, 0, out.x, o.x), (along.y, 0, out.y, o.y), (0, 1, 0, 0), (0, 0, 0, 1))), -out


def into_end(sy):
    return Vector((0, -sy, 0))


def loft(b, mat, rings, caps=(True, True)):
    """Skin consecutive closed rings (equal point counts) with quads and close the ends
    with flat n-gons. Returns the quads as {(ring, segment): face}."""
    before = b._begin()
    vs = [[b.bm.verts.new(p) for p in r] for r in rings]
    n = len(rings[0])
    grid = {}
    for i in range(len(vs) - 1):
        for j in range(n):
            k = (j + 1) % n
            grid[i, j] = b.bm.faces.new((vs[i][j], vs[i][k], vs[i + 1][k], vs[i + 1][j]))
    for ring, cap, flip in ((vs[0], caps[0], True), (vs[-1], caps[1], False)):
        if not cap:
            continue
        c = b.bm.verts.new(sum((v.co for v in ring), Vector()) / len(ring))
        for j in range(n):
            tri = (c, ring[j], ring[(j + 1) % n])
            b.bm.faces.new(tri[::-1] if flip else tri)
    b._assign(before, mat)
    return grid


def plan_ring(Lf, Lr, W, Rf, Rr, side_ys, end_fracs, arc_steps=6, fit="scale"):
    """A closed counter-clockwise plan ring: a rectangle from y = -Lf (the nose) to Lr,
    half width W, with corner radii Rf at the front and Rr at the back. Side points sit
    at the Blender y values side_ys, so colour borders line up from ring to ring; where
    the straight side is too short they are scaled towards y = 0 (fit="scale") or
    clamped, a few millimetres apart, against its ends (fit="clamp"). End points sit at
    fractions of the flat ends. Returns (points, segment kinds)."""
    lo, hi = -(Lf - Rf), Lr - Rr
    ys = sorted(side_ys)
    if fit == "scale":
        k = min(1.0, hi / (ys[-1] + 0.06), lo / (ys[0] - 0.06))
        ys = [y * k for y in ys]
    else:
        n, eps = len(ys), 0.004
        ys = [min(max(y, lo + eps * (i + 1)), hi - eps * (n - i)) for i, y in enumerate(ys)]
    half = [((W - Rf) * f, -Lf) for f in sorted(end_fracs) if f < 1.0]
    for i in range(arc_steps + 1):
        a = -math.pi / 2 + math.pi / 2 * i / arc_steps
        half.append((W - Rf + Rf * math.cos(a), lo + Rf * math.sin(a)))
    half += [(W, y) for y in ys]
    for i in range(arc_steps + 1):
        a = math.pi / 2 * i / arc_steps
        half.append((W - Rr + Rr * math.cos(a), hi + Rr * math.sin(a)))
    half += [((W - Rr) * f, Lr) for f in sorted(end_fracs, reverse=True) if f < 1.0]
    ring = half + [(-x, y) for x, y in reversed(half[1:-1])]
    kinds = []
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        mx, my = abs(x0 + x1) / 2, (y0 + y1) / 2
        if abs(mx - W) < 1e-6 and lo - 1e-6 <= my <= hi + 1e-6:
            kinds.append(SIDE)
        elif (abs(my + Lf) < 1e-6 and mx <= W - Rf + 1e-6) or (abs(my - Lr) < 1e-6 and mx <= W - Rr + 1e-6):
            kinds.append(END)
        else:
            kinds.append(ARC)
    return ring, kinds


def arch_region(sx, ay, zc, radius, x_in, sides=20):
    """A wheel arch as a convex region: a cylinder about the axle (along X), outboard of
    x_in."""
    planes = [R.plane_axis(0, sx * x_in, sx)]
    for i in range(sides):
        a = 2 * math.pi * (i + 0.5) / sides
        d = Vector((0, math.cos(a), math.sin(a)))
        planes.append((Vector((0, ay, zc)) + d * radius, -d))
    return planes


def cut_arches(b, regions, margin=0.2):
    for planes in regions:
        R.cut_region(b.bm, planes, margin=margin)
        b.bm.faces.ensure_lookup_table()
        bmesh.ops.delete(b.bm, geom=[f for f in b.bm.faces
                                     if R.inside(f.calc_center_median(), planes)], context="FACES")


def sector(b, mats_by_face, centre, out, r0, r1, xs, a0, a1, steps, sx=1, chamfer=0.0):
    """An annular sector about an axle along X, from radius r0 to r1 across xs (x0, x1),
    over angles a0..a1 (0 = towards `out` along Y, 90 = up), its outer edge on the
    outboard side (sx) chamfered. mats_by_face maps 'inner', 'outer' (with the
    chamfer), 'face' (outboard), 'back' and 'ends' to roles."""
    x_in, x_out = (xs[0], xs[1]) if sx > 0 else (xs[1], xs[0])
    c = chamfer * sx
    # The cross-section, each point naming the face that runs on to the next.
    profile = [(x_in, r0, "back"), (x_in, r1, "outer")]
    if chamfer:
        profile.append((x_out - c, r1, "outer"))
        profile.append((x_out, r1 - chamfer, "face"))
    else:
        profile.append((x_out, r1, "face"))
    profile.append((x_out, r0, "inner"))
    rings = []
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        d = Vector((0, out * math.cos(a), math.sin(a)))
        rings.append([b.bm.verts.new(Vector((x, 0, 0)) + centre + d * r) for x, r, _ in profile])
    groups = {"back": [], "outer": [], "face": [], "inner": [], "ends": []}
    n = len(profile)
    for r, q in zip(rings, rings[1:]):
        for j in range(n):
            k = (j + 1) % n
            groups[profile[j][2]].append(b.bm.faces.new((r[j], r[k], q[k], q[j])))
    groups["ends"] += [b.bm.faces.new(rings[0]), b.bm.faces.new(list(reversed(rings[-1])))]
    new = [f for g in groups.values() for f in g]
    bmesh.ops.recalc_face_normals(b.bm, faces=new)
    for g, fs in groups.items():
        for f in fs:
            f.material_index = b.materials.index(mats_by_face[g])
    return groups


def fan(b, mat, centre, pts, facing):
    """A flat one-sided polygon fan from `centre` through pts, facing `facing`."""
    before = b._begin()
    c = b.bm.verts.new(centre)
    vs = [b.bm.verts.new(p) for p in pts]
    for p, q in zip(vs, vs[1:]):
        f = b.bm.faces.new((c, p, q))
        f.normal_update()
        if f.normal.dot(facing) < 0:
            f.normal_flip()
    return b._assign(before, mat)


def ring_plate(b, mat, centre, axis, r0, r1, a0, a1, steps, out=1):
    """A flat annular band (ink round an arch lip) in the plane through `centre` normal
    to X, standing out a hair along `axis`."""
    before = b._begin()
    pts = []
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        d = Vector((0, out * math.cos(a), math.sin(a)))
        pts.append((b.bm.verts.new(centre + d * r0), b.bm.verts.new(centre + d * r1),
                    b.bm.verts.new(centre + d * r0 - axis * 0.01),
                    b.bm.verts.new(centre + d * r1 - axis * 0.01)))
    for p, q in zip(pts, pts[1:]):
        b.bm.faces.new((p[0], p[1], q[1], q[0]))
        b.bm.faces.new((p[2], q[2], q[3], p[3]))
        b.bm.faces.new((p[1], p[3], q[3], q[1]))
        b.bm.faces.new((p[0], q[0], q[2], p[2]))
    for p in (pts[0], pts[-1]):
        b.bm.faces.new((p[0], p[2], p[3], p[1]))
    new = [f for f in b.bm.faces if f not in before]
    bmesh.ops.recalc_face_normals(b.bm, faces=new)
    return b._assign(before, mat)


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def ink_loop(b, bvh, frame, pts, direction, **kw):
    R.ink(b, bvh, frame, list(pts) + [pts[0]], direction, **kw)


def rounded(x0, y0, x1, y1, r, steps=2):
    """A rounded rectangle outline (for ink round windows and doors)."""
    out = []
    for cx, cy, a in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for i in range(steps + 1):
            t = math.radians(a + 90 * i / steps)
            out.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return out


def to_object(b, name, mats, pivot=(0, 0, 0), parent=None, smooth_angle=None):
    """Builder.to_object, keeping the faces' winding as built (every part here is
    wound outwards; recalc_face_normals flips strips of the long lofted shells), with
    coordinates snapped to 0.01 mm for a byte-identical build."""
    for v in b.bm.verts:
        v.co = Vector(round(c, 5) for c in v.co)
    pivot = Vector(pivot)
    bmesh.ops.translate(b.bm, vec=-pivot, verts=b.bm.verts)
    C.canonical_order(b.bm)
    verts = [tuple(v.co) for v in b.bm.verts]
    faces, mat_idx = [], []
    for f in b.bm.faces:
        ids = [v.index for v in f.verts]
        k = ids.index(min(ids))
        faces.append(ids[k:] + ids[:k])
        mat_idx.append(f.material_index)
    b.bm.free()
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.polygons.foreach_set("material_index", mat_idx)
    for n in b.materials:
        me.materials.append(mats[n])
    if smooth_angle is None:
        me.shade_flat()
    else:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    obj.location = pivot - (C.parent_world_origin(parent) if parent else Vector())
    return obj


def finish(name, root, parts):
    C.report(parts)
    tris = C.triangle_count(parts)
    assert TRI_RANGE[0] <= tris <= TRI_RANGE[1], f"{name} has {tris} triangles, outside {TRI_RANGE}"
    C.export_glb(name)
    C.render_contact_sheet(root, name, outline=0.02)


# --- Zoox (bidirectional, from docs/art/vehicles/zoox.png) ----------------------------

ZOOX_PALETTE = {
    "body": 0xF2F2EE,
    "glass": 0x262C33,
    "trim": 0x1A1B1E,
    "accent": 0x2F6FD6,      # the blue band on the roof pods
    "light_head": 0xFFF6DE,
    "light_tail": 0xE0303A,
    "tyre": 0x232427,
    "hub": 0xC9CBCC,
    "sand": 0xA8A08C,        # the khaki lower body and fenders
    "amber": 0xF08A24,       # side markers
}
ZOOX_AXLE = 1.43             # half wheelbase
ZOOX_WHEEL_R = 0.355
ZOOX_WHEEL_X = 0.79          # tyre centre, half track
ZOOX_TYRE_W = 0.2
ZOOX_ARCH_IN = 0.6           # the wheel wells reach in to this half width
ZOOX_FENDER = (0.375, 0.445, 0.895)  # fender inner and outer radius, outer face
ZOOX_FENDER_END = 0.0                # the fender stops at axle height on the end side
# Horizontal rings: (height, half length, half width). Read off the sheet's side and
# front views: the end faces lean out a little towards the bottom, the roof crowns.
ZOOX_RINGS = [
    (0.11, 1.715, 0.765),
    (0.16, 1.745, 0.795),
    (0.26, 1.755, 0.805),
    (0.36, 1.76, 0.81),
    (0.47, 1.76, 0.815),
    (0.60, 1.755, 0.818),
    (0.75, 1.75, 0.818),
    (0.97, 1.74, 0.812),
    (1.20, 1.72, 0.80),
    (1.40, 1.70, 0.787),
    (1.53, 1.675, 0.778),
    (1.62, 1.645, 0.77),
    (1.665, 1.59, 0.735),
    (1.70, 1.52, 0.66),
    (1.73, 1.42, 0.55),
    (1.755, 1.30, 0.43),
    (1.773, 1.18, 0.31),
    (1.787, 1.08, 0.20),
]
ZOOX_SIDE_YS = [s * y for y in (0.37, 0.735, 1.05, 1.2, 1.38) for s in (-1, 1)] + [0.0]
ZOOX_END_FRACS = [0.0, 0.34, 0.68, 1.0]
# Colour borders (heights) and the side's openings (|y|).
ZOOX_SAND_SIDE, ZOOX_SAND_END = 0.36, 0.47
ZOOX_WINDOW = (0.97, 1.62, 1.38)  # bottom, top, end (|y|)
ZOOX_DOOR = (0.26, 1.62, 0.735)
ZOOX_POD = (0.715, 1.62)     # roof pod centres (|x|, |y|)


def end_ward(f, L, W):
    """Whether a corner face lies more than 30 degrees round the corner arc from the
    side: the end glass wraps that far, so a white pillar shows from the front and a
    dark band from the side, as drawn."""
    c = f.calc_center_median()
    Rc = min(0.2, 0.5 * W)
    return abs(c.y) - (L - Rc) > (abs(c.x) - (W - Rc)) * math.tan(math.radians(30))


def zoox_body(b):
    rings, kinds = [], None
    for z, L, W in ZOOX_RINGS:
        Rc = min(0.2, 0.5 * W)
        ring, k = plan_ring(L, L, W, Rc, Rc, ZOOX_SIDE_YS, ZOOX_END_FRACS)
        rings.append([Vector((x, y, z)) for x, y in ring])
        kinds = kinds or k
    grid = loft(b, "body", rings)
    names = b.materials
    for (i, j), f in grid.items():
        z = (ZOOX_RINGS[i][0] + ZOOX_RINGS[i + 1][0]) / 2
        y = abs(f.calc_center_median().y)
        role = "body"
        if kinds[j] == SIDE:
            if z < ZOOX_SAND_SIDE and not (y < ZOOX_DOOR[2] and z > ZOOX_DOOR[0]):
                role = "sand"
            elif ZOOX_WINDOW[0] < z < ZOOX_WINDOW[1] and ZOOX_DOOR[2] < y < ZOOX_WINDOW[2]:
                role = "glass"
            elif y < ZOOX_DOOR[2] and ZOOX_DOOR[0] < z < ZOOX_DOOR[1]:
                role = "glass"
        elif z < ZOOX_SAND_END:
            role = "sand"
        elif z < ZOOX_WINDOW[1] and (kinds[j] == END or end_ward(f, *ZOOX_RINGS[i][1:])):
            role = "glass"     # the end glass wraps half way round the corners
        f.material_index = names.index(role)
    # The floor.
    for f in b.bm.faces:
        if f not in grid.values() and f.calc_center_median().z < 0.2:
            f.material_index = names.index("trim")


def zoox_arches(b):
    """Wheel wells cut through the corners, the khaki fenders round them and their
    dark liners, and an ink line on each fender lip."""
    r0, r1, x1 = ZOOX_FENDER
    cut_arches(b, [arch_region(sx, sy * ZOOX_AXLE, ZOOX_WHEEL_R, r0 + 0.02, ZOOX_ARCH_IN)
                   for sx in (1, -1) for sy in (1, -1)])
    for sx in (1, -1):
        for sy in (1, -1):
            centre = Vector((0, sy * ZOOX_AXLE, ZOOX_WHEEL_R))
            a0 = ZOOX_FENDER_END
            a1 = 180 + math.degrees(math.asin((ZOOX_WHEEL_R - 0.12) / r1))
            x0 = ZOOX_ARCH_IN - 0.01
            xs = (x0, x1) if sx > 0 else (-x1, -x0)
            sector(b, {"inner": "trim", "outer": "sand", "face": "sand", "back": "trim", "ends": "sand"},
                   centre, sy, r0, r1, xs, a0, a1, 24, sx=sx, chamfer=0.035)
            # The well's inner wall.
            pts = []
            for i in range(13):
                a = math.radians(a0 + (a1 - a0) * i / 12)
                pts.append(Vector((sx * x0, sy * ZOOX_AXLE + sy * math.cos(a) * r0,
                                   ZOOX_WHEEL_R + math.sin(a) * r0)))
            fan(b, "trim", Vector((sx * x0, sy * ZOOX_AXLE, 0.12)), pts, Vector((sx, 0, 0)))
            # Ink on the fender lip.
            ring_plate(b, "trim", centre + Vector((sx * (x1 + 0.002), 0, 0)), Vector((sx, 0, 0)),
                       r1 - 0.052, r1 - 0.034, a0, a1, 24, out=sy)


def zoox_details(b, bvh):
    """Lamps, glass roof, slot and markers as plates; ink for doors, tracks and frames."""
    for sy in (-1, 1):
        f, d = end_frame(sy), into_end(sy)
        lamp = "light_head" if sy < 0 else "light_tail"
        R.plate(b, "light_head", bvh, f, rect(-0.43, 0.866, 0.43, 0.886), d, depth=0.01, steps=(8, 1))
        for sx in (1, -1):
            x0, x1 = sorted((sx * 0.45, sx * 0.67))
            R.plate(b, "trim", bvh, f, rect(x0, 0.845, x1, 0.905), d, depth=0.008, steps=(3, 1))
            x0, x1 = sorted((sx * 0.465, sx * 0.655))
            R.plate(b, lamp, bvh, f, rect(x0, 0.857, x1, 0.893), d, depth=0.013, steps=(3, 1))
            R.plate(b, "amber", bvh, f, rect(sx * 0.55 - 0.012, 0.26, sx * 0.55 + 0.012, 0.31), d,
                    depth=0.006, steps=(1, 1))
        # The sensor slot in the khaki bumper.
        R.plate(b, "trim", bvh, f, rect(-0.3, 0.15, 0.3, 0.32), d, depth=0.006, steps=(6, 2))
    # The glass roof.
    R.plate(b, "glass", bvh, R.top_frame(), rect(-0.54, -1.05, 0.54, 1.05), DOWN, depth=0.006, steps=(6, 8))
    for sx in (1, -1):
        s = R.side_frame(sx)
        for fy in (-1, 1):
            R.plate(b, "amber", bvh, s, rect(fy * 0.97 - 0.04, 0.35, fy * 0.97 + 0.04, 0.37),
                    R.inward(sx), depth=0.006, steps=(1, 1))


INK_STEP = 0.25   # flat panels need few samples along a line
CURVED_STEP = 0.04  # curved ones need many, or the line floats off the bends


def zoox_ink(b, bvh):
    dw = ZOOX_DOOR[2]
    for sx in (1, -1):
        s, d = R.side_frame(sx), R.inward(sx)
        for y in (-dw, 0.0, dw):
            R.ink(b, bvh, s, [(y, 0.12), (y, 1.6)], d, step=INK_STEP)
            R.ink(b, bvh, s, [(y, 1.6), (y, 1.7)], d, step=CURVED_STEP)
        R.ink(b, bvh, s, [(-1.47, 1.625), (1.47, 1.625)], d, step=INK_STEP)         # top door track
        R.ink(b, bvh, s, [(-1.0, 0.245), (1.0, 0.245)], d, step=INK_STEP)           # bottom door track
        for fy in (-1, 1):
            # The window's lower and outer frame, its corner rounded.
            corner = [(fy * (1.3 + 0.08 * math.sin(t)), 0.97 + 0.08 * (1 - math.cos(t)))
                      for t in (math.radians(a) for a in (0, 30, 60, 90))]
            R.ink(b, bvh, s, [(fy * dw, 0.97), *corner, (fy * 1.38, 1.625)], d, step=INK_STEP)
            # Side cameras on the pillars, door buttons by the seams.
            for y, z in ((1.31, 0.875), (0.69, 0.86)):
                R.plate(b, "trim", bvh, s, rect(fy * y - 0.016, z - 0.016, fy * y + 0.016, z + 0.016),
                        d, depth=0.008, steps=(1, 1))
            # The door's glass in its frame.
            lo, hi = sorted((fy * 0.07, fy * 0.64))
            ink_loop(b, bvh, s, rounded(lo, 0.36, hi, 1.52, 0.04), d, step=INK_STEP)
    for y in (-dw, 0.0, dw):
        R.ink(b, bvh, R.top_frame(), [(-0.72, y), (0.72, y)], DOWN, step=CURVED_STEP)


def zoox_pods(b):
    """Roof-corner pods: a black camera housing and a sensor puck with a blue band.
    The front-left puck is the lidar node."""
    for sx in (1, -1):
        for sy in (1, -1):
            c = Vector((sx * ZOOX_POD[0], sy * ZOOX_POD[1], 0))
            b.box("trim", (0.15, 0.16, 0.13), c + Vector((0, 0, 1.585)), bevel=0.025, seg=2)
            # Camera lenses looking out to the side and the end.
            b.tube("glass", c + Vector((sx * 0.07, 0, 1.585)), c + Vector((sx * 0.085, 0, 1.585)), 0.025, 0.022, sides=10)
            b.tube("glass", c + Vector((0, sy * 0.075, 1.585)), c + Vector((0, sy * 0.09, 1.585)), 0.025, 0.022, sides=10)
            if (sx, sy) != (1, -1):
                pod_puck(b, c)


def pod_puck(b, c):
    b.tube("trim", c + Vector((0, 0, 1.65)), c + Vector((0, 0, 1.85)), 0.058, 0.055, sides=16, bevel=0.01)
    b.tube("accent", c + Vector((0, 0, 1.755)), c + Vector((0, 0, 1.78)), 0.06, 0.06, sides=16)


def zoox_wheel(b, sx, ay):
    c = Vector((sx * ZOOX_WHEEL_X, ay, ZOOX_WHEEL_R))
    ax = Vector((sx, 0, 0))
    w, r = ZOOX_TYRE_W, ZOOX_WHEEL_R
    b.tube("tyre", c - ax * w / 2, c + ax * w / 2, r, r, sides=24, bevel=0.04)
    face = w / 2 + 0.004
    b.tube("trim", c + ax * (face - 0.03), c + ax * face, r * 0.76, r * 0.76, sides=24, bevel=0.006)
    # Four pale windows in an X, as on the real car's covers.
    for k in range(4):
        a = math.radians(45 + 90 * k)
        p = c + ax * face + Vector((0, math.cos(a), math.sin(a))) * r * 0.42
        b.box("hub", (0.012, 0.075, 0.13), p, rot=Matrix.Rotation(a + math.pi / 2, 4, "X"), bevel=0.004)
    b.tube("hub", c + ax * (face - 0.01), c + ax * (face + 0.01), r * 0.13, r * 0.11, sides=12)


def build_zoox():
    C.reset_scene()
    mats = C.make_materials(ZOOX_PALETTE)
    roles = list(ZOOX_PALETTE)
    root = C.empty("zoox")
    b = C.Builder(roles)
    zoox_body(b)
    zoox_arches(b)
    bvh = BVHTree.FromBMesh(b.bm)
    zoox_details(b, bvh)
    bvh = BVHTree.FromBMesh(b.bm)
    zoox_ink(b, bvh)
    zoox_pods(b)
    body = to_object(b, "body", mats, parent=root, smooth_angle=SMOOTH_ANGLE)
    lb = C.Builder(roles)
    c = Vector((ZOOX_POD[0], -ZOOX_POD[1], 0))
    pod_puck(lb, c)
    lidar = to_object(lb, "lidar", mats, pivot=c + Vector((0, 0, 1.75)), parent=root, smooth_angle=50)
    wheels = []
    for name, sx, ay in (("wheel_FL", 1, -ZOOX_AXLE), ("wheel_FR", -1, -ZOOX_AXLE),
                         ("wheel_RL", 1, ZOOX_AXLE), ("wheel_RR", -1, ZOOX_AXLE)):
        wb = C.Builder(roles)
        zoox_wheel(wb, sx, ay)
        wheels.append(to_object(wb, name, mats, pivot=Vector((sx * ZOOX_WHEEL_X, ay, ZOOX_WHEEL_R)),
                                  parent=root, smooth_angle=SMOOTH_ANGLE))
    return root, [body, lidar, *wheels]


# --- Apollo RT6 (from docs/art/vehicles/apollo.png) ----------------------------------

APOLLO_PALETTE = {
    "body": 0xF4F5F3,
    "glass": 0x222930,
    "trim": 0x1B1C1F,
    "accent": 0x2457B8,      # the deep blue lower stripe and sensor bands
    "light_head": 0xF6F8FF,
    "light_tail": 0xD8323A,
    "tyre": 0x232427,
    "hub": 0xC4C8CC,
}
APOLLO_AXLE = 1.394          # half wheelbase
APOLLO_WHEEL_R = 0.345
APOLLO_WHEEL_X = 0.79
APOLLO_TYRE_W = 0.235
APOLLO_ARCH = (0.385, 0.425, 0.912)  # arch lip inner and outer radius, outer face
APOLLO_ARCH_IN = 0.62
# Horizontal rings: (height, nose extent, tail extent, half width, nose and tail corner
# radii), read off the side, front and top views. The front face stands upright, the
# short hood rises to the windshield base at 1.17 m, the windshield rakes back to the
# flat roof; the tail is upright with a little tumblehome into the spoiler.
APOLLO_RINGS = [
    (0.15, 1.82, 1.70, 0.86, 0.45, 0.25),
    (0.20, 2.06, 1.82, 0.885, 0.5, 0.28),
    (0.26, 2.14, 2.10, 0.895, 0.5, 0.3),
    (0.30, 2.155, 2.22, 0.90, 0.5, 0.3),
    (0.32, 2.16, 2.24, 0.90, 0.5, 0.3),
    (0.43, 2.16, 2.26, 0.905, 0.5, 0.3),
    (0.60, 2.15, 2.265, 0.905, 0.5, 0.3),
    (0.80, 2.135, 2.265, 0.90, 0.5, 0.3),
    (0.92, 2.105, 2.26, 0.89, 0.5, 0.3),
    (0.97, 2.05, 2.255, 0.885, 0.5, 0.3),
    (1.02, 1.96, 2.25, 0.878, 0.5, 0.3),
    (1.06, 1.87, 2.24, 0.872, 0.5, 0.3),
    (1.10, 1.75, 2.23, 0.866, 0.5, 0.3),
    (1.13, 1.60, 2.22, 0.855, 0.48, 0.3),
    (1.155, 1.42, 2.21, 0.83, 0.45, 0.3),
    (1.17, 1.17, 2.205, 0.79, 0.4, 0.3),
    (1.30, 0.98, 2.18, 0.755, 0.4, 0.29),
    (1.45, 0.77, 2.12, 0.72, 0.4, 0.28),
    (1.62, 0.52, 2.06, 0.665, 0.4, 0.27),
    (1.66, 0.45, 2.10, 0.635, 0.4, 0.27),
    (1.70, 0.38, 2.08, 0.60, 0.38, 0.27),
    (1.725, 0.30, 2.0, 0.55, 0.36, 0.26),
    (1.745, 0.18, 1.9, 0.45, 0.33, 0.25),
]
# Side points (forward distance f; Blender y = -f): door seams, pillars, window ends.
APOLLO_SIDE_F = [1.17, 0.97, 0.40, -0.03, -0.13, -0.6, -0.89, -1.01, -1.40, -1.78]
APOLLO_END_FRACS = [0.0, 0.5, 1.0]
APOLLO_GLASS = (1.17, 1.62)
APOLLO_PILLARS = [(-0.13, -0.03), (-1.01, -0.89)]   # B and C pillars, black (f ranges)
APOLLO_SILL, APOLLO_FRONT_LOW, APOLLO_REAR_LOW = 0.30, 0.32, 0.43
APOLLO_CROWN_F = -0.22       # the roof crown, over the sliding door


def apollo_body(b):
    rings, kinds = [], None
    for z, Lf, Lr, W, Rf, Rr in APOLLO_RINGS:
        ring, k = plan_ring(Lf, Lr, W, Rf, Rr, [-f for f in APOLLO_SIDE_F], APOLLO_END_FRACS,
                            fit="clamp")
        rings.append([Vector((x, y, z)) for x, y in ring])
        kinds = kinds or k
    grid = loft(b, "body", rings)
    names = b.materials
    for (i, j), face in grid.items():
        z = (APOLLO_RINGS[i][0] + APOLLO_RINGS[i + 1][0]) / 2
        c = face.calc_center_median()
        f = -c.y
        role = "body"
        if APOLLO_GLASS[0] < z < APOLLO_GLASS[1]:
            role = "glass"
            if kinds[j] == SIDE and any(lo < f < hi for lo, hi in APOLLO_PILLARS):
                role = "trim"
        elif kinds[j] == SIDE:
            role = "trim" if z < APOLLO_SILL else "body"
        elif f > 0:
            role = "trim" if z < APOLLO_FRONT_LOW else "body"
        else:
            role = "trim" if z < APOLLO_REAR_LOW else "body"
        face.material_index = names.index(role)
    for face in b.bm.faces:
        if face not in grid.values() and face.calc_center_median().z < 0.2:
            face.material_index = names.index("trim")


def apollo_arches(b):
    """Round arches cut through the body, black lips round them and dark wells."""
    r0, r1, x1 = APOLLO_ARCH
    cut_arches(b, [arch_region(sx, sy * APOLLO_AXLE, APOLLO_WHEEL_R, r0 + 0.02, APOLLO_ARCH_IN)
                   for sx in (1, -1) for sy in (1, -1)])
    for sx in (1, -1):
        for sy in (1, -1):
            centre = Vector((0, sy * APOLLO_AXLE, APOLLO_WHEEL_R))
            a0 = -math.degrees(math.asin((APOLLO_WHEEL_R - 0.17) / r1))
            a1 = 180 - a0
            x0 = APOLLO_ARCH_IN - 0.01
            xs = (x0, x1) if sx > 0 else (-x1, -x0)
            sector(b, {"inner": "trim", "outer": "trim", "face": "trim", "back": "trim", "ends": "trim"},
                   centre, sy, r0, r1, xs, a0, a1, 20, sx=sx, chamfer=0.015)
            pts = []
            for i in range(11):
                a = math.radians(a0 + (a1 - a0) * i / 10)
                pts.append(Vector((sx * x0, sy * APOLLO_AXLE + sy * math.cos(a) * r0,
                                   APOLLO_WHEEL_R + math.sin(a) * r0)))
            fan(b, "trim", Vector((sx * x0, sy * APOLLO_AXLE, 0.17)), pts, Vector((sx, 0, 0)))


def apollo_details(b, bvh):
    """Lamps, intakes, grille, the blue stripe, mirrors and handles."""
    front, rear = end_frame(-1), end_frame(1)
    # Full-width light bar along the nose crease, the lamp clusters at its ends.
    R.plate(b, "trim", bvh, front, rect(-0.78, 0.858, 0.78, 0.912), FORWARD, depth=0.008, steps=(12, 1))
    R.plate(b, "light_head", bvh, front, rect(-0.5, 0.876, 0.5, 0.892), FORWARD, depth=0.013, steps=(8, 1))
    for sx in (1, -1):
        x0, x1 = sorted((sx * 0.53, sx * 0.76))
        R.plate(b, "light_head", bvh, front, rect(x0, 0.872, x1, 0.9), FORWARD, depth=0.013, steps=(4, 1))
        # Vertical intakes at the bumper corners.
        x0, x1 = sorted((sx * 0.66, sx * 0.76))
        R.plate(b, "trim", bvh, front, rect(x0, 0.42, x1, 0.66), FORWARD, depth=0.008, steps=(2, 2))
    # The lower grille, a wide trapezoid, and its bars.
    R.plate(b, "trim", bvh, front, [(-0.66, 0.3), (0.66, 0.3), (0.52, 0.52), (-0.52, 0.52)],
            FORWARD, depth=0.008, steps=(8, 2))
    for z in (0.37, 0.44):
        R.plate(b, "hub", bvh, front, rect(-0.5, z, 0.5, z + 0.008), FORWARD, depth=0.012, steps=(6, 1))
    # Rear: full-width tail light bar, the high stop lamp, reflectors on the corners.
    R.plate(b, "trim", bvh, rear, rect(-0.62, 0.975, 0.62, 1.075), BACKWARD, depth=0.008, steps=(12, 1))
    R.plate(b, "light_tail", bvh, rear, rect(-0.63, 1.005, 0.63, 1.03), BACKWARD, depth=0.013, steps=(12, 1))
    # ... wrapping round the corners.
    z, Lf, Lr, W, Rf, Rr = APOLLO_RINGS[9]
    for sx in (1, -1):
        f, d = corner_frame(sx * (W - Rr), Lr - Rr, math.atan2(1, sx))
        a0, a1 = sorted((-sx * 0.3, sx * 0.3))
        R.plate(b, "trim", bvh, f, rect(a0, 0.975, a1, 1.075), d, depth=0.008, steps=(6, 1))
        R.plate(b, "light_tail", bvh, f, rect(a0 + 0.01, 1.005, a1 - 0.01, 1.03), d, depth=0.013, steps=(6, 1))
    R.plate(b, "light_tail", bvh, rear, rect(-0.2, 1.585, 0.2, 1.6), BACKWARD, depth=0.01, steps=(3, 1))
    for sx in (1, -1):
        x0, x1 = sorted((sx * 0.79, sx * 0.82))
        R.plate(b, "light_tail", bvh, rear, rect(x0, 0.5, x1, 0.68), BACKWARD, depth=0.01, steps=(1, 2))
        x0, x1 = sorted((sx * 0.5, sx * 0.78))
        R.plate(b, "light_tail", bvh, rear, rect(x0, 0.37, x1, 0.385), BACKWARD, depth=0.01, steps=(2, 1))
    R.plate(b, "hub", bvh, rear, rect(-0.45, 0.33, 0.45, 0.342), BACKWARD, depth=0.01, steps=(6, 1))
    for sx in (1, -1):
        s, d = R.side_frame(sx), R.inward(sx)
        # The deep blue stripe: low on the front doors, stepping up behind the sliding
        # door's front edge, and again behind the rear wheel.
        R.plate(b, "accent", bvh, s, rect(-0.6, 0.335, 0.93, 0.40), d, depth=0.006, steps=(8, 1))
        R.plate(b, "accent", bvh, s, [(-0.98, 0.39), (-0.6, 0.335), (-0.6, 0.40), (-0.98, 0.465)],
                d, depth=0.006, steps=(2, 1))
        R.plate(b, "accent", bvh, s, rect(-2.1, 0.40, -1.84, 0.46), d, depth=0.006, steps=(3, 1))
        # Door handles.
        for f0, f1 in ((0.03, 0.23), (-0.32, -0.12)):
            R.plate(b, "hub", bvh, s, rect(f0, 0.945, f1, 0.975), d, depth=0.012, steps=(2, 1))
        apollo_mirror(b, sx)


def apollo_mirror(b, sx):
    """Door mirror: a black stalk on the door's front corner and a white cap."""
    b.box("trim", (0.12, 0.1, 0.06), Vector((sx * 0.85, -0.82, 1.16)), bevel=0.015)
    b.box("body", (0.2, 0.17, 0.13), Vector((sx * 0.93, -0.80, 1.24)), bevel=0.04, seg=2)
    b.box("trim", (0.19, 0.03, 0.11), Vector((sx * 0.93, -0.72, 1.24)), bevel=0.01)


def apollo_ink(b, bvh):
    for sx in (1, -1):
        s, d = R.side_frame(sx), R.inward(sx)
        R.ink(b, bvh, s, [(0.965, 1.165), (0.97, 0.6), (0.96, 0.31)], d, step=INK_STEP)   # front door, front
        R.ink(b, bvh, s, [(-0.03, 1.165), (-0.03, 0.31)], d, step=INK_STEP)              # B pillar
        R.ink(b, bvh, s, [(-1.03, 1.165), (-1.03, 0.54)], d, step=INK_STEP)              # sliding door, rear
        R.ink(b, bvh, s, [(-1.03, 1.07), (-1.82, 1.07)], d, step=INK_STEP)               # its track
        R.ink(b, bvh, s, [(-1.03, 0.31), (-0.03, 0.31)], d, step=INK_STEP)               # its sill
        ink_loop(b, bvh, s, rect(-1.76, 0.83, -1.56, 0.96), d, step=INK_STEP)            # charge flap
    # Hood shut lines.
    for sx in (1, -1):
        R.ink(b, bvh, R.top_frame(), [(sx * 0.66, -2.02), (sx * 0.74, -1.2)], DOWN, step=CURVED_STEP)
    # The tailgate.
    R.ink(b, bvh, end_frame(1), [(-0.74, 1.15), (-0.72, 0.47), (0.72, 0.47), (0.74, 1.15)], BACKWARD,
          step=INK_STEP)


def apollo_sensors(b, bvh):
    """The roof crown (base, camera deck and corner pucks; the lidar dome is its own
    node) and the fender sensors on the hood corners."""
    y = -APOLLO_CROWN_F
    roof = round(max(bvh.ray_cast(Vector((x, y + dy, 4)), DOWN, 6)[0].z
                     for x in (-0.3, 0, 0.3) for dy in (-0.4, 0, 0.4)), 3)
    b.box("trim", (0.66, 0.98, 0.07), Vector((0, y, roof + 0.025)), bevel=0.03, seg=2, taper=(0.94, 0.95))
    b.box("trim", (0.56, 0.62, 0.06), Vector((0, y, roof + 0.085)), bevel=0.02, taper=(0.9, 0.9))
    # A forward camera on the deck.
    b.box("trim", (0.12, 0.08, 0.06), Vector((0, y - 0.33, roof + 0.07)), bevel=0.01)
    b.box("accent", (0.08, 0.01, 0.012), Vector((0, y - 0.371, roof + 0.085)))
    for sx in (1, -1):
        for dy in (-0.5, 0.42):
            c = Vector((sx * 0.47, y + dy, roof))
            b.tube("trim", c, c + Vector((0, 0, 0.065)), 0.045, 0.042, sides=12, bevel=0.006)
            b.tube("accent", c + Vector((0, 0, 0.04)), c + Vector((0, 0, 0.052)), 0.046, 0.046, sides=12)
        # Fender sensors.
        c = Vector((sx * 0.80, -1.33, 1.04))
        b.box("trim", (0.09, 0.1, 0.13), c + Vector((0, 0, 0.065)), bevel=0.015)
        b.tube("accent", c + Vector((0, 0, 0.1)), c + Vector((0, 0, 0.115)), 0.052, 0.052, sides=12)
        b.tube("trim", c + Vector((0, 0, 0.115)), c + Vector((0, 0, 0.15)), 0.05, 0.045, sides=12)
    return roof + 0.115


def apollo_lidar(b, base):
    y = -APOLLO_CROWN_F
    b.tube("trim", Vector((0, y, base)), Vector((0, y, base + 0.17)), 0.14, 0.135, sides=20, bevel=0.01)
    b.tube("accent", Vector((0, y, base + 0.125)), Vector((0, y, base + 0.15)), 0.142, 0.14, sides=20)
    b.sphere("trim", Vector((0, y, base + 0.17)), (0.135, 0.135, 0.045), u=20, v=6)


def apollo_wheel(b, sx, ay):
    """A 20-inch alloy with five twin spokes."""
    c = Vector((sx * APOLLO_WHEEL_X, ay, APOLLO_WHEEL_R))
    ax = Vector((sx, 0, 0))
    w, r = APOLLO_TYRE_W, APOLLO_WHEEL_R
    b.tube("tyre", c - ax * w / 2, c + ax * w / 2, r, r, sides=24, bevel=0.04)
    face = w / 2 + 0.004
    rim = r * 0.74
    b.tube("trim", c + ax * (face - 0.05), c + ax * (face - 0.02), rim, rim, sides=24)
    b.tube("hub", c + ax * (face - 0.02), c + ax * face, rim, rim * 0.97, sides=24)
    b.tube("trim", c + ax * (face - 0.002), c + ax * (face + 0.002), rim * 0.9, rim * 0.9, sides=24)
    for k in range(5):
        a = math.radians(90 + 72 * k)
        for da in (-0.1, 0.1):
            d = Vector((0, math.cos(a + da), math.sin(a + da)))
            p = c + ax * face + d * rim * 0.5
            b.box("hub", (0.016, 0.03, rim * 0.86), p, rot=Matrix.Rotation(a + da - math.pi / 2, 4, "X"),
                  bevel=0.004)
    b.tube("hub", c + ax * (face - 0.01), c + ax * (face + 0.016), rim * 0.24, rim * 0.2, sides=12)
    b.tube("trim", c + ax * (face + 0.012), c + ax * (face + 0.02), rim * 0.1, rim * 0.08, sides=10)


def build_apollo():
    C.reset_scene()
    mats = C.make_materials(APOLLO_PALETTE)
    roles = list(APOLLO_PALETTE)
    root = C.empty("apollo")
    b = C.Builder(roles)
    apollo_body(b)
    apollo_arches(b)
    bvh = BVHTree.FromBMesh(b.bm)
    base = apollo_sensors(b, bvh)
    apollo_details(b, bvh)
    bvh = BVHTree.FromBMesh(b.bm)
    apollo_ink(b, bvh)
    body = to_object(b, "body", mats, parent=root, smooth_angle=SMOOTH_ANGLE)
    lb = C.Builder(roles)
    apollo_lidar(lb, base)
    lidar = to_object(lb, "lidar", mats, pivot=Vector((0, -APOLLO_CROWN_F, base + 0.1)), parent=root,
                      smooth_angle=50)
    wheels = []
    for name, sx, ay in (("wheel_FL", 1, -APOLLO_AXLE), ("wheel_FR", -1, -APOLLO_AXLE),
                         ("wheel_RL", 1, APOLLO_AXLE), ("wheel_RR", -1, APOLLO_AXLE)):
        wb = C.Builder(roles)
        apollo_wheel(wb, sx, ay)
        wheels.append(to_object(wb, name, mats, pivot=Vector((sx * APOLLO_WHEEL_X, ay, APOLLO_WHEEL_R)),
                                parent=root, smooth_angle=SMOOTH_ANGLE))
    return root, [body, lidar, *wheels]


# --- fit against the sheet --------------------------------------------------------------

def fit(car):
    import anime  # noqa: F401 - puts Pillow (user site) on the path for sheets.py
    import sheets as S

    C.reset_scene()
    path = C.MODELS_DIR / f"{car}.glb"
    bpy.ops.import_scene.gltf(filepath=str(path))
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    report = {"asset": str(path.relative_to(C.REPO)), "triangles": C.triangle_count(objs), "iou": {}}
    with tempfile.TemporaryDirectory(prefix="sheet-fit-") as tmp:
        for view in S.load(car)["body"]["views"]:
            mask = S.render_mask(car, "body", view, objs, Path(tmp) / f"{view}.png")
            report["iou"][view] = round(S.overlay(car, "body", view, mask,
                                                  C.RENDERS_DIR / f"{car}-fit-{view}.png"), 4)
    (REVIEWS / f"{car}-fit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    assert min(report["iou"].values()) >= 0.9, report


# --- the four robotaxis ------------------------------------------------------------------

FOUR = ("wayfarer", "cybercab", "zoox", "apollo")


def build_four():
    """The four robotaxis at one scale: nose to tail side on, then abreast from a low
    front 3/4, stacked into docs/renders/robotaxis-four.png."""
    rows = []
    for row, place, views in (
            ("side", lambda i: (0, -7.2 + 4.85 * i), (("side", -90),)),
            ("front", lambda i: (-4.2 + 2.8 * i, 0), (("3/4 front", -22),))):
        C.reset_scene()
        root = C.empty("four")
        for i, name in enumerate(FOUR):
            before = set(root.children)
            R.import_cab(name, root, 0.0)
            x, y = place(i)
            for o in set(root.children) - before:
                o.location.x += x
                o.location.y += y
        path = C.RENDERS_DIR / f".four-{row}.png"
        C.render_contact_sheet(root, path.stem, outline=0.02, size=2000, fill=1.0 if row == "side" else 0.9,
                               elevation=6.0 if row == "side" else 12.0, views=views)
        R.crop_to_content(path, margin=30)
        rows.append(R.load_rgb(path))
        path.unlink()
    R.save_rgb(np.concatenate(rows[::-1], axis=0), C.RENDERS_DIR / "robotaxis-four.png")


def main():
    car = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "zoox"
    if car == "four":
        build_four()
    elif car.startswith("fit-"):
        fit(car[4:])
    else:
        root, parts = {"zoox": build_zoox, "apollo": build_apollo}[car]()
        finish(car, root, parts)


main()
