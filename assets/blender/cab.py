"""The player's robotaxi: a white SUV with a lidar puck and a teal stripe.

Nodes: cab (root) > body, lidar, wheel_FL, wheel_FR, wheel_RL, wheel_RR.
Front/rear and left/right are from the driver's seat: the cab faces +Z in the game,
so its left side (wheel_FL, wheel_RL) is at +X.
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
    "body_white": 0xF2F2EE,
    "glass": 0x1E2731,
    "trim_black": 0x1C1D20,
    "stripe_teal": 0x2FCDB8,
    "light_head": 0xFFF4D6,
    "light_tail": 0xE0303A,
    "hub": 0xA6AAAF,
}
MATS = list(PALETTE)

HALF_W = 1.05  # half body width
WHEEL_R = 0.42
WHEEL_X = 1.0
WHEEL_Z = 1.5
BELT_Y = 1.25  # beltline: glass above, paint below
ROOF_BAND_Y = 1.74
CLAD_Y = 0.55  # black lower cladding below this
TUMBLEHOME = 0.15  # how much the greenhouse narrows towards the roof

# Side profile of the body in game coordinates (z forward, y up), front first.
PROFILE = [
    (2.30, 0.36),
    (2.38, 0.66),
    (2.37, 1.06),
    (2.24, 1.19),
    (1.05, 1.26),
    (0.25, 1.84),
    (-1.75, 1.86),
    (-2.22, 1.66),
    (-2.36, 1.24),
    (-2.38, 0.64),
    (-2.28, 0.36),
]


def g(x, y, z):
    """Game coordinates (Y up, +Z forward) to Blender (Z up, -Y forward)."""
    return Vector((x, -z, y))


def gsize(w, h, d):
    return (w, d, h)


# Frame whose local XY is the game's side plane (z, y) and local Z is game +X.
SIDE = Matrix(((0, 0, 1, 0), (-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def side_frame(x):
    return Matrix.Translation((x, 0, 0)) @ SIDE


def build_shell():
    """One-piece body shell: extruded profile, tumblehome, material bands, wheel wells."""
    b = C.Builder(MATS)
    b.prism("body_white", PROFILE, 2 * HALF_W, side_frame(0))
    bm = b.bm
    for y in (CLAD_Y, BELT_Y, ROOF_BAND_Y):
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, y), plane_no=(0, 0, 1))
    for v in bm.verts:
        y = v.co.z
        if y > BELT_Y + 1e-4:
            v.co.x *= 1 - TUMBLEHOME * (y - BELT_Y) / (1.86 - BELT_Y)
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    idx = {n: i for i, n in enumerate(MATS)}
    for f in bm.faces:
        c = f.calc_center_median()
        n = f.normal
        if c.z < CLAD_Y:
            f.material_index = idx["trim_black"]
        elif BELT_Y < c.z < ROOF_BAND_Y and abs(n.x) > 0.5:
            f.material_index = idx["glass"]  # side windows
        elif c.z > 1.3 and 0.3 < n.z < 0.85:
            f.material_index = idx["glass"]  # windscreen and rear window
    # Chunky chamfer on the hard edges only.
    sharp = [e for e in bm.edges if e.calc_face_angle(0) > math.radians(25)]
    bmesh.ops.bevel(bm, geom=sharp, offset=0.05, offset_type="OFFSET", segments=1,
                    profile=0.5, affect="EDGES", clamp_overlap=True)
    shell = b.to_object("_shell", MATS_BY_NAME)

    # Wheel wells: cut a cylinder pocket into each side.
    cutters = []
    for sx in (1, -1):
        for z in (WHEEL_Z, -WHEEL_Z):
            cb = C.Builder(["trim_black"])
            cb.tube("trim_black", g(sx * 0.62, WHEEL_R, z), g(sx * 1.4, WHEEL_R, z), 0.48, 0.48, sides=16)
            cut = cb.to_object("_cut", MATS_BY_NAME)
            cut.hide_render = True
            cutters.append(cut)
            mod = shell.modifiers.new("well", "BOOLEAN")
            mod.operation = "DIFFERENCE"
            mod.solver = "EXACT"
            mod.material_mode = "TRANSFER"
            mod.object = cut
    C.apply_modifiers(shell)
    for cut in cutters:
        bpy.data.objects.remove(cut)
    return shell


def build_body():
    shell = build_shell()
    b = C.Builder(MATS)
    b.merge_mesh(shell.data, [m.name for m in shell.data.materials])
    bpy.data.objects.remove(shell)

    for sx in (1, -1):
        x = sx * HALF_W
        # Wheel-arch flares: black half rings proud of the side.
        for z in (WHEEL_Z, -WHEEL_Z):
            ring = []
            n = 9
            for i in range(n + 1):
                a = math.pi * i / n
                ring.append((z + 0.63 * math.cos(a), WHEEL_R + 0.63 * math.sin(a)))
            for i in range(n, -1, -1):
                a = math.pi * i / n
                ring.append((z + 0.48 * math.cos(a), WHEEL_R + 0.48 * math.sin(a)))
            b.prism("trim_black", ring, 0.12, side_frame(x + sx * 0.04))
        # Teal swoosh on the front door, leaning forward.
        stripe = [(0.30, 0.62), (0.62, 0.62), (1.02, 1.22), (0.70, 1.22)]
        b.prism("stripe_teal", stripe, 0.03, side_frame(x + sx * 0.005))
        # Fender sensors on top of the front and rear wings.
        for z in (1.62, -1.62):
            b.box("trim_black", gsize(0.14, 0.16, 0.26), g(x + sx * 0.02, 1.16, z), bevel=0.03)
        # Mirrors.
        b.box("body_white", gsize(0.22, 0.13, 0.1), g(sx * (HALF_W + 0.06), 1.33, 0.92), bevel=0.03)
        b.box("trim_black", gsize(0.1, 0.05, 0.08), g(sx * (HALF_W - 0.02), 1.29, 0.94))
        # Slim head lights high on the nose; tail lights under the rear window.
        b.box("light_head", gsize(0.56, 0.07, 0.1), g(sx * 0.62, 0.98, 2.355), bevel=0.015)
        b.box("light_tail", gsize(0.42, 0.09, 0.1), g(sx * 0.72, 1.15, -2.35), bevel=0.015)

    # Big dark grille, blank rear plate recess.
    b.box("trim_black", gsize(1.3, 0.26, 0.1), g(0, 0.74, 2.36), bevel=0.03, taper=(1.0, 1.0))
    b.box("trim_black", gsize(0.6, 0.16, 0.08), g(0, 0.8, -2.38), bevel=0.02)
    # Teal slash on the tailgate, right of the plate as seen from behind.
    rear = Matrix.Translation(g(0, 0, -2.385)) @ Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    b.prism("stripe_teal", [(-0.38, 0.66), (-0.62, 0.66), (-0.95, 1.04), (-0.71, 1.04)], 0.04, rear)
    # Lidar pedestal on the roof.
    b.box("body_white", gsize(0.9, 0.14, 0.95), g(0, 1.92, LIDAR_Z), bevel=0.03, taper=(0.82, 0.82))
    return b.to_object("body", MATS_BY_NAME, parent=ROOT)


LIDAR_Z = -0.35
LIDAR_Y = 2.22


def build_lidar():
    b = C.Builder(MATS)
    b.tube("trim_black", g(0, 1.98, LIDAR_Z), g(0, 2.44, LIDAR_Z), 0.31, 0.28, sides=12, bevel=0.02)
    b.tube("stripe_teal", g(0, 2.13, LIDAR_Z), g(0, 2.21, LIDAR_Z), 0.325, 0.325, sides=12)
    b.tube("trim_black", g(0, 2.44, LIDAR_Z), g(0, 2.5, LIDAR_Z), 0.22, 0.12, sides=12)
    return b.to_object("lidar", MATS_BY_NAME, pivot=g(0, LIDAR_Y, LIDAR_Z), parent=ROOT)


def build_wheel(name, x, z):
    b = C.Builder(MATS)
    sx = 1 if x > 0 else -1
    w = 0.3
    b.tube("trim_black", g(x - sx * w / 2, WHEEL_R, z), g(x + sx * w / 2, WHEEL_R, z),
           WHEEL_R, WHEEL_R, sides=12, bevel=0.05)
    b.tube("hub", g(x + sx * (w / 2 - 0.02), WHEEL_R, z), g(x + sx * (w / 2 + 0.015), WHEEL_R, z),
           0.25, 0.23, sides=8)
    b.tube("trim_black", g(x + sx * (w / 2 + 0.01), WHEEL_R, z), g(x + sx * (w / 2 + 0.03), WHEEL_R, z),
           0.08, 0.06, sides=8)
    return b.to_object(name, MATS_BY_NAME, pivot=g(x, WHEEL_R, z), parent=ROOT)


C.reset_scene()
MATS_BY_NAME = C.make_materials(PALETTE)
ROOT = C.empty("cab")
parts = [build_body(), build_lidar()]
for name, x, z in (("wheel_FL", WHEEL_X, WHEEL_Z), ("wheel_FR", -WHEEL_X, WHEEL_Z),
                   ("wheel_RL", WHEEL_X, -WHEEL_Z), ("wheel_RR", -WHEEL_X, -WHEEL_Z)):
    parts.append(build_wheel(name, x, z))
C.report(parts)
assert C.triangle_count(parts) <= 3000, "cab over its triangle budget"
C.export_glb("cab")
C.render_contact_sheet(ROOT, "cab", outline=0.03)
