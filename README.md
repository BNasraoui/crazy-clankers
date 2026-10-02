# Crazy Clankers

A Crazy Taxi-style arcade game where you play the robotaxi. Three.js + TypeScript + Vite.

    npm install
    npm run dev      # http://localhost:5173 (--host, so it's reachable from a Steam Deck on your network)
    npm run build    # static site in dist/

Controls: RT/W gas, LT/S brake and reverse, stick or A/D steer, B/RB/Space drift, Start/Esc pause.

- `src/lines/`: every passenger's (and the cab's) lines, English and Chinese, one file per speaker. Edit freely; `src/quips.ts` decides when they're said.
- `src/names.ts`: the parody names each passenger type draws from.
- `src/i18n.ts`: every other on-screen string in English and Simplified Chinese, looked up with `t('key')`.
- `src/passengers.ts`: passenger types, odds and fare and tip rules.
- `src/world.ts`: the map (hills, blocks, landmarks).
- `src/car.ts`: driving physics constants.

## 3D assets

Models are built by Python scripts in `assets/blender/` (no `.blend` files are committed) and
exported to `public/models/*.glb`, with turntable previews in `docs/renders/`. Built with
**Blender 5.2.2 LTS**.

Install Blender without sudo if `blender` isn't on your PATH:

    mkdir -p ~/.local/opt ~/.local/bin
    curl -LO https://download.blender.org/release/Blender5.2/blender-5.2.2-linux-x64.tar.xz
    tar -xJf blender-5.2.2-linux-x64.tar.xz -C ~/.local/opt
    mv ~/.local/opt/blender-5.2.2-linux-x64 ~/.local/opt/blender-5.2.2
    ln -sf ~/.local/opt/blender-5.2.2/blender ~/.local/bin/blender

Rebuild everything (deterministic; same input gives byte-identical output):

    assets/blender/build.sh          # or BLENDER=/path/to/blender assets/blender/build.sh

- `common.py`: flat materials, mesh builder, glTF export, toon preview renderer.
- `cab.py`: `cab` > `body`, `lidar`, `wheel_FL/FR/RL/RR` (left = +X, the driver's left; cab faces +Z).
- `robotaxis.py`: parody robotaxis from Sketchfab models (see `docs/CREDITS.md`), built with
  `build.sh robotaxis`. `fetch_sources.py` downloads the sources into the git-ignored
  `assets/blender/sources/` using a Sketchfab API token in `~/.config/sketchfab/token`.
  - `wayfarer` (Waymo-style, from a Jaguar I-PACE) > `body`, `lidar` (spins about Y),
    `wheel_FL/FR/RL/RR`. 4.68 m long, wheel radius 0.418 m, axles at z = ±1.501, track x = ±0.805.
  - `cybercab` (Cybercab-style two-seater) > `body`, `wheel_FL/FR/RL/RR`. 4.41 m long, wheel
    radius 0.37 m, axles at z = ±1.27, track x = ±0.84.
  Each is under 12,000 triangles, uses flat role materials only (`light_*` are drawn unlit), and
  carries no logos, badges, model names or licence plates.
- `sheet_robotaxis.py`: robotaxis with no source model, built from scratch off the turnaround
  sheets in `docs/art/vehicles/` with `build.sh sheet-robotaxis`. The bodies are lofted through
  cross-section rings measured off the sheets, scaled by `calibrations/<car>.json`. Each build
  is scored against its sheet's front, side, back and top views with `sheets.py` (silhouette
  IoU at least 0.9, written to `reviews/<car>-fit.json` and `docs/renders/<car>-fit-*.png`).
  The build also renders all four robotaxis at one scale in `docs/renders/robotaxis-four.png`.
  - `zoox` (Zoox-style, identical at both ends) > `body`, `lidar` (the front-left roof pod's
    puck), `wheel_FL/FR/RL/RR`. 3.75 × 1.81 × 1.85 m, wheel radius 0.355 m, axles at
    z = ±1.43, track x = ±0.79. Adds a `sand` role (the khaki lower body and fenders) and an
    `amber` one (side markers). Both ends carry the white light bar; the lamps at the back
    (+Z is front) are `light_tail`.
  - `apollo` (Apollo RT6-style minivan) > `body`, `lidar` (the crown dome), `wheel_FL/FR/RL/RR`.
    4.44 m long, 1.81 m wide (2.06 m over the mirrors), 1.75 m to the roof and 2.07 m over the
    dome; wheel radius 0.345 m, axles at z = ±1.394, track x = ±0.79.
  Both are under 14,000 triangles.
- `techbro.py`: `techbro` > `legs`, `torso`, `head`, `arm_L`, `arm_R` > `cup`. `arm_R` is at +X so
  the game's wave (`rotation.z = 2.6`) raises it outwards.

Conventions: metres, +Y up, facing +Z, origin on the ground. Materials are plain base colours
(metallic 0, roughness 1, no textures) named by role; the game supplies toon shading and outlines.
Check a model with `npx --yes @gltf-transform/cli inspect public/models/cab.glb`.
