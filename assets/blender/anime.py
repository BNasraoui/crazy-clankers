"""Shared character modelling, albedo painting and game-equivalent cel previews.

Model in game coordinates (Y up, +Z forward, metres), convert to Blender only at
mesh construction. Shared head surfaces live in head_shape.py, UV-preserving
head construction in anime_head.py, and character hair/paint in techbro_head.py.
The untouched common.py remains the cab pipeline's stable dependency.
"""
import math
import site
import tempfile
import sys
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
    """Toon preview rig: N.L cel materials, inverted-hull outlines and ortho camera.
    Call after exporting (it rewrites materials)."""

    def __init__(self, root, outline=0.006, shadow_muls=None, sun=(40, 0, 28)):
        scene = bpy.context.scene
        self.root = root
        self.objs = [o for o in scene.objects if o.type == "MESH"]
        light = (Matrix.Rotation(math.radians(sun[2]), 3, "Z") @ Matrix.Rotation(math.radians(sun[0]), 3, "X")
                 @ Vector((0, 0, 1)))
        for m in {s.material for o in self.objs for s in o.material_slots if s.material}:
            kw = {"shadow_mul": shadow_muls[m.name]} if shadow_muls and m.name in shadow_muls else {}
            toonify(m, light=light, threshold=0.32, **kw)
        self.hulls = make_hulls(self.objs)
        self.height = 2.0
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
        self.height = height
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
        # Each tile is a crop-equivalent of the full-resolution game framebuffer.
        # Keep 2.2 actual pixels, including the 160-pixel gameplay-size character.
        width = self.height * 2.2 / h
        for hull, positions, normals in self.hulls:
            for v, p, n in zip(hull.data.vertices, positions, normals):
                v.co = p + n * width
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
    return rgba[max(ys.min() - pad, 0):ys.max() + 1 + pad, max(xs.min() - pad, 0):xs.max() + 1 + pad]


def compare(name, ref_path, ref_box, render_rgba, height=900, mirror_ref=False,
            labels=("reference", "render")):
    """Side-by-side: reference crop (x0, y0, x1, y1) next to the cropped render, both
    scaled to `height` px."""
    ref = Image.open(ref_path).convert("RGB").crop(ref_box)
    if mirror_ref:
        ref = ref.transpose(Image.FLIP_LEFT_RIGHT)
    ref = ref.resize((round(ref.width * height / ref.height), height), Image.LANCZOS)
    rr = crop_alpha(render_rgba, pad=0)
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


def make_hulls(objects):
    """Position-merged smooth normals, reversed winding, no extra shell factor."""
    mat = C.outline_material()
    result = []
    for obj in objects:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.00001)
        bm.normal_update()
        bm.verts.ensure_lookup_table()
        positions = [v.co.copy() for v in bm.verts]
        normals = [v.normal.copy() for v in bm.verts]
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
        mesh = bpy.data.meshes.new(obj.name + "_ink")
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(mat)
        for p in mesh.polygons:
            p.material_index = 0
        hull = bpy.data.objects.new(obj.name + "_ink", mesh)
        bpy.context.scene.collection.objects.link(hull)
        hull.parent = obj
        result.append((hull, positions, normals))
    return result
