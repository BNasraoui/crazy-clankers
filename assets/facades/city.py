import os, subprocess, json, sys
from concurrent.futures import ThreadPoolExecutor
F = os.path.dirname(os.path.abspath(__file__))
BASE = ('A single San Francisco building FRONT ELEVATION for use as a game texture. Perfectly straight-on orthographic elevation, no perspective, '
        'flat even lighting with no cast shadows. The facade FILLS THE ENTIRE IMAGE edge to edge: no sky, no ground, no sidewalk, no neighbouring buildings, '
        'no margins, no border. Bottom edge = where the building meets the sidewalk; top edge = top of the roofline or cornice. '
        'Drawn in EXACTLY the style of the attached references: clean manga/anime ink linework, flat colours with one soft shadow tone, crisp and readable. '
        'NO readable text, NO real brand names or logos (shop signs may show abstract shapes or simple icons only), NO people, NO cars, NO trees in front. Building: ')
# id: (district, size, description)   size: P=portrait 2:3, S=square, L=landscape 3:2
JOBS = {
 # Haight / Alamo (add to the 6 existing Victorians)
 'haight-7': ('haight', 'P', 'Queen Anne Victorian painted coral pink with cream and teal trim, a round corner-turret bay on the right, decorative shingle bands, a stair up to a front door on the left. Three storeys.'),
 'haight-8': ('haight', 'P', 'Italianate Victorian painted sky blue with white trim and gold accents, a slanted bay window on the left over a garage door, bracketed cornice. Three storeys.'),
 'haight-9': ('haight', 'P', 'Stick-Eastlake Victorian painted sage green with burgundy and cream trim, flat front with tall paired windows, ornate gable at the top, recessed entry up stairs. Three storeys.'),
 'haight-10': ('haight', 'P', 'Victorian painted lemon yellow with white trim, a square bay window spanning floors two and three, a vintage clothing shop at street level with a big display window and a purple awning (no text). Three storeys.'),
 # Pacific Heights: grand, wider
 'pac-1': ('pacheights', 'S', 'Grand Pacific Heights Edwardian painted pale grey-blue with white trim, two large bay windows, a classical columned entry porch up wide stairs, a flat roof with a heavy cornice. Four storeys.'),
 'pac-2': ('pacheights', 'S', 'Elegant Queen Anne mansion painted cream with deep green trim, a corner tower bay, a wide arched entry with stairs, a decorative gable. Three storeys.'),
 'pac-3': ('pacheights', 'S', 'Pacific Heights Shingle-style house in warm brown cedar shingles with white trim, a big bay window, a gabled roofline, a garage below. Three storeys.'),
 'pac-4': ('pacheights', 'S', 'Beaux-Arts town house painted soft butter yellow with white stone trim, symmetrical tall windows with iron balconettes, a central doorway. Four storeys.'),
 'pac-5': ('pacheights', 'S', 'Edwardian flats building painted dusty rose with white trim, two stacked bay windows side by side, a central entry with stairs. Four storeys.'),
 'pac-6': ('pacheights', 'S', 'Mediterranean-style house in warm white stucco with a red tile roof edge, arched windows, wrought-iron balconies, a garage door. Three storeys.'),
 # North Beach: dense Italianate apartments with cafes
 'nb-1': ('northbeach', 'P', 'North Beach Italianate apartment building painted pale ochre with cream trim, fire escape on the front, a cafe at street level with an awning and small round tables shown as shapes (no text). Four storeys.'),
 'nb-2': ('northbeach', 'P', 'North Beach Edwardian flats painted pale mint with white trim, bay windows stacked over a deli storefront with a striped green-white-red awning (no text). Four storeys.'),
 'nb-3': ('northbeach', 'P', 'North Beach apartment building painted terracotta orange with cream trim, tall arched windows, iron balconettes, a bakery storefront with a blue awning (no text). Four storeys.'),
 'nb-4': ('northbeach', 'P', 'North Beach Victorian flats painted pale lavender with white trim, two bay windows, an entry door with stairs. Three storeys.'),
 'nb-5': ('northbeach', 'P', 'North Beach Italianate building painted cream with dark green trim, a bracketed cornice, a bookshop at street level with a large display window and a green awning (no text). Four storeys.'),
 'nb-6': ('northbeach', 'P', 'North Beach row building painted salmon pink with white trim, simple flat front with tall windows, a garage door and a narrow entry. Three storeys.'),
 # Nob Hill: grand stone apartments and hotels
 'nob-1': ('nob', 'P', 'Nob Hill Beaux-Arts apartment building in cream limestone, seven storeys, rows of tall windows with stone surrounds, a grand arched entrance with a dark green canopy at street level, a heavy carved cornice.'),
 'nob-2': ('nob', 'P', 'Nob Hill 1920s apartment building in warm beige brick with terracotta ornament, eight storeys, bay windows in vertical columns, a doorman entrance with a burgundy canopy, an ornate top.'),
 'nob-3': ('nob', 'P', 'Nob Hill Art Deco apartment tower in pale stone, seven storeys, vertical piers and setbacks near the top, a decorative bronze entry with a black canopy.'),
 'nob-4': ('nob', 'P', 'Nob Hill grand hotel facade in pale grey stone, six storeys, rows of windows with small iron balconies, a large awning over the entrance, flag poles without flags.'),
 # SoMa: brick warehouses / lofts
 'soma-1': ('soma', 'S', 'SoMa red-brick warehouse loft, five storeys, large industrial steel-framed windows in a grid, a black fire escape zig-zagging down the front, a loading dock door at street level.'),
 'soma-2': ('soma', 'S', 'SoMa converted brick warehouse painted cream with dark trim, four storeys, arched industrial windows, a coffee shop at street level with a black awning (no text).'),
 'soma-3': ('soma', 'S', 'SoMa brown-brick printing factory converted to startup offices, five storeys, tall multi-pane windows, a sleek glass entrance at street level, a rooftop water tank.'),
 'soma-4': ('soma', 'S', 'SoMa grey concrete loft building with large modern windows, four storeys, a roll-up garage door and a bike shop at street level (no text), a fire escape on one side.'),
 # Mission: colourful Edwardians and corner stores, a mural
 'mission-1': ('mission', 'S', 'Mission District Edwardian flats painted bright turquoise with white trim, two bay windows, a taqueria at street level with a colourful papel picado-style awning pattern (no text). Three storeys.'),
 'mission-2': ('mission', 'S', 'Mission District Victorian painted hot pink and yellow trim, a slanted bay window, a front stair with an iron gate. Three storeys.'),
 'mission-3': ('mission', 'S', 'Mission District corner store building painted mustard yellow, two storeys, a bodega at street level with a red awning and produce crates shown as simple shapes (no text), flats above.'),
 'mission-4': ('mission', 'S', 'Mission District building with a big colourful painted mural covering its flat front (abstract sun, flowers and birds, NO words), two storeys, a small door and a garage at street level.'),
 'mission-5': ('mission', 'S', 'Mission District Edwardian painted lime green with purple trim, bay window, a garage door and stairs. Three storeys.'),
 'mission-6': ('mission', 'S', 'Mission District apartment building painted orange with white trim, three storeys, a laundromat at street level with a big window and a blue awning (no text).'),
 # Sunset: stucco with garages (landscape)
 'sunset-1': ('sunset', 'L', 'Outer Sunset stucco house painted pale mint, two storeys, a garage door at street level, a large picture window above with a small decorative Spanish-tile overhang.'),
 'sunset-2': ('sunset', 'L', 'Outer Sunset stucco house painted soft pink, two storeys, a garage at street level, a curved bay window above, a side stair to the entry.'),
 'sunset-3': ('sunset', 'L', 'Outer Sunset stucco house painted pale yellow, two storeys, a garage, a wide window with a geometric deco trim above, a small entry stair.'),
 'sunset-4': ('sunset', 'L', 'Outer Sunset stucco house painted sky blue, two storeys, a garage, a box bay window with white trim above.'),
 # Potrero / industrial mix
 'potrero-1': ('potrero', 'S', 'Potrero Hill cottage-style row house painted dusty teal with white trim, two storeys, a small porch and a garage. Simple and cosy.'),
 'potrero-2': ('potrero', 'S', 'Potrero Hill small brick industrial building, two storeys, big roll-up door and steel windows, a small brewery-style entrance (no text).'),
 'potrero-3': ('potrero', 'S', 'Potrero Hill modern townhouse with vertical wood siding and big windows, three storeys, a garage.'),
 # Downtown towers: tileable middle sections + street-level bases
 'tower-1': ('fidi', 'S', 'A seamlessly vertically TILEABLE section of a downtown glass curtain-wall office tower: a regular grid of blue-grey glass panels with thin silver mullions, showing exactly 4 floors, designed so the top edge matches the bottom edge when repeated.'),
 'tower-2': ('fidi', 'S', 'A seamlessly vertically TILEABLE section of an older downtown office tower in pale cream stone: rows of punched windows with dark frames, exactly 4 floors, top edge matches bottom edge when repeated.'),
 'tower-3': ('fidi', 'S', 'A seamlessly vertically TILEABLE section of a modern downtown tower with alternating white horizontal fins and dark glass bands, exactly 4 floors, top edge matches bottom edge.'),
 'tower-4': ('fidi', 'S', 'A seamlessly vertically TILEABLE section of a 1970s downtown tower with bronze-tinted glass and dark bronze vertical piers, exactly 4 floors, top edge matches bottom edge.'),
 'towerbase-1': ('fidi', 'L', 'The street-level base (two storeys) of a downtown office tower: a grand glass lobby entrance with revolving doors, polished granite piers, a slim canopy. No text.'),
 'towerbase-2': ('fidi', 'L', 'The street-level base (two storeys) of a downtown tower: stone arcade with three arches, a cafe inside one arch with outdoor tables as simple shapes (no text).'),
}
SIZE = {'P': 'Portrait 2:3.', 'S': 'Square 1:1.', 'L': 'Landscape 3:2.'}
def run(k):
    d, size, desc = JOBS[k]
    if os.path.exists(f'{F}/city/{k}.png'): print(k, 'exists'); return
    full = ('Use your built-in image generation tool to create exactly ONE image, then save/copy the generated PNG into the current directory as '
            f'{k}.png and print its absolute path. Do not write any code or other files. Image prompt: ' + BASE + desc + ' ' + SIZE[size])
    with open(f'{F}/city/{k}.log', 'w') as log:
        subprocess.run(['codex', 'exec', '--skip-git-repo-check', '-s', 'workspace-write', '-C', f'{F}/city',
                        '-i', f'{F}/ref-facade.png', '-i', f'{F}/ref-jump.png', '--', full],
                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    print(k, 'ok' if os.path.exists(f'{F}/city/{k}.png') else 'MISSING', flush=True)
json.dump({k: [v[0], v[1]] for k, v in JOBS.items()}, open(f'{F}/city/manifest.json', 'w'), indent=1)
ids = sys.argv[1:] or list(JOBS)
with ThreadPoolExecutor(max_workers=2) as ex: list(ex.map(run, ids))
