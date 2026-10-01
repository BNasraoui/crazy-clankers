# Passenger pipeline: orthographic turnarounds

Tech Bro v7 is the pilot for building all seven passengers from the approved
[turnaround sheets](turnarounds/README.md). Fit the neutral character first;
pose it only after the measured fit passes. `cast.jpg` supplies the performance
and prop pose. The turnaround front controls widths; its profile controls depths.

## Rebuild the pilot

```sh
assets/blender/build.sh
```

Tested on Blender **5.2.2**, its Python 3.13, numpy 2.3.4 and Pillow 12.3.0.
`BLENDER` overrides the Blender executable. `ASSET_PYTHON` overrides its bundled
Python executable. If Pillow is missing, install it with that Python:

```sh
~/.local/opt/blender-5.2.2/5.2/python/bin/python3.13 -m pip install --user Pillow==12.3.0
```

The default build only rebuilds Tech Bro. It runs numerical and camera tests,
records calibration, exports both GLBs, creates the cel previews, validates the
binaries, then **reimports the neutral GLB** and measures its six silhouettes.
No generation service is required. All source inputs are committed.
`build.sh cab` is a separate, explicit cab rebuild.

To iterate on neutral geometry without posing:

```sh
~/.local/bin/blender --background --factory-startup --python-exit-code 1 \
  --python assets/blender/techbro_v7.py -- fit
```

`-- preview` skips the source-mesh fit during art iteration. Always run the full
build before delivery; its final score describes the exported triangles.

## 1. Calibrate the sheets

Create `assets/blender/calibrations/<id>.json`, using `techbro.json` as the data
schema. Supply the body/head image crops, each view's horizontal axis, camera
viewing direction, screen-right vector, guide-scan strips, and measured anatomical
landmarks. Keep props and labels outside character crops. The configuration also
names the head node and staged prop nodes to exclude from body scoring.

Inspect the actual drawing as well as the guides. These sheets have genuine
cross-view differences: Tech Bro's body hair tips extend above the crown guide;
the shoe soles fall below the sole guide. Several head guides miss the intended
anatomical feature. Record **guide strokes and actual landmarks separately**.

With sheet pixels measured downwards:

```text
metres_per_pixel = character_height / (sole_pixel - crown_pixel)
world_y_at_zero  = sole_pixel * metres_per_pixel
y_metres         = world_y_at_zero - pixel_y * metres_per_pixel
x_metres         = (pixel_x - front_axis) * metres_per_pixel
```

Transfer the head sheet scale using the body's crown-to-chin distance. Do not
independently rescale each view to its own bounding box. Review the directions:
Tech Bro's body profile points right on the page; its head profile points left.
The configuration explicitly uses opposite lateral cameras to match the drawings
as supplied. This discrepancy must not be hidden by an optimizer.

Run the generic calibration audit with a Python containing numpy and Pillow:

```sh
python sheets.py <id> --output reviews/<id>-calibration.json
```

Run that command from `assets/blender/`. `sheets.measure(id)` records source
SHA-256s, detected guide rows, reviewed guides, mask areas, bounding boxes and
metric landmark heights. Adding another passenger requires a reviewed JSON,
not edits to the calibration/camera/scoring functions.

### Tech Bro calibration

Both sheets are 1672 × 941. Body scale is **0.002155689 m/pixel**: 835 pixels
from crown y=21 to sole y=856 represent 1.80 m. Head scale is
**0.000740458 m/pixel**, transferring the body's 124-pixel crown/chin span to
361 head pixels (y=172 to y=533).

| Body landmark | Guide y (px) | Actual landmark y (px) | Height (m) |
| --- | ---: | ---: | ---: |
| Crown | 40.5 | 21 | 1.8000 |
| Eyes | 88.5 | 89 | 1.6534 |
| Chin | 142.0 | 145 | 1.5327 |
| Shoulders | 197.5 | 198 | 1.4184 |
| Waist | 358.5 | 359 | 1.0714 |
| Crotch | 473.5 | 487 | 0.7954 |
| Knees | 619.5 | 620 | 0.5087 |
| Soles | 844.5 | 856 | 0.0000 |

Head guide rows: **213.5, 280.5, 353.5, 392.5, 449.5, 474.5, 525.5**.
Actual head landmarks:

| Landmark | Pixel y | Height (m) |
| --- | ---: | ---: |
| Crown | 172 | 1.8000 |
| Hairline | 270 | 1.7274 |
| Brows | 333 | 1.6808 |
| Eyes | 365 | 1.6571 |
| Nose | 407 | 1.6260 |
| Mouth | 445 | 1.5979 |
| Chin | 533 | 1.5327 |
| Neck | 591 | 1.4897 |

The eye heights differ by 3.7 mm between sheets. The larger head drawing controls
facial placement. Bounding boxes below use exclusive right/bottom coordinates;
head boxes stop at the common chin-plane crop, excluding the bust below it.

| Sheet/view | Foreground bounds `(left, top, right, bottom)` |
| --- | --- |
| Body front | `(86, 21, 580, 857)` |
| Body profile | `(749, 23, 912, 856)` |
| Body back | `(1090, 23, 1569, 856)` |
| Head front | `(36, 172, 376, 534)` |
| Head three-quarter | `(437, 171, 794, 534)` |
| Head profile | `(859, 173, 1244, 534)` |
| Head back | `(1295, 171, 1631, 534)` |

The complete audit is [v6-calibration.json](../../assets/blender/reviews/v6-calibration.json).

## 2. Build the neutral A-pose

Work in metres, game Y up and +Z forward. `anime.g/gv` converts to Blender's Z-up
coordinates. Keep the root between the feet; construct limbs around their future
animation pivots.

Trace front section widths and profile front/rear depths at anatomical and
clothing transitions. Use `head_shape.interpolate_sections` for monotone cubic
interpolation: it passes through the measured landmarks without overshooting.
The original `HeadShape` uses the same helper and retains its regression tests.
`anime_head.py` remains available for passengers that fit its general egg/jaw
surface. Tech Bro needs a more explicit sheet-derived face surface.

For this pilot:

- `techbro_v7.py` constructs neutral trousers, shoes, sleeves and hands from
  measured sections. It adapts the established open vest/shirt construction from
  `techbro.py`; the garment's internal surfaces are decimated to stay in budget.
- Face widths and depths are independent. The profile includes a forehead,
  narrow nose bridge/tip, lips, projecting chin and receding jaw. The nose's
  extra depth is localized around its center rather than applied across the
  whole face. The v7 face receives smooth ellipsoid proxy normals, independent of the
  nose and jaw triangulation, before either GLB is exported.
- Hair has a rounded crown mass with low returning strands and three tiers of
  overlapping rounded side/back clumps tapering to the nape. Ears are 70% of
  the v6 size and tucked in. The fringe antenna is folded into its neighbour. Hair pigment is lighter brown (`#604735`); sparse ink follows each
  curl's own longitudinal UVs.
- Reuse `anime.py` for lofts, cloth shells, coordinate conversion, ordinary
  materials and cel previews. `common.py` and `cab.py` remain unchanged.

Do not add preview hulls or cel emission materials before export. Neither
belongs in the game's ordinary-material GLB.

## 3. Measure the neutral silhouette

`sheets.ortho_camera(id, kind, view)` creates a **zero-elevation**, fixed-scale
camera for the reviewed pixel crop. `test_sheets_blender.py` checks all six
cameras against the analytic projection of a small metric cube, including the
reversed profile direction and rear view.

Reference segmentation retains dark ink and coloured regions, removes pale gray
guides, fills enclosed whites (eyes/shoes), and keeps the largest connected
component in each crop. Review the resulting outlines before trusting a score.
Loose, disconnected source marks are not counted as a character component.

Render the complete body without its separately staged cup. Head scores include
hair and ears, through the common y=534 crop boundary; neck/bust below that plane
is excluded from **both** source and rendered masks. This is a crown-to-chin
window, not semantic removal of every visible neck pixel above that plane.

Render alpha ≥ 0.5 defines the model mask. Compute `intersection / union` at
native crop resolution. No outline dilation, post-render scale, per-view
registration search, or optimistic best-of-several transforms enters the score.
The left panel shows the rendered outline over the original sheet. The right
panel is an XOR/difference: **cyan missing, magenta excess, gray intersection**.

After export, use the same generic scorer on the actual GLB:

```sh
~/.local/bin/blender --background --factory-startup --python-exit-code 1 \
  --python assets/blender/score_sheet_export.py -- techbro \
  --report assets/blender/reviews/v7-fit.json
```

Replace `techbro` with another calibrated passenger; `--model` accepts an
alternate neutral GLB. The report records the scored GLB's SHA-256, and
`test_fit_artifact.py` prevents a stale report from accepting a different asset.
Body views must reach **0.90**, head views **0.88**. Builds fail otherwise.

### Archived v6 exported-GLB fit

| View | Body IoU / overlay | Head IoU / overlay |
| --- | --- | --- |
| Front | [0.9107](../renders/techbro-fit-body-front.png) | [0.8955](../renders/techbro-fit-head-front.png) |
| Right profile | [0.9251](../renders/techbro-fit-body-right.png) | [0.8932](../renders/techbro-fit-head-right.png) |
| Back | [0.9012](../renders/techbro-fit-body-back.png) | [0.8888](../renders/techbro-fit-head-back.png) |

All six pass. The first pass reached 0.9242 / 0.9269 / 0.8658 on the body;
its review artifacts are retained under `reviews/v6-pass1/`. Correcting the
back shirt hem, cuff construction and leg width improved the back fit. Later
head passes replaced a flat crown, localized the nose, exposed the ears, and
refined the projecting curls; [v6-fit.json](../../assets/blender/reviews/v6-fit.json)
contains the final scores.

The registered front/back **reference masks themselves** overlap by only 0.8842.
Their arm angles, trouser gaps and sneaker widths differ. The front remains the
width reference; residual rear differences are visible in the XOR rather than
hidden by changing cameras. Passing IoU does not replace reviewing facial
expression, hair flow, or the native-size gameplay preview.

## 4. Required colour-region fit

After exporting, render **unlit flat material colours** with the same fixed
orthographic cameras, for all body and head views. Run:

```sh
blender -b --factory-startup --python assets/blender/score_diagnostics.py -- <id> \
  --model public/models/<id>-apose.glb --output assets/blender/reviews/<id>-diagnostics
```

`sheets.colour_region_fit` reads the character's data-only `regions.body` and
`regions.head` palettes. Each region supplies reviewed RGB swatches and optional
sheet-pixel row limits. These limits disambiguate white shoes from eyes and dark
vest ink from hair; never fit them to model output. Textured GLB materials use
the most frequent texture pigment as their flat albedo, since their imported
material factor is white. Plain materials retain their base colour.

Segment **both** reference and rendered RGB images by nearest palette swatch,
inside their independently extracted silhouettes. Report intersection/union for
hair, skin, vest, shirt, trousers and shoes in each body view; report hair and
skin in the crown-to-chin head views. Missing regions return null, never a
perfect score. Save the unlit renders and paired colour-labelled masks. Review
those masks before accepting numbers: source ink and painted shading still
introduce classification noise. Do not treat semantic IoU as silhouette IoU.

Compare the previous delivered export with the candidate using identical code
and calibration. Report every region, including regressions. This is a required
review diagnostic, not a new numerical pass threshold.

## 5. Required shadow cleanliness

`sheets.face_shadow_fit` reimports the neutral export and renders front, 35°
three-quarter and profile at **512 × 512**, zero elevation and a fixed
crown/chin-derived orthographic scale. Use the game's N·L step **0.32** and sun
rotation **(40°, 0°, 28°)**. `face_materials` identifies the face surface for any
character; hair, ears and neck remain visible as occluders.

Diagnostic colours encode lit face as yellow, shadow as green and non-face
occluders as blue. Texture ink, cast shadows, outline hulls and AO are absent.
Only visible face pixels below the calibrated hairline and above the chin enter
the mask. Count **8-connected** shadow islands (a diagonal raster edge remains
connected) and the total horizontal/vertical light–shadow edge length in pixels.
Edges against hair, the silhouette or the crop are excluded. No small-component
filtering, dilation or smoothing hides artifacts. Report shadow and face area as
well, so an entirely lit face cannot masquerade as a shading improvement.

Run this on both old and new neutral GLBs. Lower island count and shorter edges
are cleaner only when the preview still has an appropriate shadow shape. Review
the posed head close-ups too: posing changes the head's relation to the light.
Transfer normals from a smooth proxy surface before export when facial topology
creates fragmented shading. Preserve ordinary materials and the transferred
normals in both exports; diagnostics must not repair the imported candidate.

## 6. Transfer facial identity

Extract eyes and brows from the approved front head view; register the
three-quarter grin to the front mouth window. Retain ink/pigment and eye/tooth
whites, replacing illustrated skin and broad lighting with the flat skin albedo.
Bilinear inverse sampling maps those features into a **2048² cylindrical atlas**
using the same measured face width function as the mesh. The seam is at the
back, with per-polygon wrapping. The features foreshorten with the cheek in
profile; there are no camera-facing face planes.

The v4 generated decal remains as an archival input for v4/v5 but is unused by
v6. Other passengers need their own feature regions and grin/eye registration.

## 7. Pose, bake and export

First save `public/models/<id>-apose.glb`. Then shift the pelvis over the weight
leg, relax the free leg, roll the torso, tilt the head, and bend the neutral
sleeve sections along shoulder/elbow/wrist paths. Use new hand articulation for
the cup grip and pocket hand. Bake these deformations into the separate meshes;
keep transforms at their animation pivots.

Both Tech Bro exports retain this contract:

```text
techbro                 root at (0, 0, 0)
├── legs
├── torso
├── head                neck pivot (0, 1.502515, 0)
├── arm_L               shoulder (-0.196168, 1.399042, -0.034491)
└── arm_R               shoulder (+0.196168, 1.399042, -0.034491)
    └── cup
```

The neutral cup is staged separately at `(0.72, 0.19, 0)`, like the sheet's corner
prop, while retaining its `arm_R` parent. It is excluded explicitly from the body
fit. In the posed export it is gripped at `(0.292, 1.39, 0.155)` on +X. There is
no skeleton or animation in either baked export. A later rig can use the A-pose.

## 8. Preview and verify

The shared preview matches the game's cel presentation: a two-tone N·L step at
0.32, sun orientation `(40, 0, 28)`, tinted skin/hair/clothing shadows, and
position-merged inverted hulls displaced by 2.2 actual image pixels. It adds no
PBR lighting, AO, cast shadows or emissive material to the exported asset.

Deliver:

- `techbro.png`: posed front, three-quarter, profile and back.
- `techbro-head.png`: front, three-quarter and profile close-ups.
- `techbro-compare.png`: equal-height cast crop and posed render; reference
  explicitly mirrored for the +X cup contract.
- `techbro-small.png`: native game-size renders, not downsampled close-ups.
- `techbro-fit-{body,head}-{front,right,back}.png`: the six measured overlays.

`techbro-v6-v7-head.png` compares front, three-quarter and profile to the sheet.
`techbro-shoes.png` exposes panel, collar, lace and sole construction.

The older `techbro-head-compare.png` remains the archived v4/v5 comparison; it is
not a v6 acceptance render and is not regenerated by the new build.

Archived v6 budget:

| Export | Triangles | Nodes / meshes | Materials | Textures | Sole-to-crown height |
| --- | ---: | --- | ---: | --- | ---: |
| Posed | 29,776 | 7 / 6 | 15 | 1 × 2048², 5 × 1024² | 1.7973 m |
| A-pose | 29,232 | 7 / 6 | 15 | 1 × 2048², 5 × 1024² | 1.7999 m |

`validate_techbro.py` checks actual GLB positions, indices, unit normals, pivots,
parenting, budgets, embedded PNG sizes and ordinary opaque roughness-1,
metallic-0 materials. Current reports are in `reviews/v7-{apose-,}validation.json`; v6 reports are archived.
Independent glTF Transform inspection is retained in `reviews/v6-inspect.txt`.

Two full rebuilds must give identical hashes for both GLBs, all regenerated renders,
and the cab. Strip Blender timestamp metadata from diagnostic PNGs before saving.
The v7 record is `reviews/v7-rebuild-sha256.json`; the v6 record remains archived. Cab remains
byte-identical to main:

```text
c166f5c3f6e92ebd2c89c72f78c43c830ed1df1bf4c910afdd45353e2e40c33d
```

The pilot still simplifies fine flyaway hair, cloth folds, sneaker panels and
clear-cup optics for the triangle budget and game scale. Review those artistic
tradeoffs in the previews, independently of the silhouette gate.

## v7 acceptance results

Colour-region IoU, **v6 → v7** (same calibration and scorer):

| Region | Front | Profile | Back |
| --- | ---: | ---: | ---: |
| body hair | 0.5572 → 0.5928 | 0.6827 → 0.6972 | 0.8391 → 0.8681 |
| body skin | 0.6185 → 0.6179 | 0.6557 → 0.6684 | 0.5640 → 0.5498 |
| body vest | 0.7360 → 0.7360 | 0.7571 → 0.7571 | 0.8862 → 0.8862 |
| body shirt | 0.6833 → 0.6833 | 0.7279 → 0.7279 | 0.7305 → 0.7305 |
| body trousers | 0.8831 → 0.8822 | 0.8806 → 0.8806 | 0.8766 → 0.8760 |
| body shoes | 0.7709 → 0.7693 | 0.8190 → 0.8338 | 0.6443 → 0.6269 |
| head hair | 0.6552 → 0.6634 | 0.6974 → 0.6820 | 0.8647 → 0.8770 |
| head skin | 0.7631 → 0.7730 | 0.6951 → 0.6793 | 0.4225 → 0.4111 |

Shadow cleanliness, **v6 → v7**, 512px neutral head:

| View | Islands | Edge length (px) | Shadow pixels |
| --- | ---: | ---: | ---: |
| front | 3 → 2 | 522 → 329 | 7350 → 2769 |
| three quarter | 5 → 5 | 403 → 231 | 6390 → 1966 |
| profile | 1 → 1 | 259 → 246 | 10488 → 4910 |

Silhouette IoU, **v6 → v7**:

| View | Body (≥ 0.90) | Head (≥ 0.88) |
| --- | ---: | ---: |
| front | 0.9107 → 0.9130 | 0.8955 → 0.9130 |
| right | 0.9251 → 0.9271 | 0.8932 → 0.8856 |
| back | 0.9012 → 0.9018 | 0.8888 → 0.9091 |

All silhouette gates pass. Colour-region scores reveal remaining internal-shape differences: head-profile hair/skin and some shoe regions regress; these are reported rather than hidden by silhouette acceptance. Shadow islands total 9 → 8 and internal edge length 1,184 → 806 px. Three-quarter island count remains 5; shorter edges do not imply a perfect face.

Posed: **29,430 triangles**. Neutral: **28,886 triangles**. Both exports preserve the node contract and +X cup parenting. Cab SHA-256 stays `c166f5c3f6e92ebd2c89c72f78c43c830ed1df1bf4c910afdd45353e2e40c33d`.

Reproduction: `assets/blender/build.sh`. Generic diagnostics: `score_diagnostics.py -- <id> --model <neutral.glb> --output <directory>`. The retained v6 baseline GLB has SHA-256 `8c5d1c2628c8d5da839721970b4a57141b45ed58fa8e6dd1393fc29d415c22d1`. Raw renders, segmentation masks and complete metrics are in `reviews/v7-baseline/` and `reviews/v7-diagnostics/`.
