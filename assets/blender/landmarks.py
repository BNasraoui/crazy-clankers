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


# --- City Hall ------------------------------------------------------------------------------

CH_PAL = {"granite": 0xE7E2D6, "granite_dark": 0xC6BFAF, "trim": 0xF6F2E9, "window": 0x5D6E7F,
          "door": 0x4A3A2C, "roof": 0x6F7D84, "gold": 0xE4B03C, "gold_dark": 0xB98226, "plaza": 0xD6CFBF,
          "lawn": 0x86B24C, "leaf": 0x5E8F45, "trunk": 0x7A5440, "rail": 0x3C474E, "flag": 0x3A5FA8,
          "light_lamp": 0xFFF0C0, "light_lantern": 0xFFE2A0, "ink": INK}
CH_X0, CH_X1, CH_Y = -19.0, 1.5, 19.0     # the main block: west and east walls, half-length
CH_BASE = 1.2                              # the podium the building stands on
CH_RUST = 6.4                              # top of the rusticated ground storey
CH_ORDER = 15.4                            # top of the giant columns
CH_TOP = 18.2                              # top of the attic parapet
CH_DOME = (-8.5, 0.0)                      # the dome's centre
CH_POR = (-7.2, 7.2)                       # the portico's span across the east front


def ch_window(b, fr, x, z0, w, h, arched=False):
    f = fr @ Matrix.Translation((x, 0, 0))
    if arched:
        opening(b, "window", f, arch_pts(w, h, h - w / 2, steps=6, y=z0), proud=0.05)
        opening(b, "trim", f, arch_pts(w + 0.5, h + 0.3, h - w / 2, steps=6, y=z0 - 0.15), proud=0.025)
    else:
        opening(b, "window", f, [(-w / 2, z0), (w / 2, z0), (w / 2, z0 + h), (-w / 2, z0 + h)], proud=0.05)
        opening(b, "trim", f, [(-w / 2 - 0.25, z0 - 0.2), (w / 2 + 0.25, z0 - 0.2), (w / 2 + 0.25, z0 + h + 0.45),
                               (-w / 2 - 0.25, z0 + h + 0.45)], proud=0.025)


def ch_column(b, base, z0, z1, r=0.42, engaged=None):
    """A giant-order column: plinth, shaft, and a capital block; `engaged` (an outward
    normal) half-sinks it into the wall behind."""
    p = Vector(base)
    b.box("trim", (r * 2.6, r * 2.6, 0.5), V(p.x, p.y, z0 + 0.25))
    b.tube("granite", V(p.x, p.y, z0 + 0.5), V(p.x, p.y, z1 - 0.6), r, r * 0.88, sides=10)
    b.box("trim", (r * 2.2, r * 2.2, 0.3), V(p.x, p.y, z1 - 0.45))
    b.box("trim", (r * 2.7, r * 2.7, 0.3), V(p.x, p.y, z1 - 0.15))


def ch_cornice(b, x0, x1, y0, y1, z, h=0.7, proj=0.45):
    b.box("trim", (x1 - x0 + 2 * proj, y1 - y0 + 2 * proj, h), V((x0 + x1) / 2, (y0 + y1) / 2, z + h / 2))
    box_ink(b, ((x0 + x1) / 2, (y0 + y1) / 2, z + h / 2), (x1 - x0 + 2 * proj, y1 - y0 + 2 * proj, h), 0.1)


def build_city_hall():
    mats = C.make_materials(CH_PAL)
    root = C.empty("city_hall")
    b = Builder(CH_PAL)
    x0, x1, hy = CH_X0, CH_X1, CH_Y
    # The block: podium, rusticated ground storey, the order, the entablature and attic.
    b.box("granite_dark", (x1 - x0 + 1.2, 2 * hy + 1.2, CH_BASE), V((x0 + x1) / 2, 0, CH_BASE / 2))
    b.box("granite", (x1 - x0, 2 * hy, CH_TOP - CH_BASE), V((x0 + x1) / 2, 0, (CH_BASE + CH_TOP) / 2))
    for k in range(1, 5):
        z = CH_BASE + k * (CH_RUST - CH_BASE) / 5
        ring = [V(x0 - 0.03, -hy - 0.03, z), V(x1 + 0.03, -hy - 0.03, z), V(x1 + 0.03, hy + 0.03, z), V(x0 - 0.03, hy + 0.03, z)]
        for a, c in zip(ring, ring[1:] + ring[:1]):
            out = ((a + c) / 2 - V((x0 + x1) / 2, 0, z))
            out.z = 0
            ink_bar(b, a, c, out.normalized(), 0.07, mat="granite_dark")
    ch_cornice(b, x0, x1, -hy, hy, CH_RUST - 0.4, h=0.5, proj=0.2)
    ch_cornice(b, x0, x1, -hy, hy, CH_ORDER, h=1.0, proj=0.5)
    b.box("granite", (x1 - x0 - 0.2, 2 * hy - 0.2, 0.3), V((x0 + x1) / 2, 0, CH_TOP - 0.15))
    ch_cornice(b, x0, x1, -hy, hy, CH_TOP - 0.5, h=0.5, proj=0.2)
    b.box("roof", (x1 - x0 - 1.0, 2 * hy - 1.0, 0.4), V((x0 + x1) / 2, 0, CH_TOP + 0.1))

    # East front: end pavilions with paired columns, the long wings with columns between
    # tall windows, round-headed windows in the rusticated storey.
    east = wall_frame(V(x1, 0, 0), V(0, 1, 0), V(1, 0, 0))
    for sy in (-1, 1):
        cy = sy * (hy - 2.2)
        b.box("granite", (1.2, 4.6, CH_TOP - CH_BASE + 0.6), V(x1 + 0.6, cy, (CH_BASE + CH_TOP + 0.6) / 2))
        ch_cornice(b, x1, x1 + 1.2, cy - 2.3, cy + 2.3, CH_TOP + 0.1, h=0.5, proj=0.25)
        for off in (-1.5, 1.5):
            ch_column(b, V(x1 + 1.6, cy + off, 0), CH_RUST, CH_ORDER)
        fr = wall_frame(V(x1 + 1.2, cy, 0), V(0, 1, 0), V(1, 0, 0))
        ch_window(b, fr, 0, CH_RUST + 1.0, 1.6, 5.4, arched=True)
        ch_window(b, fr, 0, CH_BASE + 1.0, 1.6, 3.4, arched=True)
        ch_window(b, fr, 0, CH_ORDER + 1.2, 1.3, 0.9)
        # The wings between pavilion and portico.
        ys = [sy * (CH_POR[1] + 1.35 + k * 2.55) for k in range(3)]
        for y in ys:
            ch_window(b, east, y, CH_RUST + 1.2, 1.3, 4.6)
            ch_window(b, east, y, CH_BASE + 1.0, 1.3, 3.0, arched=True)
            ch_window(b, east, y, CH_ORDER + 1.25, 1.1, 0.8)
        for k in range(4):
            y = sy * (CH_POR[1] + 0.1 + k * 2.55)
            ch_column(b, V(x1 + 0.25, y, 0), CH_RUST, CH_ORDER, r=0.36)
    # The portico: a projecting centre on arched doors, six free columns, the pediment.
    py0, py1 = CH_POR
    xp = x1 + 3.4
    b.box("granite", (3.4, py1 - py0, CH_RUST - CH_BASE), V(x1 + 1.7, 0, (CH_BASE + CH_RUST) / 2))
    ch_cornice(b, x1, xp, py0, py1, CH_RUST - 0.2, h=0.6, proj=0.2)
    pfr = wall_frame(V(xp, 0, 0), V(0, 1, 0), V(1, 0, 0))
    for y in (-3.4, 0.0, 3.4):
        f = pfr @ Matrix.Translation((y, 0, 0))
        opening(b, "trim", f, arch_pts(2.6, 4.4, 3.1, steps=8, y=CH_BASE), proud=0.03)
        opening(b, "door", f, arch_pts(2.0, 4.0, 3.0, steps=8, y=CH_BASE), proud=0.06)
    for y in (-6.3, -3.8, -1.25, 1.25, 3.8, 6.3):
        ch_column(b, V(xp - 0.6, y, 0), CH_RUST, CH_ORDER, r=0.46)
    for y in (-3.8, -1.25, 1.25, 3.8):
        ch_window(b, east, y, CH_RUST + 1.0, 1.4, 5.6, arched=True)
    b.box("granite", (3.0, py1 - py0 + 1.0, 1.2), V(x1 + 1.5, 0, CH_ORDER + 0.6))
    ch_cornice(b, x1, xp, py0 - 0.3, py1 + 0.3, CH_ORDER + 1.2, h=0.5, proj=0.2)
    zp = CH_ORDER + 1.7
    tri = [(py0 - 0.6, zp), (py1 + 0.6, zp), (0.0, zp + 3.4)]
    b.prism("trim", tri, 3.6, Matrix.Translation((x1 + 1.8, 0, 0)) @ Matrix.Rotation(math.pi / 2, 4, "Z")
            @ Matrix.Rotation(math.pi / 2, 4, "X"))
    inner = [(py0 + 0.6, zp + 0.35), (py1 - 0.6, zp + 0.35), (0.0, zp + 2.75)]
    b.prism("granite", inner, 0.2, Matrix.Translation((x1 + 3.62, 0, 0)) @ Matrix.Rotation(math.pi / 2, 4, "Z")
            @ Matrix.Rotation(math.pi / 2, 4, "X"))
    for a, c in ((tri[0], tri[2]), (tri[2], tri[1]), (tri[0], tri[1])):
        ink_bar(b, V(x1 + 3.62, a[0], a[1]), V(x1 + 3.62, c[0], c[1]), V(1, 0, 0.3), 0.1)
    # The other three sides: plain windows between pilasters.
    for fr, n, span in ((wall_frame(V(x0, 0, 0), V(0, -1, 0), V(-1, 0, 0)), 13, 2 * hy),
                        (wall_frame(V(0, hy, 0) + V((x0 + x1) / 2, 0, 0), V(-1, 0, 0), V(0, 1, 0)), 7, x1 - x0),
                        (wall_frame(V(0, -hy, 0) + V((x0 + x1) / 2, 0, 0), V(1, 0, 0), V(0, -1, 0)), 7, x1 - x0)):
        for k in range(n):
            u = -span / 2 + (k + 0.5) * span / n
            ch_window(b, fr, u, CH_RUST + 1.2, 1.2, 4.4)
            ch_window(b, fr, u, CH_BASE + 1.0, 1.2, 2.8, arched=True)
            if k:
                p = fr @ Vector((u - span / n / 2, 0, 0))
                b.box("trim", (0.7, 0.7, CH_ORDER - CH_RUST - 0.2), V(p.x, p.y, (CH_RUST + CH_ORDER) / 2))
    # Front steps up to the podium, the width of the portico, and the lamp standards.
    for k in range(5):
        d = 3.8 - k * 0.7
        b.box("granite", (d, py1 - py0 + 4.0 - k * 0.3, CH_BASE / 5), V(xp + d / 2 - 0.1, 0, CH_BASE / 10 + k * CH_BASE / 5))
    for y in (py0 - 1.6, py1 + 1.6):
        b.box("granite_dark", (1.6, 1.2, 2.0), V(xp + 2.3, y, 1.0))
        b.tube("rail", V(xp + 2.3, y, 2.0), V(xp + 2.3, y, 4.6), 0.12, 0.09, sides=6)
        b.sphere("light_lamp", V(xp + 2.3, y, 4.9), (0.38, 0.38, 0.45), u=8, v=5)
    hall = part(b, "hall", mats, root)

    # The dome: square base, colonnaded drum, attic, the gilded ribbed dome, the lantern.
    b = Builder(CH_PAL)
    dx, dy = CH_DOME
    c = V(dx, dy, 0)
    b.box("granite", (17.0, 17.0, 4.6), V(dx, dy, CH_TOP + 2.3))
    ch_cornice(b, dx - 8.5, dx + 8.5, dy - 8.5, dy + 8.5, CH_TOP + 4.0, h=0.6, proj=0.3)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box("granite", (3.2, 3.2, 3.0), V(dx + sx * 7.2, dy + sy * 7.2, CH_TOP + 6.1))
            b.box("trim", (3.6, 3.6, 0.4), V(dx + sx * 7.2, dy + sy * 7.2, CH_TOP + 7.8))
            b.tube("gold", V(dx + sx * 7.2, dy + sy * 7.2, CH_TOP + 8.0), V(dx + sx * 7.2, dy + sy * 7.2, CH_TOP + 9.4), 1.1, 0.2, sides=8)
    zd0, zd1 = CH_TOP + 4.6, CH_TOP + 12.6
    def circ(r, z, n=32):
        return [V(dx + r * math.cos(2 * math.pi * k / n), dy + r * math.sin(2 * math.pi * k / n), z) for k in range(n)]
    ring_stack(b, [circ(7.0, zd0), circ(7.0, zd1)], lambda i: "granite")
    for k in range(16):
        a = 2 * math.pi * (k + 0.5) / 16
        n = V(math.cos(a), math.sin(a), 0)
        ch_column(b, c + n * 7.55, zd0, zd1 - 0.2, r=0.34)
        a2 = 2 * math.pi * k / 16
        n2 = V(math.cos(a2), math.sin(a2), 0)
        fr = wall_frame(c + n2 * 7.0, V(-n2.y, n2.x, 0), n2)
        opening(b, "window", fr, arch_pts(1.2, 4.8, 4.2, steps=6, y=zd0 + 1.4), depth=0.3, proud=0.06)
    ring_stack(b, [circ(8.1, zd1 - 0.2), circ(8.1, zd1 + 0.8), circ(7.4, zd1 + 0.8), circ(7.4, zd1 + 2.4),
                   circ(7.8, zd1 + 2.4), circ(7.8, zd1 + 2.9)], lambda i: ("trim", "trim", "granite", "trim", "trim")[i])
    for z in (zd1 + 0.8, zd1 + 2.9):
        pts = circ(8.15 if z < zd1 + 1 else 7.85, z)
        for a0, a1 in zip(pts, pts[1:] + pts[:1]):
            ink_bar(b, a0, a1, ((a0 + a1) / 2 - V(dx, dy, z)).normalized() + V(0, 0, 0.8), 0.1)
    # The dome is a little taller than a hemisphere, as the real one is.
    z0 = zd1 + 2.9
    prof = [(7.2, 0.0), (7.05, 2.0), (6.6, 4.0), (5.8, 6.0), (4.6, 8.0), (3.0, 9.8), (1.9, 10.6)]
    ring_stack(b, [circ(r, z0 + h) for r, h in prof], lambda i: "gold")
    for k in range(16):
        a = 2 * math.pi * k / 16
        pts = [V(dx + (r + 0.03) * math.cos(a), dy + (r + 0.03) * math.sin(a), z0 + h) for r, h in prof]
        for p0, p1 in zip(pts, pts[1:]):
            n = V(math.cos(a), math.sin(a), 0) + V(0, 0, 0.6)
            S.bar(b, "gold_dark", p0, p1, n, w=0.32, d=0.12, sink=0.04)
    for k in range(16):
        a = 2 * math.pi * (k + 0.5) / 16
        n = V(math.cos(a), math.sin(a), 0)
        p = c + n * 6.75 + V(0, 0, z0 + 3.2)
        b.box("gold_dark", (0.5, 0.9, 1.1), p, rot=Matrix.Rotation(a, 4, "Z"))
    zl = z0 + 10.6
    b.tube("trim", V(dx, dy, zl - 0.1), V(dx, dy, zl + 0.6), 2.3, 2.3, sides=16)
    b.tube("light_lantern", V(dx, dy, zl + 0.6), V(dx, dy, zl + 3.6), 1.5, 1.5, sides=12)
    for k in range(8):
        a = 2 * math.pi * k / 8
        p = c + V(math.cos(a), math.sin(a), 0) * 1.75
        b.box("trim", (0.42, 0.42, 3.0), p + V(0, 0, zl + 2.1))
    b.tube("trim", V(dx, dy, zl + 3.6), V(dx, dy, zl + 4.1), 2.2, 2.2, sides=16)
    b.sphere("gold", V(dx, dy, zl + 4.1), (1.9, 1.9, 1.7), u=12, v=6)
    b.tube("gold", V(dx, dy, zl + 5.4), V(dx, dy, zl + 7.4), 0.35, 0.12, sides=8)
    b.sphere("gold", V(dx, dy, zl + 7.6), (0.32, 0.32, 0.32), u=8, v=5)
    dome = part(b, "dome", mats, root, pivot=(dx, dy, CH_TOP))

    # Civic Center Plaza: a plinth, paving, two lawns under rows of clipped plane trees,
    # and the flagpoles.
    b = Builder(CH_PAL)
    b.box("granite_dark", (40.0, 40.0, 8.0), V(0, 0, -4.0 + 0.0))
    b.box("plaza", (39.8, 39.8, 0.2), V(0, 0, 0.1))
    for sy in (-1, 1):
        cy = sy * 11.5
        b.box("lawn", (9.0, 12.0, 0.3), V(13.5, cy, 0.25))
        b.box("granite", (9.4, 12.4, 0.2), V(13.5, cy, 0.15))
        for k in range(4):
            y = cy - 4.5 + k * 3.0
            for x in (9.2, 17.8):
                b.tube("trunk", V(x, y, 0.2), V(x, y, 2.4), 0.2, 0.16, sides=6)
                b.box("leaf", (2.4, 2.4, 1.8), V(x, y, 3.3), bevel=0.35)
    for y in (-2.2, 2.2):
        b.tube("rail", V(17.5, y, 0.2), V(17.5, y, 13.0), 0.14, 0.08, sides=6)
        b.sphere("gold", V(17.5, y, 13.1), (0.2, 0.2, 0.2), u=6, v=4)
    b.box("flag", (0.06, 2.6, 1.6), V(17.5, -2.2 + 1.35, 12.0))
    b.box("flag", (0.06, 2.6, 1.6), V(17.5, 2.2 + 1.35, 12.0))
    plaza = part(b, "plaza", mats, root)
    return root, [hall, dome, plaza], [
        ("3/4 east", -125, 9, V(0, 0, 24), 58, 1.0),
        ("east front", -90, 4, V(2, 0, 22), 54, 0.95),
        ("dome", -110, 6, V(dx, dy, 40), 20, 0.85),
        ("portico", -120, 10, V(4, 0, 9), 22, 1.25),
    ]


# --- Dragon Gate ----------------------------------------------------------------------------

DG_PAL = {"stone": 0xC2BCAE, "stone_dark": 0x938D80, "tile": 0x3E9A62, "tile_dark": 0x276B44,
          "beam": 0xC4392C, "beam_dark": 0x8C2620, "gold": 0xE7B53C, "blue": 0x2C5C92, "jade": 0x63BFA2,
          "lion": 0xD3CCBA, "light_lantern": 0xFF6B3D, "ink": INK}
DG_INNER = 6.4     # inner pillars, either side of the roadway (centre on the curb line)
DG_OUTER = 9.8     # outer pillars, at the back of the sidewalk: the only solid parts
DG_DEEP = 3.0      # the pillars reach this far below the street


def dg_roof(b, cx, z0, hx, hy, rise, curl, nx=10, ny=4):
    """A green-tiled roof with swept-up corners over cx ± hx by ± hy, its eave at z0 and
    its ridge along X; the rows of tiles are drawn as lines down the long slopes."""
    def perim():
        out = []
        for k in range(nx):
            out.append((-1 + 2 * k / nx, -1.0))
        for k in range(ny):
            out.append((1.0, -1 + 2 * k / ny))
        for k in range(nx):
            out.append((1 - 2 * k / nx, 1.0))
        for k in range(ny):
            out.append((-1.0, 1 - 2 * k / ny))
        return out
    uv = perim()
    T = [-0.12, 0.0, 0.2, 0.42, 0.66, 0.86, 1.0]
    rings = []
    for t in T:
        tt = max(t, 0.0)
        sx, sy = hx * (1 - 0.28 * tt), hy * (1 - 0.9 * tt)
        z = z0 + rise * tt ** 1.6 - (0.32 if t < 0 else 0.0)
        ring = []
        for u, v in uv:
            lift = curl * (1 - tt) ** 2 * abs(u) ** 6 * abs(v) ** 6
            flare = 1 + 0.07 * lift / max(curl, 1e-6)
            ring.append(V(cx + u * sx * flare, v * sy * flare, z + lift))
        rings.append(ring)
    ring_stack(b, rings, lambda i: "tile_dark" if i == 0 else "tile")
    # Tile rows on the long slopes, and the hip lines at the corners.
    for j, (u, v) in enumerate(uv):
        corner = abs(u) == 1 and abs(v) == 1
        if abs(v) == 1 and (corner or j % 2 == 0):
            n = V(0, v, 1.4)
            for r0, r1 in zip(rings[1:], rings[2:]):
                S.bar(b, "tile_dark" if not corner else "ink", r0[j], r1[j], n, w=0.16 if corner else 0.1, d=0.06, sink=0.04)
    # The eave line drawn in ink.
    for k in range(len(uv)):
        a, c = rings[1][k], rings[1][(k + 1) % len(uv)]
        out = (a + c) / 2 - V(cx, 0, (a.z + c.z) / 2)
        out.z = 0
        S.bar(b, "ink", a, c, out.normalized() + V(0, 0, 0.5), w=0.1, d=0.04, sink=0.04)
    top = rings[-1]
    zr = top[0].z
    rx = hx * (1 - 0.28)
    b.box("tile_dark", (2 * rx + 0.5, 0.55, 0.55), V(cx, 0, zr + 0.2))
    b.box("gold", (2 * rx + 0.3, 0.6, 0.12), V(cx, 0, zr + 0.05))
    return zr + 0.47, rx


def dg_dragon(b, x, zr, side):
    """A gilded dragon on the ridge end, tail curled up at the end, head reaching in."""
    s = side
    pts = [V(x + s * 0.2, 0, zr + 1.6), V(x + s * 0.45, 0, zr + 0.9), V(x, 0, zr + 0.25), V(x - s * 0.7, 0, zr + 0.2),
           V(x - s * 1.3, 0, zr + 0.75), V(x - s * 1.7, 0, zr + 1.2), V(x - s * 2.2, 0, zr + 1.15)]
    S.loft(b, "gold", pts, [0.02, 0.17, 0.24, 0.27, 0.26, 0.24, 0.0], sides=7)
    h = V(x - s * 2.1, 0, zr + 1.25)
    b.box("gold", (0.75, 0.45, 0.5), h, bevel=0.08)
    b.box("gold", (0.5, 0.3, 0.22), h + V(-s * 0.5, 0, -0.05))
    for sy in (-1, 1):
        b.tube("gold", h + V(s * 0.1, sy * 0.12, 0.2), h + V(s * 0.55, sy * 0.22, 0.75), 0.07, 0.02, sides=5)
        b.box("ink", (0.12, 0.04, 0.1), h + V(-s * 0.18, sy * 0.23, 0.08))
    for k, (dx, dz) in enumerate(((0.4, 0.55), (-0.8, 0.5), (-1.5, 0.95))):
        b.tube("jade", V(x + s * dx, 0, zr + dz), V(x + s * dx, 0, zr + dz + 0.4), 0.12, 0.0, sides=4)
    for dx in (-0.6, -1.4):
        b.tube("gold", V(x + s * dx, 0, zr + 0.5), V(x + s * dx, 0.25, zr - 0.05), 0.07, 0.06, sides=5)
        b.tube("gold", V(x + s * dx, 0, zr + 0.5), V(x + s * dx, -0.25, zr - 0.05), 0.07, 0.06, sides=5)


def dg_fish(b, x, zr, side):
    """A ridge-end carp, tail flipped up, mouth on the ridge."""
    s = side
    pts = [V(x - s * 0.2, 0, zr), V(x, 0, zr + 0.35), V(x + s * 0.12, 0, zr + 0.8), V(x + s * 0.05, 0, zr + 1.15)]
    S.loft(b, "jade", pts, [0.18, 0.24, 0.17, 0.05], sides=6)
    b.prism("gold", [(-0.35, 0), (0.35, 0), (0.45, 0.5), (0, 0.25), (-0.45, 0.5)], 0.08,
            Matrix.Translation((x + s * 0.05, 0, zr + 1.1)) @ Matrix.Rotation(math.pi / 2, 4, "X"))
    for sy in (-1, 1):
        b.box("ink", (0.08, 0.04, 0.08), V(x - s * 0.05, sy * 0.21, zr + 0.3))


def dg_lion(b, x, y, face):
    """A seated guardian lion on its plinth, facing `face` (+1 south... -1 north)."""
    b.box("stone_dark", (1.3, 1.7, 1.1), V(x, y, 0.55))
    b.box("lion", (1.4, 1.8, 0.15), V(x, y, 1.15))
    b.sphere("lion", V(x, y + face * 0.15, 1.75), (0.5, 0.6, 0.55), u=8, v=5)
    b.sphere("lion", V(x, y + face * 0.45, 2.45), (0.55, 0.5, 0.5), u=8, v=5)
    b.sphere("lion", V(x, y + face * 0.85, 2.35), (0.28, 0.2, 0.2), u=6, v=4)
    for sx in (-1, 1):
        b.box("lion", (0.22, 0.25, 0.75), V(x + sx * 0.25, y + face * 0.55, 1.6))
        b.box("ink", (0.12, 0.04, 0.08), V(x + sx * 0.2, y + face * 0.92, 2.55))
    b.sphere("lion", V(x + 0.35, y + face * 0.7, 1.35), (0.24, 0.24, 0.24), u=6, v=4)


def build_dragon_gate():
    mats = C.make_materials(DG_PAL)
    root = C.empty("dragon_gate")
    b = Builder(DG_PAL)
    # Pillars: stone shafts on plinths, reaching down past the street for the slope.
    for sx in (-1, 1):
        for x, w, top in ((sx * DG_INNER, 1.1, 8.3), (sx * DG_OUTER, 0.95, 5.6)):
            b.box("stone_dark", (w + 0.5, w + 0.6, DG_DEEP + 1.0), V(x, 0, (1.0 - DG_DEEP) / 2))
            b.box("stone", (w, w, top - 1.0), V(x, 0, (1.0 + top) / 2))
            b.box("stone_dark", (w + 0.2, w + 0.2, 0.25), V(x, 0, top - 0.1))
            for sy in (-1, 1):
                S.bar(b, "stone_dark", V(x - w / 2 + 0.12, sy * w / 2, 1.0), V(x - w / 2 + 0.12, sy * w / 2, top - 0.3), V(0, sy, 0), w=0.06, d=0.02, sink=0.02)
                S.bar(b, "stone_dark", V(x + w / 2 - 0.12, sy * w / 2, 1.0), V(x + w / 2 - 0.12, sy * w / 2, top - 0.3), V(0, sy, 0), w=0.06, d=0.02, sink=0.02)
    # The central span: two red lintels with gilt bands, the blue name board between them,
    # rows of brackets under the eaves.
    for z, h in ((5.6, 0.55), (7.2, 0.6)):
        b.box("beam", (2 * DG_INNER + 0.6, 0.8, h), V(0, 0, z + h / 2))
        for sy in (-1, 1):
            b.box("gold", (2 * DG_INNER + 0.4, 0.04, 0.1), V(0, sy * 0.41, z + h / 2))
            for x in (-4.2, 0.0, 4.2):
                b.box("jade", (1.8, 0.04, h - 0.18), V(x, sy * 0.41, z + h / 2))
                b.box("gold", (0.5, 0.06, 0.18), V(x, sy * 0.42, z + h / 2))
    b.box("beam_dark", (2 * DG_INNER - 0.4, 0.5, 1.05), V(0, 0, 6.68))
    for sy in (-1, 1):
        b.box("gold", (3.7, 0.12, 1.25), V(0, sy * 0.3, 6.68))
        b.box("blue", (3.3, 0.16, 0.95), V(0, sy * 0.33, 6.68))
        for k in range(4):
            x = -1.17 + k * 0.78
            b.box("gold", (0.42, 0.06, 0.55), V(x, sy * 0.42, 6.68))
            b.box("blue", (0.12, 0.07, 0.38), V(x - 0.06, sy * 0.44, 6.7))
    for k in range(15):
        x = -6.3 + k * 0.9
        b.box("beam_dark", (0.35, 1.5, 0.3), V(x, 0, 7.95))
        b.box("gold", (0.5, 1.9, 0.2), V(x, 0, 8.18))
    zr, rx = dg_roof(b, 0, 8.45, 7.7, 2.4, 2.1, 0.9)
    dg_dragon(b, rx - 0.3, zr, 1)
    dg_dragon(b, -rx + 0.3, zr, -1)
    b.tube("gold", V(0, 0, zr), V(0, 0, zr + 0.4), 0.15, 0.15, sides=6)
    b.sphere("beam", V(0, 0, zr + 0.75), (0.38, 0.38, 0.38), u=8, v=6)
    for k in range(5):
        a = math.pi * (0.15 + 0.7 * k / 4)
        b.tube("gold", V(0, 0, zr + 0.75) + V(math.cos(a), 0, math.sin(a)) * 0.3,
               V(0, 0, zr + 0.75) + V(math.cos(a), 0, math.sin(a)) * 0.75, 0.1, 0.0, sides=4)
    # Two red lanterns hang under the central lintel.
    for x in (-3.2, 3.2):
        b.tube("ink", V(x, 0, 5.6), V(x, 0, 5.3), 0.02, 0.02, sides=4)
        b.box("gold", (0.4, 0.4, 0.12), V(x, 0, 5.2))
        b.sphere("light_lantern", V(x, 0, 4.75), (0.42, 0.42, 0.45), u=10, v=6)
        b.box("gold", (0.36, 0.36, 0.1), V(x, 0, 4.28))
        b.tube("gold", V(x, 0, 4.24), V(x, 0, 3.8), 0.08, 0.02, sides=5)
    # The side spans over the sidewalks: a lintel, brackets and a lower roof with carp.
    for sx in (-1, 1):
        cx = sx * (DG_INNER + DG_OUTER) / 2
        span = DG_OUTER - DG_INNER
        b.box("beam", (span + 0.6, 0.7, 0.5), V(cx, 0, 4.25))
        for sy in (-1, 1):
            b.box("gold", (span + 0.4, 0.04, 0.1), V(cx, sy * 0.36, 4.25))
            b.box("jade", (1.2, 0.04, 0.32), V(cx, sy * 0.36, 4.25))
        b.box("beam_dark", (span + 0.2, 0.45, 0.5), V(cx, 0, 4.75))
        for k in range(5):
            x = cx - 1.5 + k * 0.75
            b.box("beam_dark", (0.3, 1.2, 0.25), V(x, 0, 5.12))
            b.box("gold", (0.42, 1.5, 0.16), V(x, 0, 5.3))
        zs, rs = dg_roof(b, cx, 5.45, 2.55, 1.9, 1.45, 0.6, nx=6, ny=4)
        dg_fish(b, cx + rs - 0.15, zs - 0.1, 1)
        dg_fish(b, cx - rs + 0.15, zs - 0.1, -1)
    gate = part(b, "gate", mats, root)

    # Guardian lions on the south side, beyond the sidewalk.
    b = Builder(DG_PAL)
    for sx in (-1, 1):
        dg_lion(b, sx * (DG_OUTER + 0.7), -1.9, -1)
    lions = part(b, "lions", mats, root)
    return root, [gate, lions], [
        ("3/4 south", -25, 8, V(0, 0, 5.5), 15, 1.6),
        ("south", 0, 3, V(0, 0, 5.5), 14, 1.65),
        ("ridge", -30, 12, V(4, 0, 9.5), 6, 1.4),
        ("side", -70, 6, V(0, 0, 5.0), 13, 1.1),
    ]


# --- Palace of Fine Arts --------------------------------------------------------------------

PF_PAL = {"stone": 0xEAD2B2, "stone_dark": 0xD2B08B, "trim": 0xF5E6CF, "shade": 0x6C5A52,
          "dome": 0xD4875A, "dome_rib": 0xAE6A44, "frieze": 0xC99C78, "lawn": 0x86B24C,
          "reed": 0x6E9A4A, "leaf": 0x4F7F43, "trunk": 0x7A5440, "swan": 0xF7F5EE, "beak": 0xE08A2E,
          "rail": 0x3C474E, "light_lamp": 0xFFF0C0, "ink": INK}
PF_ROT = (-7.0, 0.0)      # the rotunda's centre
PF_R = 8.0                # its piers' radius: wide enough to drive a cab through the arches
PF_ARC = (6.0, 0.0, 21.0)  # the colonnade: centre and radius of its arc
PF_WINGS = ((125.0, 163.0), (197.0, 235.0))
PF_LAGOON = (10.0, -1.0, 8.0, 13.0)  # centre, radii (x, y); the game carves it (src/world.ts)
PF_WATER = -0.5           # the lagoon's surface below the model's origin


def pf_column(b, p, z0, z1, r=0.36):
    b.box("trim", (r * 2.6, r * 2.6, 0.45), V(p.x, p.y, z0 + 0.22))
    b.tube("stone", V(p.x, p.y, z0 + 0.45), V(p.x, p.y, z1 - 0.55), r, r * 0.86, sides=10)
    b.box("trim", (r * 2.4, r * 2.4, 0.55), V(p.x, p.y, z1 - 0.27), taper=(1.25, 1.25))


def build_palace_of_fine_arts():
    mats = C.make_materials(PF_PAL)
    root = C.empty("palace_of_fine_arts")
    b = Builder(PF_PAL)
    rx, ry = PF_ROT
    c = V(rx, ry, 0)
    def octo(r, z, k0=0.5):
        return [c + V(r * math.cos(2 * math.pi * (k + k0) / 8), r * math.sin(2 * math.pi * (k + k0) / 8), z) for k in range(8)]
    # Floor and steps.
    ring_stack(b, [octo(PF_R + 2.6, -2.0), octo(PF_R + 2.6, 0.3)], lambda i: "stone_dark")
    ring_stack(b, [octo(PF_R + 1.9, 0.3), octo(PF_R + 1.9, 0.6)], lambda i: "trim")
    # Eight piers at the corners, each fronted by paired columns; arches between them.
    zs, za, ze = 7.6, 12.6, 14.2
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        n = V(math.cos(a), math.sin(a), 0)
        p = c + n * PF_R
        b.box("stone", (2.0, 2.0, za - 0.6), V(p.x, p.y, 0.6 + (za - 0.6) / 2), rot=Matrix.Rotation(a, 4, "Z"))
        t = V(-n.y, n.x, 0)
        for off in (-0.62, 0.62):
            pf_column(b, p + n * 1.25 + t * off, 0.6, za - 0.2)
    for k in range(8):
        a = 2 * math.pi * k / 8
        n = V(math.cos(a), math.sin(a), 0)
        apo = PF_R * math.cos(math.pi / 8)
        side = 2 * PF_R * math.sin(math.pi / 8)
        hw = side / 2 - 0.85
        fr = wall_frame(c + n * apo, V(-n.y, n.x, 0), n)
        spand = [(side / 2 + 0.2, za), (side / 2 + 0.2, zs), (hw, zs)] + \
                [(hw * math.cos(math.pi * j / 8), zs + hw * math.sin(math.pi * j / 8)) for j in range(1, 8)] + \
                [(-hw, zs), (-side / 2 - 0.2, zs), (-side / 2 - 0.2, za)]
        b.prism("stone", spand, 1.4, fr)
        arc = [V(hw * math.cos(math.pi * j / 8), zs + hw * math.sin(math.pi * j / 8), 0.72) for j in range(9)]
        for p0, p1 in zip(arc, arc[1:]):
            S.bar(b, "ink", fr @ p0, fr @ p1, n, w=0.12, d=0.03, sink=0.03)
    # Entablature, the attic with its relief panels, cornice, a short drum and the dome.
    ring_stack(b, [octo(PF_R + 1.95, za), octo(PF_R + 1.95, ze)], lambda i: "trim")
    for a0, a1 in zip(octo(PF_R + 1.98, ze), octo(PF_R + 1.98, ze)[1:] + octo(PF_R + 1.98, ze)[:1]):
        ink_bar(b, a0, a1, ((a0 + a1) / 2 - V(rx, ry, ze)).normalized() + V(0, 0, 0.6), 0.1)
    zt = ze + 4.0
    ring_stack(b, [octo(PF_R + 0.6, ze), octo(PF_R + 0.6, zt)], lambda i: "stone")
    for k in range(8):
        a = 2 * math.pi * k / 8
        n = V(math.cos(a), math.sin(a), 0)
        apo = (PF_R + 0.6) * math.cos(math.pi / 8)
        fr = wall_frame(c + n * apo, V(-n.y, n.x, 0), n)
        w = 2 * (PF_R + 0.6) * math.sin(math.pi / 8) - 1.4
        opening(b, "frieze", fr, [(-w / 2, ze + 0.7), (w / 2, ze + 0.7), (w / 2, zt - 0.7), (-w / 2, zt - 0.7)], proud=0.05)
        for j in range(4):
            x = -w / 2 + (j + 0.5) * w / 4
            opening(b, "trim", fr, [(x - 0.3, ze + 0.9), (x + 0.3, ze + 0.9), (x + 0.3, zt - 1.5), (x - 0.3, zt - 1.5)], proud=0.08)
            b.sphere("trim", fr @ Vector((x, zt - 1.2, 0.12)), (0.28, 0.28, 0.12), u=6, v=4)
    ring_stack(b, [octo(PF_R + 1.2, zt), octo(PF_R + 1.2, zt + 0.7)], lambda i: "trim")
    for a0, a1 in zip(octo(PF_R + 1.23, zt + 0.7), octo(PF_R + 1.23, zt + 0.7)[1:] + octo(PF_R + 1.23, zt + 0.7)[:1]):
        ink_bar(b, a0, a1, ((a0 + a1) / 2 - V(rx, ry, zt)).normalized() + V(0, 0, 0.6), 0.1)
    def circ(r, z, n=32):
        return [c + V(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), z) for k in range(n)]
    zd = zt + 0.7
    ring_stack(b, [circ(PF_R - 0.2, zd), circ(PF_R - 0.2, zd + 1.2)], lambda i: "stone_dark")
    prof = [(PF_R - 0.1, 0.0), (PF_R - 0.4, 1.8), (PF_R - 1.3, 3.6), (PF_R - 2.7, 5.2), (PF_R - 4.6, 6.4), (1.3, 7.0)]
    z0 = zd + 1.2
    ring_stack(b, [circ(r, z0 + h) for r, h in prof], lambda i: "dome")
    for k in range(16):
        a = 2 * math.pi * k / 16
        pts = [c + V((r + 0.03) * math.cos(a), (r + 0.03) * math.sin(a), z0 + h) for r, h in prof]
        for p0, p1 in zip(pts, pts[1:]):
            S.bar(b, "dome_rib", p0, p1, V(math.cos(a), math.sin(a), 0.7), w=0.3, d=0.1, sink=0.04)
    b.tube("stone", c + V(0, 0, z0 + 6.9), c + V(0, 0, z0 + 7.7), 1.4, 1.2, sides=12)
    rotunda = part(b, "rotunda", mats, root)

    # The colonnade: two wings of paired columns on an arc round the lagoon, under a deep
    # entablature topped with the planter boxes (the weeping women lean on their corners).
    b = Builder(PF_PAL)
    ax, ay, R = PF_ARC
    zc, zent = 9.0, 10.4
    for a0, a1 in PF_WINGS:
        n_st = 6
        angs = [math.radians(a0 + (a1 - a0) * k / (n_st - 1)) for k in range(n_st)]
        for a in angs:
            n = V(math.cos(a), math.sin(a), 0)
            t = V(-n.y, n.x, 0)
            p = V(ax, ay, 0) + n * R
            b.box("stone_dark", (2.6, 3.2, 0.6), V(p.x, p.y, 0.3), rot=Matrix.Rotation(a, 4, "Z"))
            for off in (-0.55, 0.55):
                for rr in (-0.9, 0.9):
                    pf_column(b, p + t * off + n * rr, 0.6, zc, r=0.3)
            b.box("frieze", (2.0, 2.0, 2.2), V(p.x, p.y, zent + 1.1), rot=Matrix.Rotation(a, 4, "Z"))
            b.box("trim", (2.3, 2.3, 0.3), V(p.x, p.y, zent + 2.35), rot=Matrix.Rotation(a, 4, "Z"))
            for sx in (-1, 1):
                for sy in (-1, 1):
                    q = p + t * (sx * 0.95) + n * (sy * 0.95)
                    b.box("trim", (0.32, 0.32, 1.9), V(q.x, q.y, zent + 1.05), rot=Matrix.Rotation(a, 4, "Z"))
            fr = wall_frame(p + n * 1.01, t, n)
            opening(b, "shade", fr, [(-0.55, zent + 0.5), (0.55, zent + 0.5), (0.55, zent + 1.7), (-0.55, zent + 1.7)], proud=0.03)
            fr = wall_frame(p - n * 1.01, -t, -n)
            opening(b, "shade", fr, [(-0.55, zent + 0.5), (0.55, zent + 0.5), (0.55, zent + 1.7), (-0.55, zent + 1.7)], proud=0.03)
        da = math.radians(1.6)
        arc = [math.radians(a0) - da + (math.radians(a1 - a0) + 2 * da) * k / 16 for k in range(17)]
        outer = [(ax + (R + 1.35) * math.cos(a), ay + (R + 1.35) * math.sin(a)) for a in arc]
        inner = [(ax + (R - 1.35) * math.cos(a), ay + (R - 1.35) * math.sin(a)) for a in arc]
        S.strip_solid(b, lambda k: "trim", outer, inner, zc, zent)
        for rr in (R + 1.38, R - 1.38):
            pts = [V(ax + rr * math.cos(a), ay + rr * math.sin(a), zent) for a in arc]
            for p0, p1 in zip(pts, pts[1:]):
                ink_bar(b, p0, p1, ((p0 + p1) / 2 - V(ax, ay, zent)).normalized() * (1 if rr > R else -1) + V(0, 0, 0.5), 0.09)
    colonnade = part(b, "colonnade", mats, root)

    # The lagoon's edge: reeds, a pair of swans, lamps, and a few trees behind.
    b = Builder(PF_PAL)
    lx, ly, lrx, lry = PF_LAGOON
    for k in range(22):
        a = 2 * math.pi * k / 22 + 0.13
        if math.cos(a) > 0.55:      # keep the near (street) bank open, so a cab can drive in
            continue
        p = V(lx + (lrx - 0.4) * math.cos(a), ly + (lry - 0.4) * math.sin(a), 0)
        for j, (dx, dy, h) in enumerate(((0, 0, 1.4), (0.35, 0.2, 1.0), (-0.3, 0.25, 1.2))):
            b.tube("reed", p + V(dx, dy, -1.0), p + V(dx * 1.4, dy * 1.4, h - 0.6), 0.14, 0.0, sides=4)
    for sx, sy, yaw in ((lx - 2.0, ly + 3.0, 0.6), (lx + 1.0, ly - 4.0, 2.4)):
        rot = Matrix.Rotation(yaw, 4, "Z")
        p = V(sx, sy, PF_WATER)
        b.sphere("swan", p + V(0, 0, 0.15), (0.75, 0.42, 0.32), u=8, v=5, rot=rot)
        f = rot @ V(1, 0, 0)
        S.loft(b, "swan", [p + f * 0.45 + V(0, 0, 0.3), p + f * 0.65 + V(0, 0, 0.8), p + f * 0.6 + V(0, 0, 1.2), p + f * 0.85 + V(0, 0, 1.25)],
               [0.13, 0.1, 0.1, 0.09], sides=6)
        b.tube("beak", p + f * 0.88 + V(0, 0, 1.25), p + f * 1.15 + V(0, 0, 1.2), 0.07, 0.02, sides=5)
    for a in (math.radians(100), math.radians(260), math.radians(180)):
        p = V(lx + (lrx + 1.6) * math.cos(a), ly + (lry + 1.6) * math.sin(a), 0)
        b.tube("rail", p, p + V(0, 0, 3.8), 0.09, 0.07, sides=6)
        b.sphere("light_lamp", p + V(0, 0, 4.0), (0.3, 0.3, 0.38), u=6, v=4)
    for x, y, r in ((-18.0, 15.0, 2.6), (-18.5, -14.0, 2.4), (-12.0, 18.0, 2.0), (-13.0, -18.0, 2.2)):
        blob_tree(b, x, y, 0, r)
    grounds = part(b, "grounds", mats, root)
    return root, [rotunda, colonnade, grounds], [
        ("3/4 lagoon", -125, 12, V(-1, 0, 11), 34, 1.25),
        ("from the lagoon", -90, 5, V(-1, 0, 11), 30, 1.35),
        ("rotunda", -150, 8, V(rx, ry, 13), 22, 0.95),
        ("colonnade", -60, 10, V(-8, 12, 7), 18, 1.25),
    ]


# --- Alcatraz -------------------------------------------------------------------------------

AZ_PAL = {"rock": 0x8E8274, "rock_dark": 0x6E6457, "rock_light": 0xA99D8A, "scrub": 0x7E9C4E,
          "scrub_dark": 0x5D7B3D, "dirt": 0xC2B192, "concrete": 0xE9E3D5, "concrete_dark": 0xC4BCA9,
          "window": 0x4A525C, "roof": 0x7E8384, "steel": 0x59606A, "tank": 0xD9D4C8, "rust": 0xA6533E,
          "road": 0x6D6B66, "stripe": 0xF3C530, "sign": 0xF2EEE2, "light_lamp": 0xFFF4C8,
          "light_beacon": 0xFFF2B0, "ink": INK}
# The island's top is an ellipse AZ_RX by AZ_RY at AZ_TOP above the water; its cliffs are
# offset ellipses down to the sea floor. src/features.ts uses the same numbers for the
# ground the cab drives on: keep them in step.
AZ_RX, AZ_RY, AZ_TOP = 17.0, 36.0, 7.0
AZ_FLOOR = -12.0           # the sea floor below the water line (SEA_FLOOR - WATER)
AZ_CLIFF = ((0.0, 7.0), (0.6, 4.6), (1.7, 1.6), (3.2, -2.4), (4.7, -6.8), (5.8, -10.4), (6.4, -12.5))
AZ_RAMP = (93.0, 76.0, 10.0)  # starts at x, runs west this far, width: sea floor to the top
AZ_CELL = (-4.0, 6.0, 12.0, 30.0, 9.0)  # cellhouse centre x, y, size x, y, height


def az_noise(i, j):
    return ((math.sin(i * 12.9898 + j * 78.233) * 43758.5453) % 1.0)


def build_alcatraz():
    mats = C.make_materials(AZ_PAL)
    root = C.empty("alcatraz")
    b = Builder(AZ_PAL)
    # Cliffs: rings of rock from the sea floor up to the flat top, in patches of three greys.
    n = 64
    rings = []
    for i, (o, z) in enumerate(reversed(AZ_CLIFF)):
        ring = []
        for j in range(n):
            a = 2 * math.pi * j / n
            jitter = 0.0 if i == len(AZ_CLIFF) - 1 else (az_noise(i, j) - 0.5) * 0.9
            ring.append(V((AZ_RX + o + jitter) * math.cos(a), (AZ_RY + o + jitter) * math.sin(a), z))
        rings.append([b.bm.verts.new(p) for p in ring])
    roles = ("rock", "rock_dark", "rock_light")
    for i in range(len(rings) - 1):
        for j in range(n):
            jn = (j + 1) % n
            f = b.bm.faces.new((rings[i][j], rings[i][jn], rings[i + 1][jn], rings[i + 1][j]))
            k = int(az_noise(j // 2, i + 7) * 3) if i < len(rings) - 2 else 0
            f.material_index = b.materials.index(roles[k])
    b.bm.faces.new(list(reversed(rings[0]))).material_index = b.materials.index("rock_dark")
    b.bm.faces.new(rings[-1]).material_index = b.materials.index("dirt")
    top = [p.co.copy() for p in rings[-1]]
    for k in range(n):
        a, c = top[k], top[(k + 1) % n]
        S.bar(b, "ink", a, c, ((a + c) / 2 - V(0, 0, AZ_TOP)).normalized() + V(0, 0, 0.6), w=0.14, d=0.04, sink=0.04)
    # Scrub on the top, bushes along the edge.
    for k in range(18):
        a = 2 * math.pi * (k + az_noise(k, 3)) / 18
        if abs(math.cos(a)) > 0.85 and math.cos(a) > 0:   # leave the landing clear
            continue
        p = V((AZ_RX - 2.0) * math.cos(a), (AZ_RY - 2.5) * math.sin(a), AZ_TOP)
        r = 1.0 + az_noise(k, 9) * 0.9
        b.sphere("scrub" if k % 3 else "scrub_dark", p + V(0, 0, 0.3), (r, r * 1.2, r * 0.6), u=7, v=4)
    for cx, cy, rx, ry in ((7.0, 18.0, 4.0, 6.0), (-9.0, -22.0, 4.0, 5.0), (9.0, -16.0, 3.5, 6.0), (-10.0, 26.0, 3.0, 3.6)):
        pts = [(cx + rx * math.cos(2 * math.pi * k / 10) * (0.85 + 0.3 * az_noise(k, cx)), cy + ry * math.sin(2 * math.pi * k / 10)) for k in range(10)]
        b.prism("scrub", pts, 0.1, Matrix.Translation((0, 0, AZ_TOP + 0.03)))
    # The road from the landing, drawn on the top.
    S.bar(b, "road", V(AZ_RX, 0, AZ_TOP), V(3.5, 0, AZ_TOP), V(0, 0, 1), w=7.0, d=0.03, sink=0.02)
    S.bar(b, "road", V(4.5, 0, AZ_TOP), V(4.5, -26, AZ_TOP), V(0, 0, 1), w=4.5, d=0.025, sink=0.02)
    # The ramp: a concrete causeway from the sea floor to the landing, hazard stripes at
    # the foot, kerbs either side.
    x0, ln, w = AZ_RAMP
    x1 = x0 - ln
    rise = AZ_TOP - AZ_FLOOR
    def rz(x):
        return AZ_FLOOR + (x0 - x) / ln * rise
    pts = [(x0, -w / 2), (x1, -w / 2), (x1, w / 2), (x0, w / 2)]
    bot, topv = [], []
    for x, y in pts:
        bot.append(b.bm.verts.new(V(x, y, AZ_FLOOR - 0.6)))
        topv.append(b.bm.verts.new(V(x, y, rz(x))))
    cmat = b.materials.index("concrete_dark")
    b.bm.faces.new(list(reversed(bot))).material_index = cmat
    b.bm.faces.new(topv).material_index = b.materials.index("concrete")
    for k in range(4):
        kn = (k + 1) % 4
        b.bm.faces.new((bot[k], bot[kn], topv[kn], topv[k])).material_index = cmat
    for sy in (-1, 1):
        y = sy * (w / 2 - 0.25)
        S.bar(b, "concrete_dark", V(x0, y, rz(x0)), V(x1 + 2.5, y, rz(x1 + 2.5)), V(0, 0, 1), w=0.5, d=0.35, sink=0.05)
        S.bar(b, "ink", V(x0, sy * w / 2, rz(x0)), V(x1 + 2.5, sy * w / 2, rz(x1 + 2.5)), V(0, sy, 0.3), w=0.1, d=0.03, sink=0.03)
        for k in range(1, 8):
            x = x0 - k * ln / 8
            b.tube("steel", V(x, y, rz(x)), V(x, y, rz(x) + 1.0), 0.1, 0.1, sides=6)
            if x < 30:
                b.sphere("light_lamp", V(x, y, rz(x) + 1.15), (0.18, 0.18, 0.18), u=6, v=4)
    for k in range(6):
        x = x0 - 0.5 - k * 0.9
        S.bar(b, "stripe" if k % 2 == 0 else "ink", V(x, -w / 2 + 0.6, rz(x) + 0.02), V(x, w / 2 - 0.6, rz(x) + 0.02),
              V(0.3, 0, 1), w=0.85, d=0.03, sink=0.03)
    for k in range(1, 16):
        x = x0 - k * ln / 16
        S.bar(b, "ink", V(x, -0.15, rz(x)), V(x - 2.0, -0.15, rz(x - 2.0)), V(0.25, 0, 1), w=0.18, d=0.025, sink=0.02)
    island = part(b, "island", mats, root)

    # The cellhouse: long, three storeys of tall barred windows, flat roof with skylights.
    b = Builder(AZ_PAL)
    cx, cy, sx, sy, h = AZ_CELL
    z0 = AZ_TOP
    b.box("concrete", (sx, sy, h + 0.8), V(cx, cy, z0 + (h - 0.8) / 2))
    cornice = (sx + 0.5, sy + 0.5, 0.5)
    b.box("concrete", cornice, V(cx, cy, z0 + h - 0.1))
    box_ink(b, (cx, cy, z0 + h - 0.1), cornice, 0.09)
    b.box("roof", (sx - 0.6, sy - 0.6, 0.3), V(cx, cy, z0 + h + 0.25))
    for k in range(4):
        b.box("concrete_dark", (3.2, 4.0, 1.0), V(cx, cy - 10.5 + k * 7.0, z0 + h + 0.8), taper=(0.8, 0.9))
        b.box("window", (2.6, 3.4, 0.08), V(cx, cy - 10.5 + k * 7.0, z0 + h + 1.32))
    b.box("concrete_dark", (sx + 0.2, sy + 0.2, 0.8), V(cx, cy, z0 + 0.0))
    for side in (-1, 1):
        x = cx + side * sx / 2
        fr = wall_frame(V(x, cy, 0), V(0, side, 0), V(side, 0, 0))
        for k in range(10):
            u = -sy / 2 + (k + 0.5) * sy / 10
            opening(b, "window", fr @ Matrix.Translation((u, 0, 0)), [(-0.7, z0 + 1.4), (0.7, z0 + 1.4), (0.7, z0 + h - 1.2), (-0.7, z0 + h - 1.2)], proud=0.05)
            for bx in (-0.35, 0.0, 0.35):
                p0 = fr @ Vector((u + bx, z0 + 1.4, 0.09))
                p1 = fr @ Vector((u + bx, z0 + h - 1.2, 0.09))
                S.bar(b, "ink", p0, p1, V(side, 0, 0), w=0.06, d=0.02, sink=0.02)
            for bz in (z0 + 3.4, z0 + 5.6):
                S.bar(b, "ink", fr @ Vector((u - 0.7, bz, 0.09)), fr @ Vector((u + 0.7, bz, 0.09)), V(side, 0, 0), w=0.08, d=0.02, sink=0.02)
    # The south end: the administration wing with the entrance and its sign, and the
    # recreation-yard wall to the north.
    ys = cy - sy / 2
    b.box("concrete", (sx + 3.0, 6.0, 6.0), V(cx, ys - 2.4, z0 + 2.6))
    b.box("concrete", (sx + 3.5, 6.5, 0.4), V(cx, ys - 2.4, z0 + 5.7))
    box_ink(b, (cx, ys - 2.4, z0 + 5.7), (sx + 3.5, 6.5, 0.4), 0.08)
    fr = wall_frame(V(cx, ys - 5.4, 0), V(1, 0, 0), V(0, -1, 0))
    opening(b, "window", fr, [(-1.0, z0), (1.0, z0), (1.0, z0 + 2.6), (-1.0, z0 + 2.6)], proud=0.06)
    opening(b, "sign", fr, [(-3.2, z0 + 3.4), (3.2, z0 + 3.4), (3.2, z0 + 4.5), (-3.2, z0 + 4.5)], proud=0.05)
    for k in range(9):
        x = -2.7 + k * 0.68
        opening(b, "ink", fr @ Matrix.Translation((x, 0, 0)), [(-0.22, z0 + 3.65), (0.22, z0 + 3.65), (0.22, z0 + 4.25), (-0.22, z0 + 4.25)], proud=0.07)
    for x in (-5.0, -2.8, 2.8, 5.0):
        opening(b, "window", fr @ Matrix.Translation((x, 0, 0)), [(-0.6, z0 + 1.0), (0.6, z0 + 1.0), (0.6, z0 + 2.6), (-0.6, z0 + 2.6)], proud=0.05)
    yn = cy + sy / 2
    wall = [(cx - sx / 2, yn), (cx - sx / 2 - 1.0, yn + 7.0), (cx + sx / 2 + 1.0, yn + 7.0), (cx + sx / 2, yn)]
    for (a0, b0), (a1, b1) in zip(wall, wall[1:]):
        p0, p1 = V(a0, b0, z0), V(a1, b1, z0)
        d = (p1 - p0)
        b.box("concrete_dark", (d.length + 0.6, 0.6, 4.0), (p0 + p1) / 2 + V(0, 0, 2.0), rot=Matrix.Rotation(math.atan2(d.y, d.x), 4, "Z"))
    cellhouse = part(b, "cellhouse", mats, root)

    # The lighthouse beside the administration wing, the water tower to the north, the
    # warden's roofless house, a guard tower.
    b = Builder(AZ_PAL)
    lx, ly = -4.0, -16.5
    oct_ = lambda r, z: [V(lx + r * math.cos(2 * math.pi * (k + 0.5) / 8), ly + r * math.sin(2 * math.pi * (k + 0.5) / 8), z) for k in range(8)]
    ring_stack(b, [oct_(2.0, z0), oct_(1.45, z0 + 15.0)], lambda i: "concrete")
    ring_stack(b, [oct_(2.3, z0 + 15.0), oct_(2.3, z0 + 15.5)], lambda i: "steel")
    for k in range(16):
        a = 2 * math.pi * k / 16
        b.box("steel", (0.08, 0.08, 1.0), V(lx + 2.2 * math.cos(a), ly + 2.2 * math.sin(a), z0 + 16.0))
    b.tube("steel", V(lx, ly, z0 + 16.45), V(lx, ly, z0 + 16.55), 2.25, 2.25, sides=16)
    b.tube("light_beacon", V(lx, ly, z0 + 15.5), V(lx, ly, z0 + 17.6), 1.2, 1.2, sides=10)
    for k in range(5):
        a = 2 * math.pi * k / 5
        b.box("steel", (0.12, 0.12, 2.1), V(lx + 1.22 * math.cos(a), ly + 1.22 * math.sin(a), z0 + 16.55))
    b.tube("steel", V(lx, ly, z0 + 17.6), V(lx, ly, z0 + 19.0), 1.5, 0.15, sides=10)
    b.sphere("steel", V(lx, ly, z0 + 19.1), (0.2, 0.2, 0.2), u=6, v=4)
    for z in (z0 + 4.0, z0 + 9.0, z0 + 13.0):
        r = 2.0 - 0.55 * (z - z0) / 15
        opening(b, "window", wall_frame(V(lx, ly - r * math.cos(math.pi / 8), 0), V(1, 0, 0), V(0, -1, 0)),
                [(-0.3, z), (0.3, z), (0.3, z + 1.0), (-0.3, z + 1.0)], proud=0.08)
    # Water tower: four legs and cross-braces, the tank with its cone roof.
    wx, wy = 7.0, 25.0
    legs = [V(wx + sxx * 2.3, wy + syy * 2.3, 0) for sxx in (-1, 1) for syy in (-1, 1)]
    for p in legs:
        b.tube("steel", p + V(0, 0, z0), p * 0.85 + V(wx, wy, 0) * 0.15 + V(0, 0, z0 + 12.0), 0.18, 0.16, sides=6)
    for zb in (z0 + 4.0, z0 + 8.0):
        for k in range(4):
            p0, p1 = legs[(0, 1, 3, 2)[k]], legs[(0, 1, 3, 2)[(k + 1) % 4]]
            sc = 1 - 0.15 * (zb - z0) / 12
            q0 = V(wx, wy, 0) + (p0 - V(wx, wy, 0)) * sc + V(0, 0, zb)
            q1 = V(wx, wy, 0) + (p1 - V(wx, wy, 0)) * sc + V(0, 0, zb)
            member(b, "steel", q0, q1, (0.14, 0.14), V(0, 0, 1))
    b.tube("tank", V(wx, wy, z0 + 12.0), V(wx, wy, z0 + 17.0), 3.0, 3.0, sides=16)
    b.tube("rust", V(wx, wy, z0 + 11.6), V(wx, wy, z0 + 12.0), 3.1, 3.1, sides=16)
    b.tube("roof", V(wx, wy, z0 + 17.0), V(wx, wy, z0 + 18.8), 3.25, 0.2, sides=16)
    for k in range(16):
        a = 2 * math.pi * k / 16
        if k % 2:
            continue
        p = V(wx + 3.02 * math.cos(a), wy + 3.02 * math.sin(a), 0)
        S.bar(b, "ink", p + V(0, 0, z0 + 12.0), p + V(0, 0, z0 + 17.0), V(math.cos(a), math.sin(a), 0), w=0.06, d=0.02, sink=0.02)
    # The red welcome painted round the tank, as blocks of lettering.
    for k in range(7):
        a = math.radians(-60 + k * 14)
        p = V(wx + 3.03 * math.cos(a), wy + 3.03 * math.sin(a), z0 + 14.6)
        b.box("rust", (0.05, 1.0, 0.7 if k % 3 else 0.9), p, rot=Matrix.Rotation(a, 4, "Z"))
    # The warden's house: a roofless shell.
    hx_, hy_ = -9.0, -25.0
    for (ax0, ay0, ax1, ay1) in ((-3, -2.5, 3, -2.5), (3, -2.5, 3, 2.5), (3, 2.5, -3, 2.5), (-3, 2.5, -3, -2.5)):
        p0, p1 = V(hx_ + ax0, hy_ + ay0, z0), V(hx_ + ax1, hy_ + ay1, z0)
        d = p1 - p0
        b.box("concrete_dark", (d.length + 0.4, 0.4, 5.0), (p0 + p1) / 2 + V(0, 0, 2.5), rot=Matrix.Rotation(math.atan2(d.y, d.x), 4, "Z"))
        nrm = V(d.y, -d.x, 0).normalized()
        fr = wall_frame((p0 + p1) / 2 + nrm * 0.2, d, nrm)
        for u in (-1.5, 1.5):
            opening(b, "window", fr @ Matrix.Translation((u, 0, 0)), [(-0.5, z0 + 2.4), (0.5, z0 + 2.4), (0.5, z0 + 4.0), (-0.5, z0 + 4.0)], proud=0.03)
    b.box("rust", (1.0, 1.0, 2.2), V(hx_ + 2.0, hy_ + 1.5, z0 + 5.6))
    # Guard tower on the north-east, and the "UNITED STATES PENITENTIARY" board at the landing.
    gx, gy = 8.0, -24.0
    for sxx in (-1, 1):
        for syy in (-1, 1):
            b.tube("steel", V(gx + sxx * 1.3, gy + syy * 1.3, z0), V(gx + sxx * 1.1, gy + syy * 1.1, z0 + 6.0), 0.12, 0.12, sides=6)
    b.box("concrete", (3.0, 3.0, 2.6), V(gx, gy, z0 + 7.3))
    b.box("window", (3.06, 2.4, 1.0), V(gx, gy, z0 + 7.8))
    b.box("roof", (3.6, 3.6, 0.3), V(gx, gy, z0 + 8.75), taper=(0.6, 0.6))
    for yy in (-1.0, 1.0):
        b.tube("steel", V(13.0, 8.0 + yy * 2.2, z0), V(13.0, 8.0 + yy * 2.2, z0 + 3.0), 0.1, 0.1, sides=6)
    b.box("sign", (0.2, 5.4, 1.6), V(13.0, 8.0, z0 + 2.6))
    for k in range(7):
        b.box("ink", (0.04, 0.45, 0.32), V(13.11, 8.0 - 2.1 + k * 0.7, z0 + 2.95))
        b.box("ink", (0.04, 0.45, 0.32), V(13.11, 8.0 - 2.1 + k * 0.7, z0 + 2.3))
    for (px, py) in ((11.0, -5.0), (11.0, 5.0)):
        b.tube("steel", V(px, py, z0), V(px, py, z0 + 4.0), 0.08, 0.07, sides=6)
        b.sphere("light_lamp", V(px, py, z0 + 4.2), (0.28, 0.28, 0.34), u=6, v=4)
    yard = part(b, "buildings", mats, root)
    return root, [island, cellhouse, yard], [
        ("from the city", -150, 14, V(10, 0, 4), 50, 1.7),
        ("east", -90, 8, V(0, 0, 8), 34, 2.2),
        ("lighthouse", -140, 10, V(-4, -14, 14), 18, 1.0),
        ("landing", -110, 16, V(30, 0, 2), 26, 1.4),
    ]


# --- build, export, render -----------------------------------------------------------------

LANDMARKS = {
    # name: builder, preview outline width per metre of view height
    "salesfarce_tower": build_salesfarce,
    "pyramid": build_pyramid,
    "ferry_building": build_ferry_building,
    "coit_tower": build_coit_tower,
    "golden_gate": build_golden_gate,
    "city_hall": build_city_hall,
    "dragon_gate": build_dragon_gate,
    "palace_of_fine_arts": build_palace_of_fine_arts,
    "alcatraz": build_alcatraz,
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
