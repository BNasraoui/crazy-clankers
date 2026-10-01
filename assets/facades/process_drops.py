# Turn the picked drop-off drawings into public/facades/drop-*.jpg and update their manifest entries in place.
#   python3 process_drops.py <workdir> <public/facades> [id ...]   (default: every id in PICKS)
# PICKS maps id -> (source png in workdir, px to trim off the top, px to trim off the bottom): the trims remove any
# sliver of sky above the roofline and of sidewalk below the wall; the sides are trimmed to keep 3:2.
import json, sys, colorsys, collections
from PIL import Image
W, OUT, *ONLY = sys.argv[1:]
# Same colour picks as process.py.
def body_colour(im):
    im = im.convert('RGB').resize((120, 180))
    c = collections.Counter()
    px = list(im.getdata())
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
PICKS = {
    'drop-lab': ('drop-lab-t2.png', 10, 36),
    'drop-crypto': ('drop-crypto-b1.png', 4, 10),  # 2026-10-02 redo: a crypto-bro Pacific Heights mansion, not a castle
    'drop-phlz': ('drop-phlz-t2.png', 0, 0),
    'drop-barris': ('drop-barris-t2.png', 0, 0),
    'drop-seriesa': ('drop-seriesa-t1.png', 6, 0),
    'drop-burrito': ('drop-burrito-t1.png', 0, 6),
    'drop-ladies-a': ('drop-ladies-a-t1.png', 0, 0),
    'drop-ladies-b': ('drop-ladies-b-t1.png', 0, 0),
}
# Where body_colour picks a trim colour over the wall, the wall colour sampled by hand.
WALL = {'drop-burrito': '#e6bd58', 'drop-crypto': '#dfdde2'}
man = json.load(open(f'{OUT}/manifest.json'))
entries = {e['id']: e for es in man.values() for e in es}
for fid, (png, top, bottom) in PICKS.items():
    if ONLY and fid not in ONLY: continue
    im = Image.open(f'{W}/{png}').convert('RGB')
    w, h = im.size
    h2 = h - top - bottom
    side = max(0, (w - h2 * 3 // 2) // 2)
    im = im.crop((side, top, w - side, h - bottom)).resize((960, 640), Image.LANCZOS)
    im.save(f'{OUT}/{fid}.jpg', quality=85)
    entries[fid].update(wall=WALL.get(fid) or body_colour(im), base=strip_colour(im, (0, int(640 * 0.96), 960, 640)))
    print(fid, entries[fid]['wall'], entries[fid]['base'])
json.dump(man, open(f'{OUT}/manifest.json', 'w'), indent=1)
