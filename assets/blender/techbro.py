"""The Tech Bro (v3): navy fleece vest, light blue oxford shirt with rolled cuffs, slim
khakis, chunky white sneakers, iced cold brew, messy dark anime hair, smug grin.

Built with anime.py: smooth lofted forms, an anime skull with a painted face texture,
sharp tapered hair locks. About 7.4 heads tall, 1.78 m. Relaxed contrapposto (weight
on the cup-side leg, the other foot stepped out), left hand shoved in his pocket, cold
brew up at chest height, head cocked towards the cup with his chin up.

docs/art/cast.jpg shows him mirrored: the game waves arm_R, which has to be on +X,
so the cup is in the +X hand and every asymmetry (cocked brow, hair sweep, smirk)
is mirrored to match.

Nodes: techbro (root) > legs, torso, head (pivot at the neck), arm_L, arm_R (pivots at
the shoulders) > cup. He faces +Z in the game. Rotating arm_R about Z by +2.6 rad
swings it up and out to wave.

Run: blender --background --factory-startup --python assets/blender/techbro.py [-- quick]
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import anime as A  # noqa: E402
import common as C  # noqa: E402
from anime import g, gv, lerp  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

PALETTE = {
    "skin": 0xF6D0B1,
    "face": 0xF6D0B1,
    "hair": 0x2B211E,
    "vest": 0x2B3352,
    "shirt": 0xAFC8EC,
    "pants": 0xD6BC90,
    "shoes": 0xF2F2F0,
    "sole": 0xBFC0C4,
    "cup": 0xE4EEF2,
    "coffee": 0x5A3420,
    "straw": 0x222222,
}
MATS = list(PALETTE)
SMOOTH = 70  # degrees: everything reads as smooth, only real creases stay crisp
TRI_BUDGET = 15000

# --- proportions (game space: Y up, +Z forward, metres) ---------------------------
HEAD = A.HeadSpec(centre=Vector((0, 1.628, 0.012)), ry_lo=0.11, chin_w=0.32, jaw_start=0.32, neck_r=0.049)
NECK = Vector((0, 1.44, -0.012))            # head pivot
SHOULDER_R = Vector((0.172, 1.414, -0.014))  # cup arm (+X)
SHOULDER_L = Vector((-0.172, 1.402, -0.014))
HIP_ROLL, SHOULDER_ROLL = 4.0, -2.5          # degrees about Z; +X hip up (weight leg)
PELVIS = Vector((0.018, 0.9, 0.0))
HEAD_TILT = ((-8, (0, 0, 1)), (16, (0, 1, 0)), (-6, (1, 0, 0)))  # roll to cup, turn, chin up


def sway(p):
    """Contrapposto: roll each torso slice about Z, interpolating hip to shoulder roll,
    and shift the hips over the standing leg."""
    t = A.smoothstep(0.9, 1.4, p.y)
    r = math.radians(lerp(HIP_ROLL, SHOULDER_ROLL, t))
    cx = lerp(PELVIS.x, 0.0, t)
    return Vector((cx + p.x * math.cos(r), p.y + p.x * math.sin(r), p.z))


def apply(b, fn):
    for v in b.bm.verts:
        v.co = gv(fn(A.to_game(v.co)))


# --- legs ----------------------------------------------------------------------

def leg(b, hip, knee, ankle):
    """Slim chinos: full thigh, narrow knee, a little break above the hem."""
    pts = [hip + Vector((0, 0.05, 0)), hip, lerp(hip, knee, 0.45), knee,
           lerp(knee, ankle, 0.45), lerp(knee, ankle, 0.85), ankle + Vector((0, 0.01, 0))]
    radii = [(0.078, 0.078), (0.084, 0.086), (0.073, 0.077), (0.062, 0.066),
             (0.058, 0.061), (0.056, 0.059), (0.06, 0.062)]
    A.limb(b, "pants", pts, radii, sides=16, cap1="flat")


def shoe(b, ankle, yaw):
    """Chunky sneaker: a hard-edged sole slab, rounded upper with a high heel collar."""
    f = Vector((math.sin(math.radians(yaw)), 0, math.cos(math.radians(yaw))))
    base = Vector((ankle.x, 0, ankle.z))

    def at(t, y):
        return base + f * t + Vector((0, y, 0))
    st = [-0.09, -0.075, -0.02, 0.06, 0.13, 0.175, 0.198]
    sw = [0.032, 0.046, 0.05, 0.057, 0.056, 0.046, 0.026]
    sh = [0.036, 0.036, 0.034, 0.028, 0.026, 0.026, 0.024]
    lift = [0.0, 0.0, 0.0, 0.0, 0.002, 0.006, 0.012]
    rings = A.path_rings([at(t, lift[i] + sh[i] / 2) for i, t in enumerate(st)],
                         [(sw[i] * 1.1, sh[i] / 2) for i in range(len(st))], (0, 1, 0), p=5.0)
    A.loft(b, "sole", rings, 12)
    ut = [-0.083, -0.07, -0.02, 0.04, 0.1, 0.15, 0.178]
    uw = [0.034, 0.045, 0.048, 0.052, 0.052, 0.043, 0.026]
    uh = [0.052, 0.06, 0.062, 0.046, 0.033, 0.026, 0.017]
    top = [0.036, 0.036, 0.034, 0.029, 0.027, 0.031, 0.034]
    pts = [at(t, top[i] + uh[i] * 0.85) for i, t in enumerate(ut)]
    rad = [(uw[i] * 1.08, uh[i] * 1.05) for i in range(len(ut))]
    A.loft(b, "shoes", A.path_rings(A.catmull(pts, 2), [r[:2] for r in A.catmull_vals(rad, 2)], (0, 1, 0)),
           12, cap1=at(0.188, 0.036))


def build_legs():
    b = C.Builder(MATS)
    pel = [(0.98, 0.148, 0.1), (0.93, 0.158, 0.108), (0.87, 0.15, 0.1), (0.81, 0.11, 0.085)]
    rings = [A.ring((0, y, 0), rx, rz, p=2.2) for y, rx, rz in pel]
    A.loft(b, "pants", rings, 20, cap1=Vector((0, 0.77, 0)))
    apply(b, sway)
    # Standing leg (+X, cup side): straight, foot under the hip.
    hip_r = sway(Vector((0.07, 0.86, 0)))
    ankle_r = Vector((0.085, 0.095, -0.01))
    knee_r = lerp(hip_r, ankle_r, 0.5) + Vector((0, 0, 0.012))
    leg(b, hip_r, knee_r, ankle_r)
    shoe(b, ankle_r, 10)
    # Free leg (-X): set out to the side, knee a touch soft.
    hip_l = sway(Vector((-0.07, 0.86, 0)))
    ankle_l = Vector((-0.2, 0.095, 0.035))
    knee_l = A.knee_ik(hip_l, ankle_l, 0.39, 0.39, (0.2, 0, 1))
    leg(b, hip_l, knee_l, ankle_l)
    shoe(b, ankle_l, -14)
    o = b.to_object("legs", MATS_BY_NAME, pivot=g(0, 0.92, 0), parent=ROOT, smooth_angle=SMOOTH)
    A.set_flat(o, {"sole"})
    return o


# --- torso ---------------------------------------------------------------------
# (y, rx, rz, cz) profiles; superellipse sections.
SHIRT = [(0.872, 0.168, 0.12, 0.0), (0.9, 0.166, 0.118, 0.0), (0.97, 0.162, 0.118, 0.0),
         (1.06, 0.15, 0.106, 0.0), (1.16, 0.15, 0.102, 0.0), (1.26, 0.16, 0.104, 0.0),
         (1.34, 0.168, 0.1, -0.004), (1.4, 0.155, 0.088, -0.008), (1.44, 0.1, 0.07, -0.01),
         (1.47, 0.05, 0.05, -0.012)]
VEST = [(0.955, 0.168, 0.122, 0.0), (0.985, 0.172, 0.127, 0.0), (1.08, 0.167, 0.122, 0.0),
        (1.18, 0.176, 0.124, 0.0), (1.28, 0.184, 0.122, -0.002), (1.36, 0.178, 0.112, -0.006),
        (1.42, 0.166, 0.098, -0.01), (1.465, 0.108, 0.084, -0.012)]


def profile(table, y):
    ys = [r[0] for r in table]
    i = max(1, min(len(ys) - 1, next((k for k, v in enumerate(ys) if v >= y), len(ys) - 1)))
    t = (y - ys[i - 1]) / (ys[i] - ys[i - 1])
    t = t * t * (3 - 2 * t)
    return [lerp(table[i - 1][k], table[i][k], t) for k in (1, 2, 3)]


def section(table, y, a, p=2.3, grow=0.0):
    rx, rz, cz = profile(table, y)
    s, c = math.sin(a), math.cos(a)
    return Vector((math.copysign(abs(s) ** (2 / p), s) * (rx + grow), y,
                   cz + math.copysign(abs(c) ** (2 / p), c) * (rz + grow)))


def opening(y):
    """Half angle (radians) of the open vest front at height y: a narrow gap showing the
    shirt placket, widening into the V under the collar."""
    return math.radians(9 + 22 * A.smoothstep(1.24, 1.465, y))


def collar_base(a):
    d = abs(math.degrees(math.atan2(math.sin(a), math.cos(a))))
    return 1.442 + 0.012 * A.smoothstep(90, 180, d) - 0.05 * A.smoothstep(70, 28, d)


def build_torso():
    b = C.Builder(MATS)
    rings = [A.ring((0, y, cz), rx, rz, p=2.3) for y, rx, rz, cz in SHIRT]
    A.loft(b, "shirt", rings, 24)
    # Fleece vest, worn open: a thick shell wrapping from one front edge round the back
    # to the other.
    n, rows = 40, 10
    grid = []
    for j in range(rows + 1):
        y = lerp(0.955, 1.465, j / rows)
        a0 = opening(y)
        grid.append([section(VEST, y, lerp(a0, 2 * math.pi - a0, i / (n - 1))) for i in range(n)])
    A.shell(b, "vest", grid, 0.014, wrap=False, axis=lambda p: Vector((0, p.y, profile(VEST, p.y)[2])))
    # Stand collar: a thick band around the back of the neck, open at the front.
    cn, crows = 26, 4
    cang = [math.radians(lerp(-150, 150, i / (cn - 1))) + math.pi for i in range(cn)]
    cgrid = []
    for j in range(crows + 1):
        s = j / crows
        row = []
        for a in cang:
            d = abs(math.degrees(math.atan2(math.sin(a), math.cos(a))))
            y0 = collar_base(a) - 0.012
            y = lerp(y0, y0 + 0.09 - 0.02 * A.smoothstep(150, 60, d), s)
            r = lerp(1.0, 0.9, s)
            row.append(Vector((math.sin(a) * 0.092 * r, y, -0.014 + math.cos(a) * 0.084 * r)))
        cgrid.append(row)
    A.shell(b, "vest", cgrid, 0.014, wrap=False, axis=lambda p: Vector((0, p.y, -0.014)))
    # Rolled fleece edge down each front.
    for sx in (1, -1):
        ys = [0.958, 1.06, 1.16, 1.26, 1.36, 1.44]
        pts = [section(VEST, y, sx * opening(y), grow=0.002) for y in ys]
        A.limb(b, "vest", pts, [(0.01, 0.012)] * len(pts), sides=8, steps=2)
    # Shirt collar points lying in the V.
    for sx in (1, -1):
        A.limb(b, "shirt", [Vector((sx * 0.052, 1.45, 0.06)), Vector((sx * 0.036, 1.41, 0.088)),
                            Vector((sx * 0.018, 1.385, 0.098))],
               [(0.014, 0.005), (0.011, 0.005), (0.003, 0.003)], sides=6, ref=(0, 0, 1), cap1="flat")
    # Armhole binding where the sleeves leave the vest.
    for sx, sh in ((1, SHOULDER_R), (-1, SHOULDER_L)):
        c = Vector((sx * 0.165, sh.y - 0.085, -0.008))
        loop = [c + Vector((sx * 0.012 * math.cos(a), 0.085 * math.sin(a), 0.1 * math.cos(a)))
                for a in (2 * math.pi * k / 16 for k in range(16))]
        rings = A.path_rings(loop, [(0.012, 0.014)] * 16, lambda i, q: q - c, closed=True)
        A.loft(b, "vest", rings, 6, closed=True)
    apply(b, sway)
    o = b.to_object("torso", MATS_BY_NAME, pivot=g(0, 0.95, 0), parent=ROOT, smooth_angle=SMOOTH)
    A.front_uv(o, "vest", VEST_TEX[0], VEST_TEX[1], fallback=(0.01, 0.99), min_nz=0.05)
    A.front_uv(o, "shirt", SHIRT_TEX[0], SHIRT_TEX[1], fallback=(0.01, 0.99), min_nz=0.05)
    return o


VEST_TEX = (0.28, 0.92)  # half size, bottom of the vest texture window


SHIRT_TEX = (0.28, 0.86)


def paint_vest():
    pt = A.Painter(1024, A.rgb(PALETTE["vest"]), *VEST_TEX)
    dark = (22, 27, 44)
    # Chest zip pocket and a small embroidered wordmark on the -X chest (his left in cast.jpg).
    pt.stroke([(-0.08, 1.255), (-0.078, 1.2), (-0.076, 1.16)], [0.004] * 3, dark)
    for k in range(7):
        x = -0.125 + k * 0.0085
        pt.stroke([(x, 1.274), (x + 0.004, 1.282)], [0.0022, 0.0022], (196, 200, 210), steps=2)
    # Hand-warmer pockets.
    for sx in (1, -1):
        pt.stroke([(sx * 0.075, 1.12), (sx * 0.088, 1.06), (sx * 0.098, 1.0)], [0.004] * 3, dark)
    return pt.save("vest")


def paint_shirt():
    """Button placket down the front, following the contrapposto sway."""
    pt = A.Painter(1024, A.rgb(PALETTE["shirt"]), *SHIRT_TEX)
    line, button = (128, 156, 204), (244, 246, 250)
    ys = [0.86, 1.0, 1.15, 1.3, 1.41]
    for dx in (-0.012, 0.012):
        pt.stroke([(sway(Vector((dx, y, 0))).x, y) for y in ys], [0.0022] * len(ys), line)
    for y in (1.36, 1.27, 1.18, 1.09, 1.0, 0.91):
        x = sway(Vector((0, y, 0))).x
        pt.ellipse(x, y, 0.0055, 0.0055, line)
        pt.ellipse(x, y, 0.0038, 0.0038, button)
    return pt.save("shirt")


# --- head ----------------------------------------------------------------------

def hairline(theta):
    """Elevation where the scalp shell stops: high forehead, clear of the ears, low nape."""
    c = math.cos(math.radians(theta))
    side = math.exp(-((abs(theta) - 95) / 30) ** 2)
    return (16 + 38 * c ** 1.5 if c > 0 else 16 + 48 * c) + 2 * side


# (theta, phi, lift) control points: theta 0 = front, +90 = +X (cup side); phi = elevation
# above the eye line. Width/thickness are half sizes in metres.
LOCKS = [
    # Fringe: a few pointed locks falling onto the forehead, swept towards +X.
    ([(-30, 82, 0.014), (-12, 66, 0.036), (6, 50, 0.032), (16, 34, 0.016)], 0.032, 0.012),
    ([(-2, 84, 0.014), (18, 68, 0.036), (34, 52, 0.032), (46, 34, 0.018)], 0.03, 0.012),
    ([(-52, 76, 0.014), (-46, 62, 0.034), (-38, 50, 0.03), (-34, 40, 0.016)], 0.026, 0.011),
    ([(26, 82, 0.014), (48, 68, 0.034), (62, 52, 0.032), (72, 38, 0.022)], 0.028, 0.011),
    ([(-14, 74, 0.014), (-4, 58, 0.034), (2, 44, 0.026), (0, 30, 0.01)], 0.015, 0.007),
    # Quiff: volume pushed up off the forehead and swept back, wide at the temples.
    ([(-20, 64, 0.01), (0, 76, 0.04), (40, 84, 0.046), (150, 80, 0.04), (172, 62, 0.04)], 0.052, 0.017),
    ([(30, 62, 0.01), (50, 74, 0.042), (90, 76, 0.048), (118, 66, 0.044), (130, 50, 0.05)], 0.046, 0.015),
    ([(-50, 62, 0.01), (-66, 74, 0.04), (-104, 74, 0.044), (-122, 62, 0.042), (-132, 48, 0.048)], 0.046, 0.015),
    ([(64, 52, 0.01), (80, 60, 0.04), (98, 58, 0.05), (112, 50, 0.062)], 0.034, 0.013),
    ([(-64, 52, 0.01), (-80, 60, 0.04), (-98, 58, 0.048), (-112, 50, 0.058)], 0.034, 0.013),
    # Messy wisps flicking out of the top.
    ([(40, 74, 0.03), (70, 80, 0.05), (96, 74, 0.068)], 0.018, 0.007),
    ([(-150, 72, 0.03), (-170, 74, 0.05), (170, 66, 0.066)], 0.018, 0.007),
    # Sides: cropped over the temples, flicking out and back; the ears stay clear.
    ([(70, 56, 0.01), (84, 40, 0.026), (94, 28, 0.032), (104, 18, 0.048)], 0.03, 0.012),
    ([(110, 56, 0.01), (118, 38, 0.03), (126, 24, 0.036), (136, 14, 0.052)], 0.032, 0.012),
    ([(-70, 56, 0.01), (-84, 40, 0.026), (-94, 28, 0.032), (-104, 18, 0.046)], 0.03, 0.012),
    ([(-110, 56, 0.01), (-118, 38, 0.03), (-126, 24, 0.036), (-136, 14, 0.05)], 0.032, 0.012),
    # Short sideburns in front of the ears.
    ([(82, 34, 0.004), (84, 22, 0.01), (85, 10, 0.006)], 0.012, 0.005),
    ([(-82, 34, 0.004), (-84, 22, 0.01), (-85, 10, 0.006)], 0.012, 0.005),
    # Back, down to a short pointed nape.
    ([(150, 56, 0.01), (155, 30, 0.032), (158, 6, 0.032), (160, -12, 0.03)], 0.04, 0.014),
    ([(180, 56, 0.01), (180, 30, 0.034), (180, 4, 0.032), (180, -16, 0.026)], 0.042, 0.014),
    ([(-150, 56, 0.01), (-155, 30, 0.032), (-158, 6, 0.032), (-160, -12, 0.03)], 0.04, 0.014),
    ([(126, 44, 0.01), (134, 26, 0.03), (140, 10, 0.034), (146, 0, 0.04)], 0.032, 0.012),
    ([(-126, 44, 0.01), (-134, 26, 0.03), (-140, 10, 0.034), (-146, 0, 0.04)], 0.032, 0.012),
]

FACE = A.FaceSpec(
    skin=PALETTE["face"],
    eyes=[A.EyeSpec(x=-0.038, w=0.04, h=0.023, lid=0.16, tilt=2, look=(-0.06, 0.0)),
          A.EyeSpec(x=0.038, w=0.039, h=0.022, lid=0.32, tilt=0, look=(-0.06, 0.0))],
    # Cocked brow on -X, flatter one over the narrower eye.
    brows=[([(-0.014, 0.026), (-0.03, 0.039), (-0.052, 0.041), (-0.07, 0.031)], [0.009, 0.0095, 0.006, 0.0]),
           ([(0.014, 0.022), (0.034, 0.026), (0.056, 0.026), (0.071, 0.019)], [0.009, 0.0085, 0.0055, 0.0])],
    nose=[([(0.004, -0.031), (0.007, -0.039), (0.001, -0.042)], [0.0, 0.0024, 0.0])],
    mouth={
        "upper": [(-0.036, -0.058), (-0.016, -0.064), (0.008, -0.065), (0.029, -0.06)],
        "lower": [(-0.036, -0.058), (-0.014, -0.075), (0.01, -0.076), (0.029, -0.06)],
        "teeth": True, "line": 0.003, "inside": 0x8A3C36,
        "ticks": [([(-0.04, -0.054), (-0.036, -0.058), (-0.037, -0.062)], [0.0, 0.0022, 0.0])],
    },
    # Little soul patch under the lip, as in cast.jpg.
    extras=[([(-0.002, -0.084), (0.0, -0.09)], [0.004, 0.0], 0x3A2A24)],
)


def build_head():
    b = C.Builder(MATS)
    A.build_head(b, HEAD)
    A.hair_cap(b, HEAD, hairline, top=0.024)
    for path, w, t in LOCKS:
        A.hair_lock(b, HEAD, path, w, t)
    tilt = A.Matrix.Identity(3)
    for deg, axis in HEAD_TILT:
        tilt = A.grot(deg, axis) @ tilt
    bmesh.ops.rotate(b.bm, verts=b.bm.verts, cent=gv(NECK), matrix=tilt)
    o = b.to_object("head", MATS_BY_NAME, pivot=gv(NECK), parent=ROOT, smooth_angle=SMOOTH)
    inv = tilt.inverted()

    def to_head(p):
        return A.to_game(inv @ (gv(p) - gv(NECK)) + gv(NECK)) - HEAD.centre
    A.front_uv(o, "face", HEAD.face_half, HEAD.face_y0, to_local=to_head)
    A.soften_face_normals(o, HEAD, to_head, lambda n: A.to_game(tilt @ gv(n)))
    return o


# --- arms, hands, cup ------------------------------------------------------------

def sleeve_arm(b, sh, elbow, wrist, roll_at=0.78):
    """Shirt sleeve from the shoulder cap to a rolled cuff on the forearm, bare wrist."""
    up = (elbow - sh).normalized()
    cuff = lerp(elbow, wrist, roll_at)
    pts = [sh - up * 0.02, sh + up * 0.01, lerp(sh, elbow, 0.5), elbow, lerp(elbow, cuff, 0.5), cuff]
    rad = [(0.036, 0.036), (0.048, 0.047), (0.048, 0.046), (0.045, 0.043), (0.043, 0.041), (0.045, 0.043)]
    A.limb(b, "shirt", pts, rad, sides=16, cap0=sh - up * 0.04, cap1="flat", ref=(0, 0, 1))
    fore = (wrist - elbow).normalized()
    A.limb(b, "shirt", [cuff - fore * 0.03, cuff, cuff + fore * 0.02],
           [(0.047, 0.045), (0.052, 0.05), (0.049, 0.047)], sides=16)
    A.limb(b, "skin", [cuff - fore * 0.02, lerp(cuff, wrist, 0.5), wrist],
           [(0.036, 0.034), (0.031, 0.028), (0.026, 0.022)], sides=12, ref=(0, 0, 1))


CUP_C = Vector((0.232, 1.405, 0.118))
CUP_H, CUP_R0, CUP_R1 = 0.15, 0.037, 0.047


def cup_r(y):
    return lerp(CUP_R0, CUP_R1, (y - (CUP_C.y - CUP_H / 2)) / CUP_H)


def around(a_deg, y, extra):
    a = math.radians(a_deg)
    r = cup_r(y) + extra
    return Vector((CUP_C.x + math.sin(a) * r, y, CUP_C.z + math.cos(a) * r))


def cup_hand(b, wrist):
    """Hand gripping the cup: palm on the body side, four fingers wrapped around the
    front, thumb round the back."""
    palm_a = -118
    palm = around(palm_a, CUP_C.y - 0.005, 0.016)
    A.limb(b, "skin", [wrist, lerp(wrist, palm, 0.6), palm],
           [(0.026, 0.02), (0.03, 0.019), (0.034, 0.018)], sides=12,
           ref=lambda i, q: q - Vector((CUP_C.x, q.y, CUP_C.z)), cap1="flat")
    A.blob(b, "skin", palm, (0.034, 0.042, 0.022), rot=A.grot(-palm_a + 90, (0, 1, 0)), u=12, v=8)
    for k, (dy, reach) in enumerate(((0.022, 30), (0.002, 38), (-0.018, 30), (-0.036, 14))):
        y = CUP_C.y + dy
        r = 0.0098 - 0.0008 * (k == 3)
        pts = [around(a, y + 0.004 * math.sin(math.radians(a)), r * 0.9)
               for a in (palm_a + 22, palm_a + 50, -40, -5, reach)]
        A.limb(b, "skin", pts, [(r, r)] * len(pts), sides=8, steps=2, cap1="flat")
    thumb = [around(a, CUP_C.y + 0.03 + 0.01 * i, 0.01) for i, a in enumerate((palm_a - 10, -160, -190, -212))]
    A.limb(b, "skin", thumb, [(0.012, 0.012)] * 4, sides=8, steps=2)


def build_arm_r():
    b = C.Builder(MATS)
    elbow = Vector((0.28, 1.165, -0.03))
    wrist = around(-140, CUP_C.y - 0.06, 0.03)
    sleeve_arm(b, SHOULDER_R, elbow, wrist, roll_at=0.62)
    cup_hand(b, wrist)
    o = b.to_object("arm_R", MATS_BY_NAME, pivot=gv(SHOULDER_R), parent=ROOT, smooth_angle=SMOOTH)
    A.fill_uv(o, "shirt", (0.01, 0.99))  # sleeves: plain shirt patch of the texture
    return o


def build_arm_l():
    b = C.Builder(MATS)
    elbow = Vector((-0.31, 1.16, -0.05))
    wrist = Vector((-0.145, 0.862, 0.096))
    sleeve_arm(b, SHOULDER_L, elbow, wrist, roll_at=0.62)
    # Hand shoved in the front pocket: a hand-shaped bulge in the khakis.
    A.blob(b, "pants", Vector((-0.13, 0.835, 0.08)), (0.034, 0.048, 0.026),
           rot=A.grot(-20, (0, 0, 1)) @ A.grot(-25, (0, 1, 0)), u=12, v=8)
    o = b.to_object("arm_L", MATS_BY_NAME, pivot=gv(SHOULDER_L), parent=ROOT, smooth_angle=SMOOTH)
    A.fill_uv(o, "shirt", (0.01, 0.99))
    return o


def build_cup(parent):
    """Iced cold brew in a clear cup: coffee body, icy band, flat lid, black straw."""
    b = C.Builder(MATS)
    c = CUP_C
    bot = c.y - CUP_H / 2
    y1 = bot + CUP_H * 0.78
    A.loft(b, "coffee", [A.ring((c.x, bot, c.z), CUP_R0, CUP_R0), A.ring((c.x, y1, c.z), cup_r(y1), cup_r(y1))], 20)
    top = bot + CUP_H
    A.loft(b, "cup", [A.ring((c.x, y1, c.z), cup_r(y1) + 0.0005, cup_r(y1) + 0.0005),
                      A.ring((c.x, top, c.z), CUP_R1, CUP_R1)], 20)
    A.loft(b, "cup", [A.ring((c.x, top, c.z), CUP_R1 + 0.004, CUP_R1 + 0.004),
                      A.ring((c.x, top + 0.012, c.z), CUP_R1 + 0.004, CUP_R1 + 0.004),
                      A.ring((c.x, top + 0.016, c.z), CUP_R1 - 0.006, CUP_R1 - 0.006)], 20)
    A.limb(b, "straw", [Vector((c.x, top - 0.02, c.z)), Vector((c.x - 0.012, top + 0.1, c.z - 0.01))],
           [(0.0045, 0.0045)] * 2, sides=8, steps=1)
    o = b.to_object("cup", MATS_BY_NAME, pivot=gv(c), parent=parent, smooth_angle=SMOOTH)
    A.set_flat(o, {"cup"})
    return o


# --- build, export, preview ----------------------------------------------------

C.reset_scene()
FACE_PNG = A.paint_face("techbro_face", FACE, HEAD)
VEST_PNG = paint_vest()
MATS_BY_NAME = A.make_materials(PALETTE, {"face": FACE_PNG, "vest": VEST_PNG, "shirt": paint_shirt()})
ROOT = C.empty("techbro")
arm_r = build_arm_r()
parts = [build_legs(), build_torso(), build_head(), build_arm_l(), arm_r, build_cup(arm_r)]
C.report(parts)
assert "quick" in ARGS or C.triangle_count(parts) <= TRI_BUDGET, "techbro over its triangle budget"
if "quick" not in ARGS:
    C.export_glb("techbro", texcoords=True)

pv = A.Preview(ROOT, outline=0.0055, shadow_muls={
    "skin": (0.87, 0.74, 0.76), "face": (0.87, 0.74, 0.76), "hair": (0.55, 0.55, 0.7)})
head_c = HEAD.centre + Vector((0.02, 0.03, 0))
if "wave" in ARGS:  # the game waves arm_R by rotating it about Z (game) by 2.6 rad
    arm_r.rotation_euler = (0, -2.6, 0)
    pv.sheet("techbro-wave", (("front", 0), ("3/4", -35)), Vector((0, 1.0, 0)), 2.2, 480, aspect=0.7)
    raise SystemExit
pv.sheet("techbro-head", (("front", 0), ("3/4", -35), ("side", -90), ("back", 180)), head_c, 0.42, 512)
if "quick" not in ARGS or "body" in ARGS:
    pv.sheet("techbro", (("front", 0), ("3/4", -35), ("side", -90), ("back", 180)),
             Vector((0, 0.9, 0)), 1.95, 720, aspect=0.6)
if "quick" not in ARGS:
    pv.aim(Vector((0, 0.9, 0)), 1.9)
    hero = pv.render(-20, 700, 1400)
    A.compare("techbro-compare", C.REPO / "docs/art/cast.jpg", (0, 88, 218, 742), hero, mirror_ref=True,
              labels=("cast.jpg, mirrored", "v3 render"))
    pv.sheet("techbro-small", (("front", 0), ("3/4", -35), ("side", -90), ("back", 180)),
             Vector((0, 0.95, 0)), 2.2, 200, aspect=0.6)
