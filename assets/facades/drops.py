# Second pass at the drop-off drawings (2026-10-01): styled on crops of the key art, not on an elevation drawing.
#   python3 drops.py <workdir> [id[:tag] ...]   -> <workdir>/<id>[-tag].png
# <workdir> must hold style-*.png, crops of the buildings in public/keyart/ (see README).
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
W = os.path.abspath(sys.argv[1])
STYLE = ('Painted in EXACTLY the rendering style of the buildings in the attached key-art crops: a bright, sunny Japanese anime background '
         'painting with crisp manga ink linework, like a frame from a modern cel-anime film: confident dark ink outlines on every edge and detail, '
         'thin and slightly broken, varying in weight, and cel-shaded shadow shapes with crisp edges; '
         'bright, clear, high-noon California sunlight (NOT golden hour, NOT sunset, NOT warm-orange cast) from the UPPER LEFT, with soft blue-violet cast shadows under every cornice, bay window, sill, awning and sign, '
         'and shadowed reveals on the right side of each window and door opening; gentle light-to-shade gradients across each wall; '
         'windows are glossy and reflect a deep blue sky with soft white cloud highlights and a few light streaks; '
         'saturated, vivid, cheerful colour with crisp white highlights, warm sunlit highlights, rich, legible, hand-painted detail. It must NOT look like flat vector clip art, '
         'an icon, an architectural line drawing, a CAD elevation or a smooth 3D render: no uniform heavy outlines, no flat unshaded fills. ')
FORMAT = ('Composition: ONE building, a perfectly straight-on front elevation (orthographic, no perspective, no vanishing points), '
          'for use as a game texture pasted on the front of a box. The facade FILLS THE ENTIRE IMAGE edge to edge: '
          'NO sky anywhere, no ground, no street, no sidewalk, no neighbouring buildings, no margins, no border, no frame. '
          'Bottom edge = the foot of the wall and the door thresholds, with NO strip of pavement or sidewalk below it; top edge = the top of the roof parapet or cornice cap (no sliver of sky above it); left and right edges = the building\'s sides. '
          'Apart from the one shop sign named below (spelled exactly, letter for letter), NO other text; NO real brand logos; NO people, NO cars, NO trees in front. ')
JOBS = {
 'drop-lab': 'A scrappy, lovable startup HQ called "THE LAB" in a two-storey SoMa brick light-industrial building with a flat parapet roofline. '
             'Sun-warmed red-orange brick with a pale cream painted band and cornice, a hand-painted cream sign board above the ground floor with bold '
             'hand-lettered teal-and-black letters reading "THE LAB". Upstairs: a row of big steel multi-pane factory windows, one pane patched with cardboard, '
             'a window unit and a tangle of cables. Ground floor: a wide roll-up garage door rolled half open, showing a cluttered, warm-lit interior with '
             'whiteboards full of scribbled diagrams, a ping-pong table, beanbags and blinking server racks; a scuffed steel side door with taped-up paper notes; '
             'a few rental e-scooters leaning against the wall; a little cheerful sticker graffiti. Satirical, scrappy, sunny.',
 'drop-crypto': 'A grand, wide three-storey Pacific Heights Edwardian mansion that a crypto millionaire has given a tacky, over-the-top makeover. The neighbours call it '
                '"CRYPTO CASTLE", but it is a real San Francisco house, NOT a castle: NO battlements, NO towers, NO turrets, NO Gothic arches, NO banners, NO stone blocks. '
                'Crisp white-painted wood siding with cream classical trim, fluted pilasters, and a deep bracketed cornice; two big three-sided bay windows, '
                'one on each side, rising through the first and second floors, their old sashes re-glazed with shiny gold-tinted mirror glass that reflects the deep blue sky and white clouds (and a few Victorian houses across the street) with a gold tint; '
                'a long black LED ticker band wrapping across the whole facade between the first and second floors, glowing with bright green candlestick charts and green up-arrows; '
                'in the middle of the second floor, between the bays, a big bold painted mural of a grinning cartoon robot with glowing red laser beams shooting from its eyes (no real logos, no real people, no text); '
                'on the roof, a sleek modern glass-box penthouse grafted on top behind the cornice, with gold-tinted glass and a thin black frame, '
                'spanning the FULL width of the house from the left edge to the right edge, its flat black roof edge forming the top edge of the image, so NO sky shows anywhere, not even in the corners; '
                'at street level in the centre, a short flight of white marble steps up to a glossy black double front door under a classical columned portico, '
                'a red velvet rope on gold stanchions across the foot of the steps, a security camera over the door, and a shiny gold robot statue with bull horns standing beside the steps; '
                'a big gold sign on the portico reading "CRYPTO CASTLE". The bays, the cornice, the portico and the statue '
                'cast crisp, deep blue-violet shadows to the lower right. Cool, clear midday light: the white paint stays crisp cool white in the sun and lavender-blue in shade, '
                'and only the glass and gold fittings are gold, with no warm golden haze. Bright, sunny and funny, readable at a glance from across the street: a gracious old house wearing a gold chain.',
 'drop-phlz': 'A third-wave coffee bar called "PHLZ COFFEE" on the ground floor of a narrow two-storey Edwardian building painted deep forest green with cream trim '
              'and a bracketed cream cornice along the top. Ground floor: tall black steel-framed shop windows showing a gleaming espresso machine, pour-over stands, '
              'minimalist wooden shelves of coffee bags and hanging plants; a glass door in the middle; a small hanging blade sign; a clean cream sans-serif sign '
              'reading "PHLZ COFFEE" on the green fascia; a blank chalkboard A-frame by the door. Upstairs: two angled bay windows with plants.',
 'drop-barris': 'A boutique fitness studio called "BARRI\'S BOOTCAMP" in a converted two-storey SoMa red-brick warehouse with a simple brick parapet. '
                'Big glass roll-up garage doors across the ground floor and big multi-pane windows upstairs, all glowing with red studio light inside, '
                'with rows of treadmills and dumbbell racks visible; black steel frames and gooseneck lamps; a bold red illuminated channel-letter sign '
                'reading "BARRI\'S BOOTCAMP" across the top. The sunlit brick outside is warm and bright, contrasting with the red glow.',
 'drop-seriesa': 'The street-level base (two storeys) of a downtown art-deco office tower housing an exclusive members-only venture capital club called '
                 '"SERIES A LOUNGE": polished black marble piers and brass trim, a stone band course along the top edge, tall brass double doors in the centre, '
                 'a red velvet rope on brass stanchions, warm amber-lit lounges with leather chairs seen through smoked-glass windows, brass wall lanterns, and '
                 'gold art-deco lettering reading "SERIES A LOUNGE" above the doors. Sunlight glints on the marble and brass.',
 'drop-burrito': 'A beloved Mission District taqueria called "BURRITO SPOT", a two-storey Italianate building painted sunshine yellow with red and teal trim '
                 'and a bracketed cornice on top. A big colourful hand-painted mural on the upper wall between the windows: a giant smiling burrito under an '
                 'Aztec-style sun with marigolds; a red scalloped awning with the sign "BURRITO SPOT"; strings of papel picado over the door; big shop windows '
                 'with a hand-painted menu board and a busy warm-lit counter inside; potted agaves by the door.',
 'drop-ladies-a': 'Four of San Francisco\'s famous Painted Ladies on Postcard Row, side by side as one continuous elevation filling the frame: identical tall narrow '
                  'Queen Anne Victorian row houses, each three storeys with a steep pointed gable, a two-storey angled bay window, ornate gingerbread trim, '
                  'and a stair up to an arched porch and front door. Colours left to right: powder blue, blush pink, butter yellow, mint green, each with cream and '
                  'contrasting accent trim. The triangles between and above the gables are filled with the dark grey slate roof behind them, so NO sky shows.',
 'drop-ladies-b': 'Three of San Francisco\'s famous Painted Ladies on Postcard Row, side by side as one continuous elevation filling the frame: identical tall narrow '
                  'Queen Anne Victorian row houses, each three storeys with a steep pointed gable, a two-storey angled bay window, ornate gingerbread trim, '
                  'and a stair up to an arched porch and front door. Colours left to right: lavender, peach, sky blue, each with cream and contrasting accent trim. '
                  'The triangles between and above the gables are filled with the dark grey slate roof behind them, so NO sky shows.',
}
def run(spec):
    k, _, tag = spec.partition(':')
    name = f'{k}-{tag}' if tag else k
    if os.path.exists(f'{W}/{name}.png'): print(name, 'exists'); return
    full = ('Use your built-in image generation tool to create exactly ONE image, then save/copy the generated PNG into the current directory as '
            f'{name}.png and print its absolute path. Do not write any code or other files. Image prompt: ' + STYLE + FORMAT + 'Building: ' + JOBS[k] +
            ' Landscape 3:2.')
    refs = [x for f in ('style-rank.png', 'style-jump.png', 'style-chaos.png') for x in ('-i', f'{W}/{f}')]
    with open(f'{W}/{name}.log', 'w') as log:
        subprocess.run([os.path.expanduser('~/.local/bin/codex'), 'exec', '--skip-git-repo-check', '-s', 'workspace-write', '-C', W, *refs, '--', full],
                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    print(name, 'ok' if os.path.exists(f'{W}/{name}.png') else 'MISSING', flush=True)
with ThreadPoolExecutor(max_workers=2) as ex: list(ex.map(run, sys.argv[2:] or list(JOBS)))
