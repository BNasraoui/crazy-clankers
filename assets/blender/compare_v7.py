"""Review board: approved sheet beside identically framed v6 and v7 previews."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parents[2]
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 22)
board = Image.new('RGB', (1230, 1310), '#f6f3eb')
draw = ImageDraw.Draw(board)
for x, title in [(10,'Approved head sheet'), (420,'v6'), (830,'v7')]:
    draw.text((x,15), title, fill='#252525', font=font)
sheet = Image.open(ROOT/'docs/art/turnarounds/techbro-head.png').convert('RGB')
before = Image.open(ROOT/'assets/blender/reviews/v7-baseline/techbro-head.png')
after = Image.open(ROOT/'docs/renders/techbro-head.png')
for i, (view, axis) in enumerate([('Front',210),('Three-quarter',620),('Profile',1068)]):
    ref = Image.new('RGB',(530,530),'white')
    ref.paste(sheet, (265-axis,-140))
    y = 60 + i*415
    board.paste(ref.resize((400,400),Image.Resampling.LANCZOS),(10,y))
    for x, im in [(420,before),(830,after)]:
        tile = im.crop((i*610,0,i*610+600,600))
        board.paste(tile.resize((400,400),Image.Resampling.LANCZOS),(x,y))
    draw.text((15,y+372),view,fill='#252525',font=font)
board.save(ROOT/'docs/renders/techbro-v6-v7-head.png')
