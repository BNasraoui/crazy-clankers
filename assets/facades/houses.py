# Third pass (2026-10-02): every district house and downtown tile redrawn in the drop-off recipe (drops.py).
#   python3 houses.py <workdir> [id[:tag] ...]   -> <workdir>/<id>[-tag].png
# <workdir> must hold style-*.png, the key-art crops (see README). Descriptions are city.py's, plus v1-v6 described
# from their first-pass drawings.
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
W = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else ''
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
          'Anything that would break the roofline (gables, turrets) stays inside the frame and is backed by the roof behind it, so no sky shows in the corners. '
          'NO readable text or lettering anywhere (shop signs show simple pictograms or abstract shapes only); NO real brand logos; NO people, NO cars, NO trees in front. ')
TILE = ('Composition: a perfectly straight-on orthographic elevation of a MIDDLE section of a tall downtown San Francisco office tower, for use as a texture '
        'that REPEATS VERTICALLY on a skyscraper: it shows exactly FOUR identical storeys stacked, each exactly one quarter of the image height, every storey drawn the same, '
        'with the image cut through the same point of the floor rhythm at the top and at the bottom edge so that the top edge matches the bottom edge seamlessly when tiled. '
        'The facade fills the entire image edge to edge; no roof, no ground, no sky around it, no neighbouring buildings, no text, no people. '
        'Light: the same bright high-noon sun from the upper left on every storey; the glass reflects deep blue sky and soft white clouds as broad diagonal streaks, '
        'never a sunset. ')
SIZE = {'P': 'Portrait 2:3.', 'S': 'Square 1:1.', 'L': 'Landscape 3:2.'}
# id: (size, description)   size: P=portrait 2:3 (640x960), S=square (768x768), L=landscape 3:2 (960x640); tower tiles are S (512x512)
JOBS = {
 # Haight / Alamo Victorians
 'v1': ('P', 'Italianate Victorian row house painted mint green with cream trim, a slanted bay window on the left on both upper floors, a bracketed cornice, a narrow front door on the right under a pedimented hood at the top of a short stair. Three storeys.'),
 'v2': ('P', 'Stick-Eastlake Victorian painted butter yellow with teal and cream trim, a decorative gable with a sunburst panel along the top, a deep arched entry porch on the left up a teal stair, square bay windows stacked on the right. Three storeys.'),
 'v3': ('P', 'Italianate Victorian flats painted slate blue with cream trim, a flat front with three columns of tall windows with bracketed hoods, a bracketed cornice, a garage door and a narrow side door at street level. Three storeys.'),
 'v4': ('P', 'Edwardian painted brick red with cream trim, a big round bay window on the right rising through the two upper floors over a garage door, an arched front door on the left. Three storeys.'),
 'v5': ('P', 'Italianate Victorian painted lavender with deep purple and cream trim, tall slanted bay windows stacked on the right, arched windows with hoods on the left, a stair with a black iron railing up to a recessed front door. Three storeys.'),
 'v6': ('P', 'Queen Anne Victorian painted peach with sage green and cream trim, a corner bay with shingle bands on the left, a pediment gable with a sunburst along the top, a stair up to a porch on the right. Three storeys.'),
 'haight-7': ('P', 'Queen Anne Victorian painted coral pink with cream and teal trim, a round corner-turret bay on the right, decorative shingle bands, a stair up to a front door on the left. Three storeys.'),
 'haight-8': ('P', 'Italianate Victorian painted sky blue with white trim and gold accents, a slanted bay window on the left over a garage door, bracketed cornice. Three storeys.'),
 'haight-9': ('P', 'Stick-Eastlake Victorian painted sage green with burgundy and cream trim, flat front with tall paired windows, ornate gable at the top, recessed entry up stairs. Three storeys.'),
 'haight-10': ('P', 'Victorian painted lemon yellow with white trim, a square bay window spanning floors two and three, a vintage clothing shop at street level with a big display window showing colourful dresses on mannequins and a purple awning. Three storeys.'),
 # Pacific Heights: grand, wider
 'pac-1': ('S', 'Grand Pacific Heights Edwardian painted pale powder blue with white trim, two large bay windows, a classical columned entry porch up wide stairs, a flat roof with a heavy cornice. Four storeys.'),
 'pac-2': ('S', 'Elegant Queen Anne mansion painted cream with deep green trim, a corner tower bay, a wide arched entry with stairs, a decorative gable. Three storeys.'),
 'pac-3': ('S', 'Pacific Heights Shingle-style house in warm honey-brown cedar shingles with white trim, a big bay window, a gabled roofline, a garage below. Three storeys.'),
 'pac-4': ('S', 'Beaux-Arts town house painted soft butter yellow with white stone trim, symmetrical tall windows with iron balconettes, a central doorway. Four storeys.'),
 'pac-5': ('S', 'Edwardian flats building painted dusty rose with white trim, two stacked bay windows side by side, a central entry with stairs. Four storeys.'),
 'pac-6': ('S', 'Mediterranean-style house in warm white stucco with a red tile roof edge, arched windows, wrought-iron balconies, a garage door. Three storeys.'),
 # North Beach: dense Italianate apartments with cafes
 'nb-1': ('P', 'North Beach Italianate apartment building painted pale ochre with cream trim, a black fire escape on the front, a cafe at street level with a striped awning and small round bistro tables. Four storeys.'),
 'nb-2': ('P', 'North Beach Edwardian flats painted pale mint with white trim, bay windows stacked over a deli storefront with a striped green-white-red awning and hanging salamis in the window. Four storeys.'),
 'nb-3': ('P', 'North Beach apartment building painted terracotta orange with cream trim, tall arched windows, iron balconettes with flower pots, a bakery storefront with a blue awning and bread in the window. Four storeys.'),
 'nb-4': ('P', 'North Beach Victorian flats painted pale lavender with white trim, two bay windows, an entry door with stairs. Three storeys.'),
 'nb-5': ('P', 'North Beach Italianate building painted cream with dark green trim, a bracketed cornice, a bookshop at street level with a large display window full of books and a green awning. Four storeys.'),
 'nb-6': ('P', 'North Beach row building painted salmon pink with white trim, simple flat front with tall windows, a garage door and a narrow entry. Three storeys.'),
 # Nob Hill: grand stone apartments and hotels
 'nob-1': ('P', 'Nob Hill Beaux-Arts apartment building in warm cream limestone, seven storeys, rows of tall windows with stone surrounds, a grand arched entrance with a dark green canopy at street level, a heavy carved cornice.'),
 'nob-2': ('P', 'Nob Hill 1920s apartment building in warm beige brick with terracotta ornament, eight storeys, bay windows in vertical columns, a doorman entrance with a burgundy canopy, an ornate top.'),
 'nob-3': ('P', 'Nob Hill Art Deco apartment tower in pale warm sandstone, seven storeys, vertical piers and setbacks near the top (backed by the building, no sky), a decorative bronze entry with a black canopy.'),
 'nob-4': ('P', 'Nob Hill grand hotel facade in pale honey-cream stone, six storeys, rows of windows with small iron balconies, a large red awning over the entrance, flag poles without flags.'),
 # SoMa: brick warehouses / lofts
 'soma-1': ('S', 'SoMa red-brick warehouse loft, five storeys, large industrial steel-framed windows in a grid, a black fire escape zig-zagging down the front, a loading dock door at street level.'),
 'soma-2': ('S', 'SoMa converted brick warehouse painted cream with dark trim, four storeys, arched industrial windows, a coffee shop at street level with a black awning.'),
 'soma-3': ('S', 'SoMa brown-brick printing factory converted to startup offices, five storeys, tall multi-pane windows, a sleek glass entrance at street level, a rooftop water tank backed by the brick parapet (no sky).'),
 'soma-4': ('S', 'SoMa concrete loft building painted warm sand beige with big modern black-framed windows, four storeys, a roll-up garage door and a bike shop at street level with bikes in the window, a fire escape on one side.'),
 # Mission: colourful Edwardians and corner stores, a mural
 'mission-1': ('S', 'Mission District Edwardian flats painted bright turquoise with white trim, two bay windows, a taqueria at street level with strings of colourful papel picado over a striped awning. Three storeys.'),
 'mission-2': ('S', 'Mission District Victorian painted hot pink with yellow trim, a slanted bay window, a front stair with an iron gate. Three storeys.'),
 'mission-3': ('S', 'Mission District corner store building painted mustard yellow, two storeys, a bodega at street level with a red awning and crates of colourful fruit and vegetables out front against the wall, flats above.'),
 'mission-4': ('S', 'Mission District building with a big colourful painted mural covering its flat front (a radiant sun, poppies, marigolds and flying birds, NO words), two storeys, a small door and a garage at street level.'),
 'mission-5': ('S', 'Mission District Edwardian painted lime green with purple trim, bay window, a garage door and stairs. Three storeys.'),
 'mission-6': ('S', 'Mission District apartment building painted orange with white trim, three storeys, a laundromat at street level with a big window showing rows of washing machines and a blue awning.'),
 # Sunset: stucco with garages
 'sunset-1': ('L', 'Outer Sunset stucco house painted pale mint, two storeys, a garage door at street level, a large picture window above with a small decorative Spanish-tile overhang.'),
 'sunset-2': ('L', 'Outer Sunset stucco house painted soft pink, two storeys, a garage at street level, a curved bay window above, a side stair to the entry.'),
 'sunset-3': ('L', 'Outer Sunset stucco house painted pale yellow, two storeys, a garage, a wide window with a geometric deco trim above, a small entry stair.'),
 'sunset-4': ('L', 'Outer Sunset stucco house painted sky blue, two storeys, a garage, a box bay window with white trim above.'),
 # Potrero
 'potrero-1': ('S', 'Potrero Hill cottage-style row house painted dusty teal with white trim, two storeys, a small porch and a garage. Simple and cosy.'),
 'potrero-2': ('S', 'Potrero Hill small red-brick industrial building, two storeys, big roll-up door and steel windows, a small brewery taproom entrance with barrels by the door.'),
 'potrero-3': ('S', 'Potrero Hill modern townhouse with warm vertical cedar wood siding and big black-framed windows, three storeys, a garage.'),
 # Downtown: vertically tiling tower sections and street-level bases
 'tower-1': ('T', 'A glass curtain-wall office tower: a regular grid of glass panels tinted sky blue with thin silver mullions and a slim silver spandrel band at each floor line.'),
 'tower-2': ('T', 'An older 1920s office tower in warm cream terracotta stone: rows of punched windows with dark green frames and stone sills, slim vertical stone piers.'),
 'tower-3': ('T', 'A modern tower with crisp white horizontal sunshade fins at each floor line over bands of blue-reflecting glass.'),
 'tower-4': ('T', 'A 1970s tower with warm bronze-tinted glass between dark bronze vertical piers and bronze spandrel panels.'),
 'towerbase-1': ('L', 'The street-level base (two storeys) of a downtown office tower: a grand double-height glass lobby with revolving doors, polished warm granite piers, a slim steel canopy, potted plants and a bright lobby inside. A stone band course along the top edge.'),
 'towerbase-2': ('L', 'The street-level base (two storeys) of a downtown tower: a warm cream stone arcade with three tall arches, a cafe inside one arch with little bistro tables and potted olive trees, glass shopfronts in the others. A stone band course along the top edge.'),
}
def run(spec):
    k, _, tag = spec.partition(':')
    name = f'{k}-{tag}' if tag else k
    if os.path.exists(f'{W}/{name}.png'): print(name, 'exists'); return
    size, desc = JOBS[k]
    body = (TILE + 'Tower: ' + desc + ' Square 1:1.') if size == 'T' else (FORMAT + 'Building: ' + desc + ' ' + SIZE[size])
    full = ('Use your built-in image generation tool to create exactly ONE image, then save/copy the generated PNG into the current directory as '
            f'{name}.png and print its absolute path. Do not write any code or other files. Image prompt: ' + STYLE + body)
    refs = [x for f in ('style-rank.png', 'style-jump.png', 'style-chaos.png') for x in ('-i', f'{W}/{f}')]
    with open(f'{W}/{name}.log', 'w') as log:
        subprocess.run([os.path.expanduser('~/.local/bin/codex'), 'exec', '--skip-git-repo-check', '-s', 'workspace-write', '-C', W, *refs, '--', full],
                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    print(name, 'ok' if os.path.exists(f'{W}/{name}.png') else 'MISSING', flush=True)
if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=2) as ex: list(ex.map(run, sys.argv[2:] or list(JOBS)))
