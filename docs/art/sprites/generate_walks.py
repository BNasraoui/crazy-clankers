import os, subprocess
from concurrent.futures import ThreadPoolExecutor
P = os.path.dirname(os.path.abspath(__file__))
IDS = ['jogger', 'dogwalker', 'scooter', 'tourist', 'hippie', 'courier']
COMMON = ('The attached image is this character\'s existing sprite sheet: match the character, outfit, colours, proportions, scale and drawing style EXACTLY. '
          'Clean early-2000s anime line art: bold even black outlines, flat colour fills with a single soft shadow tone. '
          'EXACTLY FOUR poses in ONE horizontal row of four equal-width cells, same scale, same baseline, generous empty space between cells, nothing overlapping. '
          'Pure flat white background, no ground, no shadows, no text, no labels, no borders, no brand logos. Shoes are completely plain: a single flat colour with a plain sole, with NO swooshes, NO stripes, NO logos or marks of any kind. 16:9 landscape. ')
SHEETS = {
 'fb': 'Bouncy cartoon walk animation frames, with clearly exaggerated limb motion so the walk reads from far away. Left to right: '
       '(1) FRONT view walking toward the viewer, left leg stepping forward and right arm swinging forward; '
       '(2) FRONT view walking toward the viewer, right leg stepping forward and left arm swinging forward; '
       '(3) BACK view walking away, left leg forward and right arm forward; '
       '(4) BACK view walking away, right leg forward and left arm forward.',
 'side': 'A four-frame RIGHT-facing side-view walk cycle with exaggerated, bouncy cartoon motion. Left to right: '
         '(1) contact: front heel striking, legs wide apart, arms swinging wide; '
         '(2) down: weight on the front leg, knees bent, body lowest; '
         '(3) passing: legs crossing under the body, body upright; '
         '(4) up: pushing off the back foot, body highest, arms swinging the other way.',
}
def run(job):
    pid, kind = job
    name = f'{pid}-{kind}'
    full = ('Use your built-in image generation tool to create exactly ONE image, then save/copy the generated PNG into the current directory as '
            f'{name}.png and print its absolute path. Do not write any code or other files. Image prompt: ' + COMMON + SHEETS[kind])
    with open(f'{P}/out2/{name}.log', 'w') as log:
        subprocess.run(['codex', 'exec', '--skip-git-repo-check', '-s', 'workspace-write', '-C', f'{P}/out2',
                        '-i', f'{P}/out/ped-{pid}.png', '--', full], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    print(name, 'ok' if os.path.exists(f'{P}/out2/{name}.png') else 'MISSING', flush=True)
import sys
jobs = [tuple(a.split(':')) for a in sys.argv[1:]] or [(p, k) for p in IDS for k in SHEETS]
with ThreadPoolExecutor(max_workers=6) as ex: list(ex.map(run, jobs))
