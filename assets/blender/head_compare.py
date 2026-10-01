"""Arrange unchanged cel renders and reference crops for silhouette review."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]


def head_compare(head_path=None, output_path=None):
    v4 = Image.open(ROOT/'assets/blender/reviews/v4-head.png').convert('RGB')
    v5 = Image.open(head_path or ROOT/'docs/renders/techbro-head.png').convert('RGB')
    portrait = Image.open(ROOT/'docs/art/portraits.jpg').convert('RGB').crop((148, 12, 345, 216))
    cast = Image.open(ROOT/'docs/art/cast.jpg').convert('RGB').crop((77, 91, 180, 197))
    # References are only cropped and resized: no generated or reconstructed views.
    out = Image.new('RGB', (1640, 1410), (246, 243, 234))
    draw = ImageDraw.Draw(out)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 22)
    draw.text((20, 14), 'v4 / merged head', fill='#252525', font=font)
    draw.text((540, 14), 'v5 / curved shared head', fill='#252525', font=font)
    draw.text((1060, 14), 'Reference / original drawing angles', fill='#252525', font=font)
    for row, name in enumerate(('Front', 'Three-quarter', 'Profile')):
        y = 60+row*445
        draw.text((20,y), name, fill='#252525', font=font)
        for col, sheet in enumerate((v4,v5)):
            tile = sheet.crop((row*610,0,row*610+600,600))
            tile.thumbnail((410,410),Image.Resampling.LANCZOS)
            out.paste(tile,(20+col*520,y+30))
        for ref, x, label in ((portrait,1060,'portraits.jpg'),(cast,1360,'cast.jpg')):
            tile=ref.copy();tile.thumbnail((270,300),Image.Resampling.LANCZOS)
            # Enlarge the source crop to comparable head height without changing aspect.
            tile=ref.resize((round(ref.width*300/ref.height),300),Image.Resampling.LANCZOS)
            if x+tile.width>1640:
                tile.thumbnail((260,300),Image.Resampling.LANCZOS)
            out.paste(tile,(x,y+55))
            draw.text((x,y+365),label,fill='#252525',font=font)
    out.save(output_path or ROOT/'docs/renders/techbro-head-compare.png', optimize=True)


if __name__ == '__main__':
    head_compare()
