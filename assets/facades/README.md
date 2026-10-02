# Facade drawings

How the painted facades in public/facades/ were made (first pass, 2026-10-01).

- `city.py`: the district house facades and downtown tower tiles. `drops.py`: the one-off drop-off buildings.
  Both call `codex exec` with its built-in image generation tool, with reference images attached via `-i`,
  and save `<id>.png` into a working folder (`city/` next to the script in the original run).
- `process.py`: crops, resizes and writes `public/facades/<id>.jpg`, then rebuilds `public/facades/manifest.json`
  (per drawing: district, kind, the body colour `wall` used for the building box, and the bottom-strip colour `base`
  used for the foundation band on slopes). `kind` comes from the id prefix: tower- = tile, towerbase = towerbase,
  drop- = drop, otherwise house.
- `refs/ref-facade.jpg`: the elevation reference that every drawing was given. Its flat, architectural-drawing look
  is a big part of why the drawings came out flatter than the key art.
- `refs/drop-*-old.jpg` and `refs/drop-lab.jpg`, `refs/drop-crypto.jpg`: two rounds of The Lab and Crypto Castle,
  both rejected by Ben for not matching the key art's style.

Paths in `city.py` and `process.py` point at the original scratch folder; adjust them before reuse.

## Second pass: drop-offs (2026-10-01)

All eight drop-off drawings were redrawn to match the key art. `refs/pass2/` has before/after pairs and `in-game.jpg`.

- `drops.py <workdir> id[:tag] ...` now attaches crops of the key art's buildings as the only style reference
  (`style-rank.png` = rank.jpg (860,0)-(1920,620), `style-jump.png` = jump.jpg (1400,0)-(1920,1050),
  `style-chaos.png` = chaos.jpg (1050,0)-(1920,420)); `ref-facade.jpg` is no longer given.
- The prompt asks for an anime background painting with ink lines, high-noon sun from the upper left, cast shadows
  under every projection, blue-sky reflections in the glass, and says what to avoid (vector clip art, CAD elevation,
  3D render, golden hour). The old prompt's "flat even lighting with no cast shadows" was the main cause of the flat look.
- Anything breaking the roofline is kept inside the frame: the castle's towers rise flush with the parapet and the
  gaps between merlons are backed by a stone wall; the Painted Ladies' gables sit against the slate roof behind.
- `process_drops.py <workdir> public/facades` trims the odd sliver of sky or sidewalk, keeps 3:2, writes 960x640 JPEGs
  and updates only the drop entries of `manifest.json`.

## Crypto Castle redo (2026-10-02)

Ben: "Crypto Castle should NOT be a castle." Satirical drop-offs are real San Francisco building types gone wrong, so
Crypto Castle is now a white Pacific Heights Edwardian mansion after a crypto bro's makeover (gold mirror glass in the
bays, an LED candlestick ticker, a laser-eyed robot-bull mural, a glass penthouse, a velvet rope and a gold statue).
"CRYPTO CASTLE" is what the neighbours call it. Same recipe as the second pass; the prompt says outright that it is
not a castle, and asks for cool midday light so the white paint and gold glass don't drift into golden hour.
Pick: `drop-crypto-b1.png` from the fourth of four tries. `wall` was sampled by hand from the sunlit siding,
because body_colour picks the shaded blue. `process_drops.py` now takes optional ids, so a single drawing can be
reprocessed. `refs/crypto-redo/` has the before/after and the in-game shot.

## Web formats (2026-10-02)
The game loads **AVIF** images and **meshopt-compressed** models, not the JPG/PNG and plain GLB the scripts here produce.
After writing new art into `public/`, run `scripts/avif.sh` (converts every JPG/PNG under `public/` to AVIF at quality 60
and removes the original) and compress new models with `npx @gltf-transform/cli meshopt in.glb out.glb`.

## Third pass: the whole city (2026-10-02)
Every district house (v1-v6 and the 37 city.py ids), the four tower tiles and the two lobbies, redrawn with the drop-off
recipe so they sit alongside the drop-offs. `refs/pass3/` has before/after shots per district and `all.jpg`.

- `houses.py <workdir> [id[:tag] ...]`: drops.py's style prompt and key-art crops, city.py's descriptions (v1-v6 written
  from their first-pass drawings, a few colours warmed up, "no text" shopfronts given pictograms or goods in the window).
  One try each was enough; every drawing was kept.
- `process_houses.py <workdir> public/facades [id ...]` (needs Pillow >= 11.3 for AVIF, plus numpy): trims the line of
  sky most drawings have along the top and the sidewalk strips listed in `BOTTOM`, crops to the size class, writes AVIF
  at quality 60 and updates `wall`/`base` (`WALL` overrides six where body_colour picked trim, a door or a shopfront).
- Tower tiles: the drawings show four storeys but only roughly repeat, so the crop is placed where the line just past
  each edge matches the first line on the opposite edge (vertically held to four measured storeys), then a short fade
  hides the rest. Stacking 2x2 copies shows no seam.
- `district-shots.mjs <outdir> [port]` screenshots each district (shots.mjs's camera recipe).
