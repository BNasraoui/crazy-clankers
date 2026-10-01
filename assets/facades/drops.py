import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
F = os.path.dirname(os.path.abspath(__file__))
BASE = ('A single San Francisco building FRONT ELEVATION for use as a game texture. Perfectly straight-on orthographic elevation, no perspective, '
        'flat even lighting with no cast shadows. The facade FILLS THE ENTIRE IMAGE edge to edge: no sky, no ground, no sidewalk, no neighbouring buildings, '
        'no margins, no border. Bottom edge = where the building meets the sidewalk; top edge = top of the roofline or cornice. '
        'Drawn in EXACTLY the style of the attached references: clean manga/anime ink linework, flat colours with one soft shadow tone, crisp and readable. '
        'This is a one-of-a-kind, instantly recognisable landmark storefront in a satirical San Francisco tech comedy game. '
        'Match the warm, sunny, pastel palette and the simple clean shapes of the reference facades exactly: no grey, gloomy, gritty or dark rendering, and keep small details sparse. '
        'Apart from the one shop sign named below (spelled exactly), NO other text; NO real brand logos; NO people, NO cars, NO trees in front. Building: ')
JOBS = {
 'drop-lab': 'A cheerful startup headquarters called "THE LAB" in a two-storey SoMa brick warehouse painted warm butter yellow with teal window frames and a white cornice. Big multi-pane factory windows upstairs; on the ground floor one wide roll-up door left open, showing a few whiteboards with simple doodles and a ping-pong table as clean, simple shapes; a teal door; a bold hand-painted sign reading "THE LAB" on a white panel. Simple and uncluttered.',
 'drop-crypto': 'A gaudy San Francisco Queen Anne Victorian mansion that a crypto millionaire has turned into a "castle", called "CRYPTO CASTLE", three storeys: cream paint with lots of shiny gold trim, a round corner turret with a gold conical roof, a crenellated parapet added along the roofline, a gold portcullis-style front door at the top of a stair, two hanging banners with a simple orange coin symbol (no real logos), and a gold sign reading "CRYPTO CASTLE". Sunny, bright, cheerful and a bit ridiculous.',
 'drop-phlz': 'A third-wave coffee bar called "PHLZ COFFEE" on the ground floor of a narrow two-storey Edwardian building painted deep forest green with cream trim. Tall steel-framed windows showing a gleaming espresso machine, pour-over stands and minimalist wooden shelves; a hanging blade sign and a clean sans-serif sign reading "PHLZ COFFEE"; a chalkboard A-frame by the door (blank). Upstairs: two tall bay windows with plants.',
 'drop-barris': 'A boutique fitness studio called "BARRI\'S BOOTCAMP" in a converted SoMa brick warehouse, two storeys. Big glass roll-up garage doors glowing red inside, with rows of treadmills and dumbbell racks visible as shapes; black steel frames; a bold red illuminated sign reading "BARRI\'S BOOTCAMP" across the top.',
 'drop-seriesa': 'The street-level base (two storeys) of a downtown office tower housing an exclusive members-only venture capital club called "SERIES A LOUNGE": black marble and brass, tall brass double doors, a velvet rope on brass stanchions, warm amber light through smoked-glass windows, gold art-deco lettering reading "SERIES A LOUNGE" above the doors.',
 'drop-lab-old': 'A scrappy startup headquarters called "THE LAB" in a small SoMa light-industrial building, two storeys, corrugated metal and painted concrete in grey with a safety-orange stripe. A half-open roll-up door showing whiteboards covered in diagrams, server racks with blinking lights, beanbags and a ping-pong table as shapes; a hand-painted sign reading "THE LAB"; a row of electric scooters parked outside as simple shapes.',
 'drop-crypto-old': 'A gaudy faux-medieval castle mansion called "CRYPTO CASTLE" squeezed into a San Francisco city lot, three storeys: grey stone blocks, crenellated battlements on top, two small round turrets with gold conical roofs at the corners, a portcullis-style gate as the front door, gold trim everywhere, banners with a generic glowing orange coin symbol (no real logos), stone gargoyles with glowing red laser eyes, and a gold sign reading "CRYPTO CASTLE".',
 'drop-burrito': 'A beloved Mission District taqueria called "BURRITO SPOT", two storeys, painted sunshine yellow with red trim. A huge colourful mural on the upper wall of a giant smiling burrito under an Aztec-style sun with marigolds; strings of papel picado over the door; big windows with a menu board shown as simple shapes; a red awning with the sign "BURRITO SPOT".',
 'drop-ladies-a': 'Four of San Francisco\'s famous Painted Ladies on Postcard Row, side by side as one continuous elevation: identical tall narrow Queen Anne Victorian row houses, each three storeys with a steep pointed gable, a bay window, ornate gingerbread trim and a stair up to the front door. Colours left to right: powder blue, blush pink, butter yellow, mint green, each with cream and contrasting accent trim.',
 'drop-ladies-b': 'Three of San Francisco\'s famous Painted Ladies on Postcard Row, side by side as one continuous elevation: identical tall narrow Queen Anne Victorian row houses, each three storeys with a steep pointed gable, a bay window, ornate gingerbread trim and a stair up to the front door. Colours left to right: lavender, peach, sky blue, each with cream and contrasting accent trim.',
}
def run(k):
    if os.path.exists(f'{F}/city/{k}.png'): print(k, 'exists'); return
    full = ('Use your built-in image generation tool to create exactly ONE image, then save/copy the generated PNG into the current directory as '
            f'{k}.png and print its absolute path. Do not write any code or other files. Image prompt: ' + BASE + JOBS[k] + ' Landscape 3:2.')
    with open(f'{F}/city/{k}.log', 'w') as log:
        subprocess.run(['codex', 'exec', '--skip-git-repo-check', '-s', 'workspace-write', '-C', f'{F}/city',
                        '-i', f'{F}/ref-facade.png', '-i', f'{F}/ref-jump.png', '-i', f'{F}/city/drop-burrito.png', '-i', f'{F}/city/nb-3.png', '--', full],
                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    print(k, 'ok' if os.path.exists(f'{F}/city/{k}.png') else 'MISSING', flush=True)
ids = sys.argv[1:] or list(JOBS)
with ThreadPoolExecutor(max_workers=2) as ex: list(ex.map(run, ids))
