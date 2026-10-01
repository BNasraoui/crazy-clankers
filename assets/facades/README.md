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
