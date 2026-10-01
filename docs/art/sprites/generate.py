import os, subprocess
from concurrent.futures import ThreadPoolExecutor
P = os.path.dirname(os.path.abspath(__file__))
TYPES = {
 'jogger': 'a lean jogger in a neon-yellow running top, black shorts, a headband and wireless earbuds',
 'dogwalker': 'a woman in a cream puffer jacket and leggings walking a tiny white fluffy dog on a lead',
 'scooter': 'a young guy in a grey hoodie and joggers carrying a folded electric scooter',
 'tourist': 'a sunburnt tourist in a Hawaiian shirt, cargo shorts and a sun hat, with a camera on a strap',
 'hippie': 'an old Haight-Ashbury hippie with a grey ponytail, round sunglasses, a tie-dye shirt and flared jeans',
 'courier': 'a food-delivery courier in a green cap and jacket with a big insulated delivery backpack',
}
PROMPT = ('Character sprite sheet for a 2D-sprites-in-3D arcade game (like Paper Mario or Octopath Traveler). '
 'One character, {desc}. Clean early-2000s anime line art: bold even black outlines, flat colour fills with a single soft shadow tone, '
 'natural friendly proportions, matching the people in the attached style reference. '
 'EXACTLY FIVE poses in ONE horizontal row of five equal-width cells, all at the same scale, all standing on the same baseline, '
 'with generous empty space between cells and nothing overlapping cell borders. Left to right: '
 '(1) FRONT view standing relaxed; (2) BACK view standing; (3) RIGHT-facing side view, walking, left leg forward; '
 '(4) RIGHT-facing side view, walking, right leg forward; (5) DIVING to the right in a panicked full-body leap, arms flung out, shocked face. '
 'Pure flat white background, no ground, no shadows, no text, no labels, no borders, no brand logos. 16:9 landscape.')
def run(t):
    name = f'ped-{t}'
    full = ('Use your built-in image generation tool to create exactly ONE image, then save/copy the generated PNG into the current directory as '
            f'{name}.png and print its absolute path. Do not write any code or other files. Image prompt: ' + PROMPT.format(desc=TYPES[t]))
    with open(f'{P}/out/{name}.log', 'w') as log:
        subprocess.run(['codex', 'exec', '--skip-git-repo-check', '-s', 'workspace-write', '-C', f'{P}/out', '-i', f'{P}/style.jpg', '--', full],
                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    print(name, 'ok' if os.path.exists(f'{P}/out/{name}.png') else 'MISSING', flush=True)
with ThreadPoolExecutor(max_workers=6) as ex: list(ex.map(run, TYPES))
