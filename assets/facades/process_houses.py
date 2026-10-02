# Turn the third-pass drawings (houses.py) into public/facades/<id>.avif and update those manifest entries in place.
#   python3 process_houses.py <workdir> <public/facades> [id ...]   (needs Pillow >= 11.3 for AVIF)
# Houses: a few rows of sky are trimmed off the top automatically, the sidewalk strips listed in BOTTOM off the bottom,
# and the sides are cropped to the size class (P 640x960, S 768x768, L 960x640).
# Tower tiles: each drawing shows four storeys but only roughly repeats, so the crop is placed where the line just past
# each edge matches the first line on the opposite edge (searched both ways), then the seam is softened with a short
# fade, so the 512x512 tile wraps seamlessly both ways.
import json, os, sys, colorsys, collections
import numpy as np
from PIL import Image
W, OUT, *ONLY = sys.argv[1:]
SIZES = {'P': (640, 960), 'S': (768, 768), 'L': (960, 640)}
from houses import JOBS
# Percent of the height to cut off the bottom where the drawing shows a strip of sidewalk.
BOTTOM = {'mission-3': 2.0, 'potrero-1': 2.3, 'potrero-3': 1.0, 'sunset-1': 0.5, 'sunset-3': 0.8, 'pac-6': 0.8,
          'nb-3': 1.0, 'mission-6': 0.8, 'haight-10': 0.6}
# Where body_colour picks the trim, a door or a shopfront over the wall, the wall colour sampled by hand.
WALL = {'v2': '#f8dc7a', 'v6': '#eaab84', 'haight-9': '#93a383', 'pac-6': '#f5ead4', 'nb-2': '#c2d89b', 'nb-5': '#f8ecc6'}
def body_colour(im):
    im = im.convert('RGB').resize((120, 180))
    c = collections.Counter()
    px = list(im.get_flattened_data())
    for p in px:
        h, l, s = colorsys.rgb_to_hls(*(x / 255 for x in p))
        if s < 0.18 or l < 0.22 or l > 0.86: continue
        c[(p[0] // 14, p[1] // 14, p[2] // 14)] += 1
    if not c:
        return '#%02x%02x%02x' % tuple(sum(x[i] for x in px) // len(px) for i in range(3))
    k, _ = c.most_common(1)[0]
    sel = [p for p in px if (p[0] // 14, p[1] // 14, p[2] // 14) == k]
    return '#%02x%02x%02x' % tuple(sum(x[i] for x in sel) // len(sel) for i in range(3))
def strip_colour(im, box):
    s = im.convert('RGB').crop(box).resize((1, 1))
    return '#%02x%02x%02x' % s.getpixel((0, 0))
def sky_rows(a):
    # Rows at the top that are mostly saturated sky blue, at most 3% of the height.
    r, g, b = (a[..., i].astype(int) for i in range(3))
    sky = (b - r > 70) & (b > 170) & (g > r)
    n = 0
    while n < a.shape[0] * 0.03 and sky[n].mean() > 0.5: n += 1
    return n + (2 if n else 1)
def house(fid, size):
    im = Image.open(f'{W}/{fid}.png').convert('RGB')
    w, h = im.size
    top, bottom = sky_rows(np.asarray(im)), int(h * BOTTOM.get(fid, 0.3) / 100)
    tw, th = SIZES[size]
    h2 = h - top - bottom
    w2 = min(w, round(h2 * tw / th))
    side = (w - w2) // 2
    return im.crop((side, top, side + w2, h - bottom)).resize((tw, th), Image.LANCZOS)
def best_cut(g, lo, hi):
    # Along axis 0 of the grey image g: the crop [c, c + L) with lo <= L < hi whose next line g[c + L] looks most
    # like its first line g[c], so the crop repeats seamlessly. Coarse search at 1/4 size, then refined at full size.
    def search(g, Ls, cs, k):  # k: how many lines to compare
        best = (1e9, 0, 0)
        for L in Ls:
            for c in cs(L):
                if c < 0 or c + L + k > len(g): continue
                best = min(best, (np.abs(g[c:c + k] - g[c + L:c + L + k]).mean(), L, c))
        return best
    q = g[::4, ::4]
    _, L, c = search(q, range(lo // 4, hi // 4 + 1), lambda L: range(0, len(q) - L), 2)
    _, L, c = search(g, range(max(lo, 4 * L - 4), min(hi, 4 * L + 5)), lambda L2: range(4 * c - 4, 4 * c + 5), 6)
    return c, L
def wrap(a, c, L, axis, n=12):
    a = np.moveaxis(a, axis, 0).astype(float)
    out = a[c:c + L].copy()
    for y in range(n):  # soften what is left of the seam with the lines just past each edge
        wgt = 0.5 + 0.5 * y / n
        if c + L + y < len(a): out[y] = out[y] * wgt + a[c + L + y] * (1 - wgt)
        if c - 1 - y >= 0: out[L - 1 - y] = out[L - 1 - y] * wgt + a[c - 1 - y] * (1 - wgt)
    return np.moveaxis(out, 0, axis)
def tile(fid):
    a = np.asarray(Image.open(f'{W}/{fid}.png').convert('RGB')).astype(float)
    h, w = a.shape[:2]
    g = a.mean(axis=2)
    p = g.mean(axis=1) - g.mean()
    py = h // 5 + int(np.argmax([np.dot(p[:-k], p[k:]) / (h - k) for k in range(h // 5, h // 3)]))  # one storey
    y, H = best_cut(g, 4 * py - 10, min(h - 6, 4 * py + 10))  # exactly four storeys
    x, Wd = best_cut(g.T, int(w * 0.6), w - 6)
    a = wrap(wrap(a, y, H, 0), x, Wd, 1)
    print(fid, 'storey', py, 'rows', y, '+', H, 'cols', x, '+', Wd)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).resize((512, 512), Image.LANCZOS)
man = json.load(open(f'{OUT}/manifest.json'))
entries = {e['id']: e for es in man.values() for e in es}
for fid, (size, _) in JOBS.items():
    if ONLY and fid not in ONLY: continue
    out = tile(fid) if size == 'T' else house(fid, size)
    out.save(f'{OUT}/{fid}.avif', quality=60)
    W2, H2 = out.size
    entries[fid].update(wall=WALL.get(fid) or body_colour(out), base=strip_colour(out, (0, int(H2 * 0.96), W2, H2)))
    print(fid, out.size, entries[fid]['wall'], entries[fid]['base'])
json.dump(man, open(f'{OUT}/manifest.json', 'w'), indent=1)
