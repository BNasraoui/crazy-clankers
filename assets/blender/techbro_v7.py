"""Turnaround-built Tech Bro: neutral geometry, measured fit, then baked pose.

Use Blender 5.2.2: --background --factory-startup --python techbro_v7.py.
`-- fit` exports A-pose and renders fit only; `-- preview` skips measurement.
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anime as A
import bpy
import common as C
import numpy as np
import sheets as S
import techbro as T
from head_shape import interpolate_sections
from mathutils import Vector
from PIL import Image, ImageDraw

CFG = S.load("techbro")
BS = CFG["body"]["metres_per_pixel"]
HS = CFG["head"]["metres_per_pixel"]
BY = CFG["body"]["world_y_at_zero"]
HY = CFG["head"]["world_y_at_zero"]
ARGS = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def by(y):
    return BY - y * BS


def hy(y):
    return HY - y * HS


def bpoint(x, y, z=816):
    return Vector(((x - 333) * BS, by(y), (z - 816) * BS))


def hpoint(x, y, z=1068):
    return Vector(((x - 210) * HS, hy(y), (1068 - z) * HS))


NECK = Vector((0, by(159), 0))
SHOULDERS = {s: bpoint(333 + s * 91, 207, 800) for s in [-1, 1]}
BODY = Image.open(C.REPO / "docs/art/turnarounds/techbro-body.png").convert("RGB")
HEAD = Image.open(C.REPO / "docs/art/turnarounds/techbro-head.png").convert("RGB")


def table(rows, y):
    return interpolate_sections(rows, y)


def mesh(name, b, pivot):
    return b.to_object(name, MATS, pivot=A.gv(pivot), parent=ROOT, smooth_angle=115)


def pixel_loft(b, role, rows, sides=20, power=2):
    """Rows: sheet y, front left/right x, profile rear/front x."""
    rings = []
    for y, l, r, rear, front in rows:
        rings.append(
            A.ring(
                bpoint((l + r) / 2, y, (rear + front) / 2),
                (r - l) * BS / 2,
                (front - rear) * BS / 2,
                p=power,
            )
        )
    A.loft(b, role, rings, sides, phase=0)


def build_legs():
    b = C.Builder(T.MATS)
    # Front governs the inter-leg gap and widths; side governs trouser depth.
    depth = [
        (433, 772, 877),
        (465, 769, 874),
        (500, 771, 866),
        (550, 775, 858),
        (590, 777, 851),
        (620, 771, 846),
        (650, 766, 836),
        (700, 763, 827),
        (750, 765, 826),
        (775, 771, 833),
        (791, 762, 831),
        (810, 768, 835),
    ]
    front = [
        (438, 249, 418, 333),
        (465, 247, 420, 333),
        (488, 246, 421, 333),
        (515, 246, 422, 327),
        (550, 247, 421, 318),
        (580, 248, 420, 312),
        (608, 247, 418, 307),
        (630, 249, 419, 306),
        (650, 243, 421, 301),
        (680, 241, 425, 299),
        (720, 241, 426, 294),
        (755, 242, 428, 289),
        (774, 238, 425, 290),
        (789, 237, 432, 294),
        (808, 246, 418, 287),
    ]
    for side in [-1, 1]:
        rows = []
        for y in np.linspace(438, 808, 53):
            l, r, inner = table(front, y)
            rear, fore = table(depth, y)
            lo, hi = (l, inner) if side < 0 else (666 - inner, r)
            rows.append((y, lo, hi, rear, fore))
        pixel_loft(b, "pants", rows, 20)
    # Pelvis closes above crotch, without bridging the leg gap below it.
    pixel_loft(
        b,
        "pants",
        [
            (434, 251, 417, 773, 875),
            (451, 248, 420, 770, 876),
            (480, 246, 421, 770, 870),
            (487, 247, 420, 771, 868),
        ],
        24,
    )
    for side in [-1, 1]:
        rows = []
        for y, lo, hi, rear, fore in [
            (800, 245, 285, 773, 833),
            (809, 237, 288, 765, 848),
            (820, 222, 288, 763, 889),
            (834, 210, 285, 761, 906),
            (837, 208, 286, 759, 908),
            (850, 205, 279, 761, 910),
            (855, 206, 262, 775, 894),
        ]:
            if side > 0:
                lo, hi = 666 - hi, 666 - lo
            rows.append((y, lo, hi, rear, fore))
        pixel_loft(b, "shoes", rows[:4], 20, power=2.4)
        # Distinct thick midsole, with a lip and a dark lower rubber strip.
        pixel_loft(b, "sole", rows[3:], 20, power=2.4)
        pixel_loft(b, "outsole", rows[-2:], 20, power=2.4)
        def surface(y, angle, offset=.001):
            lo, hi, rear, fore = table(rows, y)
            ca, sa = math.cos(angle), math.sin(angle)
            x = (lo+hi)/2 + (hi-lo)/2 * math.copysign(abs(ca)**(2/2.4),ca)
            z = (rear+fore)/2 + (fore-rear)/2 * math.copysign(abs(sa)**(2/2.4),sa)
            return bpoint(x,y,z) + Vector((ca*offset,0,sa*offset))

        def panel(role, heights, angles):
            grid = [[b.bm.verts.new(A.gv(surface(y,a))) for a in angles] for y in heights]
            for j in range(len(grid)-1):
                for i in range(len(angles)-1):
                    f=b.bm.faces.new((grid[j][i],grid[j][i+1],grid[j+1][i+1],grid[j+1][i]))
                    f.material_index=T.MATS.index(role)

        # Flush, unbranded grey quarters; the toe cap is a separate pale panel.
        for angle in [0, math.pi]:
            panel("shoe_panel", [815,819,824,830], np.linspace(angle-.55,angle+.55,7))
        panel("sole", [823,827,831,834], np.linspace(.90,2.24,9))
        collar=[surface(810,a,.002)+Vector((0,.004,0)) for a in np.linspace(math.pi,2*math.pi,13)]
        A.limb(b,"seam",collar,[(.003,.003)]*len(collar),sides=6,steps=1)
        # Each lace follows the actual vamp surface, including its depth taper.
        for y in [807,810,813,816,819]:
            lace=[surface(y,a,.0015) for a in np.linspace(1.25,1.89,5)]
            A.limb(b,"sole",lace,[(.0014,.0014)]*len(lace),sides=5,steps=1)
    ob = mesh("legs", b, Vector((0, by(470), 0)))
    for v in ob.data.vertices:
        v.co.x *= 0.978
    ob.data.update()
    A.front_uv(ob, "pants", 0.5, 0)
    A.front_uv(ob, "shoes", 0.5, 0, fallback=(0.01, 0.99), min_nz=0.1)
    return ob


def build_torso():
    T.ROOT = ROOT
    T.MATS_BY_NAME = MATS
    T.sway = lambda p: p.copy()
    ob = T.build_torso()
    origin = C.parent_world_origin(ob)
    # Fit original garment construction to the measured neutral garment sections.
    for v in ob.data.vertices:
        p = A.to_game(v.co + origin)
        y = float(
            np.interp(
                p.y,
                [0.85, 0.872, 0.955, 1.26, 1.4, 1.465, 1.55],
                [by(470), by(465), by(432), by(290), by(208), by(172), by(141)],
            )
        )
        p.x *= 1.19
        p.z = p.z * 1.19 + 0.012
        p.y = y
        if p.y < by(433):
            p.y = max(p.y, by(466 - 31 * (abs(p.x) / 0.205) ** 2))
        v.co = A.gv(p) - origin
    ob.data.update()
    bpy.context.view_layer.objects.active = ob
    dec = ob.modifiers.new("garment_budget", "DECIMATE")
    dec.ratio = 0.78
    bpy.ops.object.modifier_apply(modifier=dec.name)
    return ob


ARM_ROWS = [
    (195, 426, 443, 772, 818),
    (210, 427, 451, 768, 826),
    (235, 426, 463, 762, 831),
    (260, 427, 477, 762, 831),
    (282, 434, 490, 766, 826),
    (300, 447, 497, 767, 821),
    (313, 453, 510, 760, 824),
    (326, 459, 519, 760, 823),
    (337, 466, 526, 766, 822),
    (348, 474, 527, 766, 821),
    (358, 486, 521, 778, 817),
    (373, 502, 532, 782, 816),
    (392, 518, 545, 786, 816),
    (414, 535, 557, 789, 817),
    (435, 541, 566, 790, 820),
    (452, 541, 576, 786, 824),
    (470, 547, 577, 787, 823),
    (478, 551, 572, 791, 821),
]


def build_arm(side, posed=False):
    b = C.Builder(T.MATS)
    for role, lo, hi in [("shirt", 195, 358), ("skin", 354, 435 if posed else 478)]:
        rows = []
        for y in np.linspace(lo, hi, 32 if role == "shirt" else 22):
            l, r, rear, fore = table(ARM_ROWS, y)
            shift = 6 * A.smoothstep(210, 340, y)
            l -= shift
            r -= shift
            l -= 5 * math.exp(-(((y - 325) / 38) ** 2))
            if side < 0:
                l, r = 666 - r, 666 - l
            rows.append((y, l, r, rear, fore))
        pixel_loft(b, role, rows, 16)
    if posed:
        elbow = Vector((side * (0.30 if side > 0 else 0.265), 1.16, -0.025))
        wrist = (
            T.around(125, T.CUP_C.y - 0.06, 0.026)
            if side > 0
            else Vector((-0.166, 0.922, 0.118))
        )
        target = [
            (195, SHOULDERS[side] + Vector((0, 0.025, 0))),
            (207, SHOULDERS[side]),
            (305, elbow),
            (358, A.lerp(elbow, wrist, 0.43)),
            (435, wrist),
        ]

        def centre(y):
            return Vector(table([(t, *p) for t, p in target], y))

        for v in b.bm.verts:
            p = A.to_game(v.co)
            y = (BY - p.y) / BS
            l, r, rear, fore = table(ARM_ROWS, y)
            shift = 6 * A.smoothstep(210, 340, y)
            l -= shift
            r -= shift
            l -= 5 * math.exp(-(((y - 325) / 38) ** 2))
            neutral_c = bpoint(333 + side * ((l + r) / 2 - 333), y, (rear + fore) / 2)
            tangent = (centre(y + 1) - centre(y - 1)).normalized()
            depth = Vector((0, 0, 1))
            depth = (depth - tangent * depth.dot(tangent)).normalized()
            across = depth.cross(tangent).normalized()
            p = centre(y) + across * (p.x - neutral_c.x) + depth * (p.z - neutral_c.z)
            v.co = A.gv(p)
        if side > 0:
            T.cup_hand(b, wrist)
        else:
            A.limb(
                b,
                "skin",
                [wrist, (-0.149, 0.900, 0.105), (-0.134, 0.875, 0.066)],
                [(0.026, 0.018), (0.029, 0.017), (0.018, 0.012)],
                sides=12,
                steps=2,
            )
            A.limb(
                b,
                "skin",
                [
                    (-0.160, 0.911, 0.125),
                    (-0.170, 0.895, 0.130),
                    (-0.165, 0.887, 0.110),
                ],
                [(0.011, 0.009), (0.010, 0.008), (0.005, 0.005)],
                sides=8,
                steps=3,
            )
    else:
        # Relaxed separated fingers, with thumb on the inward side.
        for k, (x, end) in enumerate([(553, 497), (559, 505), (566, 504), (573, 495)]):
            pts = [
                bpoint(333 + side * (x - 333), 471, 815),
                bpoint(333 + side * (x + 2 - 333), 486, 819),
                bpoint(333 + side * (x - 1 - 333), end, 821),
            ]
            A.limb(
                b,
                "skin",
                pts,
                [(0.0055, 0.006), (0.005, 0.005), (0.0032, 0.0035)],
                sides=7,
                steps=2,
            )
        pts = [
            bpoint(333 + side * (545 - 333), 448, 819),
            bpoint(333 + side * (543 - 333), 463, 827),
            bpoint(333 + side * (545 - 333), 477, 824),
        ]
        A.limb(
            b,
            "skin",
            pts,
            [(0.009, 0.010), (0.008, 0.008), (0.004, 0.004)],
            sides=8,
            steps=2,
        )
    ob = mesh("arm_R" if side > 0 else "arm_L", b, SHOULDERS[side])
    A.fill_uv(ob, "shirt", (0.01, 0.99))
    return ob


# Anatomical surface traced from the head sheet; front widths are independent of
# the profile's forehead, nose bridge, nose tip, lips, chin, jaw and occiput.
FACE_ROWS = [
    (266, 115, 304, 971, 1150),
    (290, 112, 305, 964, 1158),
    (325, 111, 305, 945, 1164),
    (348, 110, 306, 935, 1166),
    (368, 109, 309, 932, 1166),
    (387, 109, 310, 917, 1165),
    (407, 111, 310, 894, 1162),
    (416, 111, 310, 899, 1160),
    (434, 113, 309, 915, 1158),
    (448, 118, 306, 909, 1154),
    (465, 125, 300, 919, 1147),
    (482, 138, 286, 919, 1134),
    (503, 160, 260, 918, 1118),
    (521, 182, 227, 921, 1090),
    (531, 197, 212, 938, 1055),
]


def face_surface(theta, y):
    l, r, fore, rear = table(FACE_ROWS, y)
    sx, c = math.sin(theta), math.cos(theta)
    x = (l + r) / 2 + (r - l) / 2 * sx
    # Chin/jaw sweep backwards at the sides; a real projecting centre profile.
    base = table(
        list(
            zip(
                [266, 325, 368, 407, 434, 448, 465, 482, 503, 521, 531],
                [971, 949, 941, 944, 934, 932, 926, 922, 921, 924, 938],
            )
        ),
        y,
    )[0]
    z = (
        1068 - (1068 - base) * max(c, 0) ** 0.72
        if c >= 0
        else 1068 + (rear - 1068) * (-c)
    )
    if c > 0:
        z -= (base - fore) * math.exp(-(((x - (l + r) / 2) / 19) ** 2))
    return hpoint(x, y, z)


def face_texture():
    """Extract approved pigment from front and 3/4, discard painted skin/shadows.

    Front supplies both eyes and brows. Three-quarter supplies the grin shape,
    resampled into the front mouth window. Atlas uses the mesh's cylindrical UV.
    """
    source = np.asarray(HEAD).astype(float)
    front = source.copy()
    smile = HEAD.crop((525, 420, 624, 457)).resize((92, 34), Image.Resampling.LANCZOS)
    front[423:462, 155:261] = A.rgb(T.PALETTE["face"])
    front[426:460, 162:254] = np.asarray(smile)
    region = Image.new("L", HEAD.size, 0)
    draw = ImageDraw.Draw(region)
    for poly in [
        [(120, 331), (171, 324), (180, 340), (153, 346), (122, 345)],
        [
            (202, 325),
            (240, 323),
            (265, 310),
            (285, 332),
            (284, 341),
            (249, 333),
            (222, 345),
            (206, 342),
        ],
        [(120, 350), (178, 348), (180, 375), (120, 387)],
        [(222, 345), (284, 344), (286, 370), (221, 376)],
        [(155, 423), (261, 423), (261, 462), (155, 462)],
        [(178, 387), (193, 387), (193, 416), (178, 416)],
        [(196, 399), (211, 399), (211, 409), (196, 409)],
    ]:
        draw.polygon(poly, fill=255)
    roi = np.asarray(region) / 255
    dark = np.clip((145 - front[:, :, 0]) / 55, 0, 1) * roi
    white = (
        np.clip((front.min(2) - 174) / 45, 0, 1)
        * np.clip((48 - (front.max(2) - front.min(2))) / 15, 0, 1)
        * roi
    )
    pigment = np.empty_like(front)
    pigment[:] = A.rgb(T.PALETTE["face"])
    pigment = (
        pigment * (1 - dark[:, :, None]) + np.array((45, 34, 27)) * dark[:, :, None]
    )
    pigment = (
        pigment * (1 - white[:, :, None])
        + np.array((255, 252, 241)) * white[:, :, None]
    )
    N = 2048
    theta = (np.arange(N) + 0.5) / N * 2 * math.pi - math.pi
    ys = 266 + (np.arange(N) + 0.5) / N * 265
    dims = np.array([table(FACE_ROWS, y) for y in ys])
    l, r = dims[:, 0], dims[:, 1]
    xx = (l[:, None] + r[:, None]) / 2 + (r[:, None] - l[:, None]) / 2 * np.sin(theta)[
        None, :
    ]
    yy = np.broadcast_to(ys[:, None], xx.shape)
    ix = np.clip(xx.astype(int), 0, 1670)
    iy = yy.astype(int)
    fx = (xx - ix)[:, :, None]
    fy = (yy - iy)[:, :, None]
    out = (pigment[iy, ix] * (1 - fx) + pigment[iy, ix + 1] * fx) * (1 - fy) + (
        pigment[iy + 1, ix] * (1 - fx) + pigment[iy + 1, ix + 1] * fx
    ) * fy
    out[:, np.cos(theta) < 0.1] = A.rgb(T.PALETTE["face"])
    path = A.TEX_DIR / "techbro_sheet_face.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(path)
    return path


def hair_texture():
    """Sparse curved pigment strokes, parameterized along each physical curl."""
    pt = A.Painter(1024, A.rgb(T.PALETTE["hair"]), 0.5, 0, ss=2)
    for x in [0.22]:
        pt.stroke(
            [
                (x, 0.98),
                (x - 0.05, 0.79),
                (x + 0.03, 0.49),
                (x + 0.10, 0.22),
                (x + 0.12, 0.03),
            ],
            [0, 0.0015, 0.002, 0.0015, 0],
            (49, 35, 27),
        )
    return pt.save("techbro_hair_flow_v7")


def build_head():
    b = C.Builder(T.MATS)
    hair_uv = {}

    def curl(rings, sides):
        faces = A.loft(b, "hair", rings, sides, phase=0)
        for j, (c, u, w, rx, rz, power) in enumerate(rings):
            for k in range(sides):
                angle = 2 * math.pi * k / sides
                q = c + u * (rx * math.cos(angle)) + w * (rz * math.sin(angle))
                hair_uv[tuple(round(float(v), 5) for v in q)] = (
                    k / sides,
                    1 - j / (len(rings) - 1),
                )
        return faces

    # face has explicit UVs after Builder canonicalizes topology.
    ys = sorted(set(np.linspace(266, 531, 36).tolist() + [r[0] for r in FACE_ROWS]))
    n = 40
    # Surface grid via loft rings cannot express a shaped profile, so use vertices.
    grid = [
        [
            b.bm.verts.new(A.gv(face_surface(-math.pi + 2 * math.pi * i / n, y)))
            for i in range(n)
        ]
        for y in ys
    ]
    for j in range(len(grid) - 1):
        for i in range(n):
            f = b.bm.faces.new(
                (
                    grid[j][i],
                    grid[j][(i + 1) % n],
                    grid[j + 1][(i + 1) % n],
                    grid[j + 1][i],
                )
            )
            f.material_index = T.MATS.index("face")
    for row in [grid[0], grid[-1]]:
        f = b.bm.faces.new(row)
        f.material_index = T.MATS.index("skin")
    A.limb(
        b,
        "skin",
        [NECK + Vector((0, -0.045, 0)), hpoint(215, 522, 1080), hpoint(215, 463, 1080)],
        [(0.052, 0.049), (0.052, 0.049), (0.055, 0.050)],
        sides=20,
        steps=2,
    )
    for side in [-1, 1]:
        ec = hpoint(210 + side * 111, 415, 1045)
        A.blob(b, "skin", ec, (0.0112, 0.0203, 0.0133), u=12, v=8)
        A.limb(
            b,
            "ear_ink",
            [
                ec + Vector((side * x, y, z)) * 0.7
                for x, y, z in [
                    (-0.005, -0.015, 0.016),
                    (0.006, -0.005, 0.018),
                    (0.008, 0.012, 0.016),
                    (0.001, 0.019, 0.009),
                    (-0.006, 0.004, 0.016),
                ]
            ],
            [(0.00105, 0.00105)] * 5,
            sides=5,
            steps=2,
        )
    # Hair shell from measured front and profile outer envelopes. The hairline is
    # a separate lower boundary, revealing forehead, temples and ears.
    hairrows = []
    N = 40
    R = 26
    scalp = [
        (170, 190, 216, 1038, 1072),
        (199, 141, 263, 1000, 1110),
        (203, 165, 238, 985, 1120),
        (215, 122, 270, 950, 1160),
        (230, 97, 304, 910, 1188),
        (260, 76, 328, 892, 1202),
        (290, 62, 345, 880, 1212),
        (325, 61, 349, 887, 1219),
        (360, 69, 345, 910, 1218),
        (395, 83, 335, 959, 1200),
        (430, 103, 316, 1030, 1181),
        (470, 116, 303, 1090, 1168),
        (515, 143, 281, 1110, 1144),
    ]
    for j in range(R + 1):
        row = []
        for i in range(N):
            a = -math.pi + 2 * math.pi * i / N
            c = math.cos(a)
            # Center part, hanging forehead curl, ear notch, longer wavy nape.
            low = 277 if c > 0.70 else 379 if c > 0 else 506
            low += (
                9 * math.sin(3 * a)
                + 5 * math.sin(9 * a)
                + 42 * math.exp(-(((a + 0.48) / 0.22) ** 2))
            )
            y = low + (170 - low) * (j / R)
            l, r, fore, rear = table(scalp, y)
            x = (l + r) / 2 + (r - l) / 2 * math.sin(a) * 0.965
            z = (fore + rear) / 2 - (rear - fore) / 2 * c * 1.025
            if c < 0:
                z += 6 * (-c) * math.exp(-(((y - 390) / 65) ** 2))
            row.append(b.bm.verts.new(A.gv(hpoint(x, y, z))))
        hairrows.append(row)
    for j in range(R):
        for i in range(N):
            f = b.bm.faces.new(
                (
                    hairrows[j][i],
                    hairrows[j][(i + 1) % N],
                    hairrows[j + 1][(i + 1) % N],
                    hairrows[j + 1][i],
                )
            )
            f.material_index = T.MATS.index("hair")
    f = b.bm.faces.new(hairrows[-1])
    f.material_index = T.MATS.index("hair")
    # Fine, returning S curls ride the shell; broad roots, thin curved tips.
    # Coordinates traced from visible flow in front/back, then lifted in depth.
    paths = [
        (
            [
                (167, 258, 950),
                (159, 287, 905),
                (150, 322, 879),
                (150, 351, 887),
                (162, 377, 916),
            ],
            0.016,
        ),
        (
            [
                (128, 276, 946),
                (114, 302, 903),
                (108, 321, 919),
                (107, 334, 930),
                (112, 339, 948),
            ],
            0.013,
        ),
        (
            [
                (159, 252, 946),
                (187, 222, 950),
                (236, 217, 971),
                (257, 239, 972),
                (250, 263, 957),
            ],
            0.020,
        ),
        (
            [
                (102, 277, 972),
                (137, 264, 944),
                (178, 239, 938),
                (210, 228, 948),
                (224, 251, 942),
            ],
            0.023,
        ),
        (
            [
                (84, 307, 988),
                (122, 293, 948),
                (159, 261, 931),
                (182, 257, 932),
                (175, 284, 921),
                (167, 319, 929),
                (178, 346, 945),
            ],
            0.017,
        ),
        (
            [
                (217, 264, 930),
                (246, 252, 938),
                (277, 269, 954),
                (288, 292, 970),
                (278, 312, 977),
            ],
            0.017,
        ),
        (
            [
                (261, 249, 985),
                (300, 264, 977),
                (324, 286, 985),
                (346, 291, 1002),
                (358, 280, 1010),
            ],
            0.018,
        ),
        (
            [
                (281, 294, 1015),
                (316, 314, 996),
                (337, 332, 1005),
                (357, 330, 1025),
                (367, 316, 1035),
            ],
            0.018,
        ),
        (
            [
                (104, 285, 1030),
                (82, 312, 1005),
                (77, 341, 1010),
                (60, 351, 1037),
                (46, 341, 1045),
            ],
            0.016,
        ),
        # Loose crown strands follow the cap, with tips returning to its surface.
        ([(117,232,1017),(149,206,998),(187,194,1005),(225,205,1014),(244,225,1010)], .013),
        ([(222,218,1080),(246,210,1090),(272,226,1108),(283,250,1117)], .011),
    ]
    for lock_index, (pts, width) in enumerate(paths):
        lift = 4 if lock_index < 2 else 12
        points = A.catmull([hpoint(p[0], p[1] + (12 if p[1] < 245 else 0), p[2] - lift) for p in pts], 4)
        radii = [
            (
                width * (0.22 + 0.78 * math.sin(math.pi * t)) * (1 - t) ** 0.55 + 0.0003,
                0.005 * (1 - t) + 0.0004,
            )
            for t in np.linspace(0, 1, len(points))
        ]
        curl(A.path_rings(points, radii, (0, 0, 1)), 7)
    # Layered side/back curls, alternating wave directions and lifted ends.
    for k in range(16):
        a = 2 * math.pi * k / 16
        if math.cos(a) > 0.5:
            continue
        for level in [0, 1, 2]:
            if level == 2 and math.cos(a) > -0.35:
                continue
            pts = []
            for j in range(5):
                t = j / 4
                ang = a + 0.13 * math.sin(t * math.pi * 1.5)
                y = 225 + level * 79 + t * (111 + 9 * max(0, -math.cos(a)))
                l, r, fore, rear = table(scalp, y)
                x = (l + r) / 2 + (r - l) / 2 * math.sin(ang) * 0.975
                z = (fore + rear) / 2 - (rear - fore) / 2 * math.cos(ang) * 0.975
                pts.append(hpoint(x, y, z))
            pp = A.catmull(pts, 2)
            tt = np.linspace(0, 1, len(pp))
            curl(
                A.path_rings(
                    pp,
                    [
                        (0.023 * (0.4 + 0.6*math.sin(math.pi*t)) * (1 - t) ** 0.6 + 0.0003, 0.010 * math.sin(math.pi * t) + 0.0005)
                        for t in tt
                    ],
                    lambda i, p: p - hpoint(210, 365, 1068),
                ),
                7,
            )
    ob = mesh("head", b, NECK)
    uv = ob.data.uv_layers.new(name="UVMap")
    for p in ob.data.polygons:
        role = T.MATS[p.material_index]
        for li in p.loop_indices:
            q = A.to_game(
                ob.data.vertices[ob.data.loops[li].vertex_index].co + A.gv(NECK)
            )
            y = (HY - q.y) / HS
            if role == "face":
                l, r, fore, rear = table(FACE_ROWS, y)
                sx = np.clip((q.x / HS + 210 - (l + r) / 2) / ((r - l) / 2), -1, 1)
                a = math.asin(sx)
                if q.z < 0:
                    a = math.copysign(math.pi - abs(a), a)
                uv.data[li].uv = (a / (2 * math.pi) + 0.5, 1 - (y - 266) / 265)
            elif role == "hair":
                uv.data[li].uv = hair_uv.get(
                    tuple(round(float(v), 5) for v in q), (0.01, 0.01)
                )
            else:
                uv.data[li].uv = (0.5, 0.5)
    for p in ob.data.polygons:
        us = [uv.data[li].uv.x for li in p.loop_indices]
        if max(us) - min(us) > 0.5:
            for li in p.loop_indices:
                if uv.data[li].uv.x < 0.5:
                    uv.data[li].uv.x += 1
    ob.data.update()
    faceverts = {
        i
        for p in ob.data.polygons
        if T.MATS[p.material_index] == "face"
        for i in p.vertices
    }
    normals = []
    for v in ob.data.vertices:
        q = A.to_game(v.co + A.gv(NECK))
        n = v.normal.copy()
        if v.index in faceverts:
            # Radial transfer from an ellipsoid centered inside the head. Its
            # gradient is smooth and independent of nose/jaw triangulation.
            d = q - Vector((0, hy(375), -0.012))
            proxy = Vector((d.x / .140**2, d.y / .240**2, d.z / .105**2))
            n = A.gv(proxy.normalized())
        normals.append(n)
    ob.data.normals_split_custom_set_from_vertices(normals)
    return ob


def export(name, objects):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in [ROOT] + objects:
        ob.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(C.MODELS_DIR / f"{name}.glb"),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
        export_cameras=False,
        export_lights=False,
        export_animations=False,
        export_skins=False,
        export_morph=False,
    )


def fit(parts):
    scores = {}
    for kind in ["body", "head"]:
        scores[kind] = {}
        for view in ["front", "right", "back"]:
            target = (
                parts
                if kind == "body"
                else [next(o for o in parts if o.name == "head")]
            )
            mask = S.render_mask(
                "techbro",
                kind,
                view,
                target,
                Path("/tmp") / f"techbro-fit-{kind}-{view}.png",
            )
            scores[kind][view] = S.overlay(
                "techbro",
                kind,
                view,
                mask,
                C.RENDERS_DIR / f"techbro-fit-{kind}-{view}.png",
            )
    print("FIT", json.dumps(scores))
    (Path(__file__).parent / "reviews/v7-fit.json").write_text(
        json.dumps(scores, indent=2) + "\n"
    )
    assert min(scores["body"].values()) >= 0.90, scores
    assert min(scores["head"].values()) >= 0.88, scores


def pose(parts):
    # Deform neutral garment/leg meshes once, then bake around neutral pivots.
    for ob in parts:
        if ob.name == "head":
            ob.data.transform((A.grot(-8, (1, 0, 0)) @ A.grot(3, (0, 0, 1))).to_4x4())
            ob.data.update()
            continue
        origin = C.parent_world_origin(ob)
        for v in ob.data.vertices:
            p = A.to_game(v.co + origin)
            if ob.name == "legs":
                t = max(0, min(1, p.y / 0.95))
                p.x += 0.035 * t
                if p.x < 0.01:
                    p.x -= 0.055 * (1 - t)
                    p.z += 0.025 * (1 - t)
            elif ob.name == "torso":
                t = A.smoothstep(0.9, 1.43, p.y)
                p.x += 0.035 * (1 - t)
                p.y -= p.x * 0.055
            v.co = A.gv(p) - origin
        ob.data.update()
    # Bend the same neutral sleeve sections along a shoulder/elbow/wrist path.
    # The open neutral hands become a cup grip and a pocket hand.
    for side in [-1, 1]:
        old = next(o for o in parts if o.name == ("arm_R" if side > 0 else "arm_L"))
        old_mesh = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        bpy.data.meshes.remove(old_mesh)
        parts.remove(old)
    T.SHOULDER_R = SHOULDERS[1]
    T.SHOULDER_L = SHOULDERS[-1]
    T.CUP_C = Vector((0.292, 1.39, 0.155))
    right = build_arm(1, posed=True)
    left = build_arm(-1, posed=True)
    parts.extend([left, right, T.build_cup(right)])
    return parts


def main():
    global ROOT, MATS
    C.reset_scene()
    T.sway = lambda p: p.copy()
    T.CUP_C = Vector((0.232, 1.405, 0.118))
    T.PALETTE["hair"] = 0x604735
    T.PALETTE["face"] = T.PALETTE["skin"] = 0xF3BD91
    MATS = A.make_materials(
        T.PALETTE,
        {
            "face": face_texture(),
            "hair": hair_texture(),
            "vest": T.paint_vest(),
            "shirt": T.paint_shirt(),
            "pants": T.paint_pants(),
        },
    )
    ROOT = C.empty("techbro")
    T.ROOT = ROOT
    T.MATS_BY_NAME = MATS
    parts = [build_legs(), build_torso(), build_head(), build_arm(-1), build_arm(1)]
    C.report(parts)
    assert C.triangle_count(parts) <= 30000
    neutral_cup = T.build_cup(next(o for o in parts if o.name == "arm_R"))
    neutral_cup.location += A.gv(Vector((0.72, 0.19, 0)) - T.CUP_C)
    assert C.triangle_count(parts + [neutral_cup]) <= 30000
    export("techbro-apose", parts + [neutral_cup])
    neutral_mesh = neutral_cup.data
    bpy.data.objects.remove(neutral_cup, do_unlink=True)
    bpy.data.meshes.remove(neutral_mesh)
    if "preview" not in ARGS:
        fit(parts)
    if "fit" in ARGS:
        return
    parts = pose(parts)
    C.report(parts)
    assert C.triangle_count(parts) <= 30000
    export("techbro", parts)
    pv = A.Preview(
        ROOT,
        shadow_muls={
            "skin": (0.70, 0.49, 0.40),
            "face": (0.70, 0.49, 0.40),
            "hair": (0.55, 0.55, 0.70),
        },
    )
    pv.sheet(
        "techbro-head",
        [("front", 0), ("3/4", -35), ("side", -90)],
        Vector((0, 1.664, 0.02)),
        0.39,
        600,
    )
    pv.sheet(
        "techbro",
        [("front", 0), ("3/4", -35), ("side", -90), ("back", 180)],
        Vector((0, 0.9, 0)),
        1.97,
        720,
        aspect=0.6,
    )
    pv.aim(Vector((0, 0.9, 0)), 1.95)
    hero = pv.render(15, 700, 1400)
    A.compare(
        "techbro-compare",
        C.REPO / "docs/art/cast.jpg",
        (0, 95, 218, 734),
        hero,
        mirror_ref=True,
        labels=("cast.jpg (mirrored for +X cup)", "v7: polished turnaround"),
    )
    pv.sheet(
        "techbro-shoes",
        [("front", 0), ("3/4", -35), ("side", -90)],
        Vector((0, 0.075, 0.06)),
        0.65,
        600,
    )
    pv.sheet(
        "techbro-small",
        [("front", 0), ("3/4", -35), ("side", -90), ("back", 180)],
        Vector((0, 0.9, 0)),
        2,
        180,
        aspect=0.6,
    )


if __name__ == "__main__":
    main()
