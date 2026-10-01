"""San Francisco landmarks for the city's landmark blocks, drawn in the robotaxis' and
street kit's manga cel style.

    blender --background --factory-startup --python landmarks.py -- <landmark>|all|check

Each landmark is built from scratch, exported to public/models/landmarks/<name>.glb and
rendered as a toon sheet (whole views and close-ups) at docs/renders/landmark-<name>.png;
`check` reimports the glbs, checks nodes, sizes and budgets, and writes
reviews/landmarks.json.

Conventions as the street kit: metres, Blender Z up, north +Y and east +X (the exporter
turns that into the game's +Y up with north -Z), origin on the ground at the footprint
centre. Flat role materials, normals split at 38 degrees, ink lines as thin dark plates
where an artist would draw them, and `light_*` materials for what glows at night (the
game draws those unlit). The sizes are the game's, not the real ones: the city is
compressed, so the towers are about half their real height but keep their proportions.
Blocks on a slope get a plinth: the models reach a few metres below their origin.

- salesfarce_tower: Salesforce Tower, a rounded-square shaft that tapers and curves in
  near the top, white fins and blue-grey glass bands, the open lattice crown (node
  `crown`, around a `light_crown` core) and the lobby and plaza. 165 m.
- pyramid: the Transamerica Pyramid, with rows of windows in its white faces, the
  elevator and stair wings on the east and west faces, the aluminium spire, and the
  sloping exoskeleton columns round the base. 120 m.
- ferry_building: the long arcaded hall with its arched windows, the Giralda clock tower
  (clock faces are `light_clock` discs) and the promenade on the bay side. 50 m tower.
- coit_tower: the fluted column, arched observation windows and crown, the base
  building with its arched door, and the round hilltop terrace. 33 m.
- golden_gate: two towers with stepped portal braces, the deck with its truss, the main
  cables and suspenders; origin at the water line midway between the towers.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import common as C  # noqa: E402
import robotaxis as R  # noqa: E402
import street_kit as S  # noqa: E402

SMOOTH = 38
DIR = "landmarks"
REVIEWS = Path(__file__).resolve().parent / "reviews"
INK = 0x1B1722
BUDGET = 20000
V = S.V


# --- modelling helpers ---------------------------------------------------------------------

class Builder(C.Builder):
    """common.Builder plus one-sided plates (window panes, painted bands) whose facing is
    given, not guessed: recalculating the normals of a lone quad can flip it."""

    def __init__(self, palette):
        super().__init__(list(palette))
        self.fixed = set()

    def plate(self, mat, pts, normal):
        f = self.bm.faces.new([self.bm.verts.new(Vector(p)) for p in pts])
        f.normal_update()
        if f.normal.dot(Vector(normal)) < 0:
            f.normal_flip()
        f.material_index = self.materials.index(mat)
        self.fixed.add(f)
        return f

    def to_object(self, name, mats, pivot=(0, 0, 0), parent=None, smooth_angle=None):
        bmesh.ops.recalc_face_normals(self.bm, faces=[f for f in self.bm.faces if f not in self.fixed])
        recalc = bmesh.ops.recalc_face_normals
        bmesh.ops.recalc_face_normals = lambda bm, faces: None
        try:
            return super().to_object(name, mats, pivot, parent, smooth_angle)
        finally:
            bmesh.ops.recalc_face_normals = recalc


def part(b, name, mats, root, pivot=(0, 0, 0), smooth=SMOOTH):
    return R.to_object(b, name, mats, pivot=Vector(pivot), parent=root, smooth_angle=smooth)


def squircle(sides, n=4.0, dense=720):
    """`sides` points evenly spaced along a unit superellipse |x|^n + |y|^n = 1 (a rounded
    square), starting on +X, counter-clockwise; with each point's outward normal."""
    pts = []
    for k in range(dense):
        a = 2 * math.pi * k / dense
        c, s = math.cos(a), math.sin(a)
        pts.append((math.copysign(abs(c) ** (2 / n), c), math.copysign(abs(s) ** (2 / n), s)))
    seg = [math.dist(pts[k], pts[(k + 1) % dense]) for k in range(dense)]
    total = sum(seg)
    out, acc, k = [], 0.0, 0
    for j in range(sides):
        want = total * j / sides
        while acc + seg[k] < want:
            acc += seg[k]
            k += 1
        t = (want - acc) / seg[k]
        p0, p1 = pts[k], pts[(k + 1) % dense]
        out.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t))
    norms = []
    for j in range(sides):
        a, c = out[j - 1], out[(j + 1) % sides]
        tx, ty = c[0] - a[0], c[1] - a[1]
        ln = math.hypot(tx, ty)
        norms.append((ty / ln, -tx / ln))
    return out, norms


def ring_stack(b, rings, mat_fn, caps=(True, True)):
    """A closed solid through horizontal rings of equal length (lists of Vectors);
    `mat_fn(i)` is the role of the band between ring i and i + 1."""
    bm = b.bm
    vs = [[bm.verts.new(p) for p in ring] for ring in rings]
    n = len(rings[0])
    for i in range(len(rings) - 1):
        idx = b.materials.index(mat_fn(i))
        for j in range(n):
            jn = (j + 1) % n
            bm.faces.new((vs[i][j], vs[i][jn], vs[i + 1][jn], vs[i + 1][j])).material_index = idx
    if caps[0]:
        bm.faces.new(list(reversed(vs[0]))).material_index = b.materials.index(mat_fn(0))
    if caps[1]:
        bm.faces.new(vs[-1]).material_index = b.materials.index(mat_fn(len(rings) - 2))


def arch_pts(w, h, spring, steps=8, y=0.0):
    """Outline of a round-headed arch opening, width w, total height h, the curve
    starting at `spring`; in a local XY plane (x across, y up from the sill)."""
    r = w / 2
    pts = [(-r, y), (r, y), (r, y + spring)]
    for k in range(1, steps):
        a = math.pi * k / steps
        pts.append((r * math.cos(a), y + spring + min(r, h - spring) * math.sin(a)))
    pts.append((-r, y + spring))
    return pts


def wall_frame(origin, along, normal):
    """Frame whose local X runs `along` the wall, local Y is up and local Z is the wall's
    outward `normal`, placed at `origin`."""
    x = Vector(along).normalized()
    z = Vector(normal).normalized()
    y = z.cross(x)
    return Matrix.Translation(Vector(origin)) @ Matrix((x, y, z)).transposed().to_4x4()


def opening(b, mat, frame, pts, depth=0.2, proud=0.02):
    """A dark recess drawn as a thin slab of the outline `pts` sitting on the wall."""
    b.prism(mat, pts, depth, frame @ Matrix.Translation((0, 0, proud - depth / 2)))


def ink_bar(b, p0, p1, normal, w, d=0.04, sink=0.04, mat="ink"):
    S.bar(b, mat, p0, p1, normal, w=w, d=d, sink=sink)


def box_ink(b, center, size, w, mat="ink", sides=("top",)):
    """Ink along the top edges of an axis-aligned box (a cornice line)."""
    cx, cy, cz = center
    sx, sy, sz = size
    z = cz + sz / 2
    corners = [V(cx - sx / 2, cy - sy / 2, z), V(cx + sx / 2, cy - sy / 2, z),
               V(cx + sx / 2, cy + sy / 2, z), V(cx - sx / 2, cy + sy / 2, z)]
    for k in range(4):
        a, c = corners[k], corners[(k + 1) % 4]
        out = (a + c) / 2 - V(cx, cy, z)
        out.z = 0
        ink_bar(b, a, c, out.normalized() + V(0, 0, 1), w, mat=mat)


def blob_tree(b, x, y, z, r, leaf="leaf", trunk="trunk"):
    b.tube(trunk, V(x, y, z), V(x, y, z + r * 1.1), r * 0.12, r * 0.09, sides=6)
    b.sphere(leaf, V(x, y, z + r * 1.4), (r, r, r * 0.8), u=8, v=5)


# --- Salesforce Tower ----------------------------------------------------------------------

SF_PAL = {"glass": 0x7D97AE, "glass_band": 0xC4D0DA, "fin": 0xEEF1F2, "lobby": 0xA8C5D6,
          "frame": 0x4A525A, "plaza": 0xD4CDBD, "stone": 0xA39D90, "planter": 0xBDB6A6,
          "leaf": 0x86B24C, "trunk": 0x7A6248, "roof": 0x59626C, "light_crown": 0xBFF0FF, "ink": INK}
SF_TOP = 165.0
SF_GLASS = 148.0
SF_LOBBY = 7.0
SF_SIDES = 48


def sf_w(z):
    """Half-width of the shaft: a straight taper that curves in over the top third."""
    lin = 13.0 - 1.7 * z / 150
    t = max(0.0, (z - 108) / 64)
    return lin * math.sqrt(max(0.0, 1 - t * t))


def sf_ring(unit, z, inset=0.0):
    w = sf_w(z) - inset
    return [V(x * w, y * w, z) for x, y in unit]


def sf_fins(b, unit, norms, zs, depth, mat="fin", half=0.17, sink=0.25):
    """A white fin at every ring vertex, following the shaft's profile through `zs`."""
    for (ux, uy), (nx, ny) in zip(unit, norms):
        n = V(nx, ny, 0)
        t = V(-ny, nx, 0)
        rings = []
        for z in zs:
            p = V(ux, uy, 0) * sf_w(z) + V(0, 0, z)
            rings.append([p - n * sink - t * half, p + n * depth(z) - t * half,
                          p + n * depth(z) + t * half, p - n * sink + t * half])
        ring_stack(b, rings, lambda i: mat)


def build_salesfarce():
    mats = C.make_materials(SF_PAL)
    root = C.empty("salesfarce_tower")
    unit, norms = squircle(SF_SIDES)

    # The shaft: a tall lobby, then glass with a pale band every one and a half floors.
    b = Builder(SF_PAL)
    zs, roles = [0.0, SF_LOBBY], ["lobby"]
    z = SF_LOBBY
    while z + 4.5 <= SF_GLASS + 0.01:
        zs += [z + 3.9, z + 4.5]
        roles += ["glass", "glass_band"]
        z += 4.5
    if zs[-1] < SF_GLASS:
        zs.append(SF_GLASS)
        roles.append("glass")
    ring_stack(b, [sf_ring(unit, z) for z in zs], lambda i: roles[i] if i < len(roles) else "roof")
    fin_zs = [0.0, SF_LOBBY, 30, 60, 90, 108, 116, 124, 131, 137, 142, 146, SF_GLASS]
    sf_fins(b, unit, norms, fin_zs, lambda z: 0.45 + 0.25 * max(0.0, (z - 100) / 48))
    # Lobby: a dark sill band, the entrance canopy and revolving doors on the south side.
    ring_stack(b, [sf_ring(unit, 0.0, -0.05), sf_ring(unit, 0.5, -0.05)], lambda i: "frame")
    ring_stack(b, [sf_ring(unit, SF_LOBBY - 0.3, -0.12), sf_ring(unit, SF_LOBBY + 0.3, -0.12)], lambda i: "fin")
    yf = -sf_w(5.0)
    b.box("fin", (15.0, 4.6, 0.45), V(0, yf - 2.0, 5.4))
    S.bar(b, "ink", V(-7.5, yf - 4.3, 5.2), V(7.5, yf - 4.3, 5.2), V(0, -1, 0), w=0.12, d=0.03, sink=0.03)
    for x in (-7.2, 7.2):
        b.box("frame", (0.25, 0.25, 5.2), V(x, yf - 4.1, 2.6))
    for x in (-3.6, 0.0, 3.6):
        b.tube("frame", V(x, yf + 0.2, 0), V(x, yf + 0.2, 3.2), 1.25, 1.25, sides=10)
        b.box("lobby", (0.1, 2.4, 3.0), V(x, yf + 0.2, 1.6))
    tower = part(b, "tower", mats, root)

    # The crown: the fins run on past the glass, tied by rings, round a glowing core.
    b = Builder(SF_PAL)
    crown_zs = [SF_GLASS, 152, 156, 160, 163, SF_TOP]
    sf_fins(b, unit, norms, crown_zs, lambda z: 0.75)
    for zr in (151.0, 154.6, 158.2, 161.6, SF_TOP - 0.45):
        outer = [(x * (sf_w(zr) + 0.8), y * (sf_w(zr) + 0.8)) for x, y in unit]
        inner = [(x * (sf_w(zr) - 0.35), y * (sf_w(zr) - 0.35)) for x, y in unit]
        S.strip_solid(b, lambda k: "fin", outer + outer[:1], inner + inner[:1], zr, zr + 0.45)
    core = [sf_ring(unit, z, 2.0) for z in (SF_GLASS, 152, 156, 159.5)]
    ring_stack(b, core, lambda i: "light_crown")
    ring_stack(b, [sf_ring(unit, 159.5, 2.0), sf_ring(unit, 160.1, 2.4)], lambda i: "roof")
    crown = part(b, "crown", mats, root, pivot=(0, 0, SF_GLASS))

    # Plaza: granite paving on a plinth, planters with trees, benches.
    b = Builder(SF_PAL)
    b.box("plaza", (40.0, 40.0, 4.2), V(0, 0, -2.0))
    b.box("stone", (40.4, 40.4, 0.6), V(0, 0, -0.25))
    for k in range(-3, 4):
        c = k * 5.0
        for a0, a1 in ((-19.8, -14.0), (14.0, 19.8)) if abs(c) < 14 else ((-19.8, 19.8),):
            S.bar(b, "stone", V(a0, c, 0.1), V(a1, c, 0.1), V(0, 0, 1), w=0.1, d=0.012, sink=0.02)
            S.bar(b, "stone", V(c, a0, 0.1), V(c, a1, 0.1), V(0, 0, 1), w=0.1, d=0.012, sink=0.02)
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * 16.3, sy * 16.3
            b.box("planter", (4.6, 4.6, 0.9), V(x, y, 0.45), bevel=0.08)
            blob_tree(b, x, y, 0.9, 2.3)
            b.box("frame", (4.0, 0.7, 0.45), V(x - sx * 5.0, y, 0.25))
    plaza = part(b, "plaza", mats, root)
    return root, [tower, crown, plaza], [
        ("3/4", -35, 5, V(0, 0, 84), 178, 0.55),
        ("east", -90, 5, V(0, 0, 84), 178, 0.55),
        ("crown", -35, 6, V(0, 0, 155), 30, 1.0),
        ("lobby", -25, 12, V(0, -6, 7), 34, 1.25),
    ]


# --- Transamerica Pyramid ------------------------------------------------------------------

PY_PAL = {"precast": 0xECE8DE, "window": 0x8D99A7, "spire": 0xC3CAD2, "wing": 0xE2DED2,
          "column": 0xD6D1C4, "lobby": 0x98B4C6, "frame": 0x4A525A, "plaza": 0xD2CBBB,
          "stone": 0x9F998C, "leaf": 0x4F7F43, "trunk": 0x7A5440, "light_beacon": 0xFF5A48, "ink": INK}
PY_BASE = 8.0       # top of the exoskeleton, where the pyramid's faces start
PY_TOP = 90.0       # where the faces give way to the spire
PY_TIP = 119.0
PY_SLOPE = 0.1098   # half-width lost per metre of height
PY_WING = (61.0, 92.0, 2.2)   # the wings: emerge at, top, half-depth
FACES = ((V(0, -1, 0), V(1, 0, 0)), (V(1, 0, 0), V(0, 1, 0)), (V(0, 1, 0), V(-1, 0, 0)), (V(-1, 0, 0), V(0, -1, 0)))


def py_w(z):
    if z <= PY_TOP:
        return 13.0 - PY_SLOPE * (z - PY_BASE)
    top = py_w(PY_TOP)
    return top + (0.25 - top) * (z - PY_TOP) / (PY_TIP - PY_TOP)


def py_square(z, grow=0.0):
    w = py_w(z) + grow
    return [V(w, -w, z), V(w, w, z), V(-w, w, z), V(-w, -w, z)]


def py_point(face, s, z, lift=0.0):
    """A point on face `face` (0 south, 1 east, 2 north, 3 west) at offset s along it."""
    d, a = FACES[face]
    n = (d + V(0, 0, PY_SLOPE)).normalized()
    return d * py_w(z) + a * s + V(0, 0, z) + n * lift


def member(b, mat, p0, p1, size, up):
    """A square beam from p0 to p1, its sides squared to `up`."""
    p0, p1 = Vector(p0), Vector(p1)
    b.box(mat, ((p1 - p0).length + size[0] * 0.5, size[0], size[1]), (p0 + p1) / 2, rot=S.surface_rot(p1 - p0, up))


def build_pyramid():
    mats = C.make_materials(PY_PAL)
    root = C.empty("pyramid")
    b = Builder(PY_PAL)
    z_s, z_w, hd = PY_WING
    # The faces, and the spire above them.
    ring_stack(b, [py_square(PY_BASE - 0.2), py_square(PY_TOP)], lambda i: "precast")
    ring_stack(b, [py_square(PY_TOP, -0.02), py_square(PY_TIP - 0.6, -0.02)], lambda i: "spire")
    b.tube("spire", V(0, 0, PY_TIP - 0.8), V(0, 0, PY_TIP + 0.4), 0.22, 0.08, sides=6)
    b.sphere("light_beacon", V(0, 0, PY_TIP + 0.6), (0.3, 0.3, 0.3), u=6, v=4)
    # Rows of small windows, one per floor, in vertical columns, hidden behind the wings.
    z = PY_BASE + 1.0
    while z + 1.4 < PY_TOP - 1.0:
        lo, hi = z + 0.45, z + 1.25
        w = py_w(hi) - 0.7
        m = int(2 * w / 1.2)
        for f in range(4):
            for i in range(m):
                s = (i - (m - 1) / 2) * 1.2
                if f in (1, 3) and hi > z_s - 1.0 and abs(s) < hd + 0.3:
                    continue
                n = (FACES[f][0] + V(0, 0, PY_SLOPE)).normalized()
                b.plate("window", [py_point(f, s - 0.34, lo, 0.03), py_point(f, s + 0.34, lo, 0.03),
                                   py_point(f, s + 0.34, hi, 0.03), py_point(f, s - 0.34, hi, 0.03)], n)
        z += 1.75
    # The spire's aluminium panel joints, and the joint between face and spire.
    zj = PY_TOP
    while zj < PY_TIP - 3:
        for f in range(4):
            d, a = FACES[f]
            w = py_w(zj)
            S.bar(b, "ink", d * w - a * w + V(0, 0, zj), d * w + a * w + V(0, 0, zj), d + V(0, 0, 0.13),
                  w=0.09 if zj > PY_TOP else 0.16, d=0.03, sink=0.03)
        zj += 3.4
    # The wings: elevators east, stairs west; vertical outer faces that stand out further
    # from the sloping faces the higher they go.
    for sx in (1, -1):
        xo = py_w(z_s)
        b.box("wing", (xo - 2.0, 2 * hd, z_w - z_s + 6), V(sx * (xo + 2.0) / 2, 0, (z_s - 6 + z_w) / 2))
        b.box("precast", (xo - 1.6, 2 * hd + 0.4, 0.5), V(sx * (xo + 1.6) / 2, 0, z_w + 0.25))
        for y in (-hd, hd):
            S.bar(b, "ink", V(sx * xo, y, z_s), V(sx * xo, y, z_w), V(sx, 0, 0), w=0.1, d=0.03, sink=0.03)
        if sx < 0:
            zz = z_s + 1.0
            while zz < z_w - 2:
                b.plate("window", [V(-xo - 0.03, -0.45, zz), V(-xo - 0.03, 0.45, zz),
                                   V(-xo - 0.03, 0.45, zz + 0.9), V(-xo - 0.03, -0.45, zz + 0.9)], V(-1, 0, 0))
                zz += 3.5
        else:
            for y in (-0.7, 0.7):
                S.bar(b, "ink", V(xo, y, z_s + 2), V(xo, y, z_w - 1), V(1, 0, 0), w=0.08, d=0.03, sink=0.03)
    # The base: a recessed glass lobby inside sloping exoskeleton columns, under a deep
    # transfer beam.
    b.box("lobby", (21.0, 21.0, PY_BASE), V(0, 0, PY_BASE / 2))
    for x in (-7.0, 0.0, 7.0):
        S.bar(b, "frame", V(x, -10.5, 0), V(x, -10.5, PY_BASE), V(0, -1, 0), w=0.18, d=0.04, sink=0.02)
    b.box("frame", (5.0, 0.6, 3.2), V(0, -10.6, 1.6))
    ring_stack(b, [py_square(PY_BASE - 1.4, 0.35), py_square(PY_BASE + 0.25, 0.35)], lambda i: "column")
    S.bar(b, "ink", *py_square(PY_BASE - 1.4, 0.37)[3:4], py_square(PY_BASE - 1.4, 0.37)[0], V(0, -1, 0), w=0.1, d=0.03, sink=0.03)
    for f in range(4):
        d, a = FACES[f]
        up = (d + V(0, 0, PY_SLOPE)).normalized()
        w0, w1 = py_w(0) - 0.3, py_w(PY_BASE - 1.4) - 0.3
        foot = [-w0, -w0 / 2, 0.0, w0 / 2, w0]
        head = [-w1 * 0.75, -w1 * 0.25, w1 * 0.25, w1 * 0.75]
        for k, s in enumerate(foot):
            g = d * w0 + a * s
            for t in (k - 1, k):
                if 0 <= t < len(head):
                    member(b, "column", g, d * w1 + a * head[t] + V(0, 0, PY_BASE - 1.4), (0.9, 0.9), up)
        member(b, "column", d * w0 + a * w0, d * w1 + a * w1 + V(0, 0, PY_BASE - 1.0), (1.2, 1.2), up)
    tower = part(b, "tower", mats, root)
    # Plaza on a plinth, with Redwood Park's little grove on the east side.
    b = Builder(PY_PAL)
    b.box("stone", (40.0, 40.0, 16.0), V(0, 0, -8.0 + 0.0))
    b.box("plaza", (39.6, 39.6, 0.3), V(0, 0, 0.05))
    for k in (-1, 1):
        for c in (-17.0, 17.0):
            S.bar(b, "stone", V(c, -19.8, 0.2), V(c, 19.8, 0.2), V(0, 0, 1), w=0.1, d=0.012, sink=0.02)
            S.bar(b, "stone", V(-19.8, c, 0.2), V(19.8, c, 0.2), V(0, 0, 1), w=0.1, d=0.012, sink=0.02)
    for x, y, h in ((17.4, -12.0, 11.0), (17.6, -5.0, 13.0), (16.9, 2.5, 9.5), (17.5, 9.0, 12.0), (17.0, 15.5, 10.0)):
        b.tube("trunk", V(x, y, 0.2), V(x, y, 2.4), 0.35, 0.28, sides=6)
        b.tube("leaf", V(x, y, 1.6), V(x, y, 1.6 + h), 2.0, 0.0, sides=7)
    for y in (-14.0, 14.0):
        b.box("frame", (0.7, 4.0, 0.45), V(-17.0, y, 0.4))
    plaza = part(b, "plaza", mats, root)
    return root, [tower, plaza], [
        ("3/4", -35, 5, V(0, 0, 58), 126, 0.62),
        ("south", 0, 5, V(0, 0, 58), 126, 0.62),
        ("wings and spire", -20, 4, V(0, 0, 96), 46, 0.9),
        ("base", -30, 12, V(0, -4, 6), 38, 1.3),
    ]


# --- Ferry Building ------------------------------------------------------------------------

FB_PAL = {"stone": 0xE6DBC2, "stone_dark": 0xCBBE9F, "trim": 0xF4EEDF, "arch": 0x4A4E57,
          "window": 0x6F8597, "roof": 0x7F8E89, "skylight": 0xAECBD8, "cap": 0x6F8079,
          "pave": 0xD3CBB9, "plinth": 0xA49D8E, "rail": 0x3C474E, "wood": 0x9B6B3E,
          "light_clock": 0xFFF6DC, "light_lamp": 0xFFF0C0, "ink": INK}
FB_HALL = (-15.0, 8.0, -16.0, 16.0, 12.0)        # x0, x1, y0, y1, cornice height
FB_PAV = (-15.6, 8.6, 16.0, 19.6, 13.6)          # the end pavilions (mirrored to -y)
FB_TOWER = (-12.6, 0.0, 7.0)                     # centre x, y, side


def fb_bay(b, frame, upper=True, ground=True, w=2.3):
    """One bay of the arcade: a dark arch below, an arched window in a pale surround above."""
    if ground:
        opening(b, "arch", frame, arch_pts(w, 4.9, 3.6, y=0.25), proud=0.06)
        opening(b, "trim", frame, arch_pts(w + 0.6, 5.2, 3.6, y=0.25), proud=0.03)
    if upper:
        opening(b, "window", frame, arch_pts(w * 0.72, 3.3, 2.4, y=6.9), proud=0.08)
        opening(b, "trim", frame, arch_pts(w * 0.72 + 0.5, 3.55, 2.4, y=6.75), proud=0.04)


def fb_facade(b, plane, normal, centres, w=2.3, pilasters=(), top=11.6):
    """Bays at `centres` along a wall; `plane` is the wall's x (east/west walls) or y."""
    n = Vector(normal)
    along = V(-n.y, n.x, 0)
    at = (lambda c: V(plane, c, 0)) if abs(n.x) > 0 else (lambda c: V(c, plane, 0))
    for c in centres:
        fb_bay(b, wall_frame(at(c), along, n), w=w)
    for c in pilasters:
        b.box("trim", (0.5, 0.5, top - 0.9), at(c) + V(0, 0, (top - 0.9) / 2 + 0.6))


def fb_tier(b, c, side, z0, z1, mat="stone"):
    b.box(mat, (side, side, z1 - z0), V(c.x, c.y, (z0 + z1) / 2))


def fb_cornice(b, c, side, z, h=0.55):
    b.box("trim", (side, side, h), V(c.x, c.y, z + h / 2))
    box_ink(b, (c.x, c.y, z + h / 2), (side, side, h), 0.09)


def fb_balustrade(b, c, side, z, h=1.0, pitch=0.62):
    """Rail and balusters round a square at height z, with an urn at each corner."""
    half = side / 2
    for k in range(4):
        d = [V(1, 0, 0), V(0, 1, 0), V(-1, 0, 0), V(0, -1, 0)][k]
        a = V(-d.y, d.x, 0)
        m = int(side / pitch)
        for i in range(1, m):
            p = c + d * (half - 0.2) + a * (-half + side * i / m)
            b.box("trim", (0.16, 0.16, h - 0.2), V(p.x, p.y, z + (h - 0.2) / 2))
    b.box("trim", (side, side, 0.18), V(c.x, c.y, z + h - 0.09))
    b.box("trim", (side - 0.6, side - 0.6, 0.2), V(c.x, c.y, z + h - 0.15))
    for sx in (-1, 1):
        for sy in (-1, 1):
            p = c + V(sx * (half - 0.25), sy * (half - 0.25), 0)
            b.box("trim", (0.5, 0.5, h + 0.1), V(p.x, p.y, z + (h + 0.1) / 2))
            b.sphere("trim", V(p.x, p.y, z + h + 0.45), (0.3, 0.3, 0.38), u=6, v=4)


def fb_clock(b, centre, n, r=2.2):
    n = Vector(n)
    b.tube("ink", centre - n * 0.05, centre + n * 0.12, r + 0.22, r + 0.22, sides=20)
    b.tube("light_clock", centre, centre + n * 0.2, r, r, sides=20)
    face = centre + n * 0.2
    up = V(0, 0, 1)
    side = n.cross(up)
    for k in range(12):
        a = 2 * math.pi * k / 12
        u = side * math.sin(a) + up * math.cos(a)
        S.bar(b, "ink", face + u * (r - 0.35), face + u * (r - 0.1), n, w=0.12 if k % 3 else 0.2, d=0.03, sink=0.02)
    for a, ln, w in ((math.radians(-60), 1.2, 0.2), (math.radians(60), 1.75, 0.13)):
        u = side * math.sin(a) + up * math.cos(a)
        S.bar(b, "ink", face, face + u * ln, n, w=w, d=0.05, sink=0.02)


def fb_arch_ring(b, c, side, z, count, w, h, spring, mat="arch"):
    """`count` arched openings on every side of a square stage."""
    half = side / 2
    for d in (V(1, 0, 0), V(0, 1, 0), V(-1, 0, 0), V(0, -1, 0)):
        a = V(-d.y, d.x, 0)
        for i in range(count):
            off = (i - (count - 1) / 2) * side / count
            fr = wall_frame(c + d * half + a * off, a, d)
            opening(b, mat, fr, arch_pts(w, h, spring, y=z), proud=0.06)
            opening(b, "trim", fr, arch_pts(w + 0.4, h + 0.22, spring, y=z - 0.12), proud=0.03)


def build_ferry_building():
    mats = C.make_materials(FB_PAL)
    root = C.empty("ferry_building")
    x0, x1, y0, y1, ht = FB_HALL
    px0, px1, py0, py1, hp = FB_PAV
    tx, ty, side = FB_TOWER

    b = Builder(FB_PAL)
    # The hall and its end pavilions, a dark plinth course, belt course and cornice.
    b.box("stone", (x1 - x0, y1 - y0 + 1, ht), V((x0 + x1) / 2, 0, ht / 2))
    for sy in (-1, 1):
        cy = sy * (py0 + py1) / 2
        b.box("stone", (px1 - px0, py1 - py0, hp), V((px0 + px1) / 2, cy, hp / 2))
        b.box("trim", (px1 - px0 + 0.6, py1 - py0 + 0.6, 0.6), V((px0 + px1) / 2, cy, hp - 0.3))
        box_ink(b, ((px0 + px1) / 2, cy, hp - 0.3), (px1 - px0 + 0.6, py1 - py0 + 0.6, 0.6), 0.1)
        b.box("stone", (px1 - px0 - 1.0, py1 - py0 - 1.0, 1.0), V((px0 + px1) / 2, cy, hp + 0.5))
        b.box("stone_dark", (px1 - px0 + 0.3, py1 - py0 + 0.3, 0.8), V((px0 + px1) / 2, cy, 0.4))
        b.box("trim", (px1 - px0 + 0.3, py1 - py0 + 0.3, 0.4), V((px0 + px1) / 2, cy, 6.2))
    b.box("stone_dark", (x1 - x0 + 0.3, y1 - y0 + 1, 0.8), V((x0 + x1) / 2, 0, 0.4))
    b.box("trim", (x1 - x0 + 0.3, y1 - y0 + 1, 0.4), V((x0 + x1) / 2, 0, 6.2))
    b.box("trim", (x1 - x0 + 0.8, y1 - y0 + 1, 0.6), V((x0 + x1) / 2, 0, ht - 0.3))
    for xe in (x0 - 0.4, x1 + 0.4):
        S.bar(b, "ink", V(xe, y0, ht), V(xe, y1, ht), V(math.copysign(1, xe), 0, 1), w=0.1, d=0.03, sink=0.03)
    b.box("stone", (x1 - x0 - 0.6, y1 - y0 + 1, 1.0), V((x0 + x1) / 2, 0, ht + 0.5))
    # The roof: a low gable with the nave's long skylight along the ridge.
    rx = (x0 + x1) / 2
    for sy0, sy1 in ((y0 - 0.5, y1 + 0.5),):
        b.prism("roof", [(x0 + 0.3, ht + 1.0), (x1 - 0.3, ht + 1.0), (rx + 3.0, ht + 3.6), (rx - 3.0, ht + 3.6)],
                sy1 - sy0, Matrix.Rotation(math.pi / 2, 4, "X") @ Matrix.Translation((0, 0, 0)))
    b.box("skylight", (6.4, y1 - y0 + 0.2, 1.4), V(rx, 0, ht + 4.2))
    b.box("roof", (7.0, y1 - y0 + 0.6, 0.3), V(rx, 0, ht + 5.0))
    for k in range(-7, 8):
        for sx in (-1, 1):
            S.bar(b, "ink", V(rx + sx * 3.2, k * 2.1, ht + 3.5), V(rx + sx * 3.2, k * 2.1, ht + 4.9), V(sx, 0, 0), w=0.08, d=0.02, sink=0.02)
    # The arcades: west on the plaza, east on the bay, and the pavilions' ends.
    west = [s * (4.6 + (k + 0.5) * 11.4 / 4) for s in (-1, 1) for k in range(4)]
    piers = [s * (4.6 + k * 11.4 / 4) for s in (-1, 1) for k in range(5)]
    fb_facade(b, x0, V(-1, 0, 0), west, pilasters=piers)
    east = [-y1 + (k + 0.5) * 2 * y1 / 11 for k in range(11)]
    fb_facade(b, x1, V(1, 0, 0), east, pilasters=[-y1 + k * 2 * y1 / 11 for k in range(12)])
    for sy in (-1, 1):
        cy = sy * (py0 + py1) / 2
        fb_facade(b, px0, V(-1, 0, 0), [cy], w=2.6)
        fb_facade(b, px1, V(1, 0, 0), [cy], w=2.6)
        end = [px0 + (k + 0.5) * (px1 - px0) / 6 for k in range(6)]
        fb_facade(b, sy * py1, V(0, sy, 0), end, w=2.1)
    # The clock tower: the shaft rises from the west front, then the clock stage,
    # two arcaded belfry stages behind balustrades, and the pyramidal cap and flagpole.
    c = V(tx, ty, 0)
    fb_tier(b, c, side, 0, 28.0)
    b.box("stone_dark", (side + 0.3, side + 0.3, 0.8), V(tx, ty, 0.4))
    for d in (V(1, 0, 0), V(0, 1, 0), V(-1, 0, 0), V(0, -1, 0)):
        a = V(-d.y, d.x, 0)
        for off in (-1.6, 1.6):
            p = c + d * (side / 2) + a * off
            b.box("stone_dark", (1.5 if d.x == 0 else 0.1, 0.1 if d.x == 0 else 1.5, 12.0), p + V(0, 0, 20.5))
        for zz in (14.5, 23.0):
            fr = wall_frame(c + d * (side / 2), a, d)
            for off in (-0.6, 0.6):
                opening(b, "window", fr @ Matrix.Translation((off, 0, 0)), arch_pts(0.8, 2.0, 1.6, y=zz), proud=0.06)
        for zz in (13.5, 27.4):
            S.bar(b, "trim", c + d * (side / 2 + 0.05) - a * side / 2 + V(0, 0, zz),
                  c + d * (side / 2 + 0.05) + a * side / 2 + V(0, 0, zz), d, w=0.35, d=0.15, sink=0.05)
    fr = wall_frame(c + V(-side / 2, 0, 0), V(0, -1, 0), V(-1, 0, 0))
    opening(b, "arch", fr, arch_pts(3.6, 7.5, 5.6, y=0.0), proud=0.08)
    opening(b, "trim", fr, arch_pts(4.6, 8.0, 5.6, y=0.0), proud=0.04)
    fb_cornice(b, c, side + 0.6, 28.0)
    fb_tier(b, c, side - 0.2, 28.5, 35.0)
    for d in (V(1, 0, 0), V(0, 1, 0), V(-1, 0, 0), V(0, -1, 0)):
        fb_clock(b, c + d * ((side - 0.2) / 2) + V(0, 0, 31.7), d)
    fb_cornice(b, c, side + 0.6, 35.0, h=0.5)
    fb_balustrade(b, c, side + 0.6, 35.5)
    fb_tier(b, c, side - 1.4, 35.5, 41.5)
    fb_arch_ring(b, c, side - 1.4, 36.5, 2, 1.3, 4.0, 3.2)
    fb_cornice(b, c, side - 0.8, 41.5, h=0.45)
    fb_balustrade(b, c, side - 0.8, 41.95, h=0.9)
    fb_tier(b, c, side - 2.8, 41.95, 45.6)
    fb_arch_ring(b, c, side - 2.8, 42.6, 1, 1.4, 2.6, 2.0)
    fb_cornice(b, c, side - 2.3, 45.6, h=0.4)
    b.box("cap", (side - 2.4, side - 2.4, 4.4), V(tx, ty, 46.0 + 2.2), taper=(0.08, 0.08))
    b.tube("trim", V(tx, ty, 50.2), V(tx, ty, 50.6), 0.35, 0.25, sides=8)
    b.tube("rail", V(tx, ty, 50.4), V(tx, ty, 55.0), 0.08, 0.05, sides=6)
    b.sphere("trim", V(tx, ty, 55.1), (0.16, 0.16, 0.16), u=6, v=4)
    hall = part(b, "hall", mats, root)

    # Ground: plaza paving west, the bay promenade east with its railing, lamps, benches.
    b = Builder(FB_PAL)
    b.box("plinth", (36.0, 40.0, 3.2), V(0, 0, -1.5))
    b.box("pave", (36.0, 40.0, 0.2), V(0, 0, 0.1))
    for k in range(1, 6):
        x = x1 + k * 1.7
        S.bar(b, "plinth", V(x, -19.9, 0.2), V(x, 19.9, 0.2), V(0, 0, 1), w=0.08, d=0.01, sink=0.02)
    for x in (-16.5, -17.6):
        S.bar(b, "plinth", V(x, -19.9, 0.2), V(x, 19.9, 0.2), V(0, 0, 1), w=0.08, d=0.01, sink=0.02)
    xr = 17.6
    b.box("rail", (0.12, 39.6, 0.12), V(xr, 0, 1.1))
    b.box("rail", (0.08, 39.6, 0.08), V(xr, 0, 0.6))
    for k in range(21):
        b.box("rail", (0.1, 0.1, 1.0), V(xr, -19.8 + k * 1.98, 0.7))
    for y in (-14.0, -4.5, 4.5, 14.0):
        b.tube("rail", V(16.2, y, 0.2), V(16.2, y, 4.6), 0.1, 0.07, sides=6)
        b.sphere("light_lamp", V(16.2, y, 4.8), (0.3, 0.3, 0.38), u=6, v=4)
        b.box("rail", (0.5, 0.5, 0.12), V(16.2, y, 4.55))
    for y in (-9.0, 0.0, 9.0):
        b.box("wood", (0.6, 2.4, 0.12), V(13.0, y, 0.65))
        b.box("wood", (0.12, 2.4, 0.5), V(13.25, y, 0.95))
        b.box("rail", (0.5, 0.1, 0.45), V(13.0, y - 1.0, 0.42))
        b.box("rail", (0.5, 0.1, 0.45), V(13.0, y + 1.0, 0.42))
    for y in (-18.0, -11.5, 11.5, 18.0):
        b.tube("rail", V(17.0, y, 0.2), V(17.0, y, 0.8), 0.22, 0.18, sides=8)
    ground = part(b, "ground", mats, root)
    return root, [hall, ground], [
        ("3/4 west", 50, 9, V(-4, 0, 22), 62, 1.0),
        ("west front", 90, 4, V(0, 0, 24), 60, 0.9),
        ("clock tower", 60, 6, V(tx, ty, 41), 22, 0.85),
        ("bay side", -130, 12, V(4, 0, 12), 40, 1.25),
    ]


# --- Coit Tower -----------------------------------------------------------------------------

CT_PAL = {"concrete": 0xEFE8D6, "flute": 0xD3C9B3, "trim": 0xF7F2E6, "arch": 0x3F434C,
          "door": 0x6B4A33, "base": 0xE3DBC6, "roof": 0xB9AE98, "wall": 0xB3AA95, "course": 0x8C8473, "pave": 0xD8D0BE,
          "rail": 0x3C474E, "wood": 0x9B6B3E, "light_lamp": 0xFFF0C0, "ink": INK}
CT_R = 3.8
CT_TERRACE = 9.5
CT_FLUTES = 24


def ct_radius(z):
    return CT_R + (3.45 - CT_R) * min(1.0, max(0.0, z / 26.0))


def ct_ring(z, r=None, flutes=True, sides=CT_FLUTES * 2):
    r = ct_radius(z) if r is None else r
    out = []
    for j in range(sides):
        a = 2 * math.pi * j / sides
        k = 1.0 - (0.045 if flutes and j % 2 else 0.0)
        out.append(V(math.cos(a) * r * k, math.sin(a) * r * k, z))
    return out


def ct_arches(b, z, r, count, w, h, spring, mat="arch", offset=0.0, trim=True):
    for i in range(count):
        a = 2 * math.pi * (i + offset) / count
        n = V(math.cos(a), math.sin(a), 0)
        fr = wall_frame(n * r, V(-n.y, n.x, 0), n)
        opening(b, mat, fr, arch_pts(w, h, spring, y=z), depth=0.4, proud=0.06)
        if trim:
            opening(b, "trim", fr, arch_pts(w + 0.35, h + 0.2, spring, y=z - 0.12), depth=0.4, proud=0.03)


def build_coit_tower():
    mats = C.make_materials(CT_PAL)
    root = C.empty("coit_tower")
    b = Builder(CT_PAL)
    # The fluted column: shallow flutes, each groove drawn as a faint line.
    zs = [0.0, 6.0, 12.0, 18.0, 25.6]
    ring_stack(b, [ct_ring(z) for z in zs], lambda i: "concrete")
    for j in range(1, CT_FLUTES * 2, 2):
        a = 2 * math.pi * j / (CT_FLUTES * 2)
        n = V(math.cos(a), math.sin(a), 0)
        p0, p1 = n * ct_radius(5.8) * 0.955, n * ct_radius(25.4) * 0.955
        S.bar(b, "flute", p0 + V(0, 0, 5.8), p1 + V(0, 0, 25.4), n, w=0.12, d=0.02, sink=0.02)
    # The observation level: a ring of tall open arches between piers, under the crown.
    ring_stack(b, [ct_ring(25.6, 3.62, False), ct_ring(26.2, 3.62, False)], lambda i: "trim")
    ring_stack(b, [ct_ring(26.2, 3.45, False), ct_ring(30.4, 3.45, False)], lambda i: "concrete")
    ct_arches(b, 26.5, 3.45, 12, 1.0, 3.5, 2.95)
    ring_stack(b, [ct_ring(30.4, 3.7, False), ct_ring(30.8, 3.95, False), ct_ring(31.4, 3.95, False)], lambda i: "trim")
    ring_stack(b, [ct_ring(31.4, 3.55, False), ct_ring(32.5, 3.55, False), ct_ring(32.7, 3.7, False),
                   ct_ring(33.0, 3.7, False)], lambda i: ("concrete", "trim", "trim")[i])
    ct_arches(b, 31.6, 3.55, 24, 0.4, 0.7, 0.5, offset=0.5, trim=False)
    ring_stack(b, [ct_ring(33.0, 3.2, False), ct_ring(33.15, 2.4, False)], lambda i: "roof")
    tower = part(b, "tower", mats, root)

    # The base building: a low block round the column's foot, its arched door to the south.
    b = Builder(CT_PAL)
    bw, bh = 10.4, 5.6
    b.box("base", (bw, bw, bh), V(0, 0, bh / 2))
    b.box("trim", (bw + 0.5, bw + 0.5, 0.55), V(0, 0, bh - 0.1))
    box_ink(b, (0, 0, bh - 0.1), (bw + 0.5, bw + 0.5, 0.55), 0.07)
    b.box("roof", (bw - 0.4, bw - 0.4, 0.3), V(0, 0, bh + 0.25))
    b.box("trim", (bw + 0.3, bw + 0.3, 0.5), V(0, 0, 0.25))
    for d in (V(1, 0, 0), V(0, 1, 0), V(-1, 0, 0), V(0, -1, 0)):
        a = V(-d.y, d.x, 0)
        fr = wall_frame(d * bw / 2, a, d)
        if d.y < 0:
            b.box("base", (4.6, 1.2, bh + 0.8), V(0, -bw / 2 - 0.4, (bh + 0.8) / 2))
            b.box("trim", (5.0, 1.5, 0.5), V(0, -bw / 2 - 0.4, bh + 0.55))
            fr = wall_frame(V(0, -bw / 2 - 1.0, 0), a, d)
            opening(b, "trim", fr, arch_pts(3.0, 4.6, 3.1, y=0.2), proud=0.04)
            opening(b, "door", fr, arch_pts(2.4, 4.2, 3.0, y=0.2), proud=0.08)
            for off in (-3.3, 3.3):
                opening(b, "arch", fr @ Matrix.Translation((off, 0, 0.5)), arch_pts(1.1, 2.6, 1.9, y=1.4), proud=0.06)
            for k in range(3):
                b.box("trim", (4.6 - k * 0.3, 0.45, 0.18), V(0, -bw / 2 - 1.2 - (2 - k) * 0.4, 0.09 + 0.18 * k))
        else:
            for off in (-3.0, 0.0, 3.0):
                opening(b, "arch", fr @ Matrix.Translation((off, 0, 0)), arch_pts(1.2, 3.0, 2.25, y=1.4), proud=0.06)
                opening(b, "trim", fr @ Matrix.Translation((off, 0, 0)), arch_pts(1.55, 3.2, 2.25, y=1.25), proud=0.03)
    base = part(b, "base", mats, root)

    # The hilltop terrace: round, paved, behind a low parapet, on a retaining wall that
    # reaches down the slope.
    b = Builder(CT_PAL)
    R0 = CT_TERRACE
    ring_stack(b, [ct_ring(-10.0, R0, False, 48), ct_ring(0.12, R0, False, 48)],
               lambda i: "wall")
    ring_stack(b, [ct_ring(0.12, R0 - 0.02, False, 48), ct_ring(0.16, R0 - 0.02, False, 48)], lambda i: "pave")
    for zc in (-1.6, -3.4, -5.2, -7.0, -8.8):
        ring_stack(b, [ct_ring(zc, R0 + 0.06, False, 48), ct_ring(zc + 0.14, R0 + 0.06, False, 48)], lambda i: "course")
    ring_stack(b, [ct_ring(-0.35, R0 + 0.2, False, 48), ct_ring(0.1, R0 + 0.2, False, 48)], lambda i: "trim")
    gap = math.radians(14)
    arc = [(-math.pi / 2 + gap) + (2 * math.pi - 2 * gap) * k / 40 for k in range(41)]
    outer = [(math.cos(a) * (R0 + 0.15), math.sin(a) * (R0 + 0.15)) for a in arc]
    inner = [(math.cos(a) * (R0 - 0.45), math.sin(a) * (R0 - 0.45)) for a in arc]
    S.strip_solid(b, lambda k: "trim", outer, inner, 0.1, 0.85)
    for k in range(0, 40, 4):
        a = arc[k]
        n = V(math.cos(a), math.sin(a), 0)
        b.box("trim", (0.75, 0.75, 1.1), n * (R0 - 0.15) + V(0, 0, 0.55), rot=Matrix.Rotation(a, 4, "Z"))
    for k in range(-3, 4):
        half = math.sqrt((R0 - 0.5) ** 2 - (k * 2.4) ** 2)
        S.bar(b, "wall", V(-half, k * 2.4, 0.16), V(half, k * 2.4, 0.16), V(0, 0, 1), w=0.08, d=0.01, sink=0.02)
    for a in (math.radians(-60), math.radians(-120), math.radians(20), math.radians(160)):
        n = V(math.cos(a), math.sin(a), 0)
        p = n * (R0 - 1.2)
        b.tube("rail", p, p + V(0, 0, 3.6), 0.08, 0.06, sides=6)
        b.sphere("light_lamp", p + V(0, 0, 3.8), (0.25, 0.25, 0.32), u=6, v=4)
    for a in (math.radians(-35), math.radians(-145)):
        n = V(math.cos(a), math.sin(a), 0)
        b.box("wood", (2.2, 0.55, 0.12), n * (R0 - 1.4) + V(0, 0, 0.6), rot=Matrix.Rotation(a + math.pi / 2, 4, "Z"))
    terrace = part(b, "terrace", mats, root)
    return root, [tower, base, terrace], [
        ("3/4", -35, 8, V(0, 0, 16.0), 40, 0.85),
        ("east", -90, 6, V(0, 0, 16.0), 40, 0.85),
        ("observation level", -25, 6, V(0, 0, 29.5), 10, 1.0),
        ("door", -15, 14, V(0, -5, 4), 17, 1.25),
    ]


# --- Golden Gate ----------------------------------------------------------------------------

GG_PAL = {"orange": 0xC4402F, "orange_dark": 0x9E3226, "concrete": 0xB8B2A6, "road": 0x5B5F66,
          "light_beacon": 0xFF4A3A, "ink": INK}
GG_TOWER_X = 95.0          # towers either side of the origin (the game's x = -340 and -150)
GG_SPAN = 260.0            # the deck runs to here each way
GG_LEG_Y = 5.5             # leg centres across the bridge
GG_DECK = 22.6             # road surface
GG_TRUSS_Y = 4.3
GG_TOP = 88.0
GG_SADDLE = 86.5
GG_SAG = 28.0              # the main cables' low point
GG_TIERS = ((3.0, 40.0, 4.6, 2.7), (40.0, 58.0, 4.2, 2.5), (58.0, 74.0, 3.8, 2.3), (74.0, GG_TOP, 3.4, 2.1))
GG_PORTALS = (38.0, 56.0, 72.0, 85.0)


def gg_cable_z(x):
    """The main cables: a parabola between the towers, sagging side spans down to the
    deck ends."""
    ax = abs(x)
    if ax <= GG_TOWER_X:
        t = ax / GG_TOWER_X
        return GG_SAG + (GG_SADDLE - GG_SAG) * t * t
    t = (GG_SPAN - ax) / (GG_SPAN - GG_TOWER_X)
    return GG_DECK + 1.4 + (GG_SADDLE - GG_DECK - 1.4) * t * t


def gg_tower(b, tx):
    # The pier, its fender, and each leg's setbacks (stepping back on the outer side).
    b.box("concrete", (10.0, 18.0, 19.0), V(tx, 0, -6.5), bevel=1.5, seg=2)
    b.box("concrete", (8.6, 16.4, 0.6), V(tx, 0, 3.2))
    for sy in (-1, 1):
        for z0, z1, along, across in GG_TIERS:
            inner = GG_LEG_Y - GG_TIERS[0][3] / 2
            yc = sy * (inner + across / 2)
            b.box("orange", (along, across, z1 - z0), V(tx, yc, (z0 + z1) / 2))
            b.box("orange", (along + 0.3, across + 0.3, 0.5), V(tx, yc, z1 - 0.25))
            for sx in (-1, 1):
                for off in (-0.45, 0.45):
                    p = V(tx + sx * along / 2, yc + off * across * 0.8, 0)
                    S.bar(b, "orange_dark", p + V(0, 0, z0 + 0.8), p + V(0, 0, z1 - 0.8), V(sx, 0, 0), w=0.22, d=0.03, sink=0.03)
        top_y = sy * (GG_LEG_Y - GG_TIERS[0][3] / 2 + GG_TIERS[-1][3] / 2)
        b.box("orange", (2.6, 1.6, 1.2), V(tx, top_y, GG_TOP + 0.6))
        b.box("orange", (1.6, 1.0, 1.0), V(tx, top_y, GG_TOP + 1.7))
        b.tube("orange_dark", V(tx, top_y, GG_TOP + 2.2), V(tx, top_y, GG_TOP + 3.2), 0.12, 0.1, sides=6)
        b.sphere("light_beacon", V(tx, top_y, GG_TOP + 3.4), (0.3, 0.3, 0.3), u=6, v=4)
        b.box("orange_dark", (3.2, 1.2, 1.4), V(tx, sy * 4.6, GG_SADDLE - 0.3))
    # Portal struts with stepped art-deco corners, and the X-bracing under the deck.
    inner = GG_LEG_Y - GG_TIERS[0][3] / 2
    for k, z in enumerate(GG_PORTALS):
        h = 3.2 if k < 3 else 3.8
        along = GG_TIERS[min(k + 1, 3)][2] * 0.85
        span = 2 * inner + 0.4
        b.box("orange", (along, span, h), V(tx, 0, z))
        for sx in (-1, 1):
            for off in (-2.4, -0.8, 0.8, 2.4):
                p = V(tx + sx * along / 2, off, 0)
                S.bar(b, "orange_dark", p + V(0, 0, z - h / 2 + 0.4), p + V(0, 0, z + h / 2 - 0.4), V(sx, 0, 0), w=0.25, d=0.03, sink=0.03)
        for sy in (-1, 1):
            for st in range(3):
                d = 0.75 * (3 - st)
                b.box("orange", (along * 0.96, d, 0.55), V(tx, sy * (inner - d / 2), z - h / 2 - 0.27 - 0.55 * st))
    for z0, z1 in ((4.0, 11.0), (11.0, 18.0)):
        for sy in (-1, 1):
            p0, p1 = V(tx, -sy * inner, z0), V(tx, sy * inner, z1)
            member(b, "orange", p0, p1, (1.0, 1.0), V(1, 0, 0))
    b.box("orange", (3.6, 2 * inner + 0.4, 1.6), V(tx, 0, 18.4))


def build_golden_gate():
    mats = C.make_materials(GG_PAL)
    root = C.empty("golden_gate")
    b = Builder(GG_PAL)
    for tx in (-GG_TOWER_X, GG_TOWER_X):
        gg_tower(b, tx)
    towers = part(b, "towers", mats, root)

    b = Builder(GG_PAL)
    L = 2 * GG_SPAN
    zt, zb = GG_DECK - 0.4, GG_DECK - 4.6       # truss top and bottom chords
    b.box("road", (L, 2 * GG_TRUSS_Y - 0.6, 0.5), V(0, 0, GG_DECK - 0.25))
    b.box("orange", (L, 2 * GG_TRUSS_Y + 0.4, 0.5), V(0, 0, GG_DECK - 0.75))
    for y in (-1.2, 1.2):
        b.box("concrete", (L, 0.25, 0.04), V(0, y, GG_DECK + 0.01))
    for sy in (-1, 1):
        y = sy * GG_TRUSS_Y
        b.box("orange", (L, 0.5, 0.6), V(0, y, zt))
        b.box("orange", (L, 0.5, 0.6), V(0, y, zb))
        b.box("orange", (L, 0.12, 0.12), V(0, sy * (GG_TRUSS_Y + 0.2), GG_DECK + 1.1))
        n = int(L / 7.6)
        for k in range(n + 1):
            x = -GG_SPAN + k * L / n
            b.box("orange", (0.4, 0.4, zt - zb), V(x, y, (zt + zb) / 2))
            if k < n:
                x1 = -GG_SPAN + (k + 1) * L / n
                a, c = (V(x, y, zb), V(x1, y, zt)) if k % 2 else (V(x, y, zt), V(x1, y, zb))
                member(b, "orange", a, c, (0.32, 0.32), V(0, sy, 0))
            if k % 2 == 0:
                b.box("orange", (0.12, 0.12, 1.1), V(x, sy * (GG_TRUSS_Y + 0.2), GG_DECK + 0.55))
    deck = part(b, "deck", mats, root)

    # Main cables and suspenders; the suspenders every other truss panel.
    b = Builder(GG_PAL)
    for sy in (-1, 1):
        xs = [-GG_SPAN + 520.0 * k / 64 for k in range(65)] + [-GG_TOWER_X, GG_TOWER_X]
        xs = sorted(set(round(x, 3) for x in xs))
        S.loft(b, "orange", [V(x, sy * 4.6, gg_cable_z(x)) for x in xs], [0.42] * len(xs), sides=6)
        n = int(L / 7.6)
        for k in range(1, n):
            x = -GG_SPAN + k * L / n
            zc = gg_cable_z(x)
            if abs(abs(x) - GG_TOWER_X) < 3 or zc - GG_DECK < 2.0:
                continue
            b.box("orange_dark", (0.14, 0.14, zc - GG_DECK - 1.6), V(x, sy * 4.5, (zc + GG_DECK + 1.6) / 2))
    cables = part(b, "cables", mats, root)
    return root, [towers, deck, cables], [
        ("side", 0, 4, V(0, 0, 40), 140, 2.6),
        ("portals", 90, 3, V(-GG_TOWER_X, 0, 50), 100, 0.62),
        ("tower top", 70, 6, V(-GG_TOWER_X, 0, 80), 26, 0.9),
        ("deck", -35, 8, V(40, 0, 20), 18, 1.4),
    ]


# --- build, export, render -----------------------------------------------------------------

LANDMARKS = {
    # name: builder, preview outline width per metre of view height
    "salesfarce_tower": build_salesfarce,
    "pyramid": build_pyramid,
    "ferry_building": build_ferry_building,
    "coit_tower": build_coit_tower,
    "golden_gate": build_golden_gate,
}


def render_sheet(root, name, shots, height=900):
    """One tile per shot (label, turn in degrees, camera elevation in degrees, target in
    model space, metres of view height, aspect); tiles side by side, toon-shaded with
    inverted-hull outlines scaled to each shot."""
    scene = bpy.context.scene
    model = [o for o in scene.objects if o.type == "MESH"]
    for m in {s.material for o in model for s in o.material_slots if s.material}:
        C.toonify(m)
    ground_mat = bpy.data.materials.new("_ground")
    ground_mat.use_nodes = True
    ground_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (
        *[C.srgb_to_linear(c) for c in C.BG], 1)
    C.toonify(ground_mat, shadow_mul=(0.82, 0.83, 0.9))
    bpy.ops.mesh.primitive_plane_add(size=600)
    bpy.context.active_object.data.materials.append(ground_mat)
    sun_data = bpy.data.lights.new("sun", "SUN")
    sun_data.energy = 3.0
    sun_data.angle = math.radians(1.0)
    sun = bpy.data.objects.new("sun", sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 50
    cam_data.sensor_fit = "VERTICAL"
    cam_data.clip_end = 5000
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    scene.world = w
    r = scene.render
    r.engine = "BLENDER_EEVEE"
    r.film_transparent = True
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.eevee.taa_render_samples = 16
    eevee = scene.eevee
    if hasattr(eevee, "shadow_resolution_scale"):
        eevee.shadow_resolution_scale = 1.0
    vfov = 2 * math.atan(cam_data.sensor_height / 2 / cam_data.lens)
    tiles = []
    tmp = C.RENDERS_DIR / f".{name}_tmp.png"
    for label, turn, elev, target, view_h, aspect in shots:
        for o in [o for o in scene.objects if o.name.endswith("_outline")]:
            bpy.data.objects.remove(o)
        C.add_outlines(model, view_h * 0.0011)
        root.rotation_euler = (0, 0, math.radians(turn))
        bpy.context.view_layer.update()
        t = Matrix.Rotation(math.radians(turn), 4, "Z") @ Vector(target)
        d = view_h / 2 / math.tan(vfov / 2)
        el = math.radians(elev)
        cam.location = t + V(0, -d * math.cos(el), d * math.sin(el))
        cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler()
        r.resolution_y = height
        r.resolution_x = round(height * aspect)
        r.filepath = str(tmp)
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(str(tmp))
        img.colorspace_settings.name = "Non-Color"
        px = np.empty(r.resolution_x * height * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(height, r.resolution_x, 4)
        a = px[..., 3:4]
        tiles.append(px[..., :3] * a + np.array(C.BG, dtype=np.float32) * (1 - a))
        bpy.data.images.remove(img)
        tmp.unlink()
        print(f"  shot {label}")
    root.rotation_euler = (0, 0, 0)
    gap = np.ones((height, 10, 3), dtype=np.float32) * np.array(C.BG, dtype=np.float32)
    row = []
    for tile in tiles:
        row += [tile, gap]
    R.save_rgb(np.concatenate(row[:-1], axis=1), C.RENDERS_DIR / f"{name}.png")


def build(name):
    C.reset_scene()
    root, parts, shots = LANDMARKS[name]()
    meshes = [p for p in parts if p.type == "MESH"]
    C.report(parts)
    tris = C.triangle_count(meshes)
    assert tris <= BUDGET, f"{name} has {tris} triangles, over the budget of {BUDGET}"
    (C.MODELS_DIR / DIR).mkdir(parents=True, exist_ok=True)
    C.export_glb(f"{DIR}/{name}")
    render_sheet(root, f"landmark-{name}", shots)


def check():
    """Reimport every glb: nodes, triangle counts, bounds; reviews/landmarks.json."""
    out = {}
    for name in LANDMARKS:
        C.reset_scene()
        bpy.ops.import_scene.gltf(filepath=str(C.MODELS_DIR / DIR / f"{name}.glb"))
        objs = list(bpy.context.scene.objects)
        meshes = [o for o in objs if o.type == "MESH"]
        pts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
        lo = [round(min(p[i] for p in pts), 2) for i in range(3)]
        hi = [round(max(p[i] for p in pts), 2) for i in range(3)]
        tris = C.triangle_count(meshes)
        out[name] = {
            "triangles": tris, "budget": BUDGET,
            # Blender axes after import: X east, Y north (game -Z), Z up.
            "min": lo, "max": hi,
            "nodes": sorted(o.name for o in objs if o.parent is not None or o.type != "MESH"),
            "materials": sorted({s.material.name for o in meshes for s in o.material_slots if s.material}),
        }
        assert tris <= BUDGET, (name, tris)
    def fits(name, half_x, half_y, top):
        o = out[name]
        assert max(-o["min"][0], o["max"][0]) <= half_x + 0.3, (name, o)
        assert max(-o["min"][1], o["max"][1]) <= half_y + 0.3, (name, o)
        assert top[0] <= o["max"][2] <= top[1], (name, o)

    fits("salesfarce_tower", 20, 20, (160, 166))
    fits("pyramid", 20, 20, (118, 121))
    fits("ferry_building", 18, 20, (49, 56))
    fits("coit_tower", 10, 10, (32.5, 34))
    fits("golden_gate", GG_SPAN, 9, (GG_TOP, GG_TOP + 4))
    assert "crown" in out["salesfarce_tower"]["nodes"], out["salesfarce_tower"]
    assert "light_crown" in out["salesfarce_tower"]["materials"]
    assert "light_clock" in out["ferry_building"]["materials"]
    assert {"towers", "deck", "cables"} <= set(out["golden_gate"]["nodes"])
    (REVIEWS / "landmarks.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


def main():
    arg = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "all"
    if arg == "check":
        check()
    elif arg == "all":
        for name in LANDMARKS:
            build(name)
    else:
        build(arg)


if __name__ == "__main__":
    main()
