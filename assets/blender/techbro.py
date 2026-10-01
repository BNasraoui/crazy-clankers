"""The Tech Bro: navy fleece vest, light blue shirt with rolled sleeves, khakis, white
sneakers, iced cold brew, soft brown anime hair, smug little smile.

Flat early-2000s anime-cel proportions: about 6.7 heads tall, rounded tapered limbs,
relaxed contrapposto (weight on his left leg, hip out, other knee bent), left hand in
his pocket, cold brew held up at chest height, head tilted towards the cup.

Nodes: techbro (root) > legs, torso, head, arm_L, arm_R > cup.
He faces +Z in the game. arm_R sits at +X so the game's wave (arm_R.rotation.z = 2.6)
raises it up and outwards; the cup rides along in that hand.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import common as C  # noqa: E402

PALETTE = {
    "skin": 0xF1C8A8,
    "hair": 0x4A2E1E,
    "vest": 0x26324A,
    "shirt": 0x9CC3E6,
    "pants": 0xC9B184,
    "shoes": 0xE9ECF0,
    "sole": 0xFFFFFF,
    "cup": 0xDCECF0,
    "coffee": 0x4B2C1A,
    "straw": 0x1F1F1F,
    "line_dark": 0x1A1414,
}
MATS = list(PALETTE)
SMOOTH = 50  # degrees; soft rounded forms, only real creases stay crisp

# Joints, game coordinates (Y up, +Z forward, metres).
SHOULDER_R = Vector((0.205, 1.395, 0.0))
SHOULDER_L = Vector((-0.205, 1.375, 0.0))  # weight side: shoulder drops
PELVIS = Vector((-0.035, 0.93, 0.005))     # hip pushed out over the standing leg
HIP_ROLL, SHOULDER_ROLL = -6.0, 4.0        # degrees about Z; contrapposto counter-tilt
HEAD_C = Vector((0, 1.615, 0.012))         # skull centre before the head tilt
HEAD_R = (0.112, 0.133, 0.12)
NECK = Vector((0, 1.42, 0))                # head pivot


def g(x, y, z):
    """Game coordinates (Y up, +Z forward) to Blender (Z up, -Y forward)."""
    return Vector((x, -z, y))


def gv(v):
    return g(*v)


def to_game(co):
    return Vector((co.x, co.z, -co.y))


def grot(deg, axis):
    """Blender-space rotation about a game-space axis."""
    return Matrix.Rotation(math.radians(deg), 3, gv(axis))


def rot_xy(v, deg):
    a = math.radians(deg)
    return Vector((v.x * math.cos(a) - v.y * math.sin(a), v.x * math.sin(a) + v.y * math.cos(a), v.z))


# --- lofted shapes -----------------------------------------------------------
# A ring is (centre, u, w, rx, rz, p) in game space: a superellipse of radii rx along u
# and rz along w (p=2 is an ellipse, higher is boxier).

def ring(c, rx, rz, roll=0.0, pitch=0.0, p=2.0):
    """Horizontal ring, rolled about Z and pitched about X (positive pitch drops the front)."""
    m = Matrix.Rotation(math.radians(roll), 3, "Z") @ Matrix.Rotation(math.radians(pitch), 3, "X")
    return (Vector(c), m @ Vector((1, 0, 0)), m @ Vector((0, 0, 1)), rx, rz, p)


def path_rings(pts, radii, ref, p=2.0, closed=False):
    """Rings perpendicular to a polyline. `ref(i, c)` (or a vector) gives the rz direction."""
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


def loft(b, mat, rings, sides, cap0="flat", cap1="flat", closed=False):
    """Skin rings into a closed shell. A cap is "flat", None, or a tip point (game space)."""
    before = b._begin()
    bm = b.bm
    loops = []
    for c, u, w, rx, rz, p in rings:
        loop = []
        for k in range(sides):
            a = 2 * math.pi * (k + 0.5) / sides
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
    return b._assign(before, mat)


def catmull(pts, steps=2):
    """Catmull-Rom through `pts`, `steps` samples per segment."""
    pts = [Vector(q) for q in pts]
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


def decal(b, mat, bvh, pts, z0=1.0, depth=0.008, lift=0.0015, step=None):
    """A thin plate following the existing surface: the game-space (x, y) outline is
    projected along -Z onto `bvh` and thickened along the surface normal."""
    before = b._begin()
    bm = b.bm
    dense = []  # with `step`, subdivide long edges so the plate hugs the faceted surface
    for i, (x0, y0) in enumerate(pts):
        x1, y1 = pts[(i + 1) % len(pts)]
        k = max(1, math.ceil(math.hypot(x1 - x0, y1 - y0) / step)) if step else 1
        dense += [(x0 + (x1 - x0) * j / k, y0 + (y1 - y0) * j / k) for j in range(k)]
    front, back = [], []
    for x, y in dense:
        hit, n, _i, _d = bvh.ray_cast(g(x, y, z0), gv((0, 0, -1)))
        assert hit is not None, f"decal point {(x, y)} missed the surface"
        front.append(bm.verts.new(hit + n * (lift + depth / 2)))
        back.append(bm.verts.new(hit + n * (lift - depth / 2)))
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    k = len(dense)
    for i in range(k):
        j = (i + 1) % k
        bm.faces.new((back[i], back[j], front[j], front[i]))
    return b._assign(before, mat)


def ellipse_pts(cx, cy, rx, ry, n=8, rot=0.0):
    a0 = math.radians(rot)
    return [(cx + rx * math.cos(2 * math.pi * k / n) * math.cos(a0) - ry * math.sin(2 * math.pi * k / n) * math.sin(a0),
             cy + rx * math.cos(2 * math.pi * k / n) * math.sin(a0) + ry * math.sin(2 * math.pi * k / n) * math.cos(a0))
            for k in range(n)]


def limb(b, mat, pts, radii, sides, ref=(0, 0, 1), cap0="flat", cap1="flat", p=2.0):
    return loft(b, mat, path_rings(pts, radii, ref, p), sides, cap0, cap1)


# --- legs --------------------------------------------------------------------

def knee_ik(hip, ankle, thigh, shin, bend):
    """Two-bone solve; `bend` is the direction the knee pushes towards."""
    d = ankle - hip
    dist = d.length
    if dist >= thigh + shin:
        return hip + d * (thigh / (thigh + shin))
    a = (thigh ** 2 - shin ** 2 + dist ** 2) / (2 * dist)
    h = math.sqrt(max(thigh ** 2 - a ** 2, 0.0))
    dn = d.normalized()
    perp = (Vector(bend) - dn * Vector(bend).dot(dn)).normalized()
    return hip + dn * a + perp * h


def hip_joint(sx):
    return PELVIS + rot_xy(Vector((sx * 0.092, -0.02, 0)), HIP_ROLL)


def leg(b, hip, knee, ankle):
    """Khaki leg: wide thigh, a little slack at the knee, slimmer shin, loose hem."""
    def lerp(a, c, t):
        return a + (c - a) * t
    pts = [hip + Vector((0, 0.035, -0.01)), hip, lerp(hip, knee, 0.3), lerp(hip, knee, 0.65), knee,
           lerp(knee, ankle, 0.3), lerp(knee, ankle, 0.65), ankle + Vector((0, 0.03, 0)), ankle]
    radii = [(0.07, 0.07), (0.09, 0.09), (0.09, 0.096), (0.079, 0.084), (0.07, 0.075),
             (0.064, 0.067), (0.06, 0.063), (0.063, 0.066), (0.069, 0.072)]
    limb(b, "pants", pts, radii, 10, cap0=hip + Vector((0, 0.06, -0.01)))


def shoe(b, ankle, yaw):
    """Chunky sneaker: separate white sole slab with a raised heel, rounded toe box."""
    f = Vector((math.sin(math.radians(yaw)), 0, math.cos(math.radians(yaw))))
    base = Vector((ankle.x, 0, ankle.z))

    def at(t, y):
        return base + f * t + Vector((0, y, 0))
    # Sole: rounded-rectangle sections; thicker at the heel, toe springs up a touch.
    st = [-0.085, -0.07, -0.02, 0.06, 0.13, 0.17, 0.19]
    sw = [0.03, 0.044, 0.047, 0.055, 0.054, 0.044, 0.026]
    sh = [0.042, 0.044, 0.04, 0.032, 0.028, 0.028, 0.024]
    lift = [0.0, 0.0, 0.0, 0.0, 0.002, 0.006, 0.011]
    rings = path_rings([at(t, lift[i] + sh[i] / 2) for i, t in enumerate(st)],
                       [(sw[i] * 1.12, sh[i] / 2) for i in range(len(st))], (0, 1, 0), p=4.0)
    loft(b, "sole", rings, 8)
    # Upper: high heel collar, rounded toe box sitting on the sole.
    ut = [-0.078, -0.064, -0.02, 0.04, 0.1, 0.145, 0.172]
    uw = [0.032, 0.043, 0.046, 0.05, 0.05, 0.042, 0.026]
    uh = [0.05, 0.058, 0.06, 0.046, 0.034, 0.027, 0.018]
    sole_top = [0.043, 0.044, 0.041, 0.034, 0.031, 0.034, 0.035]
    rings = path_rings([at(t, sole_top[i] + uh[i] * 0.85) for i, t in enumerate(ut)],
                       [(uw[i] * 1.12, uh[i] * 1.06) for i in range(len(ut))], (0, 1, 0))
    loft(b, "shoes", rings, 10, cap1=at(0.182, 0.04))


def build_legs():
    b = C.Builder(MATS)
    # Pelvis: rolled with the hips.
    for_ring = [(1.0, 0.15, 0.106), (0.93, 0.168, 0.116), (0.86, 0.16, 0.104), (0.80, 0.125, 0.09)]
    rings = [ring(PELVIS + rot_xy(Vector((0, y - PELVIS.y, 0)), HIP_ROLL), rx, rz, roll=HIP_ROLL)
             for y, rx, rz in for_ring]
    loft(b, "pants", rings, 12, cap1=PELVIS + rot_xy(Vector((0, -0.16, 0)), HIP_ROLL))
    # Standing leg (-X): nearly straight, foot under the body.
    hip_l = hip_joint(-1)
    ankle_l = Vector((-0.085, 0.115, -0.01))
    knee_l = hip_l + (ankle_l - hip_l) * 0.51 + Vector((0, 0, 0.012))
    leg(b, hip_l, knee_l, ankle_l)
    shoe(b, ankle_l, -8)
    # Free leg (+X): hip drops, knee bends forward and in, foot set out and forward.
    hip_r = hip_joint(1)
    ankle_r = Vector((0.155, 0.12, 0.085))
    knee_r = knee_ik(hip_r, ankle_r, 0.42, 0.41, (-0.35, 0, 1))
    leg(b, hip_r, knee_r, ankle_r)
    shoe(b, ankle_r, 18)
    return b.to_object("legs", MATS_BY_NAME, pivot=g(0, 0.92, 0), parent=ROOT, smooth_angle=SMOOTH)


# --- torso -------------------------------------------------------------------

def torso_ring(y, cx, rx, rz, cz=0.0, pitch=0.0):
    t = min(max((y - 0.93) / (1.37 - 0.93), 0.0), 1.0)
    roll = HIP_ROLL + (SHOULDER_ROLL - HIP_ROLL) * t
    return ring((cx, y, cz), rx, rz, roll=roll, pitch=pitch, p=2.3)


def build_torso():
    b = C.Builder(MATS)
    # Shirt, untucked: the hem flares out over the khakis below the vest.
    shirt = [(0.845, -0.034, 0.2, 0.148), (0.87, -0.034, 0.198, 0.146), (0.95, -0.032, 0.186, 0.132), (1.05, -0.022, 0.163, 0.112),
             (1.18, -0.01, 0.175, 0.118), (1.3, 0.0, 0.18, 0.11), (1.37, 0.0, 0.15, 0.092),
             (1.41, 0.0, 0.08, 0.068)]
    loft(b, "shirt", [torso_ring(*r) for r in shirt], 12)
    # Fleece vest: puffy body with a tucked-in hem, narrowing to straps above the armpits.
    vest = [(0.965, -0.026, 0.186, 0.13), (0.99, -0.026, 0.198, 0.142), (1.09, -0.02, 0.204, 0.15),
            (1.19, -0.01, 0.21, 0.153), (1.265, -0.003, 0.2, 0.146), (1.325, 0.0, 0.152, 0.128),
            (1.39, 0.0, 0.112, 0.104)]
    loft(b, "vest", [torso_ring(y, cx, rx, rz, cz=-0.004) for y, cx, rx, rz in vest], 14)
    # Raised collar: a thick stand-up band, lower at the front so it clears the chin.
    collar = [ring((0, 1.365, -0.012), 0.112, 0.104, SHOULDER_ROLL, 12),
              ring((0, 1.47, -0.022), 0.1, 0.098, SHOULDER_ROLL, 16),
              ring((0, 1.468, -0.022), 0.078, 0.076, SHOULDER_ROLL, 16),
              ring((0, 1.375, -0.012), 0.072, 0.07, SHOULDER_ROLL, 12)]
    loft(b, "vest", collar, 12, closed=True)
    # Armhole binding standing off the shirt, wrapped around each arm root.
    for sx in (1, -1):
        sh = SHOULDER_R if sx > 0 else SHOULDER_L
        c = Vector((sx * 0.168, sh.y - 0.085, -0.005))
        loop = [c + Vector((0, 0.072 * math.sin(a), 0.098 * math.cos(a)))
                for a in (2 * math.pi * k / 10 for k in range(10))]
        rings = path_rings(loop, [(0.013, 0.016)] * 10, lambda i, q: q - c, closed=True)
        loft(b, "vest", rings, 4, closed=True)
    # Open V at the neck showing the shirt, and the zip down the front.
    bvh = BVHTree.FromBMesh(b.bm)
    v = [(-0.07, 1.4), (-0.05, 1.36), (-0.03, 1.32), (-0.012, 1.285), (0.0, 1.265), (0.012, 1.285),
         (0.03, 1.32), (0.05, 1.36), (0.07, 1.4)]
    decal(b, "shirt", bvh, v, depth=0.01)
    zip_line = [(-0.02 * (1.265 - y) / 0.3, y) for y in (1.265, 1.19, 1.11, 1.04, 0.968)]
    decal(b, "line_dark", bvh, [(x - 0.004, y) for x, y in zip_line]
          + [(x + 0.004, y) for x, y in reversed(zip_line)], depth=0.006)
    return b.to_object("torso", MATS_BY_NAME, pivot=g(0, 0.95, 0), parent=ROOT, smooth_angle=SMOOTH)


# --- head --------------------------------------------------------------------

HAIR_C = HEAD_C + Vector((0, 0.014, -0.01))
HAIR_R = (HEAD_R[0] * 1.1, HEAD_R[1] * 1.1, HEAD_R[2] * 1.1)


def hair_pt(theta, phi, lift):
    """Point over the hair shell: azimuth theta (0 = front, 90 = +X), elevation phi."""
    t, p = math.radians(theta), math.radians(phi)
    s = 1 + lift
    return HAIR_C + Vector((HAIR_R[0] * s * math.sin(t) * math.cos(p), HAIR_R[1] * s * math.sin(p),
                            HAIR_R[2] * s * math.cos(t) * math.cos(p)))


def lock(b, path, width, thick):
    """Soft chunky hair lock: fattens just after the root, tapers to a rounded tip."""
    path = [(path[0][0], path[0][1], path[0][2] - 0.04)] + path[1:]  # root sinks into the shell
    pts = catmull([hair_pt(*q) for q in path], 2)
    n = len(pts)
    prof = [max(0.3, math.sin(math.pi * (0.28 + 0.72 * i / (n - 1)))) for i in range(n)]
    radii = [(width * f, thick * (0.5 + 0.5 * f)) for f in prof]
    rings = path_rings(pts, radii, lambda i, c: c - HAIR_C)
    tip = pts[-1] + (pts[-1] - pts[-2]).normalized() * width * 0.45
    loft(b, "hair", rings, 6, cap0="flat", cap1=tip)


# (azimuth, elevation, lift) control points; widths and thicknesses are radii.
LOCKS = [
    # Fringe: big locks falling over the forehead, swept towards -X.
    ([(30, 70, 0.0), (16, 52, 0.09), (2, 34, 0.11), (-8, 20, 0.09)], 0.034, 0.016),
    ([(55, 60, 0.0), (46, 42, 0.09), (36, 26, 0.1), (30, 16, 0.08)], 0.03, 0.015),
    ([(-10, 68, 0.0), (-26, 50, 0.09), (-38, 32, 0.1), (-44, 18, 0.08)], 0.03, 0.014),
    ([(75, 50, 0.0), (72, 32, 0.08), (68, 16, 0.07)], 0.024, 0.012),
    # Top: full swept volume over the crown.
    ([(170, 58, 0.02), (120, 76, 0.06), (50, 78, 0.06), (20, 68, 0.04)], 0.052, 0.022),
    ([(-150, 56, 0.02), (-110, 74, 0.06), (-50, 74, 0.06), (-25, 64, 0.04)], 0.048, 0.02),
    ([(125, 46, 0.02), (100, 64, 0.06), (70, 68, 0.05)], 0.04, 0.018),
    # Sides, behind the cheek and over the top of the ear.
    ([(95, 52, 0.02), (102, 28, 0.09), (106, 6, 0.09), (108, -10, 0.05)], 0.032, 0.015),
    ([(-95, 52, 0.02), (-102, 28, 0.09), (-106, 6, 0.09), (-108, -10, 0.05)], 0.032, 0.015),
    # Back, falling to the nape.
    ([(140, 55, 0.02), (148, 20, 0.1), (152, -15, 0.09), (156, -36, 0.05)], 0.04, 0.017),
    ([(-140, 55, 0.02), (-148, 20, 0.1), (-152, -15, 0.09), (-156, -36, 0.05)], 0.04, 0.017),
    ([(180, 50, 0.02), (180, 15, 0.1), (178, -18, 0.09), (176, -40, 0.05)], 0.044, 0.018),
]


def hairline(theta):
    """Elevation (degrees) below which the hair shell tucks inside the skull."""
    c = math.cos(math.radians(theta))
    return 2 + 33 * c if c > 0 else 2 + 44 * c


def build_head():
    b = C.Builder(MATS)
    hc = HEAD_C
    rx, ry, rz = HEAD_R
    b.tube("skin", gv(NECK + Vector((0, -0.03, -0.01))), gv(NECK + Vector((0, 0.11, 0.0))), 0.05, 0.048, sides=8)
    # Skull: an ellipsoid whose lower half narrows into a soft, rounded anime jaw.
    faces = b.sphere("skin", gv(hc), (rx, rz, ry), u=14, v=10)
    for v in {v for f in faces for v in f.verts}:
        d = to_game(v.co) - hc
        if d.y < 0:
            t = -d.y / ry
            d.x *= 1 - 0.3 * t ** 1.4
            d.z *= 1 - (0.12 if d.z > 0 else 0.3) * t
            d.z += 0.012 * t * max(0.0, 1 - abs(d.x) / rx)  # chin a touch forward
        v.co = gv(hc + d)
    for sx in (1, -1):
        b.sphere("skin", gv(hc + Vector((sx * 0.106, -0.018, -0.008))), (0.02, 0.026, 0.034), u=6, v=4)
    # Face, flush with the skin: two dark ovals, simple brows (one cocked), smug smile.
    bvh = BVHTree.FromBMesh(b.bm)
    ey = hc.y - 0.022
    for sx in (1, -1):
        decal(b, "line_dark", bvh, ellipse_pts(sx * 0.041, ey, 0.011, 0.017), depth=0.006)
    decal(b, "line_dark", bvh, [(0.022, ey + 0.036), (0.064, ey + 0.05), (0.068, ey + 0.041), (0.024, ey + 0.028)],
          depth=0.006, step=0.016)
    decal(b, "line_dark", bvh, [(-0.022, ey + 0.031), (-0.066, ey + 0.035), (-0.068, ey + 0.026), (-0.024, ey + 0.023)],
          depth=0.006, step=0.016)
    my = hc.y - 0.078
    smile = [(-0.022, 0.003), (-0.008, -0.003), (0.008, -0.002), (0.021, 0.004), (0.03, 0.013),
             (0.026, 0.004), (0.01, -0.008), (-0.006, -0.009), (-0.02, -0.003)]
    decal(b, "line_dark", bvh, [(0.004 + x, my + y) for x, y in smile], depth=0.006)
    # Hair shell: fuller on top; below the hairline it tucks inside the skull.
    faces = b.sphere("hair", gv(HAIR_C), (HAIR_R[0], HAIR_R[2], HAIR_R[1]), u=12, v=9)
    for v in {v for f in faces for v in f.verts}:
        d = to_game(v.co) - HAIR_C
        theta = math.degrees(math.atan2(d.x, d.z))
        n = Vector((d.x / HAIR_R[0], d.y / HAIR_R[1], d.z / HAIR_R[2]))
        phi = math.degrees(math.asin(max(-1.0, min(1.0, n.y / n.length))))
        if phi < hairline(theta):
            v.co = gv(HAIR_C + d * 0.82)
        elif d.y > 0:
            v.co = gv(HAIR_C + Vector((d.x, d.y * 1.07, d.z)))
    for path, w, t in LOCKS:
        lock(b, path, w, t)
    # Head tilts towards the cup (+X) and dips a little to look at it.
    tilt = grot(-8, (0, 0, 1)) @ grot(2, (1, 0, 0))
    bmesh.ops.rotate(b.bm, verts=b.bm.verts, cent=gv(NECK), matrix=tilt)
    return b.to_object("head", MATS_BY_NAME, pivot=gv(NECK), parent=ROOT, smooth_angle=SMOOTH)


# --- arms and cup ------------------------------------------------------------

def build_arm(name, sh, elbow, wrist, hand_size):
    """Sleeve from the shoulder pivot, rolled cuff below the elbow, bare forearm, hand."""
    b = C.Builder(MATS)
    up = (elbow - sh).normalized()
    fore = (wrist - elbow).normalized()
    sleeve = [sh - up * 0.03, sh, sh + (elbow - sh) * 0.35, sh + (elbow - sh) * 0.7, elbow]
    limb(b, "shirt", sleeve, [(0.046, 0.045), (0.06, 0.058), (0.056, 0.055), (0.051, 0.05), (0.048, 0.047)],
         10, cap0=sh - up * 0.048, cap1=None)
    cuff = [elbow - up * 0.025, elbow + fore * 0.01, elbow + fore * 0.05, elbow + fore * 0.075]
    limb(b, "shirt", cuff, [(0.05, 0.049), (0.056, 0.055), (0.056, 0.055), (0.05, 0.049)], 10)
    arm = [elbow + fore * 0.03, elbow + fore * 0.12, wrist]
    limb(b, "skin", arm, [(0.04, 0.038), (0.037, 0.035), (0.029, 0.027)], 8)
    hand = wrist + fore * 0.045
    b.sphere("skin", gv(hand), hand_size, u=8, v=5,
             rot=C.look_rot(gv(fore)))
    return b.to_object(name, MATS_BY_NAME, pivot=gv(sh), parent=ROOT, smooth_angle=SMOOTH), hand


def build_cup(hand, parent):
    """Iced cold brew in a clear cup: coffee body, icy top, domed lid, black straw."""
    b = C.Builder(MATS)
    c = hand + Vector((-0.035, 0.05, 0.03))
    bot, h = c.y - 0.1, 0.19
    b.tube("coffee", g(c.x, bot, c.z), g(c.x, bot + 0.13, c.z), 0.044, 0.053, sides=12)
    b.tube("cup", g(c.x, bot + 0.13, c.z), g(c.x, bot + h, c.z), 0.053, 0.057, sides=12)
    b.tube("cup", g(c.x, bot + h, c.z), g(c.x, bot + h + 0.022, c.z), 0.06, 0.032, sides=12)
    b.tube("straw", g(c.x, bot + 0.12, c.z), g(c.x - 0.015, bot + h + 0.085, c.z - 0.012), 0.008, 0.008,
           sides=6)
    return b.to_object("cup", MATS_BY_NAME, pivot=gv(c), parent=parent, smooth_angle=SMOOTH)


C.reset_scene()
MATS_BY_NAME = C.make_materials(PALETTE)
ROOT = C.empty("techbro")
parts = [build_legs(), build_torso(), build_head()]
# Left hand shoved in the front pocket; the hand itself sinks into the khakis.
arm_l, _ = build_arm("arm_L", SHOULDER_L, Vector((-0.282, 1.115, -0.05)), Vector((-0.17, 0.935, 0.07)),
                     (0.03, 0.026, 0.04))
# Right forearm bent up and forward, holding the cup at chest height.
arm_r, hand_r = build_arm("arm_R", SHOULDER_R, Vector((0.262, 1.13, -0.045)), Vector((0.19, 1.26, 0.17)),
                          (0.042, 0.038, 0.052))
parts += [arm_l, arm_r, build_cup(hand_r, arm_r)]
C.report(parts)
assert C.triangle_count(parts) <= 4000, "techbro over its triangle budget"
C.export_glb("techbro")
C.render_contact_sheet(ROOT, "techbro", outline=0.008, fill=1.0, skip_outline=("line_dark",))

# Head close-up (front, 3/4, side, back) to check the hair and face.
cam = bpy.context.scene.camera
head_c = gv(HEAD_C + Vector((0.03, 0.0, 0.0)))
cam.data.lens = 70.0
dist = 0.26 / math.tan(math.atan(cam.data.sensor_width / (2 * 70.0)))
el = math.radians(6)
cam.location = head_c + Vector((0, -dist * math.cos(el), dist * math.sin(el)))
cam.rotation_euler = (head_c - cam.location).to_track_quat("-Z", "Y").to_euler()
views = (("front", 0), ("3/4 front", -35), ("side", -90), ("back", 180))
C.save_sheet(C.render_views(ROOT, "techbro-head", views, 480), "techbro-head", 480)
