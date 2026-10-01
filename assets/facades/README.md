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

Paths in the scripts point at the original scratch folder; adjust them before reuse.
