import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
P = os.path.dirname(os.path.abspath(__file__))
R = os.path.expanduser('~/crazy-clankers-wt')
C = {
 'techbro': ('a handsome slim young man: messy wavy brown hair, smug toothy grin; navy fleece vest worn OPEN over a buttoned light-blue oxford shirt hanging untucked, sleeves rolled; slim khaki chinos; chunky white sneakers', 'holding an iced cold brew in a clear plastic cup with a black straw'),
 'cmo': ('a stylish young woman: very long straight black hair, lash extensions, gold hoop earrings, playful wink; pink cropped tank top; olive cargo pants; chunky white-and-pink sneakers; small black shoulder bag', 'holding a pink smartphone up for a selfie'),
 'ceo': ('a lean man in his fifties: grey slicked-back hair, furious shouting face with a forehead vein; black turtleneck; charcoal trousers with a black belt; black leather shoes', 'pointing aggressively'),
 'founder': ('a scruffy young man: messy curly dark-brown hair, big hopeful grin; oversized orange hoodie; loose blue jeans; beige sneakers', 'clutching a stack of stock certificates'),
 'sweater': ('a small slim man: neat short black hair, round glasses, calm earnest closed-eye smile; grey crewneck sweater with a white collar; navy trousers; white sneakers', 'hands clasped politely'),
 'rocket': ('a tall man: short dark swept hair, confident smirk; black t-shirt under a black jacket; black jeans; black boots', 'holding a white toy rocket with red fins'),
 'safety': ('a slim young man: curly brown hair, black glasses, worried expression; blue crewneck sweater over a white collared shirt; brown chinos; grey sneakers', 'holding a very long printed report'),
}
def run(cid):
    desc, prop = C[cid]
    name = f'pax-{cid}'
    prompt = (f'Character sprite sheet for a 2D-sprites-in-3D arcade taxi game. One character: {desc}. '
      'The attached images are this character\'s approved model sheet and portrait: match the face, hair, outfit, colours, proportions and drawing style EXACTLY. '
      'Clean early-2000s anime line art: bold even black outlines, flat colour fills with a single soft shadow tone. '
      'EXACTLY FIVE full-body poses in ONE horizontal row of five equal-width cells, all at the same scale, standing on the same baseline, '
      'with generous empty space between cells and nothing overlapping. Left to right: '
      f'(1) FRONT view standing, {prop}; '
      '(2) FRONT view hailing a taxi: one arm raised high above the head, hand open and waving, eager expression; '
      '(3) the same hailing pose with the raised arm tilted the other way (second frame of a waving animation); '
      '(4) RIGHT-facing side view standing; '
      '(5) BACK view standing. '
      'Pure flat white background, no ground, no shadows, no text, no labels, no borders, no brand logos; shoes completely plain with no swooshes, stripes or marks. 16:9 landscape.')
    full = ('Use your built-in image generation tool to create exactly ONE image, then save/copy the generated PNG into the current directory as '
            f'{name}.png and print its absolute path. Do not write any code or other files. Image prompt: ' + prompt)
    with open(f'{P}/out/{name}.log', 'w') as log:
        subprocess.run(['codex', 'exec', '--skip-git-repo-check', '-s', 'workspace-write', '-C', f'{P}/out',
                        '-i', f'{R}/docs/art/turnarounds/{cid}-body.png', '-i', f'{R}/public/portraits/{cid}.jpg', '--', full],
                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    print(name, 'ok' if os.path.exists(f'{P}/out/{name}.png') else 'MISSING', flush=True)
ids = sys.argv[1:] or list(C)
with ThreadPoolExecutor(max_workers=7) as ex: list(ex.map(run, ids))
