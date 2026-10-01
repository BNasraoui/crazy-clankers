# Turn generated facade drawings into game textures + a manifest with colours.
#   public/facades/<id>.jpg and public/facades/manifest.json
import json, os, sys, colorsys, collections
from PIL import Image
F = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1]
man = json.load(open(f'{F}/city/manifest.json'))
# The six original Haight Victorians.
for i in range(1, 7): man[f'v{i}'] = ['haight', 'P']
SIZES = {'P': (640, 960), 'S': (768, 768), 'L': (960, 640)}
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
out = collections.defaultdict(list)
for fid, (district, size) in sorted(man.items()):
    src = f'{F}/city/{fid}.png' if not fid.startswith('v') else f'{F}/out/{fid}.png'
    if not os.path.exists(src): continue
    im = Image.open(src).convert('RGB')
    w, h = im.size
    im = im.crop((8, 8, w - 8, h - 8))  # trim any hairline border
    kind = 'tile' if fid.startswith('tower-') else 'towerbase' if fid.startswith('towerbase') else 'drop' if fid.startswith('drop-') else 'house'
    tw, th = (512, 512) if kind == 'tile' else SIZES[size]
    im.resize((tw, th), Image.LANCZOS).save(f'{OUT}/{fid}.jpg', quality=84)
    W, H = im.size
    out[district].append({'id': fid, 'kind': kind, 'wall': body_colour(im), 'base': strip_colour(im, (0, int(H * 0.96), W, H))})
json.dump(out, open(f'{OUT}/manifest.json', 'w'), indent=1)
print({k: len(v) for k, v in out.items()})
