# Cut each 5-pose sheet into frames: find the five largest figures (connected
# non-white blobs, merging small bits like a dog or a leash into the nearest
# figure), key out the white background, and save tight-cropped RGBA frames
# scaled to one shared height so every pose has the same pixels-per-metre.
import sys, json, os
import numpy as np
from PIL import Image
from scipy import ndimage
SRC, OUT = sys.argv[1], sys.argv[2]
NAMES = ['front', 'back', 'walk1', 'walk2', 'dive']
meta = {}
for f in sorted(os.listdir(SRC)):
    if not (f.startswith('ped-') and f.endswith('.png')): continue
    pid = f[4:-4]
    im = np.asarray(Image.open(f'{SRC}/{f}').convert('RGB')).astype(np.int16)
    white = (im.min(axis=2) > 236) & (np.ptp(im, axis=2) < 18)
    fg = ndimage.binary_closing(~white, iterations=3)
    # Figures: the five biggest connected blobs; smaller blobs (a dog, a leash,
    # a stray hair) join whichever big blob is nearest horizontally.
    lab, n = ndimage.label(fg)
    sizes = ndimage.sum(fg, lab, range(1, n + 1))
    order = np.argsort(sizes)[::-1]
    if n < 5:
        print(pid, 'found', n, 'blobs, skipping'); continue
    big = sorted(order[:5] + 1, key=lambda l: ndimage.center_of_mass(lab == l)[1])
    groups = {int(l): (lab == l) for l in big}
    cx = {l: ndimage.center_of_mass(m)[1] for l, m in groups.items()}
    for l in order[5:] + 1:
        if sizes[l - 1] < 40: continue
        m = lab == l
        x = ndimage.center_of_mass(m)[1]
        tgt = min(cx, key=lambda k: abs(cx[k] - x))
        groups[tgt] |= m
    masks = [groups[int(l)] for l in big]
    boxes = []
    for m in masks:
        ys, xs = np.where(m)
        boxes.append((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    # Standing poses set the scale: height of the front figure = 1.75 m.
    stand_h = boxes[0][3] - boxes[0][1]
    base = max(b[3] for b in boxes[:4])  # shared ground line for standing/walking poses
    for name, m, (x0, y0, x1, y1) in zip(NAMES, masks, boxes):
        pad = 4
        x0, x1 = max(0, x0 - pad), min(im.shape[1], x1 + pad)
        y0 = max(0, y0 - pad)
        y1 = min(im.shape[0], (base if name != 'dive' else y1) + pad)
        rgb = im[y0:y1, x0:x1].astype(np.uint8)
        # Alpha: white background removed, with a soft edge on near-white pixels.
        mn = im[y0:y1, x0:x1].min(axis=2)
        own = ndimage.binary_dilation(m, iterations=2)[y0:y1, x0:x1]
        a = np.clip((250 - mn) * 18, 0, 255).astype(np.uint8)
        a[~own] = 0  # drop pixels that belong to the neighbouring pose
        # Fill enclosed white areas (white shoes, eyes, sleeves) back in as opaque.
        holes = ndimage.binary_fill_holes(a > 128) & (a <= 128)
        hl, hn = ndimage.label(holes)
        if hn:
            hs = ndimage.sum(holes, hl, range(1, hn + 1))
            small = np.isin(hl, np.where(hs < 1500)[0] + 1)
            a[small] = 255
        img = Image.fromarray(np.dstack([rgb, a]), 'RGBA')
        scale = 320 / stand_h  # 320 px = 1.75 m
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
        img.save(f'{OUT}/{pid}-{name}.png', optimize=True)
        meta.setdefault(pid, {})[name] = [img.width, img.height]
json.dump(meta, open(f'{OUT}/sprites.json', 'w'), indent=1)
print(json.dumps(meta))
