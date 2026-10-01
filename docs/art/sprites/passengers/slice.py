# Cut pedestrian sprite sheets into transparent frames with a bold ink outline.
#   ped-<id>.png      -> front, back, walk1, walk2, dive   (original 5-pose sheet)
#   <id>-fb.png       -> fwalk1, fwalk2, bwalk1, bwalk2    (front/back walk)
#   <id>-side.png     -> swalk1..swalk4                    (side walk cycle)
# Each sheet is scaled so its tallest standing figure is 320 px (= 1.75 m in game).
import sys, json, os
import numpy as np
from PIL import Image
from scipy import ndimage
SRC1, OUT = sys.argv[1], sys.argv[2]
OUTLINE = 9  # px of ink around each figure, at 320 px per 1.75 m
INK = (27, 23, 34)

def figures(path, count):
    im = np.asarray(Image.open(path).convert('RGB')).astype(np.int16)
    white = (im.min(axis=2) > 236) & (np.ptp(im, axis=2) < 18)
    fg = ndimage.binary_closing(~white, iterations=3)
    lab, n = ndimage.label(fg)
    if n < count: return None, None
    sizes = ndimage.sum(fg, lab, range(1, n + 1))
    order = np.argsort(sizes)[::-1]
    big = sorted(order[:count] + 1, key=lambda l: ndimage.center_of_mass(lab == l)[1])
    groups = {int(l): (lab == l) for l in big}
    cx = {l: ndimage.center_of_mass(m)[1] for l, m in groups.items()}
    for l in order[count:] + 1:
        if sizes[l - 1] < 40: continue
        m = lab == l
        x = ndimage.center_of_mass(m)[1]
        groups[min(cx, key=lambda k: abs(cx[k] - x))] |= m
    return im, [groups[int(l)] for l in big]

def cut(im, m, scale):
    ys, xs = np.where(m)
    pad = 4
    x0, x1 = max(0, xs.min() - pad), min(im.shape[1], xs.max() + 1 + pad)
    y0, y1 = max(0, ys.min() - pad), min(im.shape[0], ys.max() + 1 + pad)
    rgb = im[y0:y1, x0:x1].astype(np.uint8)
    mn = im[y0:y1, x0:x1].min(axis=2)
    own = ndimage.binary_dilation(m, iterations=2)[y0:y1, x0:x1]
    a = np.clip((250 - mn) * 18, 0, 255).astype(np.uint8)
    a[~own] = 0
    holes = ndimage.binary_fill_holes(a > 128) & (a <= 128)
    hl, hn = ndimage.label(holes)
    if hn:
        hs = ndimage.sum(holes, hl, range(1, hn + 1))
        a[np.isin(hl, np.where(hs < 1500)[0] + 1)] = 255
    img = Image.fromarray(np.dstack([rgb, a]), 'RGBA')
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    # Bold outline: grow the silhouette and paint the ring in ink, under the figure.
    arr = np.asarray(img).copy()
    solid = arr[..., 3] > 110
    padded = np.pad(solid, OUTLINE + 1)
    ring = ndimage.binary_dilation(padded, structure=ndimage.generate_binary_structure(2, 1), iterations=OUTLINE)
    out = np.zeros(ring.shape + (4,), np.uint8)
    out[ring] = (*INK, 255)
    inner = np.pad(arr, ((OUTLINE + 1,) * 2, (OUTLINE + 1,) * 2, (0, 0)))
    alpha = inner[..., 3:4] / 255.0
    out[..., :3] = (inner[..., :3] * alpha + out[..., :3] * (1 - alpha)).astype(np.uint8)
    out[..., 3] = np.maximum(out[..., 3], inner[..., 3])
    return Image.fromarray(out, 'RGBA')

meta = {}
def do(path, names, stand, pid):
    im, masks = figures(path, len(names))
    if masks is None: print('skip', path); return
    hs = [np.where(m.any(axis=1))[0] for m in masks]
    tallest = max(h.max() - h.min() for i, h in enumerate(hs) if names[i] in stand)
    scale = 320 / tallest
    for name, m in zip(names, masks):
        img = cut(im, m, scale)
        img.save(f'{OUT}/pax-{pid}-{name}.png', optimize=True)
        meta.setdefault(pid, {})[name] = [img.width, img.height]
for f in sorted(os.listdir(SRC1)):
    if f.startswith('pax-') and f.endswith('.png'):
        do(f'{SRC1}/{f}', ['front', 'wave1', 'wave2', 'side', 'back'], {'front', 'side', 'back'}, f[4:-4])
json.dump(meta, open(f'{OUT}/passengers.json', 'w'), indent=1)
print({k: sorted(v) for k, v in meta.items()})
