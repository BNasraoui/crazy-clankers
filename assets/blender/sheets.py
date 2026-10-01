"""Character-independent orthographic sheet calibration and silhouette metrology.

Coordinates are sheet pixels (top left origin) and game metres (Y up, +Z front).
No bounding-box normalization, registration search, or outline in the score.
Requires numpy and Pillow; Blender is imported only by the camera/render helpers.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Calibration:
    height: float
    crown: float
    soles: float
    front_axis: float
    side_axis: float

    @property
    def metres_per_pixel(self):
        if self.soles <= self.crown or self.height <= 0:
            raise ValueError("positive height and soles below crown required")
        return self.height / (self.soles - self.crown)

    def pixel_to_world(self, x, y, side=False, sign=1):
        s = self.metres_per_pixel
        return (
            sign * (x - (self.side_axis if side else self.front_axis)) * s,
            (self.soles - y) * s,
        )

    def world_to_pixel(self, horizontal, height, side=False, sign=1):
        s = self.metres_per_pixel
        return (
            (self.side_axis if side else self.front_axis) + sign * horizontal / s,
            self.soles - height / s,
        )


def iou(reference, rendered):
    a, b = np.asarray(reference, dtype=bool), np.asarray(rendered, dtype=bool)
    if a.shape != b.shape:
        raise ValueError("masks must share fixed pixel registration")
    union = np.count_nonzero(a | b)
    if not union:
        raise ValueError("empty reference and rendered silhouette")
    return float(np.count_nonzero(a & b) / union)


def silhouette(image):
    """Remove pale neutral guides, retain coloured fills/ink and enclosed whites.

    Crops must exclude labels/props. Keep the largest 4-connected component;
    exported target masks are reviewable, not generated from the model.
    """
    rgb = np.asarray(image.convert("RGB")).astype(np.int16)
    dark = (rgb.min(2) < 170) | ((rgb.max(2) - rgb.min(2) > 22) & (rgb.min(2) < 235))
    # Fill enclosed white shoes/eyes. The padding guarantees an outside seed.
    im = Image.fromarray(np.pad(dark, 1).astype(np.uint8) * 255).copy()
    ImageDraw.floodfill(im, (0, 0), 128, thresh=0)
    filled = np.asarray(im)[1:-1, 1:-1] != 128
    visited = np.zeros_like(filled)
    best = []
    h, w = filled.shape
    for y, x in zip(*np.nonzero(filled)):
        if visited[y, x]:
            continue
        todo = [(int(y), int(x))]
        visited[y, x] = True
        component = []
        while todo:
            j, i = todo.pop()
            component.append((j, i))
            for yy, xx in ((j - 1, i), (j + 1, i), (j, i - 1), (j, i + 1)):
                if (
                    0 <= yy < h
                    and 0 <= xx < w
                    and filled[yy, xx]
                    and not visited[yy, xx]
                ):
                    visited[yy, xx] = True
                    todo.append((yy, xx))
        if len(component) > len(best):
            best = component
    out = np.zeros_like(filled)
    if best:
        yy, xx = zip(*best)
        out[yy, xx] = True
    return out


def bounds(mask):
    yy, xx = np.nonzero(mask)
    if not len(xx):
        raise ValueError("empty silhouette")
    return [int(xx.min()), int(yy.min()), int(xx.max() + 1), int(yy.max() + 1)]


def guide_rows(image, x_ranges, threshold=185):
    """Locate pale neutral horizontal lines in unobstructed sheet margins."""
    a = np.asarray(image.convert("RGB")).astype(np.int16)
    strips = np.concatenate([a[:, lo:hi] for lo, hi in x_ranges], axis=1)
    gray = (
        (strips.max(2) - strips.min(2) < 18)
        & (strips.mean(2) < 230)
        & (strips.mean(2) > threshold)
    )
    rows = np.flatnonzero(gray.mean(1) > 0.6)
    groups = np.split(rows, np.where(np.diff(rows) > 1)[0] + 1)
    return [float(np.mean(g)) for g in groups if len(g)]


def load(character):
    path = Path(__file__).parent / "calibrations" / f"{character}.json"
    data = json.loads(path.read_text())
    return data


def reference(character, kind, view):
    cfg = load(character)
    v = cfg[kind]["views"][view]
    path = ROOT / "docs/art/turnarounds" / f"{character}-{kind}.png"
    im = Image.open(path).convert("RGB").crop(v["crop"])
    return im, silhouette(im)


def ortho_camera(character, kind, view):
    """Exact pixel camera, with zero elevation; no auto fit to model bounds."""
    import anime as A
    import bpy
    from mathutils import Vector

    cfg = load(character)
    k = cfg[kind]
    v = k["views"][view]
    x0, y0, x1, y1 = v["crop"]
    s = k["metres_per_pixel"]
    height = k["world_y_at_zero"] - (y0 + y1) * 0.5 * s
    horizontal = ((x0 + x1) * 0.5 - v["axis"]) * s * v["sign"]
    direction = Vector(v["direction"])
    right = Vector(v["right"])
    target = A.gv(right * horizontal + Vector((0, height, 0)))
    camera = bpy.data.cameras.new(f"fit-{kind}-{view}")
    camera.type = "ORTHO"
    camera.ortho_scale = max(x1 - x0, y1 - y0) * s
    obj = bpy.data.objects.new(camera.name, camera)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = target + A.gv(direction) * 5
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()
    scene = bpy.context.scene
    scene.camera = obj
    scene.render.resolution_x = x1 - x0
    scene.render.resolution_y = y1 - y0
    scene.render.resolution_percentage = 100
    return obj


def render_mask(character, kind, view, objects, path):
    import bpy

    scene = bpy.context.scene
    visible = set(objects)
    state = {o: o.hide_render for o in scene.objects if o.type == "MESH"}
    for o in state:
        o.hide_render = o not in visible
    camera = ortho_camera(character, kind, view)
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.film_transparent = True
    scene.eevee.taa_render_samples = 16
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    pixels = np.asarray(Image.open(path).convert("RGBA"))
    Image.fromarray(pixels).save(path)  # Discard Blender render timestamps.
    mask = pixels[:, :, 3] >= 128
    for o, hidden in state.items():
        o.hide_render = hidden
    bpy.data.objects.remove(camera, do_unlink=True)
    return mask


def overlay(character, kind, view, rendered, output):
    """Reference + outline, then XOR: cyan missing, magenta excess, gray overlap."""
    ref, target = reference(character, kind, view)
    score = iou(target, rendered)
    a = np.asarray(ref).copy()
    edge = np.asarray(
        Image.fromarray(rendered.astype(np.uint8) * 255).filter(
            ImageFilter.MaxFilter(3)
        )
    ) != np.asarray(
        Image.fromarray(rendered.astype(np.uint8) * 255).filter(
            ImageFilter.MinFilter(3)
        )
    )
    a[edge] = (235, 30, 140)
    diff = np.full_like(a, 250)
    diff[target & rendered] = (130, 137, 145)
    diff[target & ~rendered] = (0, 185, 210)
    diff[rendered & ~target] = (235, 30, 140)
    out = Image.new("RGB", (a.shape[1] * 2, a.shape[0] + 42), "white")
    out.paste(Image.fromarray(a), (0, 42))
    out.paste(Image.fromarray(diff), (a.shape[1], 42))
    d = ImageDraw.Draw(out)
    d.text(
        (8, 8),
        f"{character} {kind} {view}: IoU {score:.4f} | outline / XOR",
        fill="black",
    )
    d.text(
        (8, 23),
        "cyan = reference only; magenta = model only; gray = intersection",
        fill="black",
    )
    out.save(output)
    return score


def measure(character):
    """Audit calibrated source images: hashes, guides, bounds and metric landmarks.

    Each passenger supplies a small data-only calibrations/<id>.json. Drawing
    conventions and asymmetric view directions must be reviewed by a person.
    """
    import hashlib

    cfg = load(character)
    result = {"character": character, "height_m": cfg["height_m"]}
    for kind in ["body", "head"]:
        k = cfg[kind]
        path = ROOT / "docs/art/turnarounds" / f"{character}-{kind}.png"
        im = Image.open(path).convert("RGB")
        entry = {key: k[key] for key in ["metres_per_pixel", "world_y_at_zero"]}
        entry["source_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        entry["size_pixels"] = list(im.size)
        entry["detected_guides_pixels"] = guide_rows(im, k["guide_scan_ranges"])
        entry["reviewed_guides_pixels"] = k["guides"]
        entry["landmarks"] = {
            name: {
                "pixel_y": y,
                "height_m": k["world_y_at_zero"] - y * k["metres_per_pixel"],
            }
            for name, y in k["landmarks"].items()
        }
        for group in ["views", "auxiliary_views"]:
            entry[group] = {}
            for view, v in k.get(group, {}).items():
                mask = silhouette(im.crop(v["crop"]))
                bb = bounds(mask)
                x, y, _, _ = v["crop"]
                entry[group][view] = {
                    **v,
                    "bounds_pixels": [bb[0] + x, bb[1] + y, bb[2] + x, bb[3] + y],
                    "mask_area_pixels": int(mask.sum()),
                }
        result[kind] = entry
    return result


# Semantic diagnostics use the same fixed cameras as silhouette acceptance.
def segment_regions(image, foreground, regions, crop_y=0):
    """Nearest reviewed RGB swatch within optional sheet-y intervals.

    All foreground pixels, including line art, belong to a region. Intervals
    disambiguate white eyes from white shoes; never derive them from the model.
    Label zero is background, remaining labels follow configuration order.
    """
    rgb = np.asarray(image)[..., :3].astype(float)
    yy = np.arange(rgb.shape[0])[:, None] + crop_y
    distances = []
    for region in regions.values():
        colours = np.asarray(region['colours'], dtype=float)
        d = np.min(np.sum((rgb[..., None, :] - colours) ** 2, axis=-1), axis=-1)
        lo, hi = region.get('rows', [-float('inf'), float('inf')])
        distances.append(np.where((yy >= lo) & (yy <= hi), d, np.inf))
    labels = np.argmin(distances, axis=0).astype(np.uint8) + 1
    labels[~np.asarray(foreground, dtype=bool)] = 0
    return labels


def region_iou(reference_labels, rendered_labels, names):
    result = {}
    for i, name in enumerate(names, 1):
        a, b = reference_labels == i, rendered_labels == i
        result[name] = iou(a, b) if np.any(a | b) else None
    return result


def shadow_cleanliness(shadow, face):
    """8-connected islands and Manhattan light/shadow edge length in pixels.

    Only edges between two face pixels count; silhouette/occlusion boundaries
    are excluded. No removal of small islands or smoothing hides artifacts.
    """
    face = np.asarray(face, dtype=bool)
    shadow = np.asarray(shadow, dtype=bool) & face
    seen = np.zeros_like(shadow)
    islands = 0
    h, w = shadow.shape
    for y, x in zip(*np.nonzero(shadow)):
        if seen[y, x]:
            continue
        islands += 1
        todo = [(y, x)]
        seen[y, x] = True
        while todo:
            y, x = todo.pop()
            for j, i in ((y-1,x), (y+1,x), (y,x-1), (y,x+1), (y-1,x-1), (y-1,x+1), (y+1,x-1), (y+1,x+1)):
                if 0 <= j < h and 0 <= i < w and shadow[j,i] and not seen[j,i]:
                    seen[j,i] = True
                    todo.append((j,i))
    edge = np.count_nonzero((shadow[1:] != shadow[:-1]) & face[1:] & face[:-1])
    edge += np.count_nonzero((shadow[:,1:] != shadow[:,:-1]) & face[:,1:] & face[:,:-1])
    return {'islands': islands, 'edge_pixels': int(edge), 'shadow_pixels': int(shadow.sum()), 'face_pixels': int(face.sum())}


def diagnostic_material(name, colour, shadow=False):
    import bpy
    import anime as A
    import math
    from mathutils import Matrix, Vector
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*colour, 1)
    if shadow:
        light = Matrix.Rotation(math.radians(28), 3, 'Z') @ Matrix.Rotation(math.radians(40), 3, 'X') @ Vector((0,0,1))
        A.toonify(mat, shadow_mul=(0,1,0), threshold=0.32, light=light)
    else:
        nt = mat.node_tree
        nt.nodes.clear()
        emit = nt.nodes.new('ShaderNodeEmission')
        emit.inputs['Color'].default_value = (*colour, 1)
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(emit.outputs[0], out.inputs['Surface'])
    return mat


def colour_region_fit(character, objects, output):
    """Render flat material albedo and return every region IoU, plus audit masks."""
    import bpy
    cfg = load(character)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    originals = {o: list(o.data.materials) for o in objects}
    scene = bpy.context.scene
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    # One flat material for each original material, retaining its actual albedo.
    for o, mats in originals.items():
        for i, mat in enumerate(mats):
            base = mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value[:3]
            tex = next((n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image), None)
            if tex:
                # glTF uses a white factor for textured materials. Recover the
                # dominant flat pigment, not the white factor or painted ink.
                pixels = np.array(tex.image.pixels[:], dtype=np.float32).reshape(-1,4)[:,:3]
                quantized = np.round(pixels * 255).astype(np.uint8)
                colours, counts = np.unique(quantized, axis=0, return_counts=True)
                srgb = colours[np.argmax(counts)] / 255
                base = np.where(srgb <= .04045, srgb / 12.92, ((srgb + .055)/1.055)**2.4)
            o.data.materials[i] = diagnostic_material('flat-' + mat.name, base)
    result = {}
    try:
        for kind in ['body', 'head']:
            settings = cfg['regions'][kind]
            targets = objects if kind == 'body' else [o for o in objects if o.name == cfg['head_node']]
            result[kind] = {}
            for view, v in cfg[kind]['views'].items():
                path = output / f'{character}-regions-{kind}-{view}.png'
                foreground = render_mask(character, kind, view, targets, path)
                ref, target = reference(character, kind, view)
                a = segment_regions(ref, target, settings, v['crop'][1])
                b = segment_regions(Image.open(path), foreground, settings, v['crop'][1])
                result[kind][view] = region_iou(a, b, settings)
                palette = np.array([[255,255,255], [99,65,37], [245,178,127], [48,57,85], [141,180,223], [194,158,103], [130,135,137]], dtype=np.uint8)
                # Arbitrary character region counts are supported with a stable palette.
                if len(settings) >= len(palette):
                    palette = np.array([[255,255,255]] + [[(i*73)%230,(i*137)%230,(i*191)%230] for i in range(1,len(settings)+1)], dtype=np.uint8)
                Image.fromarray(np.concatenate([palette[a], palette[b]], axis=1)).save(output / f'{character}-region-labels-{kind}-{view}.png')
    finally:
        for o, mats in originals.items():
            for i, mat in enumerate(mats): o.data.materials[i] = mat
    return result


def face_shadow_fit(character, head, output):
    """Texture-free N.L pass: yellow lit face, green shadow, blue non-face occluders.

    Fixed 512px orthographic front/35 degree/profile views. Head remains neutral,
    so light orientation and pixel scale agree across versions and characters.
    """
    import bpy
    import anime as A
    import math
    from mathutils import Vector
    cfg = load(character)
    k = cfg['head']
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    originals = list(head.data.materials)
    roles = cfg['face_materials']
    for i, mat in enumerate(originals):
        is_face = mat.name.split('.')[0] in roles
        head.data.materials[i] = diagnostic_material('shadow-face' if is_face else 'occluder', (1,1,0) if is_face else (0,0,1), is_face)
    states = {o: o.hide_render for o in scene.objects if o.type == 'MESH'}
    for o in states: o.hide_render = o != head
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.color_mode = 'RGBA'
    scene.eevee.taa_render_samples = 16
    cd = bpy.data.cameras.new('shadow-camera')
    cd.type = 'ORTHO'
    span = (k['chin_pixel'] - k['crown_pixel']) * k['metres_per_pixel']
    cd.ortho_scale = span * 1.2
    camera = bpy.data.objects.new(cd.name, cd)
    scene.collection.objects.link(camera)
    scene.camera = camera
    mid = k['world_y_at_zero'] - (k['chin_pixel'] + k['crown_pixel']) / 2 * k['metres_per_pixel']
    target = A.gv(Vector((0,mid,0)))
    result = {}
    try:
        for view, degrees in [('front',0), ('three_quarter',35), ('profile',90)]:
            a = math.radians(degrees)
            camera.location = target + A.gv(Vector((math.sin(a)*5,0,math.cos(a)*5)))
            camera.rotation_euler = (target-camera.location).to_track_quat('-Z','Y').to_euler()
            path = output / f'{character}-shadow-{view}.png'
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            im = np.asarray(Image.open(path).convert('RGBA'))
            Image.fromarray(im).save(path)  # Stable bytes, without render timestamps.
            yy = mid + (256 - np.arange(512) - .5) * cd.ortho_scale / 512
            top = k['world_y_at_zero'] - k['landmarks']['hairline']*k['metres_per_pixel']
            bottom = k['world_y_at_zero'] - k['chin_pixel']*k['metres_per_pixel']
            face = (im[:,:,3] >= 128) & (im[:,:,1] >= 128) & (im[:,:,2] < 128) & (yy[:,None] < top) & (yy[:,None] > bottom)
            result[view] = shadow_cleanliness(im[:,:,0] < 128, face)
    finally:
        for i, mat in enumerate(originals): head.data.materials[i] = mat
        for o, hidden in states.items(): o.hide_render = hidden
        bpy.data.objects.remove(camera, do_unlink=True)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "character", help="character id with a reviewed calibration JSON"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(measure(args.character), indent=2) + "\n"
    if args.output:
        args.output.write_text(report)
    else:
        print(report, end="")
