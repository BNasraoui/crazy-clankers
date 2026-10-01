"""Shared helpers for the Crazy Clankers Blender scripts.

Run the model scripts headless, e.g.:
    blender --background --factory-startup --python assets/blender/cab.py

Coordinates: the scripts model in Blender space (Z up, models face -Y). The glTF
exporter converts to the game's convention (Y up, models face +Z), so Blender +X
stays +X in the game.
"""
import math
import os
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

REPO = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO / "public" / "models"
RENDERS_DIR = REPO / "docs" / "renders"


# --- scene and materials -----------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_linear(h):
    return tuple(srgb_to_linear(((h >> s) & 0xFF) / 255) for s in (16, 8, 0))


def make_materials(palette):
    """palette: {role_name: 0xRRGGBB}. Plain flat base colours, metallic 0, roughness 1."""
    mats = {}
    for name, hexcol in palette.items():
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        bsdf = m.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (*hex_linear(hexcol), 1.0)
        bsdf.inputs["Metallic"].default_value = 0.0
        bsdf.inputs["Roughness"].default_value = 1.0
        m.diffuse_color = (*hex_linear(hexcol), 1.0)
        m.use_backface_culling = True  # closed meshes: export single-sided
        mats[name] = m
    return mats


# --- mesh building -----------------------------------------------------------

def look_rot(direction):
    """Rotation matrix taking local +Z onto `direction`."""
    return Vector(direction).normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()


class Builder:
    """Accumulates primitives into one bmesh; each primitive gets a material role.

    All coordinates are absolute (model space). `to_object` moves the pivot to the
    object origin, so nodes keep their pivots without any object rotation or scale.
    """

    def __init__(self, materials):
        self.materials = list(materials)
        self.bm = bmesh.new()

    def _assign(self, before, mat):
        idx = self.materials.index(mat)
        new = [f for f in self.bm.faces if f not in before]
        for f in new:
            f.material_index = idx
        return new

    def _begin(self):
        return set(self.bm.faces)

    def _bevel(self, faces, width, segments):
        if width <= 0:
            return
        self.bm.edges.index_update()
        edges = sorted({e for f in faces for e in f.edges}, key=lambda e: e.index)
        bmesh.ops.bevel(self.bm, geom=edges, offset=width, offset_type="OFFSET",
                        segments=segments, profile=0.5, affect="EDGES", clamp_overlap=True)

    def box(self, mat, size, center, rot=None, bevel=0.0, seg=1, taper=None):
        """Axis-aligned box (optionally rotated). taper=(sx, sy) scales the +Z face."""
        before = self._begin()
        m = Matrix.Translation(center) @ (rot or Matrix()) @ Matrix.Diagonal((*size, 1))
        res = bmesh.ops.create_cube(self.bm, size=1.0, matrix=m)
        if taper:
            local = [(m.inverted() @ v.co) for v in res["verts"]]
            for v, lc in zip(res["verts"], local):
                if lc.z > 0:
                    v.co = m @ Vector((lc.x * taper[0], lc.y * taper[1], lc.z))
        faces = [f for f in self.bm.faces if f not in before]
        self._bevel(faces, bevel, seg)
        return self._assign(before, mat)

    def tube(self, mat, p0, p1, r0, r1, sides=8, bevel=0.0, squash=(1.0, 1.0), spin=0.0):
        """Tapered cylinder from p0 to p1; r1=0 makes a cone. squash scales the cross-section."""
        before = self._begin()
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        m = (Matrix.Translation((p0 + p1) / 2) @ look_rot(d) @ Matrix.Rotation(spin, 4, "Z")
             @ Matrix.Diagonal((squash[0], squash[1], 1, 1)))
        bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=sides,
                              radius1=r0, radius2=max(r1, 0.0), depth=d.length, matrix=m)
        faces = [f for f in self.bm.faces if f not in before]
        self._bevel(faces, bevel, 1)
        return self._assign(before, mat)

    def sphere(self, mat, center, radii, u=10, v=6, rot=None):
        before = self._begin()
        m = Matrix.Translation(center) @ (rot or Matrix()) @ Matrix.Diagonal((*radii, 1))
        bmesh.ops.create_uvsphere(self.bm, u_segments=u, v_segments=v, radius=1.0, matrix=m)
        return self._assign(before, mat)

    def prism(self, mat, pts, depth, frame, bevel=0.0, seg=1):
        """Extrude a 2D polygon `pts` (in the frame's local XY) by `depth` along local Z,
        centred on Z=0. `frame` is a 4x4 matrix placing it in model space."""
        before = self._begin()
        bot = [self.bm.verts.new(frame @ Vector((x, y, -depth / 2))) for x, y in pts]
        top = [self.bm.verts.new(frame @ Vector((x, y, depth / 2))) for x, y in pts]
        n = len(pts)
        self.bm.faces.new(list(reversed(bot)))
        self.bm.faces.new(top)
        for i in range(n):
            j = (i + 1) % n
            self.bm.faces.new((bot[i], bot[j], top[j], top[i]))
        faces = [f for f in self.bm.faces if f not in before]
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)
        self._bevel(faces, bevel, seg)
        return self._assign(before, mat)

    def merge_mesh(self, mesh, mat_names):
        """Append an existing mesh, remapping its material slots by name."""
        before = self._begin()
        tmp = bmesh.new()
        tmp.from_mesh(mesh)
        remap = {i: self.materials.index(n) for i, n in enumerate(mat_names)}
        for f in tmp.faces:
            f.material_index = remap[f.material_index]
        tmp_mesh = bpy.data.meshes.new("_tmp")
        tmp.to_mesh(tmp_mesh)
        tmp.free()
        self.bm.from_mesh(tmp_mesh)
        bpy.data.meshes.remove(tmp_mesh)
        return [f for f in self.bm.faces if f not in before]

    def to_object(self, name, mats, pivot=(0, 0, 0), parent=None, smooth_angle=None):
        pivot = Vector(pivot)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        bmesh.ops.translate(self.bm, vec=-pivot, verts=self.bm.verts)
        canonical_order(self.bm)
        verts = [tuple(v.co) for v in self.bm.verts]
        faces, mat_idx = [], []
        for f in self.bm.faces:
            ids = [v.index for v in f.verts]
            k = ids.index(min(ids))  # canonical loop start, winding unchanged
            faces.append(ids[k:] + ids[:k])
            mat_idx.append(f.material_index)
        self.bm.free()
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        me.polygons.foreach_set("material_index", mat_idx)
        for n in self.materials:
            me.materials.append(mats[n])
        if smooth_angle is None:
            me.shade_flat()
        else:
            me.shade_smooth()
            me.set_sharp_from_angle(angle=math.radians(smooth_angle))
        obj = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(obj)
        if parent is not None:
            obj.parent = parent
            obj.location = pivot - parent_world_origin(parent)
        else:
            obj.location = pivot
        return obj


def canonical_order(bm):
    """Sort elements by geometry so rebuilds are byte-identical; some bmesh ops
    otherwise emit faces in an order that varies from run to run."""
    def rank_sort(seq, key):
        seq.index_update()
        order = sorted(seq, key=key)
        rank = {e.index: i for i, e in enumerate(order)}
        seq.sort(key=lambda e: rank[e.index])
        seq.index_update()

    def co(c):
        return tuple(round(x, 5) for x in c)

    rank_sort(bm.verts, lambda v: co(v.co))
    rank_sort(bm.edges, lambda e: sorted(v.index for v in e.verts))
    rank_sort(bm.faces, lambda f: (f.material_index, co(f.calc_center_median()),
                                   sorted(v.index for v in f.verts)))


def parent_world_origin(obj):
    loc = Vector((0, 0, 0))
    while obj is not None:
        loc += obj.location
        obj = obj.parent
    return loc


def empty(name, location=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.3
    bpy.context.scene.collection.objects.link(e)
    e.parent = parent
    e.location = location
    return e


def apply_modifiers(obj):
    """Bake an object's modifier stack into its mesh without bpy.ops."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    obj.modifiers.clear()
    old = obj.data
    obj.data = me
    bpy.data.meshes.remove(old)


def triangle_count(objs):
    return sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs if o.type == "MESH")


# --- export ------------------------------------------------------------------

def export_glb(name, texcoords=False):
    """texcoords=True exports UVs (and so embeds image textures) for textured models."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    path = MODELS_DIR / f"{name}.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(path), export_format="GLB", export_yup=True, export_apply=True,
        export_cameras=False, export_lights=False, export_texcoords=texcoords,
        export_normals=True, export_tangents=False, export_materials="EXPORT",
        export_animations=False, export_skins=False, export_morph=False,
        export_extras=False, use_selection=False,
    )
    print(f"exported {path}")
    return path


# --- toon preview render -----------------------------------------------------

BG = (0.965, 0.953, 0.925)  # cream page, sRGB


def toonify(mat, shadow_mul=(0.62, 0.64, 0.78), threshold=0.4):
    """Swap a flat material for a two-tone cel shader (render previews only)."""
    base = mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value[:3]
    shadow = tuple(c * m for c, m in zip(base, shadow_mul))
    nt = mat.node_tree
    nt.nodes.clear()
    diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    ramp.color_ramp.elements[1].position = threshold
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*shadow, 1)
    mix.inputs["B"].default_value = (*base, 1)
    emit = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(diff.outputs[0], s2r.inputs[0])
    nt.links.new(s2r.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], emit.inputs["Color"])
    nt.links.new(emit.outputs[0], out.inputs["Surface"])


def outline_material():
    m = bpy.data.materials.new("_outline")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (0.01, 0.01, 0.012, 1)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(emit.outputs[0], out.inputs["Surface"])
    m.use_backface_culling = True
    return m


def add_outlines(objs, width, skip_mats=()):
    """Inverted-hull outlines: a culled, inside-out copy of each mesh pushed out along
    its normals. The hull is its own object so it can skip casting shadows. Faces using
    a material named in `skip_mats` (e.g. painted-on face details) get no hull."""
    om = outline_material()
    for o in objs:
        if o.type != "MESH":
            continue
        bm = bmesh.new()
        bm.from_mesh(o.data)
        skip = {i for i, s in enumerate(o.material_slots) if s.material and s.material.name in skip_mats}
        if skip:
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in skip], context="FACES")
        bm.normal_update()
        for v in bm.verts:
            v.co += v.normal * width * min(v.calc_shell_factor(), 2.0)
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        me = bpy.data.meshes.new(o.name + "_outline")
        bm.to_mesh(me)
        bm.free()
        me.materials.clear()
        me.materials.append(om)
        for p in me.polygons:
            p.material_index = 0
        hull = bpy.data.objects.new(o.name + "_outline", me)
        bpy.context.scene.collection.objects.link(hull)
        hull.parent = o
        hull.visible_shadow = False


def render_contact_sheet(root, name, outline, size=640, fill=0.9, elevation=10.0, lens=70.0,
                         views=(("front", 0), ("3/4 front", -35), ("side", -90), ("back", 180)),
                         skip_outline=()):
    """Turntable preview: rotate `root` about Z under a fixed sun and camera, render
    each view with Eevee, and stitch them into docs/renders/<name>.png. `fill` scales
    the camera distance (lower = tighter framing)."""
    scene = bpy.context.scene
    model_objs = [o for o in scene.objects if o.type == "MESH"]
    for m in {s.material for o in model_objs for s in o.material_slots if s.material}:
        toonify(m)
    add_outlines(model_objs, outline, skip_outline)

    # Bounds for framing.
    dg = bpy.context.evaluated_depsgraph_get()
    pts = [o.matrix_world @ Vector(c) for o in model_objs for c in o.evaluated_get(dg).bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    centre = (lo + hi) / 2
    radius = (hi - lo).length / 2

    # Ground that matches the page colour, so only the cast shadow shows.
    ground_mat = bpy.data.materials.new("_ground")
    ground_mat.use_nodes = True
    ground_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (
        *[srgb_to_linear(c) for c in BG], 1)
    toonify(ground_mat, shadow_mul=(0.82, 0.83, 0.9))
    bpy.ops.mesh.primitive_plane_add(size=200)
    ground = bpy.context.active_object
    ground.data.materials.append(ground_mat)

    sun_data = bpy.data.lights.new("sun", "SUN")
    sun_data.energy = 3.0
    sun_data.angle = math.radians(1.0)
    sun = bpy.data.objects.new("sun", sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-35))

    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = lens
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    fov = 2 * math.atan(cam_data.sensor_width / (2 * lens))
    dist = radius / math.sin(fov / 2) * fill
    el = math.radians(elevation)
    cam.location = centre + Vector((0, -dist * math.cos(el), dist * math.sin(el)))
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()

    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    scene.world = world

    r = scene.render
    r.engine = "BLENDER_EEVEE"
    r.resolution_x = r.resolution_y = size
    r.film_transparent = True
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.eevee.taa_render_samples = 16

    tiles = render_views(root, name, views, size)
    save_sheet(tiles, name, size)


def render_views(root, name, views, size):
    """Render `root` turned to each (label, degrees) view; returns RGB tiles over BG."""
    scene = bpy.context.scene
    r = scene.render
    r.resolution_x = r.resolution_y = size
    tmp = RENDERS_DIR / f".{name}_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    tiles = []
    for i, (_label, deg) in enumerate(views):
        root.rotation_euler = (0, 0, math.radians(deg))
        r.filepath = str(tmp / f"{i}.png")
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(r.filepath)
        img.colorspace_settings.name = "Non-Color"
        px = np.empty(size * size * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(size, size, 4)
        a = px[..., 3:4]
        rgb = px[..., :3] * a + np.array(BG, dtype=np.float32) * (1 - a)
        tiles.append(rgb)
        bpy.data.images.remove(img)
        os.remove(r.filepath)
    tmp.rmdir()
    root.rotation_euler = (0, 0, 0)
    return tiles


def save_sheet(tiles, name, size):
    """Stitch tiles left to right into docs/renders/<name>.png."""
    gap = np.ones((size, 8, 3), dtype=np.float32) * np.array(BG, dtype=np.float32)
    row = []
    for t in tiles:
        row += [t, gap]
    sheet = np.concatenate(row[:-1], axis=1)
    h, w = sheet.shape[:2]
    out = bpy.data.images.new(f"{name}_sheet", w, h, alpha=False)
    out.colorspace_settings.name = "Non-Color"
    out.pixels.foreach_set(np.concatenate([sheet, np.ones((h, w, 1), np.float32)], axis=2).ravel())
    out.filepath_raw = str(RENDERS_DIR / f"{name}.png")
    out.file_format = "PNG"
    out.save()
    print(f"rendered {out.filepath_raw}")


def report(objs):
    for o in sorted(objs, key=lambda o: o.name):
        tris = triangle_count([o]) if o.type == "MESH" else 0
        print(f"  {o.name:10s} parent={o.parent.name if o.parent else '-':8s} "
              f"origin={tuple(round(c, 3) for c in o.location)} tris={tris}")
    print(f"  total tris={triangle_count(objs)}")
