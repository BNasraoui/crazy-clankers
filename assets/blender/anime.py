"""Anime-cel character kit for the Crazy Clankers passengers.

Everything here works in *game* coordinates (Y up, +Z forward, metres) and converts
to Blender space (Z up, -Y forward) at the last moment with `g`/`gv`. A character
script mostly supplies parameters: a palette, a HeadSpec, a FaceSpec, hair locks and
body joints. See docs/art/CHARACTER_PIPELINE.md for the recipe.

Pieces:
  * lofting: `catmull`, `path_rings`, `loft`, `limb`, `ring` - smooth tube-like forms
  * `HeadSpec` / `build_head` - anime skull (round cranium, small V jaw, eyes on the
    vertical middle), nose bump, ears, neck; front faces get the `face` material
  * `hair_cap` / `hair_lock` - a scalp shell plus sharp, tapered blade-like locks
  * `FaceSpec` / `paint_face` - procedural anime face texture (Pillow, 4x supersampled)
  * `Painter` - generic metric painter for other detail textures (vest zips etc.)
  * `make_materials`, `front_uv` - flat role materials, optional embedded textures
  * `Preview` - Eevee two-tone toon + inverted-hull previews, compare and small renders
"""
import math
import site
import tempfile
import sys
from dataclasses import dataclass, field
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

import common as C

# Blender runs its Python without the user site; Pillow is installed there with
#   <blender>/5.x/python/bin/python3.13 -m pip install --user pillow
if site.getusersitepackages() not in sys.path:
    sys.path.append(site.getusersitepackages())
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:  # pragma: no cover
    raise SystemExit("anime.py needs Pillow in Blender's Python: "
                     f"{sys.executable} -m pip install --user pillow") from e

TEX_DIR = Path(tempfile.gettempdir()) / "clankers_textures"


# --- coordinates ---------------------------------------------------------------

def g(x, y, z):
    """Game coordinates (Y up, +Z forward) to Blender (Z up, -Y forward)."""
    return Vector((x, -z, y))


def gv(v):
    return g(*v)


def to_game(co):
    return Vector((co.x, co.z, -co.y))


def grot(deg, axis):
    """Blender-space 3x3 rotation about a game-space axis."""
    return Matrix.Rotation(math.radians(deg), 3, gv(axis))


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


# --- lofting -----------------------------------------------------------------
# A ring is (centre, u, w, rx, rz, p) in game space: a superellipse with radius rx
# along u and rz along w (p=2 ellipse, higher is boxier, lower is pinched).

def ring(c, rx, rz, roll=0.0, pitch=0.0, p=2.0):
    """Horizontal ring, rolled about Z and pitched about X (positive pitch drops the front)."""
    m = Matrix.Rotation(math.radians(roll), 3, "Z") @ Matrix.Rotation(math.radians(pitch), 3, "X")
    return (Vector(c), m @ Vector((1, 0, 0)), m @ Vector((0, 0, 1)), rx, rz, p)


def path_rings(pts, radii, ref, p=2.0, closed=False):
    """Rings perpendicular to a polyline. `ref` (vector or fn(i, c)) gives the rz direction."""
    pts = [Vector(q) for q in pts]
    n = len(pts)
    out = []
    for i, c in enumerate(pts):
        if closed:
            t = pts[(i + 1) % n] - pts[i - 1]
        else:
            t = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        t.normalize()
        r = Vector(ref(i, c) if callable(ref) else ref)
        w = (r - t * r.dot(t)).normalized()
        u = t.cross(w)
        rx, rz = radii[i]
        out.append((c, u, w, rx, rz, p))
    return out


def loft(b, mat, rings, sides, cap0="flat", cap1="flat", closed=False, phase=0.5):
    """Skin rings into a shell. A cap is "flat", None (open) or a tip point (game space).
    phase=0 puts vertices on the +-u extremes (sharp blade edges for hair)."""
    before = b._begin()
    bm = b.bm
    loops = []
    for c, u, w, rx, rz, p in rings:
        loop = []
        for k in range(sides):
            a = 2 * math.pi * (k + phase) / sides
            ca, sa = math.cos(a), math.sin(a)
            x = math.copysign(abs(ca) ** (2 / p), ca)
            z = math.copysign(abs(sa) ** (2 / p), sa)
            loop.append(bm.verts.new(gv(c + u * (rx * x) + w * (rz * z))))
        loops.append(loop)
    pairs = list(zip(loops, loops[1:])) + ([(loops[-1], loops[0])] if closed else [])
    for l0, l1 in pairs:
        for k in range(sides):
            j = (k + 1) % sides
            bm.faces.new((l0[k], l0[j], l1[j], l1[k]))
    if not closed:
        for loop, cap in ((loops[0], cap0), (loops[-1], cap1)):
            if cap is None:
                continue
            if isinstance(cap, str):
                bm.faces.new(loop)
            else:
                tip = bm.verts.new(gv(cap))
                for k in range(sides):
                    bm.faces.new((loop[k], loop[(k + 1) % sides], tip))
    faces = b._assign(before, mat)
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def catmull(pts, steps=3):
    """Catmull-Rom through `pts`, `steps` samples per segment."""
    pts = [Vector(q) for q in pts]
    if len(pts) < 2:
        return pts
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1:i + 3]
        for s in range(steps):
            t = s / steps
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (3 * p1 - p0 - 3 * p2 + p3) * t * t * t))
    out.append(pts[-1])
    return out


def catmull_vals(vals, steps=3):
    """Catmull-Rom for tuples of floats (radii etc.), matching `catmull` sampling."""
    vs = [Vector(v) if hasattr(v, "__len__") else Vector((v, 0)) for v in vals]
    return [tuple(v) for v in catmull(vs, steps)]


def limb(b, mat, pts, radii, sides=14, ref=(0, 0, 1), cap0="flat", cap1="flat", p=2.0, steps=3):
    """Smooth tube through control points; radii (rx, rz) are interpolated too."""
    dense = catmull(pts, steps)
    rad = [tuple(r)[:2] for r in catmull_vals(radii, steps)]
    return loft(b, mat, path_rings(dense, rad, ref, p), sides, cap0, cap1)


def shell(b, mat, grid, thickness, wrap=True, axis=None):
    """Thick cloth panel (vests, collars, hoods) from a grid of outer points: rows run
    bottom to top, columns around the body. The inner wall is offset horizontally
    towards `axis(p)` (default the Y axis) by `thickness`; rims close the edges."""
    before = b._begin()
    bm = b.bm
    rows, n = len(grid), len(grid[0])
    outer = [[bm.verts.new(gv(p)) for p in row] for row in grid]
    inner = []
    for row in grid:
        r = []
        for p in row:
            d = p - (axis(p) if axis else Vector((0, p.y, 0)))
            d.y = 0
            d = d.normalized() if d.length > 1e-6 else Vector((0, 0, 1))
            r.append(bm.verts.new(gv(p - d * thickness)))
        inner.append(r)
    cols = range(n) if wrap else range(n - 1)
    for j in range(rows - 1):
        for i in cols:
            k = (i + 1) % n
            bm.faces.new((outer[j][i], outer[j][k], outer[j + 1][k], outer[j + 1][i]))
            bm.faces.new((inner[j][i], inner[j + 1][i], inner[j + 1][k], inner[j][k]))
    for j in (0, rows - 1):
        for i in cols:
            k = (i + 1) % n
            bm.faces.new((outer[j][i], inner[j][i], inner[j][k], outer[j][k]))
    if not wrap:
        for i in (0, n - 1):
            for j in range(rows - 1):
                bm.faces.new((outer[j][i], outer[j + 1][i], inner[j + 1][i], inner[j][i]))
    faces = b._assign(before, mat)
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def blob(b, mat, centre, radii, rot=None, u=16, v=10):
    """Smooth ellipsoid in game space; `rot` is a Blender-space 3x3 rotation."""
    m = (rot or Matrix()).to_4x4()
    return b.sphere(mat, gv(centre), (radii[0], radii[2], radii[1]), u=u, v=v, rot=m)


def knee_ik(hip, ankle, thigh, shin, bend):
    """Two-bone solve; `bend` is the direction the middle joint pushes towards."""
    d = ankle - hip
    dist = d.length
    if dist >= thigh + shin:
        return hip + d * (thigh / (thigh + shin))
    a = (thigh ** 2 - shin ** 2 + dist ** 2) / (2 * dist)
    h = math.sqrt(max(thigh ** 2 - a ** 2, 0.0))
    dn = d.normalized()
    perp = (Vector(bend) - dn * Vector(bend).dot(dn)).normalized()
    return hip + dn * a + perp * h


# --- head --------------------------------------------------------------------

@dataclass
class HeadSpec:
    """Anime skull around `centre` (game space, at eye level: the eyes sit on the
    vertical middle of the skull). Radii in metres."""
    centre: Vector
    rx: float = 0.084       # half width at the temples
    ry_up: float = 0.122    # eye line to crown
    ry_lo: float = 0.118    # eye line to chin
    rz_f: float = 0.094     # centre to forehead/face front
    rz_b: float = 0.112     # centre to back of the cranium
    jaw_start: float = 0.18  # how far below the eye line (0..1) the jaw starts to narrow
    chin_w: float = 0.2     # chin half width as a fraction of rx
    chin_back: float = 0.22  # how far the chin sits back from the face plane (fraction)
    jaw_back: float = 0.8   # how much the back of the jaw tucks in towards the neck
    nose_y: float = -0.036  # nose tip below the eye line
    nose_h: float = 0.009   # nose bump height
    ear_y: float = -0.018
    ear_size: tuple = (0.011, 0.03, 0.02)  # thickness, height, depth
    neck_r: float = 0.041
    neck_z: float = -0.022
    face_half: float = 0.105  # half size of the square face texture window
    face_y0: float = -0.135   # bottom of the face window, relative to centre


def skull_offset(h, d):
    """Offset from the head centre for unit direction d (game space)."""
    x, y, z = d
    if y >= 0:
        return Vector((x * h.rx, y * h.ry_up, z * (h.rz_f if z > 0 else h.rz_b)))
    t = -y
    s = math.sqrt(max(1 - t * t, 1e-9))
    cx, cz = x / s, z / s  # direction around the ring at this height
    taper = (1 - h.chin_w) * smoothstep(h.jaw_start, 1.0, t)
    front = (cz + 1) / 2
    hw = h.rx * (1 - taper * (0.75 + 0.25 * front))
    zf = h.rz_f * (1 - h.chin_back * t * t)
    zb = h.rz_b * (1 - h.jaw_back * smoothstep(0.05, 0.95, t))
    r = s ** 0.45  # keep rings full until close to the chin, then close quickly
    return Vector((cx * hw * r, -t * h.ry_lo, cz * (zf if cz > 0 else zb) * r))


def head_point(h, theta, phi, lift=0.0):
    """Point on/over the skull: azimuth theta (0 = front, +90 = +X), elevation phi."""
    t, p = math.radians(theta), math.radians(phi)
    d = Vector((math.sin(t) * math.cos(p), math.sin(p), math.cos(t) * math.cos(p)))
    off = skull_offset(h, d)
    return h.centre + off + off.normalized() * lift


def build_head(b, h, skin="skin", face="face", u=32, v=24):
    """Skull, nose bump, ears and neck. Front faces get the `face` material."""
    c = h.centre
    neck_top = c + Vector((0, -0.06, h.neck_z))
    limb(b, skin, [c + Vector((0, -0.25, h.neck_z - 0.01)), neck_top + Vector((0, -0.04, 0)), neck_top],
         [(h.neck_r, h.neck_r * 0.95)] * 3, sides=14, ref=(0, 0, 1))
    faces = b.sphere(skin, gv(c), (1, 1, 1), u=u, v=v)
    for vert in {v for f in faces for v in f.verts}:
        d = to_game(vert.co) - c
        d.normalize()
        off = skull_offset(h, d)
        # Nose: a small soft wedge on the face plane.
        if off.z > 0:
            ny = (off.y - h.nose_y)
            k = math.exp(-(off.x / 0.011) ** 2 - (ny / (0.02 if ny > 0 else 0.008)) ** 2)
            off.z += h.nose_h * k
        vert.co = gv(c + off)
    for f in faces:
        n = to_game(f.normal)
        cen = to_game(f.calc_center_median()) - c
        if n.z > 0.3 and cen.y < 0.07:
            f.material_index = b.materials.index(face)
    ex, ey, ez = h.ear_size
    for sx in (1, -1):
        blob(b, skin, c + Vector((sx * (h.rx - 0.002), h.ear_y, -0.012)), (ex, ey / 2, ez / 2),
             rot=grot(sx * 12, (0, 1, 0)) @ grot(-8, (1, 0, 0)), u=10, v=8)


def soften_face_normals(obj, h, to_head, from_head, blend=0.8):
    """Anime face normals: bend the skull's vertex normals towards those of a smooth
    ellipsoid so the toon shadow on the face is one clean rounded shape instead of
    following every facet. `to_head(game_pt)` maps object points to the untilted head
    frame (relative to the centre); `from_head(vec)` maps directions back."""
    me = obj.data
    origin = C.parent_world_origin(obj)
    skull_mats = {i for i, s in enumerate(obj.material_slots) if s.material and s.material.name in ("skin", "face")}
    skull_verts = {v for p in me.polygons if p.material_index in skull_mats for v in p.vertices}
    normals = []
    for v in me.vertices:
        n = Vector(v.normal)
        if v.index in skull_verts:
            q = to_head(to_game(v.co + origin))
            if q.y > -h.ry_lo * 1.02 and q.length < max(h.ry_up, h.rz_b) * 1.05 and abs(q.x) < h.rx * 0.98:
                ry = h.ry_up if q.y > 0 else h.ry_lo * 1.3
                rz = h.rz_f if q.z > 0 else h.rz_b
                e = Vector((q.x / h.rx ** 2, q.y / ry ** 2, q.z / rz ** 2)).normalized()
                n = lerp(n, gv(from_head(e)), blend)
        normals.append(n.normalized())
    me.normals_split_custom_set_from_vertices(normals)


def hair_cap(b, h, hairline, lift=0.012, top=0.016, mat="hair", u=28, v=18):
    """Scalp shell following the skull. `hairline(theta)` gives the elevation (deg)
    below which the shell tucks inside the skull."""
    faces = b.sphere(mat, gv(h.centre), (1, 1, 1), u=u, v=v)
    for vert in {v for f in faces for v in f.verts}:
        d = (to_game(vert.co) - h.centre).normalized()
        theta = math.degrees(math.atan2(d.x, d.z))
        phi = math.degrees(math.asin(max(-1.0, min(1.0, d.y))))
        k = smoothstep(hairline(theta) - 10, hairline(theta) + 3, phi)
        off = skull_offset(h, d)
        vert.co = gv(h.centre + off + off.normalized() * lerp(-0.012, lift + top * max(d.y, 0), k))


def hair_lock(b, h, path, width, thick, mat="hair", steps=3, sides=6, bulge=0.3, flat=False):
    """A sharp anime lock: a blade-shaped (lens section) tube following `path`
    [(theta, phi, lift), ...] over the skull, widest just after the root and
    tapering to a pointed tip. The root sinks into the scalp."""
    pts = [head_point(h, *path[0][:2], path[0][2] - 0.012)] + [head_point(h, *q) for q in path[1:]]
    pts = catmull(pts, steps)
    n = len(pts)
    radii = []
    for i in range(n):
        s = i / (n - 1)
        prof = (1 - s ** 1.6) ** 0.9 * (1 + bulge * math.sin(math.pi * min(s * 1.6, 1)))
        radii.append((max(width * prof, 0.0015), max(thick * (0.35 + 0.65 * prof), 0.001)))
    rings = path_rings(pts, radii, lambda i, q: q - h.centre, p=1.6 if not flat else 2.0)
    tip = pts[-1] + (pts[-1] - pts[-2]).normalized() * width * 0.9
    return loft(b, mat, rings, sides, "flat", tip, phase=0.0)


# --- painting ----------------------------------------------------------------

class Painter:
    """Paints in metric coordinates onto a square texture window: x in
    [cx - half, cx + half] maps left to right, y in [y0, y0 + 2*half] bottom to top.
    Draws at `ss`x resolution and downsamples for clean anti-aliased ink."""

    def __init__(self, size, bg, half, y0, cx=0.0, ss=4):
        self.size, self.ss, self.half, self.y0, self.cx = size, ss, half, y0, cx
        self.S = size * ss
        self.img = Image.new("RGB", (self.S, self.S), bg)
        self.draw = ImageDraw.Draw(self.img)

    def px(self, x, y):
        return ((x - self.cx + self.half) / (2 * self.half) * self.S,
                (1 - (y - self.y0) / (2 * self.half)) * self.S)

    def m(self, metres):
        return metres / (2 * self.half) * self.S

    def poly(self, pts, fill, draw=None):
        (draw or self.draw).polygon([self.px(*p) for p in pts], fill=fill)

    def ellipse(self, cx, cy, rx, ry, fill, rot=0.0, n=48, draw=None):
        a0 = math.radians(rot)
        pts = []
        for k in range(n):
            a = 2 * math.pi * k / n
            x, y = rx * math.cos(a), ry * math.sin(a)
            pts.append((cx + x * math.cos(a0) - y * math.sin(a0), cy + x * math.sin(a0) + y * math.cos(a0)))
        self.poly(pts, fill, draw)

    def stroke(self, ctrl, widths, fill, steps=12, draw=None):
        """Tapered ink stroke through control points. `widths` are full widths (m) at
        each control point; 0 gives a sharp taper."""
        pts = catmull([Vector((x, y, 0)) for x, y in ctrl], steps)
        ws = [w[0] for w in catmull_vals(widths, steps)]
        left, right = [], []
        for i, p in enumerate(pts):
            t = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
            t.normalize()
            n = Vector((-t.y, t.x, 0))
            w = max(ws[i], 0.0) / 2
            left.append((p.x + n.x * w, p.y + n.y * w))
            right.append((p.x - n.x * w, p.y - n.y * w))
        self.poly(left + right[::-1], fill, draw)
        for i in (0, len(pts) - 1):  # round caps where the stroke is thick
            w = max(ws[i], 0.0) / 2
            if w > 0:
                self.ellipse(pts[i].x, pts[i].y, w, w, fill, n=16, draw=draw)

    def curve(self, ctrl, steps=12):
        return [(p.x, p.y) for p in catmull([Vector((x, y, 0)) for x, y in ctrl], steps)]

    def layer(self):
        """A transparent layer and its mask, to clip shapes (e.g. iris to the eye white)."""
        lay = Image.new("RGBA", (self.S, self.S), (0, 0, 0, 0))
        return lay, ImageDraw.Draw(lay)

    def composite(self, lay, mask=None):
        a = lay.split()[3]
        if mask is not None:
            a = Image.fromarray(np.minimum(np.asarray(a), np.asarray(mask)))
        self.img.paste(lay.convert("RGB"), (0, 0), a)

    def save(self, name):
        TEX_DIR.mkdir(parents=True, exist_ok=True)
        path = TEX_DIR / f"{name}.png"
        self.img.resize((self.size, self.size), Image.LANCZOS).save(path)
        return path


def rgb(h):
    return ((h >> 16) & 255, (h >> 8) & 255, h & 255)


@dataclass
class EyeSpec:
    x: float              # centre (head-local metres; +X is screen right in front view)
    y: float = 0.0
    w: float = 0.03       # corner to corner
    h: float = 0.021      # open height
    lid: float = 0.0      # 0 open .. 1 shut (smug half-lid ~0.3)
    tilt: float = 4.0     # degrees; outer corner up
    look: tuple = (0.0, 0.0)  # iris offset, fraction of eye size


@dataclass
class FaceSpec:
    """Anime face, painted as seen from the front. Distances relative to head centre."""
    skin: int
    ink: int = 0x2A1B16
    iris: int = 0x6B4A36
    iris_dark: int = 0x2E1D16
    brow: int = 0x2A1B16
    eyes: list = field(default_factory=list)  # EyeSpec per eye
    brows: list = field(default_factory=list)  # [(ctrl pts, widths)]
    nose: list = field(default_factory=list)   # [(ctrl pts, widths)]
    mouth: dict = field(default_factory=dict)  # see paint_mouth
    extras: list = field(default_factory=list)  # [(ctrl pts, widths, colour)]
    blush: list = field(default_factory=list)   # [(x, y, rx, ry)] faint cheek hatch


def eye_curves(e):
    """Upper and lower lid curves, inner corner -> outer corner, as control points."""
    side = 1 if e.x >= 0 else -1
    hw = e.w / 2
    a = math.radians(e.tilt)

    def p(u, v):  # u along the eye (-1 inner .. 1 outer), v up
        return (e.x + side * u * hw * math.cos(a), e.y + u * hw * math.sin(a) + v)
    top = e.h * 0.55 * (1 - e.lid)
    upper = [p(-1, -0.002), p(-0.55, top * 0.75), p(0.05, top), p(0.6, top * 0.85), p(1.0, top * 0.25)]
    lower = [p(-1, -0.002), p(-0.4, -e.h * 0.42), p(0.3, -e.h * 0.45), p(0.85, -e.h * 0.25), p(1.0, top * 0.15)]
    return upper, lower


def paint_eye(pt, f, e):
    side = 1 if e.x >= 0 else -1
    upper, lower = eye_curves(e)
    ucurve, lcurve = pt.curve(upper), pt.curve(lower)
    # Eye white, clipped region for the iris.
    mask = Image.new("L", (pt.S, pt.S), 0)
    ImageDraw.Draw(mask).polygon([pt.px(*q) for q in ucurve + lcurve[::-1]], fill=255)
    pt.poly(ucurve + lcurve[::-1], (255, 255, 255))
    lay, d = pt.layer()
    ix, iy = e.x + e.look[0] * e.w, e.y - e.h * 0.05 + e.look[1] * e.h
    irx, iry = e.w * 0.3, e.h * 0.62
    pt.ellipse(ix, iy, irx, iry, rgb(f.iris) + (255,), draw=d)
    # Dark top band and a soft-edged inner ring.
    band, bd = pt.layer()
    pt.ellipse(ix, iy, irx, iry, rgb(f.iris_dark) + (255,), draw=bd)
    pt.ellipse(ix, iy - iry * 0.55, irx * 1.3, iry * 0.95, (0, 0, 0, 0), draw=bd)
    lay.alpha_composite(band)
    pt.ellipse(ix, iy, irx * 0.45, iry * 0.5, rgb(f.iris_dark) + (255,), draw=d)  # pupil
    pt.ellipse(ix - side * irx * 0.32, iy + iry * 0.3, irx * 0.32, iry * 0.26, (255, 255, 255, 255), draw=d)
    pt.ellipse(ix + side * irx * 0.4, iy - iry * 0.42, irx * 0.14, iry * 0.12, (255, 255, 255, 255), draw=d)
    pt.composite(lay, mask)
    ink = rgb(f.ink)
    # Thick upper lash line, heaviest at the outer corner, with a small flick.
    ul = list(upper)
    flick = (ul[-1][0] + side * e.w * 0.14, ul[-1][1] - e.h * 0.12)
    pt.stroke(ul + [flick], [e.h * 0.1, e.h * 0.2, e.h * 0.24, e.h * 0.26, e.h * 0.22, 0.0], ink)
    # Thin lower line on the outer two thirds.
    pt.stroke(lower[1:], [0.0, e.h * 0.09, e.h * 0.1, 0.0], ink)
    # Lid crease above.
    crease = [(q[0], q[1] + e.h * 0.25) for q in upper[1:4]]
    pt.stroke(crease, [0.0, e.h * 0.07, 0.0], ink)


def paint_mouth(pt, f, m):
    """m: {'upper': ctrl pts, 'lower': ctrl pts (same end points), 'teeth': bool,
    'line': width, 'corner': (x, y) tick}"""
    ink = rgb(f.ink)
    up, lo = pt.curve(m["upper"]), pt.curve(m["lower"])
    if m.get("teeth"):
        pt.poly(up + lo[::-1], (255, 255, 255))
        mask = Image.new("L", (pt.S, pt.S), 0)
        ImageDraw.Draw(mask).polygon([pt.px(*q) for q in up + lo[::-1]], fill=255)
        lay, d = pt.layer()  # mouth interior shadow under the teeth
        lo_in = [(x, y + 0.004) for x, y in lo]
        d.polygon([pt.px(*q) for q in lo_in + lo[::-1]], fill=rgb(m.get("inside", 0x9B4A44)) + (255,))
        pt.composite(lay, mask)
    lw = m.get("line", 0.0028)
    n = len(m["upper"])
    pt.stroke(m["upper"], [lw * 0.4] + [lw] * (n - 2) + [lw * 0.5], ink)
    nl = len(m["lower"])
    pt.stroke(m["lower"], [lw * 0.3] + [lw * 0.55] * (nl - 2) + [lw * 0.3], ink)
    for ctrl, widths in m.get("ticks", []):
        pt.stroke(ctrl, widths, ink)


def paint_face(name, f, h, size=1024):
    """Paint the face texture for HeadSpec `h`. Background is the flat skin colour, so
    the face material blends into the skin everywhere outside the features."""
    pt = Painter(size, rgb(f.skin), h.face_half, h.face_y0)
    for x, y, rx, ry in f.blush:
        lay, d = pt.layer()
        for k in range(4):  # faint diagonal hatch
            xx = x - rx + (k + 0.5) * rx / 2
            pt.stroke([(xx - ry * 0.25, y - ry * 0.6), (xx + ry * 0.25, y + ry * 0.6)],
                      [0.0012, 0.0012], (232, 150, 140, 255), steps=2, draw=d)
        pt.composite(lay)
    for ctrl, widths in f.brows:
        pt.stroke(ctrl, widths, rgb(f.brow))
    for e in f.eyes:
        paint_eye(pt, f, e)
    for ctrl, widths in f.nose:
        pt.stroke(ctrl, widths, rgb(f.ink))
    if f.mouth:
        paint_mouth(pt, f, f.mouth)
    for ctrl, widths, col in f.extras:
        pt.stroke(ctrl, widths, rgb(col))
    return pt.save(name)


# --- materials and UVs -------------------------------------------------------

def make_materials(palette, textures=None):
    """Flat role materials (metallic 0, roughness 1). textures: {role: png path} feeds an
    embedded image into that role's base colour (the flat colour is kept as a fallback)."""
    mats = C.make_materials(palette)
    for role, path in (textures or {}).items():
        m = mats[role]
        nt = m.node_tree
        img = bpy.data.images.load(str(path))
        img.name = f"{role}_tex"
        img.pack()
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        tex.interpolation = "Linear"
        nt.links.new(tex.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    return mats


def front_uv(obj, mat_name, half, y0, cx=0.0, to_local=None, fallback=None, min_nz=None):
    """Front (orthographic, along -Z) projection UVs for faces using `mat_name`.
    `to_local(game_point)` maps object-space points (in game coords, relative to the
    model origin) into the painting frame. Faces whose normal faces away from the
    front (n.z < min_nz) get the `fallback` UV, a plain patch of the texture."""
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active.data
    idx = [i for i, s in enumerate(obj.material_slots) if s.material and s.material.name == mat_name]
    origin = C.parent_world_origin(obj)
    for poly in me.polygons:
        if poly.material_index not in idx:
            continue
        n = to_game(poly.normal)
        use_fb = fallback is not None and min_nz is not None and n.z < min_nz
        for li in poly.loop_indices:
            if use_fb:
                uv[li].uv = fallback
                continue
            p = to_game(me.vertices[me.loops[li].vertex_index].co + origin)
            if to_local:
                p = to_local(p)
            uv[li].uv = ((p.x - cx + half) / (2 * half), (p.y - y0) / (2 * half))


def fill_uv(obj, mat_name, uv):
    """Point every face of `mat_name` at one plain texel (parts that share a textured
    material but carry none of its details, e.g. sleeves of a shirt with a placket)."""
    front_uv(obj, mat_name, 1.0, 0.0, fallback=uv, min_nz=2.0)


def set_flat(obj, mat_names):
    """Hard edges only where the design has them: flat-shade these materials' faces."""
    idx = {i for i, s in enumerate(obj.material_slots) if s.material and s.material.name in mat_names}
    for p in obj.data.polygons:
        if p.material_index in idx:
            p.use_smooth = False


# --- previews ----------------------------------------------------------------

def _sock(sockets, ident):
    return next(s for s in sockets if s.identifier == ident)


def toonify(mat, shadow_mul=(0.7, 0.68, 0.84), threshold=0.32, light=None):
    """Two-tone cel shader for previews; keeps an image texture if the material has one.
    With `light` (unit vector towards the sun) the ramp uses plain N.L, like a game toon
    shader: no cast shadows on the body, so faces stay clean. Without it, Eevee's
    shadowed diffuse is used (the ground needs that to show the cast shadow)."""
    nt = mat.node_tree
    tex_old = next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None)
    img = tex_old.image if tex_old else None
    base = nt.nodes["Principled BSDF"].inputs["Base Color"].default_value[:3] \
        if "Principled BSDF" in nt.nodes else (0.8, 0.8, 0.8)
    nt.nodes.clear()
    diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    ramp.color_ramp.elements[1].position = threshold
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    shade = nt.nodes.new("ShaderNodeMix")
    shade.data_type = "RGBA"
    shade.blend_type = "MULTIPLY"
    _sock(shade.inputs, "Factor_Float").default_value = 1.0
    _sock(shade.inputs, "B_Color").default_value = (*shadow_mul, 1)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    if img:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        nt.links.new(tex.outputs["Color"], _sock(shade.inputs, "A_Color"))
        nt.links.new(tex.outputs["Color"], _sock(mix.inputs, "B_Color"))
    else:
        _sock(shade.inputs, "A_Color").default_value = (*base, 1)
        _sock(mix.inputs, "B_Color").default_value = (*base, 1)
    nt.links.new(_sock(shade.outputs, "Result_Color"), _sock(mix.inputs, "A_Color"))
    emit = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if light is None:
        nt.links.new(diff.outputs[0], s2r.inputs[0])
        nt.links.new(s2r.outputs["Color"], ramp.inputs["Fac"])
    else:
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        dot = nt.nodes.new("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        dot.inputs[1].default_value = tuple(light)
        nt.links.new(geo.outputs["Normal"], dot.inputs[0])
        nt.links.new(dot.outputs["Value"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], _sock(mix.inputs, "Factor_Float"))
    nt.links.new(_sock(mix.outputs, "Result_Color"), emit.inputs["Color"])
    nt.links.new(emit.outputs[0], out.inputs["Surface"])


class Preview:
    """Toon preview rig: cel materials, inverted-hull outlines, sun, ground, ortho camera.
    Call after exporting (it rewrites materials)."""

    def __init__(self, root, outline=0.006, shadow_muls=None, sun=(40, 0, 28)):
        scene = bpy.context.scene
        self.root = root
        self.objs = [o for o in scene.objects if o.type == "MESH"]
        light = (Matrix.Rotation(math.radians(sun[2]), 3, "Z") @ Matrix.Rotation(math.radians(sun[0]), 3, "X")
                 @ Vector((0, 0, 1)))
        for m in {s.material for o in self.objs for s in o.material_slots if s.material}:
            kw = {"shadow_mul": shadow_muls[m.name]} if shadow_muls and m.name in shadow_muls else {}
            toonify(m, light=light, threshold=0.12, **kw)
        C.add_outlines(self.objs, outline)
        gm = bpy.data.materials.new("_ground")
        gm.use_nodes = True
        gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (
            *[C.srgb_to_linear(c) for c in C.BG], 1)
        toonify(gm, shadow_mul=(0.84, 0.85, 0.92))
        me = bpy.data.meshes.new("_ground")
        s = 50
        me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
        me.materials.append(gm)
        scene.collection.objects.link(bpy.data.objects.new("_ground", me))
        sd = bpy.data.lights.new("sun", "SUN")
        sd.energy = 3.0
        sd.angle = math.radians(1.0)
        self.sun = bpy.data.objects.new("sun", sd)
        scene.collection.objects.link(self.sun)
        self.sun.rotation_euler = tuple(math.radians(a) for a in sun)
        cd = bpy.data.cameras.new("cam")
        cd.type = "ORTHO"
        self.cam = bpy.data.objects.new("cam", cd)
        scene.collection.objects.link(self.cam)
        scene.camera = self.cam
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

    def aim(self, centre, height, aspect=1.0, elevation=6.0):
        """Ortho camera on game point `centre`, framing `height` metres vertically."""
        cam = self.cam
        cam.data.ortho_scale = height * max(aspect, 1.0)
        c = gv(centre)
        el = math.radians(elevation)
        cam.location = c + Vector((0, -6 * math.cos(el), 6 * math.sin(el)))
        cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()

    def render(self, yaw, w, h):
        """Render the root turned by `yaw` degrees; returns an RGBA float array (top row first)."""
        scene = bpy.context.scene
        r = scene.render
        r.resolution_x, r.resolution_y = w, h
        self.root.rotation_euler = (0, 0, math.radians(yaw))
        path = C.RENDERS_DIR / ".tmp_render.png"
        r.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        self.root.rotation_euler = (0, 0, 0)
        im = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32) / 255
        path.unlink()
        return im

    @staticmethod
    def over_bg(rgba):
        a = rgba[..., 3:4]
        return rgba[..., :3] * a + np.array(C.BG, dtype=np.float32) * (1 - a)

    def sheet(self, name, views, centre, height, size, aspect=1.0):
        """Row of views, each `size` px tall and `size * aspect` wide."""
        self.aim(centre, height, aspect)
        w = round(size * aspect)
        tiles = [self.over_bg(self.render(yaw, w, size)) for _l, yaw in views]
        gap = np.ones((size, 10, 3), np.float32) * np.array(C.BG, np.float32)
        row = []
        for t in tiles:
            row += [t, gap]
        save_png(np.concatenate(row[:-1], axis=1), name)


def save_png(arr, name):
    path = C.RENDERS_DIR / f"{name}.png"
    Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path, optimize=True)
    print(f"rendered {path}")
    return path


def crop_alpha(rgba, pad=4):
    ys, xs = np.nonzero(rgba[..., 3] > 0.02)
    return rgba[max(ys.min() - pad, 0):ys.max() + pad, max(xs.min() - pad, 0):xs.max() + pad]


def compare(name, ref_path, ref_box, render_rgba, height=900, mirror_ref=False,
            labels=("reference", "render")):
    """Side-by-side: reference crop (x0, y0, x1, y1) next to the cropped render, both
    scaled to `height` px."""
    ref = Image.open(ref_path).convert("RGB").crop(ref_box)
    if mirror_ref:
        ref = ref.transpose(Image.FLIP_LEFT_RIGHT)
    ref = ref.resize((round(ref.width * height / ref.height), height), Image.LANCZOS)
    rr = crop_alpha(render_rgba)
    ren = Image.fromarray((np.clip(Preview.over_bg(rr), 0, 1) * 255).astype(np.uint8))
    # Match the figure height: reference crops are tight to the figure as well.
    ren = ren.resize((round(ren.width * height / ren.height), height), Image.LANCZOS)
    bg = tuple(int(c * 255) for c in C.BG)
    top = 44
    gap = 60
    out = Image.new("RGB", (ref.width + ren.width + 40 + gap, height + top + 20), bg)
    out.paste(ref, (20, top))
    out.paste(ren, (ref.width + 20 + gap, top))
    d = ImageDraw.Draw(out)
    font = ImageFont.load_default(size=22)
    d.text((20, 10), labels[0], fill=(40, 40, 40), font=font)
    d.text((ref.width + 20 + gap, 10), labels[1], fill=(40, 40, 40), font=font)
    path = C.RENDERS_DIR / f"{name}.png"
    out.save(path, optimize=True)
    print(f"rendered {path}")
