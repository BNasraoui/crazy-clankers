"""The San Francisco street kit: the props that fill the streets in the key art
(public/keyart/*.jpg), drawn in the robotaxis' manga cel style.

    blender --background --factory-startup --python street_kit.py -- <prop>|all|strip|check

Each prop is built from scratch out of simple primitives, exported to
public/models/street/<prop>.glb and rendered as a close-up toon sheet at
docs/renders/street-<prop>.png. `strip` lays every prop on a strip of road and
sidewalk with the Wayfarer for scale (docs/renders/street-kit.png); `check` reimports
the glbs, checks nodes and budgets, and writes reviews/street-kit.json.

Conventions as the robotaxis: metres, Blender Z up and -Y forward (the exporter turns
that into the game's +Y up, +Z forward), origin on the ground at the base. Flat role
materials, normals split at 38 degrees, ink lines as thin dark plates where an artist
would draw them. The trees' foliage is clumps of jagged low-poly blobs whose normals
point out from each clump's centre (bent a little away from the crown's centre), so a
two-tone cel shader gives each clump one soft, clean shadow shape.
"""
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import common as C  # noqa: E402
import robotaxis as R  # noqa: E402

SMOOTH = 38
STREET = "street"
REVIEWS = Path(__file__).resolve().parent / "reviews"
INK = 0x18181C
INK_W = 0.022


# --- shared modelling ------------------------------------------------------------------

def V(*a):
    return Vector(a)


def surface_rot(along, normal):
    """Rotation whose local X runs `along` and local Z is `normal`."""
    x = Vector(along).normalized()
    z = Vector(normal).normalized()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed().to_4x4()


def bar(b, mat, p0, p1, normal, w=INK_W, d=0.006, sink=0.006):
    """A thin strip from p0 to p1 lying on a surface whose outward normal is `normal`:
    `d` proud of it, `sink` below it, a little longer than the segment so joints close."""
    p0, p1, n = Vector(p0), Vector(p1), Vector(normal).normalized()
    c = (p0 + p1) / 2 + n * (d - sink) / 2
    b.box(mat, ((p1 - p0).length + w, w, d + sink), c, rot=surface_rot(p1 - p0, n))


def frame_lines(b, mat, pts, normal, **kw):
    for p0, p1 in zip(pts, pts[1:] + pts[:1]):
        bar(b, mat, p0, p1, normal, **kw)


def side_rect(sx, y0, y1, z0, z1, x):
    """A rectangle's corners on the side plane x = sx * x."""
    return [V(sx * x, y0, z0), V(sx * x, y1, z0), V(sx * x, y1, z1), V(sx * x, y0, z1)]


def loft(b, mat, pts, radii, sides=8, prof=None, spin=0.0, caps=(True, True), mat_fn=None, twist=0.0,
         stagger=False):
    """A tube through the polyline `pts` with a ring radius per point (0 at an end makes
    a point). `prof(j)` scales the radius of side j (flutes, diamonds); `twist` turns
    each successive ring by that many radians, `stagger` every other ring by half a side
    (diamond facets); `mat_fn(i, j)` picks a role per face."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    tans = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]
    ref = V(0, 0, 1) if abs(tans[0].z) < 0.9 else V(1, 0, 0)
    u = (ref - tans[0] * ref.dot(tans[0])).normalized()
    rings = []
    bm = b.bm
    before = b._begin()
    for i, (p, t, r) in enumerate(zip(pts, tans, radii)):
        u = (u - t * u.dot(t)).normalized()
        w = t.cross(u)
        if r <= 0:
            rings.append([bm.verts.new(p)])
            continue
        ring = []
        for j in range(sides):
            a = spin + twist * i + 2 * math.pi * (j + (0.5 if stagger and i % 2 else 0.0)) / sides
            k = prof(i, j) if prof else 1.0
            ring.append(bm.verts.new(p + (u * math.cos(a) + w * math.sin(a)) * r * k))
        rings.append(ring)
    mats = []
    for i in range(n - 1):
        r0, r1 = rings[i], rings[i + 1]
        for j in range(sides):
            jn = (j + 1) % sides
            if len(r0) == 1:
                f = bm.faces.new((r0[0], r1[jn], r1[j]))
            elif len(r1) == 1:
                f = bm.faces.new((r0[j], r0[jn], r1[0]))
            else:
                f = bm.faces.new((r0[j], r0[jn], r1[jn], r1[j]))
            mats.append((f, mat_fn(i, j) if mat_fn else mat))
    if caps[0] and len(rings[0]) > 1:
        mats.append((bm.faces.new(list(reversed(rings[0]))), mat))
    if caps[1] and len(rings[-1]) > 1:
        mats.append((bm.faces.new(rings[-1]), mat))
    for f, m in mats:
        f.material_index = b.materials.index(m)
    return [f for f in bm.faces if f not in before]


def strip_solid(b, mat_fn, outer, inner, z0, z1):
    """A wall between two matching plan polylines (outer, inner), from z0 to z1, closed.
    `mat_fn(k)` picks the role of segment k (both faces, top and bottom)."""
    bm = b.bm
    vo0 = [bm.verts.new(V(x, y, z0)) for x, y in outer]
    vo1 = [bm.verts.new(V(x, y, z1)) for x, y in outer]
    vi0 = [bm.verts.new(V(x, y, z0)) for x, y in inner]
    vi1 = [bm.verts.new(V(x, y, z1)) for x, y in inner]
    n = len(outer)
    for k in range(n - 1):
        idx = b.materials.index(mat_fn(k))
        for quad in ((vo0[k], vo0[k + 1], vo1[k + 1], vo1[k]), (vi0[k + 1], vi0[k], vi1[k], vi1[k + 1]),
                     (vo1[k], vo1[k + 1], vi1[k + 1], vi1[k]), (vo0[k + 1], vo0[k], vi0[k], vi0[k + 1])):
            bm.faces.new(quad).material_index = idx
    for k, m in ((0, mat_fn(0)), (n - 1, mat_fn(n - 2))):
        bm.faces.new((vo0[k], vo1[k], vi1[k], vi0[k])).material_index = b.materials.index(m)


def grid_slab(b, top_mat, edge_mat, grid, thickness):
    """A closed slab whose top surface is the point grid[i][j]; the underside is the same
    grid `thickness` lower. Top and underside take `top_mat`, the rim `edge_mat`."""
    bm = b.bm
    rows, cols = len(grid), len(grid[0])
    top = [[bm.verts.new(Vector(p)) for p in row] for row in grid]
    bot = [[bm.verts.new(Vector(p) - V(0, 0, thickness)) for p in row] for row in grid]
    ti, ei = b.materials.index(top_mat), b.materials.index(edge_mat)
    for i in range(rows - 1):
        for j in range(cols - 1):
            bm.faces.new((top[i][j], top[i][j + 1], top[i + 1][j + 1], top[i + 1][j])).material_index = ti
            bm.faces.new((bot[i][j], bot[i + 1][j], bot[i + 1][j + 1], bot[i][j + 1])).material_index = ti
    rim = ([(i, 0) for i in range(rows - 1)] + [(rows - 1, j) for j in range(cols - 1)]
           + [(i, cols - 1) for i in range(rows - 1, 0, -1)] + [(0, j) for j in range(cols - 1, 0, -1)])
    for (i0, j0), (i1, j1) in zip(rim, rim[1:] + rim[:1]):
        bm.faces.new((top[i0][j0], bot[i0][j0], bot[i1][j1], top[i1][j1])).material_index = ei


class Foliage:
    """Leaf geometry with authored per-vertex normals (the anime-tree trick): every
    vertex of a clump gets the direction from the clump's centre, bent `bias` towards
    the direction from the crown's centre to the clump."""

    def __init__(self, roles, crown):
        self.roles = list(roles)
        self.crown = Vector(crown)
        self.verts, self.normals, self.faces, self.mats = [], [], [], []

    def _add(self, pts, normals, faces, mat, centre):
        base = len(self.verts)
        self.verts += [Vector(p) for p in pts]
        self.normals += [Vector(n).normalized() for n in normals]
        centres = centre if isinstance(centre, list) else [centre] * len(faces)
        for f, ctr in zip(faces, centres):
            f = [base + k for k in f]
            # Wind every face outwards from the clump (or cross-section) centre.
            a, b_, c = (self.verts[k] for k in f[:3])
            mid = sum((self.verts[k] for k in f), Vector()) / len(f)
            if (b_ - a).cross(c - a).dot(mid - ctr) < 0:
                f = f[::-1]
            self.faces.append(f)
            self.mats.append(self.roles.index(mat))

    def clump(self, mat, c, radii, rng, u=9, rings=4, jag=0.2, under=0.7, bias=0.3, spin=None):
        """A jagged blob: a low UV sphere whose vertices alternate in and out (a leafy,
        star-like silhouette), each ring turned half a step on so the facets interlock.
        The underside is flattened by `under`."""
        c = Vector(c)
        spin = rng.uniform(0, 2 * math.pi) if spin is None else spin
        out = (c - self.crown)
        out = out.normalized() if out.length > 1e-6 else V(0, 0, 1)
        pts, normals = [], []

        def add(d, f):
            z = d.z * radii[2] * f * (under if d.z < 0 else 1.0)
            pts.append(c + V(d.x * radii[0] * f, d.y * radii[1] * f, z))
            normals.append(d * (1 - bias) + out * bias)

        add(V(0, 0, 1), 1.0 + jag * 0.3)
        for k in range(1, rings + 1):
            lat = math.pi / 2 - math.pi * k / (rings + 1)
            for j in range(u):
                lon = spin + 2 * math.pi * j / u + k * math.pi / u
                d = V(math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))
                f = 1 + (jag if (j + k) % 2 == 0 else -0.55 * jag) + rng.uniform(-0.05, 0.05)
                add(d, f)
        add(V(0, 0, -1), 1.0)
        bottom = len(pts) - 1
        faces = []
        ring = lambda k, j: 1 + (k - 1) * u + (j % u)  # noqa: E731
        for j in range(u):
            faces.append((0, ring(1, j), ring(1, j + 1)))
            faces.append((bottom, ring(rings, j + 1), ring(rings, j)))
        for k in range(1, rings):
            for j in range(u):
                faces.append((ring(k, j), ring(k + 1, j), ring(k, j + 1)))
                faces.append((ring(k, j + 1), ring(k + 1, j), ring(k + 1, j + 1)))
        self._add(pts, normals, faces, mat, c)

    def sheet(self, mat, pts, normals, faces, centre):
        self._add(pts, normals, faces, mat, centre)

    def to_object(self, name, mats, parent):
        me = bpy.data.meshes.new(name)
        verts = [tuple(round(x, 5) for x in v) for v in self.verts]
        me.from_pydata(verts, [], self.faces)
        me.polygons.foreach_set("material_index", self.mats)
        for n in self.roles:
            me.materials.append(mats[n])
        me.shade_smooth()
        me.normals_split_custom_set_from_vertices(
            [tuple(round(x, 4) for x in n.normalized()) for n in self.normals])
        obj = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(obj)
        obj.parent = parent
        return obj


def part(b, name, mats, root, pivot=(0, 0, 0), smooth=SMOOTH):
    return R.to_object(b, name, mats, pivot=Vector(pivot), parent=root, smooth_angle=smooth)


# --- cable car (Powell-Hyde) ------------------------------------------------------------

CAR_PALETTE = {
    "body": 0x7C1F27,       # maroon lower panels
    "cream": 0xEDE2C4,      # upper panels, posts, letterboards
    "trim": 0xD9A93E,       # gold leaf pinstripes and window trim
    "brass": 0xE0B651,      # grab poles, bell
    "glass": 0x323D4A,
    "roof": 0x4A3F3B,
    "accent": 0x2D5A9C,     # the blue line under the eaves
    "wood": 0x9C6B3C,       # benches, running boards, brake blocks
    "metal": 0x55595F,      # trucks, grip, levers
    "wheel": 0x2C2D31,
    "light_head": 0xFFF2C4,
    "lamp_red": 0xD7372F,
    "ink": INK,
}
CAR_L = 4.15            # half length to the dash bows
CAR_BOW = 0.4           # how far the rounded ends reach out
CAR_X = 1.02            # side panels' outer face
CAR_BOARD = 1.2         # running boards' outer edge
FLOOR = 0.78
SILL = 0.5
EAVE = 2.62
ROOF_HW = 1.12
OPEN_FRONT = (-CAR_L + CAR_BOW, -1.45)   # the open grip section
CABIN = (-1.45, 2.95)                     # the enclosed saloon
WHEEL_R = 0.3
GAUGE_X = 0.534                           # 3 ft 6 in gauge, rail centres
AXLES = (-3.1, -2.1, 2.1, 3.1)


def bow(sy, r_scale=1.0, steps=10):
    """The plan of one rounded end, from the left side round to the right, at a
    fraction of the full half width."""
    pts = []
    y0 = sy * (CAR_L - CAR_BOW)
    for i in range(steps + 1):
        t = math.pi * i / steps
        x = CAR_X * r_scale * math.cos(t)
        y = y0 + sy * CAR_BOW * r_scale * math.sin(t)
        pts.append((x, y))
    return pts


def plan_normal(x0, y0, x1, y1, sy):
    """Outward normal of a chord of an end's bow (so a strip lies flat on that facet)."""
    n = V(y1 - y0, -(x1 - x0), 0).normalized()
    return n if n.y * sy > 0 or (abs(n.y) < 1e-6 and n.x * (x0 + x1) > 0) else -n


def car_floor(b):
    # The back bow runs from +X round to -X; the mirrored front bow closes the loop.
    plan = bow(1) + [(x, -y) for x, y in bow(1)][::-1]
    b.prism("body", plan, FLOOR - SILL, Matrix.Translation(V(0, 0, (FLOOR + SILL) / 2)))
    # Wooden deck in the open section and on the rear platform.
    b.box("wood", (2 * CAR_X - 0.1, OPEN_FRONT[1] - OPEN_FRONT[0], 0.02), V(0, sum(OPEN_FRONT) / 2, FLOOR + 0.01))
    b.box("wood", (2 * CAR_X - 0.1, CAR_L - CAR_BOW - CABIN[1], 0.02),
          V(0, (CAR_L - CAR_BOW + CABIN[1]) / 2, FLOOR + 0.01))


def car_dash(b, sy, top):
    """The rounded end: a maroon dash panel with a cream cap rail and a gold line."""
    outer = bow(sy)
    inner = bow(sy, 0.94)
    strip_solid(b, lambda k: "body", outer, inner, SILL, top)
    strip_solid(b, lambda k: "cream", bow(sy, 1.015), bow(sy, 0.92), top, top + 0.07)
    # Gold pinstripe and an ink seam along the cap rail, as plates on the curve.
    for z, mat, w in ((top - 0.12, "trim", 0.018), (SILL + 0.1, "trim", 0.018), (top, "ink", INK_W)):
        for (x0, y0), (x1, y1) in zip(outer[1:-2], outer[2:-1]):
            bar(b, mat, V(x0, y0, z), V(x1, y1, z), plan_normal(x0, y0, x1, y1, sy), w=w, d=0.005)


def car_windscreen(b, sy):
    """Above the front dash: three panes on the curve between cream posts."""
    z0, z1 = 1.62, EAVE
    breaks = [(0, 0.07, "cream"), (0.07, 0.31, "glass"), (0.31, 0.36, "cream"), (0.36, 0.64, "glass"),
              (0.64, 0.69, "cream"), (0.69, 0.93, "glass"), (0.93, 1.0, "cream")]
    outer, inner, roles = [], [], []
    for t0, t1, role in breaks:
        n = max(1, round((t1 - t0) * 12))
        for i in range(n):
            roles.append(role)
        ts = [t0 + (t1 - t0) * i / n for i in range(n + 1)]
        for t in ts if not outer else ts[1:]:
            a = math.pi * t
            for lst, s in ((outer, 0.985), (inner, 0.94)):
                lst.append((CAR_X * s * math.cos(a), sy * (CAR_L - CAR_BOW + CAR_BOW * s * math.sin(a))))
    strip_solid(b, lambda k: roles[k], outer, inner, z0, z1 - 0.3)
    # Header board (a blank destination sign) between the panes and the roof.
    strip_solid(b, lambda k: "cream", bow(sy, 0.99), bow(sy, 0.9), z1 - 0.3, z1)
    for z in (z0, z1 - 0.3):
        for (x0, y0), (x1, y1) in zip(outer[1:-2], outer[2:-1]):
            bar(b, "trim", V(x0, y0, z), V(x1, y1, z), plan_normal(x0, y0, x1, y1, sy), w=0.03, d=0.012)


def car_cabin_side(b, sx):
    y0, y1 = CABIN
    n_win, post = 6, 0.13
    win = (y1 - y0 - (n_win + 1) * post) / n_win
    X = CAR_X
    nrm = V(sx, 0, 0)
    b.box("body", (0.06, y1 - y0, 1.42 - SILL), V(sx * (X - 0.03), (y0 + y1) / 2, (SILL + 1.42) / 2))
    b.box("cream", (0.09, y1 - y0 + 0.02, 0.08), V(sx * (X - 0.03), (y0 + y1) / 2, 1.46))      # belt rail
    b.box("glass", (0.03, y1 - y0, 0.8), V(sx * (X - 0.05), (y0 + y1) / 2, 1.9))
    b.box("cream", (0.06, y1 - y0, EAVE - 2.3), V(sx * (X - 0.03), (y0 + y1) / 2, (2.3 + EAVE) / 2))
    for k in range(n_win + 1):
        yc = y0 + post / 2 + k * (post + win)
        b.box("cream", (0.06, post, 0.8), V(sx * (X - 0.03), yc, 1.9))
        if 0 < k < n_win:
            bar(b, "ink", V(sx * X, yc, SILL + 0.03), V(sx * X, yc, 1.4), nrm)   # panel joints
    for k in range(n_win):
        ya = y0 + post + k * (post + win)
        yb = ya + win
        frame_lines(b, "trim", side_rect(sx, ya + 0.01, yb - 0.01, 1.51, 2.29, X), nrm, w=0.03, d=0.012)
        frame_lines(b, "trim", side_rect(sx, ya + 0.06, yb - 0.06, SILL + 0.14, 1.3, X), nrm, w=0.018, d=0.005)
        # A transom bar across the top of each window, as on the real sashes.
        bar(b, "cream", V(sx * X, ya, 2.08), V(sx * X, yb, 2.08), nrm, w=0.05, d=0.01, sink=0.03)
    frame_lines(b, "trim", side_rect(sx, y0 + 0.08, y1 - 0.08, 2.36, EAVE - 0.06, X), nrm, w=0.018, d=0.005)
    bar(b, "ink", V(sx * X, y0, 2.3), V(sx * X, y1, 2.3), nrm)


def car_bulkhead(b, sy_face, y):
    """The cabin's end wall facing into an open section: windows either side of a door."""
    d = 0.06
    yc = y + sy_face * d / 2
    nrm = V(0, sy_face, 0)
    b.box("body", (2 * (CAR_X - 0.06), d, 1.42 - FLOOR), V(0, yc, (FLOOR + 1.42) / 2))
    b.box("cream", (2 * (CAR_X - 0.06), d, EAVE - 1.42), V(0, yc, (1.42 + EAVE) / 2))
    yo = y + sy_face * (d + 0.004)
    for xc in (-0.62, 0.62):
        b.box("glass", (0.5, 0.012, 0.72), V(xc, yo, 1.88))
        frame_lines(b, "trim", [V(xc - 0.25, yo, 1.52), V(xc + 0.25, yo, 1.52), V(xc + 0.25, yo, 2.24),
                                V(xc - 0.25, yo, 2.24)], nrm, w=0.03, d=0.012)
    b.box("wood", (0.66, 0.02, 1.62), V(0, yo, FLOOR + 0.81))                    # the door
    b.box("glass", (0.44, 0.012, 0.6), V(0, yo + sy_face * 0.012, 1.95))
    frame_lines(b, "ink", [V(-0.33, yo, FLOOR), V(0.33, yo, FLOOR), V(0.33, yo, FLOOR + 1.62),
                           V(-0.33, yo, FLOOR + 1.62)], nrm, d=0.016)


def car_open_section(b, sx):
    """Outward-facing benches over a maroon apron, with brass poles up to the roof."""
    y0, y1 = OPEN_FRONT
    X = CAR_X
    nrm = V(sx, 0, 0)
    seat = 1.0
    b.box("body", (0.06, y1 - y0, seat - SILL), V(sx * (X - 0.03), (y0 + y1) / 2, (SILL + seat) / 2))
    b.box("wood", (0.46, y1 - y0, 0.07), V(sx * (X - 0.21), (y0 + y1) / 2, seat + 0.035))       # bench
    b.box("wood", (0.06, y1 - y0, 0.5), V(sx * (X - 0.46), (y0 + y1) / 2, seat + 0.32), rot=Matrix.Rotation(
        sx * math.radians(-8), 4, "Y"))                                                               # back
    b.box("cream", (0.08, y1 - y0, 0.06), V(sx * (X - 0.5), (y0 + y1) / 2, seat + 0.58))          # back rail
    panels = 3
    pw = (y1 - y0) / panels
    for k in range(panels):
        ya, yb = y0 + k * pw, y0 + (k + 1) * pw
        frame_lines(b, "trim", side_rect(sx, ya + 0.08, yb - 0.08, SILL + 0.08, seat - 0.1, X), nrm, w=0.018, d=0.005)
        if k:
            bar(b, "ink", V(sx * X, ya, SILL + 0.03), V(sx * X, ya, seat - 0.02), nrm)
    for y in (y0 + 0.12, y0 + 0.8, y0 + 1.5, y1 - 0.12):
        b.tube("brass", V(sx * (X - 0.03), y, seat + 0.07), V(sx * (X - 0.03), y, EAVE), 0.024, 0.024, sides=8)


def car_rear_platform(b, sx):
    y0, y1 = CABIN[1], CAR_L - CAR_BOW
    for y in (y0 + 0.1, y1 - 0.05):
        b.tube("brass", V(sx * (CAR_X - 0.05), y, FLOOR), V(sx * (CAR_X - 0.05), y, EAVE), 0.024, 0.024, sides=8)
    # Grab rail along the platform side at hand height.
    b.tube("brass", V(sx * (CAR_X - 0.05), y0 + 0.1, 1.55), V(sx * (CAR_X - 0.05), y1 - 0.05, 1.55), 0.018, 0.018, sides=6)


def car_running_board(b, sx):
    y0, y1 = OPEN_FRONT[0] + 0.05, CABIN[1] - 0.05
    b.box("wood", (CAR_BOARD - CAR_X, y1 - y0, 0.06), V(sx * (CAR_X + CAR_BOARD) / 2, (y0 + y1) / 2, SILL - 0.02))
    bar(b, "ink", V(sx * CAR_BOARD, y0, SILL - 0.02), V(sx * CAR_BOARD, y1, SILL - 0.02), V(sx, 0, 0), w=0.014, d=0.004)
    for y in np.linspace(y0 + 0.2, y1 - 0.2, 6):
        b.box("metal", (CAR_BOARD - CAR_X, 0.05, 0.12), V(sx * (CAR_X + CAR_BOARD) / 2 - sx * 0.02, float(y), SILL - 0.1))


def roof_grid(hw_flat, half_len, rise, z_eave, dip, rows=24, cols=10, end_len=0.45):
    grid = []
    for i in range(rows + 1):
        y = -half_len + 2 * half_len * i / rows
        over = max(0.0, abs(y) - (half_len - end_len))
        hw = hw_flat * math.sqrt(max(0.0, 1 - (over / (end_len * 1.2)) ** 2))
        s = max(0.0, (abs(y) - (half_len - 0.9)) / 0.9)
        row = []
        for j in range(cols + 1):
            u = -1 + 2 * j / cols
            row.append(V(u * hw, y, z_eave + rise * (1 - u * u) - dip * s * s))
        grid.append(row)
    return grid


def car_roof(b):
    grid_slab(b, "roof", "accent", roof_grid(ROOF_HW, CAR_L + 0.02, 0.24, EAVE + 0.08, 0.1), 0.08)
    # The clerestory: a raised lantern down the middle with a row of small lights.
    y0, y1 = -3.35, 3.25
    z0, z1 = EAVE + 0.2, 3.02
    for sx in (-1, 1):
        b.box("cream", (0.05, y1 - y0, z1 - z0), V(sx * 0.55, (y0 + y1) / 2, (z0 + z1) / 2))
        n = 14
        step = (y1 - y0) / n
        for k in range(n):
            yc = y0 + step * (k + 0.5)
            b.box("glass", (0.012, step - 0.1, 0.12), V(sx * 0.578, yc, (z0 + z1) / 2 + 0.03))
        bar(b, "trim", V(sx * 0.575, y0, z0 + 0.06), V(sx * 0.575, y1, z0 + 0.06), V(sx, 0, 0), w=0.016, d=0.004)
    for sy, y in ((-1, y0), (1, y1)):
        b.box("cream", (1.1, 0.05, z1 - z0), V(0, y, (z0 + z1) / 2))
    grid = [[V(-0.66 + 1.32 * j / 8, y0 - 0.12 + (y1 - y0 + 0.24) * i / 4,
               z1 + 0.06 + 0.12 * (1 - (-1 + 2 * j / 8) ** 2)) for j in range(9)] for i in range(5)]
    grid_slab(b, "roof", "roof", grid, 0.06)


def car_running_gear(b):
    """Trucks, track brake shoes and the grip reaching down into the slot."""
    for yc in (-2.6, 2.6):
        for sx in (-1, 1):
            b.box("metal", (0.08, 1.5, 0.16), V(sx * 0.76, yc, 0.36))
            b.box("wood", (0.09, 0.5, 0.12), V(sx * GAUGE_X, yc, 0.12))            # track brake shoe
            b.box("metal", (0.05, 0.6, 0.06), V(sx * GAUGE_X, yc, 0.21))
        b.box("metal", (1.6, 0.18, 0.12), V(0, yc, 0.42))                          # bolster
    b.box("metal", (0.05, 0.38, FLOOR - 0.02), V(0, -2.62, (FLOOR - 0.02) / 2))     # the grip
    b.box("metal", (0.14, 0.5, 0.08), V(0, -2.62, 0.06))                           # grip jaws
    for sy in (-1, 1):
        # Bumper bar across each end, below the dash.
        pts = [(x * 1.02, y + sy * 0.02) for x, y in bow(sy, 1.0, 8)]
        strip_solid(b, lambda k: "wood", pts, [(x * 0.93, y - sy * 0.06) for x, y in pts], SILL - 0.1, SILL)


def car_controls(b):
    """The gripman's lever and brakes in the open section, the bell, the brake wheel."""
    b.box("metal", (0.12, 0.6, 0.1), V(0, -2.7, FLOOR + 0.05))                         # lever quadrant
    b.tube("metal", V(0, -2.62, FLOOR), V(0, -2.92, 2.0), 0.032, 0.026, sides=8)
    b.tube("wood", V(-0.12, -2.92, 2.0), V(0.12, -2.92, 2.0), 0.04, 0.04, sides=8)       # handle
    for sx in (-1, 1):
        b.tube("metal", V(sx * 0.3, -2.3, FLOOR), V(sx * 0.34, -2.5, 1.7), 0.024, 0.02, sides=6)
        b.sphere("wood", V(sx * 0.34, -2.5, 1.72), (0.05, 0.05, 0.05), u=6, v=4)
    b.tube("metal", V(0.18, -2.0, FLOOR), V(0.2, -2.15, 1.55), 0.022, 0.02, sides=6)     # emergency brake
    b.sphere("lamp_red", V(0.2, -2.15, 1.58), (0.06, 0.06, 0.06), u=6, v=4)
    b.tube("brass", V(0, -3.45, EAVE), V(0, -3.45, EAVE - 0.1), 0.015, 0.015, sides=6)   # bell
    b.tube("brass", V(0, -3.45, EAVE - 0.1), V(0, -3.45, EAVE - 0.3), 0.06, 0.15, sides=10)
    # The conductor's brake wheel on the rear platform.
    b.tube("metal", V(0.5, 3.55, FLOOR), V(0.5, 3.55, 1.35), 0.03, 0.03, sides=6)
    b.tube("metal", V(0.5, 3.55, 1.35), V(0.5, 3.55, 1.37), 0.15, 0.15, sides=12)


def car_lamps(b):
    yf = -CAR_L - 0.01
    b.tube("metal", V(0, yf + 0.1, 1.2), V(0, yf - 0.06, 1.2), 0.16, 0.16, sides=14)
    b.tube("light_head", V(0, yf - 0.06, 1.2), V(0, yf - 0.075, 1.2), 0.12, 0.12, sides=14)
    yr = CAR_L + 0.01
    for sx in (-1, 1):
        b.tube("lamp_red", V(sx * 0.6, yr - 0.1 * 0.3, 1.25), V(sx * 0.6, yr + 0.05, 1.25), 0.07, 0.07, sides=10)
    b.tube("metal", V(0, yr - 0.1, 1.2), V(0, yr + 0.05, 1.2), 0.12, 0.12, sides=12)
    b.tube("light_head", V(0, yr + 0.05, 1.2), V(0, yr + 0.06, 1.2), 0.09, 0.09, sides=12)


def car_wheelset(b, y):
    for sx in (-1, 1):
        x = sx * GAUGE_X
        b.tube("wheel", V(x + sx * 0.05, y, WHEEL_R), V(x - sx * 0.03, y, WHEEL_R), WHEEL_R, WHEEL_R, sides=16)
        b.tube("wheel", V(x - sx * 0.03, y, WHEEL_R), V(x - sx * 0.055, y, WHEEL_R), WHEEL_R + 0.03, WHEEL_R + 0.03, sides=16)
        b.tube("metal", V(x + sx * 0.055, y, WHEEL_R), V(x + sx * 0.07, y, WHEEL_R), 0.1, 0.07, sides=10)
    b.tube("metal", V(-GAUGE_X, y, WHEEL_R), V(GAUGE_X, y, WHEEL_R), 0.05, 0.05, sides=8)


def build_cable_car():
    mats = C.make_materials(CAR_PALETTE)
    roles = list(CAR_PALETTE)
    root = C.empty("cable_car")
    b = C.Builder(roles)
    car_floor(b)
    car_dash(b, -1, 1.55)
    car_windscreen(b, -1)
    car_dash(b, 1, 1.42)
    for sx in (-1, 1):
        car_cabin_side(b, sx)
        car_open_section(b, sx)
        car_rear_platform(b, sx)
        car_running_board(b, sx)
    car_bulkhead(b, -1, CABIN[0])
    car_bulkhead(b, 1, CABIN[1])
    for sx in (-1, 1):  # rear platform's end poles carry the roof over the open back
        b.tube("brass", V(sx * 0.45, CAR_L - 0.08, 1.49), V(sx * 0.45, CAR_L - 0.08, EAVE + 0.05), 0.024, 0.024, sides=8)
    car_roof(b)
    car_running_gear(b)
    car_controls(b)
    car_lamps(b)
    parts = [part(b, "body", mats, root)]
    for name, y in zip(("wheel_F1", "wheel_F2", "wheel_R1", "wheel_R2"), AXLES):
        wb = C.Builder(roles)
        car_wheelset(wb, y)
        parts.append(part(wb, name, mats, root, pivot=(0, y, WHEEL_R)))
    return root, parts


# --- cable car track ---------------------------------------------------------------------

TRACK_PALETTE = {"rail": 0xB9BEC4, "slot_rail": 0x8C9197, "slot": 0x141416, "groove": 0x2A2B2F}


def build_track():
    mats = C.make_materials(TRACK_PALETTE)
    root = C.empty("cable_car_track")
    b = C.Builder(list(TRACK_PALETTE))
    L = 10.0
    for sx in (-1, 1):
        b.box("rail", (0.065, L, 0.014), V(sx * GAUGE_X, 0, 0.003))
        b.box("groove", (0.04, L, 0.01), V(sx * (GAUGE_X - 0.055), 0, 0.001))      # flangeway
        b.box("slot_rail", (0.08, L, 0.012), V(sx * 0.055, 0, 0.002))
    b.box("slot", (0.03, L, 0.012), V(0, 0, 0.002))
    return root, [part(b, "track", mats, root)]


# --- street lamp ------------------------------------------------------------------------

LAMP_PALETTE = {"pole": 0x2E5A53, "trim": 0x23443F, "light_head": 0xFFF0C0, "ink": INK}


def build_lamp():
    mats = C.make_materials(LAMP_PALETTE)
    root = C.empty("street_lamp")
    b = C.Builder(list(LAMP_PALETTE))
    # Octagonal cast base, then a fluted shaft tapering to a collar under the arm.
    loft(b, "pole", [V(0, 0, 0), V(0, 0, 0.12), V(0, 0, 0.75), V(0, 0, 1.05)], [0.24, 0.22, 0.17, 0.12],
         sides=8, spin=math.pi / 8)
    b.tube("trim", V(0, 0, 0.72), V(0, 0, 0.8), 0.2, 0.2, sides=8, spin=math.pi / 8)
    flute = lambda i, j: 1.0 if j % 2 == 0 else 0.86  # noqa: E731
    loft(b, "pole", [V(0, 0, 1.0), V(0, 0, 4.0), V(0, 0, 7.3)], [0.11, 0.095, 0.075], sides=12, prof=flute)
    for z, r in ((1.05, 0.13), (3.0, 0.11), (7.25, 0.1)):
        b.tube("trim", V(0, 0, z), V(0, 0, z + 0.07), r, r, sides=10)
    b.tube("pole", V(0, 0, 7.32), V(0, 0, 7.62), 0.08, 0.035, sides=8)
    b.sphere("trim", V(0, 0, 7.68), (0.06, 0.06, 0.07), u=8, v=4)
    # The arm: a quarter circle up and out of the shaft, then level out over the street.
    R0, z0 = 0.6, 6.95
    arm = [V(R0 - R0 * math.cos(a), 0, z0 + R0 * math.sin(a)) for a in np.linspace(0, math.pi / 2, 6)]
    end = V(1.6, 0, z0 + R0 - 0.04)
    arm.append(end)
    loft(b, "pole", arm, [0.05] * (len(arm) - 1) + [0.042], sides=6)
    b.sphere("trim", end + V(0.05, 0, 0), (0.06, 0.06, 0.06), u=6, v=4)
    # A scroll brace under the arm: a sweep from the shaft ending in a curl.
    brace = [V(0.05, 0, 6.25), V(0.2, 0, 6.6), V(0.45, 0, 6.85)]
    brace += [V(0.62 + 0.13 * math.cos(a), 0, 6.98 + 0.13 * math.sin(a)) for a in np.linspace(-2.4, 2.2, 6)]
    loft(b, "trim", brace, [0.024] * len(brace), sides=6)
    b.tube("trim", V(1.0, 0, z0 + R0 - 0.02), V(0.7, 0, 6.88), 0.02, 0.02, sides=6)
    # The lantern hangs from the end of the arm: cap, glass, base and finial.
    lx = end.x - 0.06
    b.tube("pole", V(lx, 0, end.z), V(lx, 0, 7.5), 0.03, 0.03, sides=6)
    loft(b, "pole", [V(lx, 0, 7.52), V(lx, 0, 7.4), V(lx, 0, 7.36)], [0.06, 0.3, 0.3], sides=8, spin=math.pi / 8)
    loft(b, "light_head", [V(lx, 0, 7.36), V(lx, 0, 6.88)], [0.23, 0.16], sides=8, spin=math.pi / 8)
    for j in range(8):
        a = math.pi / 8 + 2 * math.pi * j / 8
        d = V(math.cos(a), math.sin(a), 0)
        bar(b, "pole", V(lx, 0, 7.36) + d * 0.23, V(lx, 0, 6.88) + d * 0.16, d, w=0.03, d=0.01, sink=0.01)
    loft(b, "pole", [V(lx, 0, 6.88), V(lx, 0, 6.82), V(lx, 0, 6.7)], [0.18, 0.15, 0.0], sides=8, spin=math.pi / 8)
    return root, [part(b, "lamp", mats, root)]


# --- trolley and utility poles -------------------------------------------------------------

TROLLEY_PALETTE = {"metal": 0x6E747A, "trim": 0x4A4F55, "band": 0xE3C340, "ink": INK}


def build_trolley_pole():
    mats = C.make_materials(TROLLEY_PALETTE)
    root = C.empty("trolley_pole")
    b = C.Builder(list(TROLLEY_PALETTE))
    b.box("trim", (0.5, 0.5, 0.04), V(0, 0, 0.02))
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.tube("trim", V(sx * 0.18, sy * 0.18, 0.04), V(sx * 0.18, sy * 0.18, 0.1), 0.025, 0.025, sides=6)
    b.tube("trim", V(0, 0, 0.04), V(0, 0, 0.6), 0.2, 0.17, sides=12)
    loft(b, "metal", [V(0, 0, 0.6), V(0, 0, 4.5), V(0, 0, 9.0)], [0.16, 0.13, 0.1], sides=12)
    b.tube("band", V(0, 0, 2.2), V(0, 0, 2.5), 0.155, 0.155, sides=12)            # painted band
    b.sphere("trim", V(0, 0, 9.03), (0.11, 0.11, 0.09), u=10, v=4)
    # Span-wire clamp near the top with an eye facing the street (-Y, game +Z).
    b.tube("trim", V(0, 0, 8.5), V(0, 0, 8.62), 0.125, 0.125, sides=12)
    b.box("trim", (0.04, 0.2, 0.08), V(0, -0.2, 8.56))
    b.tube("trim", V(-0.02, -0.32, 8.56), V(0.02, -0.32, 8.56), 0.05, 0.05, sides=8)
    wire = C.empty("wire", V(0, -0.32, 8.56), root)
    return root, [part(b, "pole", mats, root), wire]


UTILITY_PALETTE = {"wood": 0x7A5A3C, "wood_dark": 0x5E4530, "metal": 0x777C82, "insulator": 0x8CC4B0, "ink": INK}


def build_utility_pole():
    mats = C.make_materials(UTILITY_PALETTE)
    root = C.empty("utility_pole")
    b = C.Builder(list(UTILITY_PALETTE))
    loft(b, "wood", [V(0, 0, 0), V(0, 0, 5.0), V(0, 0, 10.4)], [0.17, 0.145, 0.12], sides=10)
    b.sphere("wood_dark", V(0, 0, 10.4), (0.12, 0.12, 0.04), u=10, v=3)
    # Grain: a few ink checks up the pole, as an artist would scratch them in.
    for z0, z1, a in ((1.0, 2.3, 0.3), (3.4, 4.2, 2.1), (5.6, 6.9, 4.0), (7.4, 8.0, 1.2)):
        d = V(math.cos(a), math.sin(a), 0)
        bar(b, "wood_dark", d * 0.16 + V(0, 0, z0), d * 0.15 + V(0, 0, z1), d, w=0.025, d=0.008, sink=0.02)
    # Step bolts.
    for k, z in enumerate(np.arange(2.6, 9.0, 0.6)):
        a = math.pi / 2 if k % 2 else -math.pi / 2
        d = V(math.cos(a), math.sin(a), 0)
        b.tube("metal", d * 0.12 + V(0, 0, float(z)), d * 0.3 + V(0, 0, float(z)), 0.014, 0.014, sides=4)
    # Crossarm with braces and four pin insulators.
    za = 9.7
    b.box("wood", (2.4, 0.1, 0.12), V(0, -0.17, za), bevel=0.01)
    for sx in (-1, 1):
        b.tube("metal", V(0, -0.14, za - 0.65), V(sx * 0.6, -0.15, za - 0.06), 0.015, 0.015, sides=4)
    wires = []
    for k, x in enumerate((-1.1, -0.45, 0.45, 1.1)):
        base = V(x, -0.17, za + 0.06)
        b.tube("metal", base, base + V(0, 0, 0.08), 0.015, 0.015, sides=6)
        loft(b, "insulator", [base + V(0, 0, 0.08), base + V(0, 0, 0.13), base + V(0, 0, 0.18),
                              base + V(0, 0, 0.26)], [0.05, 0.075, 0.05, 0.045], sides=6)
        wires.append(C.empty(f"wire_{k}", base + V(0, 0, 0.24), root))
    # A pole-top transformer can on the back.
    b.tube("metal", V(0, 0.42, 7.6), V(0, 0.42, 8.5), 0.24, 0.24, sides=10)
    b.tube("metal", V(0, 0.42, 8.5), V(0, 0.42, 8.56), 0.26, 0.2, sides=10)
    b.box("metal", (0.12, 0.2, 0.5), V(0, 0.2, 8.0))
    b.tube("insulator", V(0, 0.42, 8.56), V(0, 0.42, 8.72), 0.04, 0.03, sides=6)
    for z in (7.75, 8.35):
        b.tube("ink", V(0, 0.42, z), V(0, 0.42, z + 0.025), 0.245, 0.245, sides=10)
    return root, [part(b, "pole", mats, root), *wires]


# --- Muni shelter ---------------------------------------------------------------------------

SHELTER_PALETTE = {"frame": 0x3C4248, "glass": 0xBFDCE4, "glint": 0xF4FAFB, "roof": 0x9EA7AD,
                   "bench": 0x70777E, "ad_panel": 0xF0C35A, "ink": INK}


def glass_panel(b, p0, p1, z0, z1, normal, glint=True):
    """A pane with a thin frame and two diagonal anime glints."""
    p0, p1 = Vector(p0), Vector(p1)
    along = (p1 - p0)
    L = along.length
    c = (p0 + p1) / 2 + V(0, 0, (z0 + z1) / 2)
    rot = surface_rot(along, normal)
    b.box("glass", (L, 0.02, z1 - z0), c, rot=rot @ Matrix.Rotation(math.pi / 2, 4, "X"))
    if glint:
        u = along.normalized()
        for t, w in ((0.25, 0.07), (0.38, 0.03)):
            a = p0 + u * L * t + V(0, 0, z0 + 0.25 * (z1 - z0))
            bb = a + u * 0.45 + V(0, 0, 0.45 * (z1 - z0))
            for s in (1, -1):
                bar(b, "glint", a, bb, Vector(normal) * s, w=w, d=0.006, sink=-0.008)


def build_shelter():
    mats = C.make_materials(SHELTER_PALETTE)
    root = C.empty("muni_shelter")
    b = C.Builder(list(SHELTER_PALETTE))
    X, YB, YF, H = 1.95, 0.7, -0.55, 2.4       # half length, back and side-panel front, post height
    # Posts.
    for x in (-X, 0.0, X):
        b.box("frame", (0.08, 0.08, H), V(x, YB, H / 2))
    b.box("frame", (0.08, 0.08, H), V(-X, YF, H / 2))
    # Back wall: two glass bays with rails.
    for xa, xb in ((-X, 0.0), (0.0, X)):
        glass_panel(b, V(xa + 0.04, YB, 0), V(xb - 0.04, YB, 0), 0.16, 2.25, V(0, -1, 0))
    for z in (0.12, 1.0, 2.28):
        b.box("frame", (2 * X, 0.06, 0.06), V(0, YB, z))
    # Left side glass; right side the double-sided ad box.
    glass_panel(b, V(-X, YF + 0.04, 0), V(-X, YB - 0.04, 0), 0.16, 2.25, V(-1, 0, 0))
    for z in (0.12, 2.28):
        b.box("frame", (0.06, YB - YF, 0.06), V(-X, (YB + YF) / 2, z))
    b.box("frame", (0.22, YB - YF + 0.08, 2.2), V(X, (YB + YF) / 2, 1.2), bevel=0.02)
    for s in (-1, 1):
        b.box("ad_panel", (0.02, YB - YF - 0.16, 1.7), V(X + s * 0.11, (YB + YF) / 2, 1.25))
    b.box("frame", (0.3, YB - YF + 0.14, 0.12), V(X, (YB + YF) / 2, 0.06))
    # The roof: a shallow vault cantilevered towards the kerb.
    rows, cols = 10, 6
    grid = [[V(-X - 0.15 + (2 * X + 0.3) * j / cols, 0.85 - 1.85 * i / rows,
               2.48 + 0.2 * (1 - ((0.85 - 1.85 * i / rows + 0.075) / 0.925) ** 2)) for j in range(cols + 1)]
            for i in range(rows + 1)]
    grid_slab(b, "roof", "frame", grid, 0.05)
    for x in (-X, 0.0, X):
        b.box("frame", (0.06, 0.14, 0.2), V(x, YB, H + 0.08))
    b.box("frame", (2 * X + 0.3, 0.05, 0.06), V(0, -1.0, 2.46))                  # roof edge beam
    # Bench: three slats on two legs, against the back wall.
    for k in range(3):
        b.box("bench", (2.0, 0.1, 0.035), V(-0.75, YB - 0.12 - 0.12 * k, 0.46), bevel=0.008)
    for x in (-1.6, 0.1):
        b.box("frame", (0.05, 0.36, 0.05), V(x, YB - 0.24, 0.42))
        b.box("frame", (0.05, 0.05, 0.42), V(x, YB - 0.38, 0.21))
    return root, [part(b, "shelter", mats, root)]


# --- small street furniture --------------------------------------------------------------------

BENCH_PALETTE = {"wood": 0xA8743F, "frame": 0x2F4A3C, "ink": INK}


def build_bench():
    mats = C.make_materials(BENCH_PALETTE)
    root = C.empty("bench")
    b = C.Builder(list(BENCH_PALETTE))
    L = 1.8
    # Cast iron ends: a side profile (y, z) with legs, seat and a raked back.
    end = [(-0.3, 0.0), (-0.22, 0.0), (-0.18, 0.36), (0.12, 0.36), (0.2, 0.0), (0.28, 0.0), (0.24, 0.44),
           (0.3, 0.9), (0.24, 0.92), (0.16, 0.48), (-0.28, 0.48)]
    for sx in (-1, 1):
        frame = Matrix.Translation(V(sx * (L / 2 - 0.1), 0, 0)) @ Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
        b.prism("frame", end, 0.06, frame)
    for k in range(4):
        b.box("wood", (L, 0.1, 0.035), V(0, -0.25 + 0.115 * k, 0.5), bevel=0.008)
    for k in range(3):
        z = 0.58 + 0.12 * k
        y = 0.19 + 0.12 * (z - 0.48) / 0.44 + 0.03
        b.box("wood", (L, 0.035, 0.09), V(0, y, z), rot=Matrix.Rotation(math.radians(-12), 4, "X"), bevel=0.008)
    b.box("frame", (L - 0.2, 0.03, 0.03), V(0, -0.05, 0.4))
    return root, [part(b, "body", mats, root)]


PLANTER_PALETTE = {"concrete": 0xCFC7B5, "cap": 0xE4DDCC, "soil": 0x5A4030,
                   "leaf_light": 0x9CCB47, "leaf_dark": 0x3E7F3C, "ink": INK}


def build_planter():
    mats = C.make_materials(PLANTER_PALETTE)
    root = C.empty("planter")
    b = C.Builder(list(PLANTER_PALETTE))
    S, H, T = 1.4, 0.45, 0.12
    for sx, sy, w, d in ((0, -1, S, T), (0, 1, S, T), (-1, 0, T, S - 2 * T), (1, 0, T, S - 2 * T)):
        b.box("concrete", (w, d, H), V(sx * (S - T) / 2, sy * (S - T) / 2, H / 2))
        b.box("cap", (w + 0.04 if sy else w + 0.04, d + 0.04 if sx else d + 0.04, 0.05),
              V(sx * (S - T) / 2, sy * (S - T) / 2, H + 0.02), bevel=0.01)
    b.box("soil", (S - 2 * T, S - 2 * T, 0.05), V(0, 0, H - 0.08))
    for sx in (-1, 1):
        bar(b, "ink", V(sx * S / 2, -0.15, 0.02), V(sx * S / 2, -0.05, H - 0.02), V(sx, 0, 0), w=0.012, d=0.004)
    box = part(b, "box", mats, root)
    f = Foliage(PLANTER_PALETTE, (0, 0, 0.2))
    rng = random.Random(7)
    for k in range(7):
        a = 2 * math.pi * k / 7 + 0.4
        r = 0.43 + 0.04 * (k % 2)
        f.clump("leaf_light" if k % 3 else "leaf_dark", V(r * math.cos(a), r * math.sin(a), H + 0.04),
                (0.17, 0.17, 0.13), rng, u=7, rings=3, jag=0.25)
    return root, [box, f.to_object("shrubs", mats, root)]


HYDRANT_PALETTE = {"body": 0xF1EEE6, "cap": 0x2F6FC0, "metal": 0x5F646A, "ink": INK}


def build_hydrant():
    mats = C.make_materials(HYDRANT_PALETTE)
    root = C.empty("fire_hydrant")
    b = C.Builder(list(HYDRANT_PALETTE))
    b.tube("body", V(0, 0, 0), V(0, 0, 0.08), 0.2, 0.19, sides=12)
    for z in (0.09, 0.5):
        b.tube("body", V(0, 0, z), V(0, 0, z + 0.04), 0.17, 0.17, sides=12)          # flanges
        for j in range(6):
            a = 2 * math.pi * j / 6
            b.box("metal", (0.025, 0.025, 0.03), V(0.165 * math.cos(a), 0.165 * math.sin(a), z + 0.05))
    loft(b, "body", [V(0, 0, 0.08), V(0, 0, 0.3), V(0, 0, 0.62)], [0.14, 0.135, 0.13], sides=12, caps=(False, False))
    # Bonnet dome and the pentagon operating nut.
    loft(b, "cap", [V(0, 0, 0.6), V(0, 0, 0.66), V(0, 0, 0.74), V(0, 0, 0.79)], [0.16, 0.155, 0.12, 0.05], sides=12)
    b.tube("cap", V(0, 0, 0.78), V(0, 0, 0.84), 0.045, 0.04, sides=5)
    b.tube("body", V(0, 0, 0.6), V(0, 0, 0.63), 0.175, 0.175, sides=12)
    # Two hose outlets on the sides and the big pumper outlet on the front, capped.
    for d, r, L in ((V(1, 0, 0), 0.055, 0.1), (V(-1, 0, 0), 0.055, 0.1), (V(0, -1, 0), 0.075, 0.09)):
        c = V(0, 0, 0.42)
        b.tube("body", c + d * 0.1, c + d * (0.1 + L), r, r, sides=10)
        b.tube("cap", c + d * (0.1 + L), c + d * (0.13 + L), r + 0.012, r + 0.012, sides=10)
        b.tube("cap", c + d * (0.13 + L), c + d * (0.15 + L), 0.025, 0.025, sides=5)
    bar(b, "ink", V(0, -0.135, 0.2), V(0, -0.132, 0.3), V(0, -1, 0), w=0.012, d=0.004)
    return root, [part(b, "hydrant", mats, root)]


# --- trees ----------------------------------------------------------------------------------

def fib_dirs(n, z_min=-1.0):
    out = []
    golden = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        if z < z_min:
            continue
        r = math.sqrt(1 - z * z)
        out.append(V(r * math.cos(golden * i), r * math.sin(golden * i), z))
    return out


def leaf_role(d, light=0.35, dark=-0.25):
    """Upper clumps catch the sun, the underside stays in shade."""
    s = d.z + 0.25 * d.x - 0.2 * d.y
    return "leaf_light" if s > light else ("leaf_dark" if s < dark else "leaf_mid")


PLANE_PALETTE = {"bark": 0x8B8466, "bark_light": 0xCFC79D, "leaf_light": 0x9DCB45,
                 "leaf_mid": 0x5FA13B, "leaf_dark": 0x2F6B3A, "ink": INK}


def build_tree_plane():
    mats = C.make_materials(PLANE_PALETTE)
    root = C.empty("tree_plane")
    rng = random.Random(11)
    b = C.Builder(list(PLANE_PALETTE))
    # The London plane's camouflage bark: patches of cream over olive grey.
    camo = lambda i, j: "bark_light" if (i * 3 + j * 2 + (i * j) % 3) % 5 in (0, 3) else "bark"  # noqa: E731
    trunk = [V(0, 0, 0), V(0.03, 0, 0.5), V(0.06, 0.02, 1.1), V(0.04, 0.05, 1.7), V(0, 0.04, 2.3), V(0, 0, 2.6)]
    loft(b, "bark", trunk, [0.3, 0.23, 0.21, 0.2, 0.19, 0.17], sides=10, mat_fn=camo)
    limbs = [(V(1.6, 0.3, 4.6), 0.0), (V(-1.2, 1.2, 4.9), 0.0), (V(-0.6, -1.5, 4.5), 0.0), (V(0.3, 0.1, 5.3), 0.0)]
    for tip, _ in limbs:
        base = V(0, 0, 2.4)
        mid = base.lerp(tip, 0.5) + V(0, 0, 0.25)
        loft(b, "bark", [base, mid, tip], [0.13, 0.09, 0.05], sides=8, mat_fn=lambda i, j: camo(i + 2, j))
    for tip, base in ((V(2.2, -0.6, 5.0), V(1.0, 0.2, 3.9)), (V(-2.0, 0.2, 4.6), V(-0.7, 0.8, 3.9))):
        loft(b, "bark", [base, tip], [0.06, 0.03], sides=6)
    trunk_obj = part(b, "trunk", mats, root)

    crown = V(0, 0, 4.75)
    f = Foliage(PLANE_PALETTE, crown)
    # An irregular crown: a few lobes, each a shell of small star-shaped clumps.
    for d in fib_dirs(64, z_min=-0.55):
        d = (d + V(rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15), 0)).normalized()
        lobe = 1.0 + 0.16 * math.sin(3 * math.atan2(d.y, d.x) + 0.7) + 0.08 * d.z
        c = crown + V(d.x * 2.6 * lobe, d.y * 2.6 * lobe, d.z * 1.75 * lobe)
        r = rng.uniform(0.6, 0.78)
        f.clump(leaf_role(d), c, (r, r, r * 0.85), rng, u=7, rings=3, jag=0.42)
    for c in (V(0.6, 0.3, 4.3), V(-0.7, -0.2, 4.5)):
        f.clump("leaf_dark", crown + (c - V(0, 0, 4.75)), (1.5, 1.5, 1.1), rng, jag=0.15)
    return root, [trunk_obj, f.to_object("leaves", mats, root)]


CYPRESS_PALETTE = {"bark": 0x6E5440, "bark_light": 0x8E735A, "leaf_light": 0x6FA344,
                   "leaf_mid": 0x447F3D, "leaf_dark": 0x264F34, "ink": INK}


def build_tree_cypress():
    mats = C.make_materials(CYPRESS_PALETTE)
    root = C.empty("tree_cypress")
    rng = random.Random(23)
    b = C.Builder(list(CYPRESS_PALETTE))
    ridges = lambda i, j: 1.0 if j % 2 == 0 else 0.88  # noqa: E731
    shade = lambda i, j: "bark_light" if (j + i) % 4 == 0 else "bark"  # noqa: E731
    # Rises plumb out of the ground (so the base ring sits flat), then leans downwind.
    trunk = [V(0, 0, 0), V(0, 0, 0.3), V(0.1, 0, 0.8), V(0.3, 0.1, 1.6), V(0.5, 0.05, 2.1)]
    loft(b, "bark", trunk, [0.55, 0.47, 0.42, 0.4, 0.36], sides=12, prof=ridges, mat_fn=shade, twist=0.15)
    # The wind (from -X) has bent every limb downwind and flattened the top.
    limbs = [
        [V(0.5, 0.05, 2.0), V(1.4, 0.4, 3.4), V(2.8, 0.7, 4.4), V(4.0, 0.9, 5.0)],
        [V(0.45, 0.0, 2.0), V(0.8, -0.7, 3.8), V(1.8, -1.2, 5.6), V(2.6, -1.4, 7.0)],
        [V(0.4, 0.1, 2.0), V(0.2, 0.9, 4.0), V(0.6, 1.4, 6.0), V(1.4, 1.6, 7.6)],
        [V(0.4, 0.0, 2.0), V(-0.4, -0.2, 4.2), V(-0.7, -0.4, 6.4), V(-0.3, -0.5, 8.0)],
    ]
    for pts in limbs:
        loft(b, "bark", pts, [0.28, 0.2, 0.14, 0.08], sides=8, prof=ridges, mat_fn=shade, twist=0.2)
    trunk_obj = part(b, "trunk", mats, root)

    crown = V(1.2, 0, 7.4)
    f = Foliage(CYPRESS_PALETTE, crown)
    # Pads in tiers along the limbs, and a broad flat table on top, longer downwind.
    pads = []
    for tip, n, spread in ((limbs[0][-1], 3, 1.0), (limbs[1][-1], 3, 1.1), (limbs[2][-1], 3, 1.0), (limbs[3][-1], 2, 0.9)):
        for k in range(n):
            a = 2 * math.pi * k / n + rng.uniform(0, 1)
            pads.append((tip + V(spread * math.cos(a), spread * math.sin(a), rng.uniform(-0.2, 0.3)), 1.0))
    for k in range(10):
        x = -1.6 + 6.2 * (k % 5) / 4 + rng.uniform(-0.3, 0.3)
        y = (-0.9 if k < 5 else 0.9) + rng.uniform(-0.3, 0.3)
        pads.append((V(x, y, 9.1 - 0.12 * abs(x - 1.2) + rng.uniform(-0.15, 0.1)), 1.15))
    for c, s in pads:
        d = (c - crown)
        d = V(d.x / 4, d.y / 3, d.z / 2).normalized()
        rx = rng.uniform(1.4, 1.8) * s
        top = c.z > 8.6
        f.clump("leaf_light" if top else leaf_role(d, 0.5, -0.1), c, (rx, rx * 0.8, 0.62 if top else 0.75),
                rng, u=11, rings=3, jag=0.3, under=0.55, bias=0.45)
    for c in (V(0.6, 0, 6.8), V(2.4, 0.2, 7.4)):
        f.clump("leaf_dark", c, (1.6, 1.4, 1.0), rng, jag=0.15)
    return root, [trunk_obj, f.to_object("leaves", mats, root)]


PALM_PALETTE = {"bark": 0x8C6A45, "bark_light": 0xB08E62, "knob": 0x9B7A3E, "leaf_light": 0x9CC24A,
                "leaf_mid": 0x5F9A3C, "leaf_dark": 0x3A6E37, "ink": INK}
PALM_TOP = 6.2


def frond(f, mat, start, azim, elev, length, droop, width, rng, stations=7):
    """One feather frond: a lens-section ribbon arching out and down, its width
    zig-zagging so the outline reads as leaflets. Normals point up off the frond and
    out from the crown."""
    h = V(math.cos(azim), math.sin(azim), 0)
    side = V(-h.y, h.x, 0)
    pts, nrm, faces, centres = [], [], [], []
    rows, spine = [], []
    for i in range(stations + 1):
        t = i / stations
        p = start + h * length * t * math.cos(elev) + V(0, 0, length * t * math.sin(elev) - droop * length * t * t)
        spine.append(p)
        if i == stations:
            rows.append([len(pts)])
            pts.append(p)
            nrm.append(h)
            continue
        tan = h * math.cos(elev) + V(0, 0, math.sin(elev) - 2 * droop * t)
        up = side.cross(tan).normalized()
        w = width * (0.35 + 0.65 * math.sin(math.pi * min(1.0, t * 1.15))) * (1.0 if i % 2 else 0.62)
        if i == 0:
            w = 0.08
        out = (p - f.crown).normalized()
        base = len(pts)
        for q, n in ((p + side * w - up * w * 0.3, up * 0.5 + out * 0.5 + side * 0.2),
                     (p + up * 0.05, up * 0.6 + out * 0.4),
                     (p - side * w - up * w * 0.3, up * 0.5 + out * 0.5 - side * 0.2),
                     (p - up * 0.05, out * 0.7 - up * 0.3)):
            pts.append(q)
            nrm.append(n)
        rows.append([base, base + 1, base + 2, base + 3])
    for i in range(stations):
        r0, r1 = rows[i], rows[i + 1]
        for k in range(4):
            kn = (k + 1) % 4
            if len(r1) == 1:
                faces.append((r0[k], r0[kn], r1[0]))
                # The tip face: wind it away from the last section's centre, set back.
                centres.append(spine[i] - (spine[i + 1] - spine[i]) * 0.5)
            else:
                faces.append((r0[k], r0[kn], r1[kn], r1[k]))
                centres.append((spine[i] + spine[i + 1]) / 2)
    faces.append(tuple(rows[0]))
    centres.append(spine[0] + (spine[1] - spine[0]) * 0.5)
    f.sheet(mat, pts, nrm, faces, centres)


def build_tree_palm():
    mats = C.make_materials(PALM_PALETTE)
    root = C.empty("tree_palm")
    rng = random.Random(31)
    b = C.Builder(list(PALM_PALETTE))
    # The trunk's diamond leaf-base pattern: rings turned half a side each step, in
    # alternating tones, with a slight bulge at each ring.
    n = 15
    pts = [V(0.02 * math.sin(i * 0.5), 0, PALM_TOP * i / n) for i in range(n + 1)]
    radii = [0.58 if i == 0 else 0.44 - 0.03 * i / n for i in range(n + 1)]
    diamonds = lambda i, j: "bark_light" if (i + j) % 2 == 0 else "bark"  # noqa: E731
    bulge = lambda i, j: 1.0 if j % 2 == 0 else 1.08  # noqa: E731
    loft(b, "bark", pts, radii, sides=10, prof=bulge, mat_fn=diamonds, stagger=True)
    trunk_obj = part(b, "trunk", mats, root)

    crown = V(0, 0, PALM_TOP + 0.7)
    f = Foliage(PALM_PALETTE, crown)
    # The "pineapple": a ball of old frond bases where the crown springs.
    f.clump("knob", V(0, 0, PALM_TOP + 0.45), (0.78, 0.78, 0.7), rng, u=10, rings=4, jag=0.18, bias=0.0)
    tiers = [  # (count, elevation deg, length, droop, width, role, phase)
        (8, 58, 3.6, 0.42, 0.55, "leaf_light", 0.0),
        (13, 38, 4.8, 0.5, 0.68, "leaf_light", 0.3),
        (13, 16, 5.0, 0.5, 0.68, "leaf_mid", 0.1),
        (10, -6, 4.4, 0.42, 0.62, "leaf_dark", 0.5),
    ]
    for count, elev, length, droop, width, role, phase in tiers:
        for k in range(count):
            az = 2 * math.pi * (k + phase + rng.uniform(-0.15, 0.15)) / count
            h = V(math.cos(az), math.sin(az), 0)
            start = crown + h * 0.35 + V(0, 0, 0.25 + 0.3 * math.sin(math.radians(elev)))
            mat = role if role != "leaf_light" or k % 3 else "leaf_mid"
            frond(f, mat, start, az, math.radians(elev + rng.uniform(-6, 6)), length * rng.uniform(0.9, 1.05),
                  droop, width, rng)
    return root, [trunk_obj, f.to_object("leaves", mats, root)]


# --- build, export, render -------------------------------------------------------------------

PROPS = {
    # name: (builder, triangle budget, preview outline width)
    "cable_car": (build_cable_car, 16000, 0.02),
    "cable_car_track": (build_track, 400, 0.005),
    "street_lamp": (build_lamp, 800, 0.012),
    "trolley_pole": (build_trolley_pole, 800, 0.012),
    "utility_pole": (build_utility_pole, 800, 0.012),
    "muni_shelter": (build_shelter, 2000, 0.012),
    "tree_plane": (build_tree_plane, 3000, 0.03),
    "tree_cypress": (build_tree_cypress, 3000, 0.035),
    "tree_palm": (build_tree_palm, 3000, 0.012),
    "bench": (build_bench, 600, 0.008),
    "planter": (build_planter, 1000, 0.01),
    "fire_hydrant": (build_hydrant, 800, 0.006),
}


def build_prop(name):
    C.reset_scene()
    builder, budget, outline = PROPS[name]
    root, parts = builder()
    meshes = [p for p in parts if p.type == "MESH"]
    C.report(parts)
    tris = C.triangle_count(meshes)
    assert tris <= budget, f"{name} has {tris} triangles, over its budget of {budget}"
    (C.MODELS_DIR / STREET).mkdir(parents=True, exist_ok=True)
    C.export_glb(f"{STREET}/{name}")
    views = (("3/4 front", -35), ("side", -90), ("back 3/4", 145)) if name.startswith("tree") else \
        (("front", 0), ("3/4 front", -35), ("side", -90), ("back", 180))
    tall = name.startswith(("cable", "street_lamp")) or name.endswith("_pole")
    C.render_contact_sheet(root, f"street-{name}", outline=outline, views=views, fill=1.0 if tall else 0.85)


# The strip: (prop, x, y, turn in degrees). Road from y=-9 to the kerb at y=1.
STRIP = [
    ("street_lamp", -23.5, 1.7, -90), ("tree_plane", -20.5, 2.4, 0), ("planter", -20.5, 2.4, 0),
    ("trolley_pole", -16.5, 1.6, 0), ("fire_hydrant", -14.5, 1.6, 20),
    ("muni_shelter", -10.0, 4.0, 0), ("bench", -5.0, 4.4, 0), ("tree_palm", -0.5, 3.6, 0),
    ("utility_pole", 4.5, 1.7, 0), ("street_lamp", 8.0, 1.7, -90), ("tree_cypress", 13.5, 4.2, 0),
    ("tree_plane", 21.0, 2.4, 40), ("planter", 21.0, 2.4, 0), ("bench", 24.5, 4.4, 0),
]
KERB_H = 0.15


def strip_ground():
    pal = {"asphalt": 0x5B5F66, "kerb": 0xD8D2C4, "sidewalk": 0xC9C2B3, "line": 0xF2C230, "ink": INK}
    mats = C.make_materials(pal)
    b = C.Builder(list(pal))
    x0, x1 = -29.0, 29.0
    b.box("asphalt", (x1 - x0, 10.0, 0.1), V(0, -4.0, -0.05))
    b.box("kerb", (x1 - x0, 0.25, KERB_H + 0.1), V(0, 1.125, (KERB_H - 0.1) / 2))
    b.box("sidewalk", (x1 - x0, 5.0, KERB_H + 0.1), V(0, 3.75, (KERB_H - 0.1) / 2))
    for x in np.arange(x0 + 1.5, x1, 1.5):
        bar(b, "ink", V(float(x), 1.25, KERB_H), V(float(x), 6.25, KERB_H), V(0, 0, 1), w=0.02, d=0.003)
    for y in (-3.95, -4.15):
        b.box("line", (x1 - x0, 0.1, 0.01), V(0, y, 0.002))
    for x in np.arange(x0 + 1, x1, 4.0):
        b.box("line", (2.0, 0.12, 0.01), V(float(x) + 1, -1.5, 0.002))
    return R.to_object(b, "ground", mats)


def build_strip():
    """Every prop on a strip of road and sidewalk, a cable car on its track and the
    Wayfarer at the kerb for scale: docs/renders/street-kit.png."""
    C.reset_scene()
    world = C.empty("strip")
    strip_ground().parent = world
    placed = [(n, x, y, t, KERB_H) for n, x, y, t in STRIP]
    placed += [("cable_car_track", x, -6.6, 90, 0.0) for x in (-25.0, -15.0, -5.0, 5.0, 15.0, 25.0)]
    placed += [("cable_car", 15.0, -6.6, -90, 0.0)]
    for name, x, y, turn, z in placed:
        root, _ = PROPS[name][0]()
        root.parent = world
        root.location = (x, y, z)
        root.rotation_euler = (0, 0, math.radians(turn))
    before = set(world.children)
    R.import_cab("wayfarer", world, 0.0)
    for o in set(world.children) - before:
        o.rotation_mode = "XYZ"
        o.rotation_euler = (0, 0, math.radians(-90))
        o.location = (-3.0, -0.2, 0)
    render_wide(world, "street-kit", width=3000, height=1150, outline=0.028,
                target=V(-1.0, -1.0, 3.2), distance=41.0, elevation=9.0, lens=30.0, azimuth=-8.0)
    R.crop_to_content(C.RENDERS_DIR / "street-kit.png", margin=40)


def render_wide(world, name, width, height, outline, target, distance, elevation, lens, azimuth=0.0):
    """Like common.render_contact_sheet but one wide perspective shot of a laid-out scene."""
    scene = bpy.context.scene
    objs = [o for o in scene.objects if o.type == "MESH"]
    for m in {s.material for o in objs for s in o.material_slots if s.material}:
        if m.node_tree and "Principled BSDF" in m.node_tree.nodes:
            C.toonify(m)
    C.add_outlines(objs, outline)
    sun_data = bpy.data.lights.new("sun", "SUN")
    sun_data.energy = 3.0
    sun_data.angle = math.radians(1.0)
    sun = bpy.data.objects.new("sun", sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = lens
    cam_data.sensor_fit = "HORIZONTAL"
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    el, az = math.radians(elevation), math.radians(azimuth)
    cam.location = target + V(distance * math.cos(el) * math.sin(az), -distance * math.cos(el) * math.cos(az),
                              distance * math.sin(el))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (*[C.srgb_to_linear(c) for c in C.BG], 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    scene.world = w
    r = scene.render
    r.engine = "BLENDER_EEVEE"
    r.resolution_x, r.resolution_y = width, height
    r.film_transparent = True
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.eevee.taa_render_samples = 16
    tmp = C.RENDERS_DIR / f".{name}_tmp.png"
    r.filepath = str(tmp)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(tmp))
    img.colorspace_settings.name = "Non-Color"
    px = np.empty(width * height * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(height, width, 4)
    a = px[..., 3:4]
    rgb = px[..., :3] * a + np.array(C.BG, dtype=np.float32) * (1 - a)
    bpy.data.images.remove(img)
    tmp.unlink()
    R.save_rgb(rgb[::-1][::-1], C.RENDERS_DIR / f"{name}.png")


def check():
    """Reimport every glb: node names, triangle counts, bounds; reviews/street-kit.json."""
    out = {}
    for name, (_, budget, _) in PROPS.items():
        C.reset_scene()
        path = C.MODELS_DIR / STREET / f"{name}.glb"
        bpy.ops.import_scene.gltf(filepath=str(path))
        objs = list(bpy.context.scene.objects)
        meshes = [o for o in objs if o.type == "MESH"]
        pts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
        lo = [round(min(p[i] for p in pts), 3) for i in range(3)]
        hi = [round(max(p[i] for p in pts), 3) for i in range(3)]
        tris = C.triangle_count(meshes)
        mats = sorted({s.material.name for o in meshes for s in o.material_slots if s.material})
        out[name] = {
            "triangles": tris, "budget": budget,
            # Blender axes after import: X right, Y back (game -Z), Z up.
            "size_m": {"x": round(hi[0] - lo[0], 2), "length": round(hi[1] - lo[1], 2), "height": round(hi[2] - lo[2], 2)},
            "min_z": lo[2],
            "nodes": sorted(o.name for o in objs if o.parent is not None or o.type != "MESH"),
            "materials": mats,
        }
        assert tris <= budget, (name, tris)
        # The cable car's wheel flanges dip into the rails' flangeways, below the road.
        assert -(0.04 if name == "cable_car" else 0.02) < lo[2] < 0.02, (name, lo)
    n = out["cable_car"]["nodes"]
    assert {"body", "wheel_F1", "wheel_F2", "wheel_R1", "wheel_R2"} <= set(n), n
    assert "wire" in out["trolley_pole"]["nodes"]
    assert {f"wire_{k}" for k in range(4)} <= set(out["utility_pole"]["nodes"])
    for t in ("tree_plane", "tree_cypress", "tree_palm"):
        assert "trunk" in out[t]["nodes"], out[t]
    (REVIEWS / "street-kit.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


def main():
    arg = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "all"
    if arg == "strip":
        build_strip()
    elif arg == "check":
        check()
    elif arg == "all":
        for name in PROPS:
            build_prop(name)
    else:
        build_prop(arg)


if __name__ == "__main__":
    main()
