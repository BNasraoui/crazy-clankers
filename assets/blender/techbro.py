"""The Tech Bro: navy fleece vest, light blue shirt, khakis, white sneakers, iced
cold brew, messy dark hair, smug grin.

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

import common as C  # noqa: E402

PALETTE = {
    "skin": 0xF1C8A8,
    "hair": 0x2B1D16,
    "vest": 0x26324A,
    "shirt": 0x9CC3E6,
    "pants": 0xC4AE7E,
    "shoes": 0xF4F4F2,
    "sole": 0xC2C6CC,
    "cup": 0xDCECF0,
    "coffee": 0x4B2C1A,
    "straw": 0x1F1F1F,
    "line_dark": 0x1A1414,
    "teeth": 0xFFFFFF,
}
MATS = list(PALETTE)
SMOOTH = 40  # degrees; softer faces than the cab, hard edges stay crisp

SHOULDER = (0.245, 1.37)  # x, y of the shoulder pivots
HEAD_C = Vector((0, 1.6, 0.01))  # head centre (game coordinates)
HEAD_R = (0.12, 0.136, 0.128)


def g(x, y, z):
    """Game coordinates (Y up, +Z forward) to Blender (Z up, -Y forward)."""
    return Vector((x, -z, y))


def gv(v):
    return g(*v)


def gsize(w, h, d):
    return (w, d, h)


def front_frame(z):
    """Frame whose local XY is the game's front plane (x, y), local Z pointing +Z."""
    return Matrix.Translation(g(0, 0, z)) @ Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def build_legs():
    b = C.Builder(MATS)
    b.box("pants", gsize(0.36, 0.17, 0.23), g(0, 0.9, 0), bevel=0.04)
    for sx in (1, -1):
        b.tube("pants", g(sx * 0.1, 0.95, 0), g(sx * 0.14, 0.11, 0), 0.095, 0.072, sides=8)
        b.box("sole", gsize(0.13, 0.035, 0.31), g(sx * 0.145, 0.018, 0.045), bevel=0.012)
        b.box("shoes", gsize(0.125, 0.095, 0.29), g(sx * 0.145, 0.08, 0.04), bevel=0.03,
              taper=(0.9, 0.8))
    return b.to_object("legs", MATS_BY_NAME, pivot=g(0, 0.92, 0), parent=ROOT, smooth_angle=SMOOTH)


def build_torso():
    b = C.Builder(MATS)
    b.box("shirt", gsize(0.33, 0.52, 0.21), g(0, 1.16, 0), bevel=0.04, taper=(1.2, 1.0))
    b.box("vest", gsize(0.40, 0.48, 0.27), g(0, 1.19, 0), bevel=0.07, seg=2, taper=(1.18, 1.0))
    b.tube("vest", g(0, 1.38, -0.005), g(0, 1.5, -0.005), 0.105, 0.095, sides=8)
    # Open V at the collar showing the shirt, and the zip.
    b.prism("shirt", [(-0.075, 1.44), (0.075, 1.44), (0, 1.29)], 0.02, front_frame(0.134))
    b.box("line_dark", gsize(0.012, 0.31, 0.012), g(0, 1.13, 0.137))
    return b.to_object("torso", MATS_BY_NAME, pivot=g(0, 0.95, 0), parent=ROOT, smooth_angle=SMOOTH)


def spike(b, base, direction, length, radius, sides=4):
    base = Vector(base)
    tip = base + Vector(direction).normalized() * length
    b.tube("hair", gv(base), gv(tip), radius, 0.0, sides=sides)


def build_head():
    b = C.Builder(MATS)
    hc = HEAD_C
    rx, ry, rz = HEAD_R

    def at(dx, dy, dz):
        return gv(hc + Vector((dx, dy, dz)))

    b.tube("skin", g(0, 1.40, 0), g(0, 1.52, 0.005), 0.054, 0.052, sides=8)
    # Head: an ellipsoid with the lower half pulled into a jaw and chin.
    faces = b.sphere("skin", gv(hc), gsize(*HEAD_R), u=10, v=8)
    for v in {v for f in faces for v in f.verts}:
        dy = hc.y - v.co.z  # depth below the head centre
        if dy > 0:
            t = dy / ry
            v.co.x *= 1 - 0.38 * t
            v.co.y -= 0.02 * t  # chin slightly forward (game +z is Blender -y)
    for sx in (1, -1):
        b.box("skin", gsize(0.028, 0.055, 0.04), at(sx * 0.118, -0.01, -0.01), bevel=0.008)
    # Face: smug half-lidded eyes, one cocked brow, lopsided grin.
    fz = rz * 0.84
    for sx in (1, -1):
        b.box("line_dark", gsize(0.032, 0.03, 0.02), at(sx * 0.048, 0.008, fz), bevel=0.005)
    b.box("hair", gsize(0.05, 0.013, 0.02), at(0.05, 0.05, fz - 0.01),
          rot=Matrix.Rotation(math.radians(14), 4, "Y"))
    b.box("hair", gsize(0.05, 0.013, 0.02), at(-0.05, 0.042, fz - 0.01),
          rot=Matrix.Rotation(math.radians(-6), 4, "Y"))
    grin = [(-0.04, -0.044), (0.0, -0.043), (0.05, -0.03), (0.03, -0.056), (0.0, -0.064), (-0.028, -0.058)]
    b.prism("teeth", [(x, hc.y + y) for x, y in grin], 0.04, front_frame(hc.z + 0.115))
    # Messy dark hair: a full cap for volume plus chunky tufts swept forward and to the side.
    b.sphere("hair", at(0, 0.052, -0.012), gsize(rx * 1.12, ry * 0.72, rz * 1.12), u=10, v=6)
    b.sphere("hair", at(0, -0.005, -0.04), gsize(rx * 1.06, ry * 0.78, rz * 0.95), u=10, v=6)
    for sx in (1, -1):
        b.box("hair", gsize(0.03, 0.07, 0.05), at(sx * 0.112, 0.0, 0.0))
    tufts = [
        # (base offset from head centre, direction, length, radius)  all in game axes
        ((-0.06, 0.10, 0.08), (0.7, -0.3, 1.0), 0.09, 0.055),    # fringe sweeping to +X
        ((0.0, 0.11, 0.08), (0.8, -0.45, 0.8), 0.095, 0.055),
        ((0.06, 0.09, 0.08), (0.8, -0.8, 0.6), 0.075, 0.045),
        ((-0.08, 0.07, 0.07), (-0.2, -0.6, 1.0), 0.07, 0.04),
        ((-0.03, 0.13, 0.03), (0.3, 0.7, 0.6), 0.07, 0.055),     # crown, messy
        ((0.04, 0.13, -0.01), (0.7, 0.6, 0.0), 0.07, 0.055),
        ((-0.06, 0.12, -0.02), (-0.8, 0.6, 0.1), 0.065, 0.05),
        ((0.0, 0.12, -0.07), (0.1, 0.4, -1.0), 0.075, 0.055),
        ((0.10, 0.07, 0.0), (1.0, -0.2, 0.2), 0.055, 0.045),     # sides
        ((-0.10, 0.07, -0.02), (-1.0, -0.1, -0.3), 0.055, 0.045),
        ((0.06, 0.02, -0.11), (0.4, -0.5, -1.0), 0.06, 0.045),   # back
        ((-0.06, 0.02, -0.11), (-0.4, -0.5, -1.0), 0.06, 0.045),
    ]
    for off, d, ln, r in tufts:
        spike(b, hc + Vector(off), d, ln, r, sides=5)
    # A slight cocky tilt towards the cup hand.
    bmesh.ops.rotate(b.bm, verts=b.bm.verts, cent=g(0, 1.42, 0),
                     matrix=Matrix.Rotation(math.radians(-6), 3, "Y"))
    return b.to_object("head", MATS_BY_NAME, pivot=g(0, 1.42, 0), parent=ROOT, smooth_angle=SMOOTH)


def build_arm(name, sx, wrist):
    """Arm from the shoulder pivot. `wrist` is given for the +X side; mirrored by sx."""
    b = C.Builder(MATS)
    sh = Vector((sx * SHOULDER[0], SHOULDER[1], 0))
    a = math.radians(12)  # A-pose spread
    elbow = sh + Vector((sx * 0.3 * math.sin(a), -0.3 * math.cos(a), 0))
    wr = Vector((sx * wrist[0], wrist[1], wrist[2]))
    b.sphere("shirt", gv(sh), gsize(0.062, 0.062, 0.062), u=8, v=4)
    b.tube("shirt", gv(sh), gv(elbow), 0.056, 0.05, sides=8)
    # Rolled-up cuff, bare forearm, hand.
    fore = (wr - elbow).normalized()
    b.tube("shirt", gv(elbow - fore * 0.02), gv(elbow + fore * 0.05), 0.058, 0.056, sides=8)
    b.tube("skin", gv(elbow), gv(wr), 0.043, 0.036, sides=8)
    b.sphere("skin", gv(wr + fore * 0.05), gsize(0.045, 0.06, 0.052), u=8, v=4)
    return b.to_object(name, MATS_BY_NAME, pivot=gv(sh), parent=ROOT, smooth_angle=SMOOTH), wr + fore * 0.05


def build_cup(hand, parent):
    """Iced cold brew in a clear cup: coffee body, icy top, domed lid, black straw."""
    b = C.Builder(MATS)
    c = hand + Vector((-0.035, 0.07, 0.035))
    bot, h = c.y - 0.1, 0.2
    b.tube("coffee", g(c.x, bot, c.z), g(c.x, bot + 0.14, c.z), 0.046, 0.055, sides=10)
    b.tube("cup", g(c.x, bot + 0.14, c.z), g(c.x, bot + h, c.z), 0.055, 0.059, sides=10)
    b.tube("cup", g(c.x, bot + h, c.z), g(c.x, bot + h + 0.025, c.z), 0.062, 0.03, sides=10)
    b.tube("straw", g(c.x, bot + 0.12, c.z), g(c.x - 0.02, bot + h + 0.09, c.z - 0.01), 0.008, 0.008, sides=5)
    return b.to_object("cup", MATS_BY_NAME, pivot=gv(c), parent=parent, smooth_angle=SMOOTH)


C.reset_scene()
MATS_BY_NAME = C.make_materials(PALETTE)
ROOT = C.empty("techbro")
parts = [build_legs(), build_torso(), build_head()]
arm_l, _ = build_arm("arm_L", -1, (0.345, 0.84, 0.0))
# Right forearm bent up and forward, holding the cup at chest height.
arm_r, hand_r = build_arm("arm_R", 1, (0.27, 1.21, 0.215))
parts += [arm_l, arm_r, build_cup(hand_r, arm_r)]
C.report(parts)
assert C.triangle_count(parts) <= 4000, "techbro over its triangle budget"
C.export_glb("techbro")
C.render_contact_sheet(ROOT, "techbro", outline=0.008, fill=1.0)
