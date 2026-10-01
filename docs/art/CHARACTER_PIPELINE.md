# Character pipeline: Tech Bro v4

The acceptance reference is `cast.jpg`, with `portraits.jpg` supplying facial detail. `scene-target.jpg` defines the flat, inked game presentation. The GLB is a real volumetric character, including its profile; the comparison is a render of that GLB's source geometry, not a replacement illustration.

## Rebuild

```sh
assets/blender/build.sh
# Or just the passenger:
~/.local/bin/blender --background --factory-startup --python-exit-code 1 \
  --python assets/blender/techbro.py
python3 assets/blender/validate_techbro.py
npx --yes @gltf-transform/cli inspect public/models/techbro.glb
```

Tested with Blender 5.2.2 on a GTX 1070. `BLENDER` overrides the executable; the build script also finds `~/.local/bin/blender`. Blender supplies numpy. Pillow must be installed in Blender's Python user site. The helper's import error prints the installation command using the actual Python executable. No generation service, downloaded model, GPU sculpting extension or API credential is needed to rebuild.

The committed transparent facial decal is an art input, just as a hand-painted texture would be. It was made with the built-in imagegen tool using the supplied references. Its exact prompt and provenance are in [textures/README.md](../../assets/blender/textures/README.md). Rebuilding resamples that fixed source; it does not regenerate it nondeterministically.

`-- quick` renders the head without exporting; `-- quick body` additionally renders the contact sheet. The ordinary build exports and renders everything. Preview materials and hulls are created **after** export and never enter the GLB.

## Files and responsibilities

| File | Responsibility |
| --- | --- |
| `assets/blender/techbro.py` | Character palette, body sections, clothing, relaxed pose, hands, cup, hierarchy, export and view framing |
| `assets/blender/techbro_head.py` | Continuous shaped head surface, cylindrical UV atlas, facial normal editing, ears, scalp and swept hair clumps |
| `assets/blender/anime.py` | Coordinate conversion, lofts, cloth shells, painting utilities, materials, two-tone preview and merged-normal hulls |
| `assets/blender/textures/techbro-face-decal.png` | Transparent facial ink and pigment source; no skin, skull, hair or background |
| `assets/blender/validate_techbro.py` | Reads the actual binary to check hierarchy, bounds, triangles, normals, material factors, embedded texture sizes and cab hash |
| `assets/blender/reviews/` | Actual intermediate head/comparison renders and final validation evidence |

`common.py` and `cab.py` are unchanged. `build.sh` rebuilds both models. The cab hash remains:

```text
c166f5c3f6e92ebd2c89c72f78c43c830ed1df1bf4c910afdd45353e2e40c33d
```

## Geometry and UV construction

Work in metres, Y up, facing +Z. `g`/`gv` convert to Blender coordinates; the exporter converts back. Vertices are baked in their posed positions. Each part's local coordinates are measured from its animation pivot, so runtime movement needs no skeleton.

```text
techbro                     origin between feet
├── legs
├── torso
├── head                    neck pivot (0, 1.44, -0.012)
├── arm_L                   shoulder pivot (-0.172, 1.402, -0.014)
└── arm_R                   shoulder pivot (+0.172, 1.414, -0.014)
    └── cup
```

The head is built from anatomical sections: a rounded cranium, broad cheek region, mandibular corner, short chin plane and an actual bridge/nose/muzzle profile. It is not an ellipsoid with facial plates. The nose and chin remain visible from the side. The final head is widened relative to the first passes to recover the reference's adult jaw and head-to-shoulder ratio.

The head's UV seam is at the back. `u = theta/(2*pi) + 0.5`; `v = (y + 0.115)/0.240`, relative to the eye centre. The painter inverse-samples the transparent facial features onto those UVs using the section width at each height. Facial detail therefore follows the cheeks around the head; no front camera is used to project the completed face. UV loops survive export, including the rear seam. The source's neutral tonal variation in whites is flattened, and eyebrows are converted to flat pigment before compositing over uniform skin colour.

Face normals blend the real surface normals with a broad forward-facing cheek field. This limits noisy cel terminators without flattening the geometry. The edited normals are exported. The inverted-hull normals are calculated separately from merged positions, so they do not inherit that stylization.

Hair is a scalp shell with overlapping, closed, broad curved clumps. Each clump has its own root-to-tip UV island, a shallow convex section and a taper contained within its path. There is no extra spear past the last control point. Large paths establish the sweep; a small number of secondary shapes establish the fringe, temples and nape. Sparse ink paths in the hair texture follow the UV flow. Avoid adding lots of narrow locks to compensate for a wrong overall silhouette.

Clothing uses elliptical sections and thick open shells. The shirt has a real upper V opening, folded collar panels, a split untucked hem and a raised hem at the pocket. The vest is open, with a standing collar, armhole binding, front edges, pockets and geometric folds. Trouser centre lines are continuous through the knees; diagonal folds deform the surface instead of cutting it into rings. Shoes have separate upper, panels, sole, outsole, tongue and laces. Fingers curve around the cup; the pocket hand's distal geometry enters the trousers and its thumb stays visible.

## Material and preview contract

All exported materials have metallic 0 and roughness 1 (the glTF default when omitted). The textured materials use a white base factor, avoiding multiplication of the pigment twice. Textures are embedded PNGs. There are no baked scene shadows, normal maps, PBR textures, emissive materials or lighting extensions.

The preview computes a single hard N·L step at 0.32. Lit colour is the base colour/texture; shadow colour is that same colour multiplied in linear space by a tint:

- skin and face: `(0.70, 0.49, 0.40)`;
- hair: `(0.55, 0.55, 0.70)`;
- other roles: `(0.70, 0.68, 0.84)`.

The preview key direction comes from the fixed `(40, 0, 28)` degree sun orientation, but shading evaluates N·L directly: there are no scene-light, ambient-occlusion, cast-shadow or PBR contributions. Standard colour management converts the result to sRGB.

Every model mesh receives a reversed hull using position-merged smooth normals. The hull displacement corresponds to **2.2 actual image pixels** in each orthographic view. Each tile is treated as a crop from a full-resolution game framebuffer. In particular the small preview keeps 2.2 pixels around a roughly 160-pixel character; it does not downsample a larger character with an artificially fine outline. Hulls use backface culling.

Outputs:

- `docs/renders/techbro.png`: front, three-quarter, side and rear;
- `docs/renders/techbro-head.png`: front, three-quarter and side close-ups;
- `docs/renders/techbro-compare.png`: tight cast crop and rendered character at equal height, corresponding three-quarter orientation;
- `docs/renders/techbro-small.png`: four views at approximately 160 pixels of character height.

The comparison explicitly mirrors the cast crop because the required cup arm is +X. The character is never mirrored just for the render. Images use a cream background and the same materials/geometry as export. The illustrated reference has artist-adjusted perspective; the preview uses an orthographic camera.

## Review record

Each pass below was built, rendered and visually inspected. `reviews/passN-head.png` and `reviews/passN-compare.png` retain passes 1–12. The files in `docs/renders/` are pass 13. The notes distinguish improvements from remaining discrepancies rather than treating a triangle count as visual acceptance.

| Pass | Face and head | Hair silhouette/flow | Proportions, clothing and colour; next correction |
| --- | --- | --- | --- |
| 1 | Round, friendly eyes and smile; weak adult jaw. Nose exists in profile, unlike a flat decal plane. | Too tall, tubular curls and excessive volume. | Narrow sleeves, uniform shirt hem, featureless chinos and shoes, opaque-looking lid, mitten-like pocket bulge. Warm skin and darker navy introduced. Lower/flatten hair and lengthen jaw first. |
| 2 | Longer chin; face still reads too pleasant and youthful. Smooth brows and large eye glints differ from the reference. | Crown lower, but neatly divided front curls; visible scalp gaps. | Better sleeve volume and separately modelled pocket hand, but it floats outside the opening. Trousers and footwear remain plain. Correct mouth/brows and clothing construction. |
| 3 | Firmer brows, wider tooth band; grin still generic. | Front sweep extends farther across temple; crown remains too tidy. | Added trouser folds and shoe components. Knee folds accidentally read as joins; laces are mostly buried. Shirt tails too shallow; sleeve bends too mechanical. Fix expression, collar and folds. |
| 4 | Narrower irises and a stronger jaw; chin pitch went the wrong way. | Returning wisps introduce small knots; broad clumps still dominate like a helmet. | Skin-coloured shirt faces create a blocky opening. Pocket hand/trim still protrude. Lighter khakis, shoe outsole and visible ice improve role colours. Replace the opening with geometry and correct chin pitch. |
| 5 | Chin up and profile improved. Jaw remains too tapered, brow too round. | Front clumps seated nearer scalp; some small gaps remain. | True shirt opening, shaped tails and pocket lift; opening too deep, pocket trim looks like a floating stick. Sleeve fold placement still too smooth. Use the enlarged cast crop to correct the jaw and eyebrows. |
| 6 | Wider jaw and angular brow bars; procedural eyes/grin still lack the source drawing's personality. | Diagonal fringe and sideburns, but sideburn attachment is imperfect. | Added seam ink and simplified logo; pocket position closer, trim still floats. Trouser crease rings persist. Rebuild leg curves and improve folded cloth. |
| 7 | Same expression limitation; colour/shadow contrast closer. | Overall shape stable, with excessive scalp dominance. | Continuous trouser curves remove knee joins. Vest and sleeve folds added. Laces now visible. The pocket trim is still visibly detached, so remove that piece rather than hiding it in the camera. |
| 8 | Broader teeth and stronger ink; generic procedural facial drawing remains the main mismatch. | Hair still too groomed. | Detached trim removed, thumb shortened. Native-pixel outline makes the 160px review faithful to the game. Compare shows substantially less cloth detail than the illustration. Replace the facial art source while preserving geometry/UVs. |
| 9 | Reference-guided transparent facial art improves eyelids, irises, brow expression and teeth. Profile remains volumetric. | Broad masses still sink into scalp; sideburns can look detached. | Same pose/clothing. The generated decal's skin-free alpha and neutral whites are checked; it is then resampled into the cylindrical atlas. Fix scalp/clump intersections next. |
| 10 | Face art retained; squarer jaw and grin read more clearly. | Lower scalp shell exposes major waves; sideburns connected. Knotted secondary wisps removed. | More hip sway. Shirt/vest atlas bounds identified as too short for collars, so enlarge their UV windows. |
| 11 | Face holds across views, but the equal-height comparison exposes a head that is too narrow relative to the reference. | Added layered forehead sweep and one returning crown curl. Pole duplicates removed. | Atlases cover collars; inspection/rebuild passes. Pocket elbow is still too far out for the relaxed reference. Widen the head/neck 15% and bring elbow inward. |
| 12 | Wider head/neck and the reference-based expression retained. | Large overlapping waves, shaped fringe, sideburns and nape are visible from all sides. | Less extended pocket elbow; checked full-body, profile, rear and native-size views. Final validation and byte reproducibility checks below. |

| 13 | Face and proportions retained. | Removed the blunt crown curl visible in the final close-up. | Canonicalized UV-preserving head geometry after the rebuild check detected nondeterministic GLB ordering; reran export and all previews. |

**Remaining art differences:** the hair is more controlled and less finely broken at the silhouette than the drawing; the garment folds and stitching are much sparser; the hand and sneaker shapes are simplified; the cup uses opaque cel materials rather than real clear plastic; the reference's jaw/neck shadow is more graphically deliberate. The new face source is closer to the selected character, but these renders do not establish an independent blind “same studio” pass. Ben's likeness review remains the acceptance gate; technical validation is not a substitute for it.

## Export validation

Final GLB: **28,690 triangles; 7 nodes; 6 meshes; 16 materials; 5 embedded textures**. The face atlas is 2048²; shirt, hair, vest and pants are 1024². Height is approximately **1.797 m**, feet approximately **0.0002 m** above the origin. No skeleton or animations. Actual bounds and file size are recorded in `assets/blender/reviews/validation.json`; the independent glTF Transform report is `inspect.txt` alongside it.

`validate_techbro.py` checks the exported binary rather than trusting in-memory Blender objects: it verifies node parenting/pivots, +X cup arm, dimensions, finite unit normals, legal indices, triangle budget, role materials, metallic/roughness, neutral textured base factors, texture embedding/resolution and the exact cab SHA-256. Repeated full builds are compared by SHA-256, including the cab and all delivered previews.

## Building the remaining six passengers

1. Start with a tight cast crop and the corresponding portrait. Write down the identifying silhouette, facial proportions, expression and costume shapes before using the helpers. Do not share the Tech Bro's head shape merely because it is available.
2. Establish body height and head/shoulder ratio, then model the front, three-quarter and profile head together. The nose, chin and jaw must work without face ink. Use the first comparison to decide silhouette changes.
3. Design a few large hair masses with coherent flow and a scalp that stays inside them. Add secondary strands only where they change character identity. Check the rear and side, not just the hero angle.
4. Paint transparent facial pigment/ink without skin shading. Commit that source. Give each head an appropriate unwrap; a cylindrical map suits this character but is not a universal face template. Inspect eyes and mouth across the cheek curvature and preserve UV seams.
5. Pose the body and hands before clothing detail. Put cloth openings, collars, hems, pocket lips and cuffs in geometry when they affect the silhouette. Keep linework in albedo. Avoid disjoint anatomical rings at knees/elbows.
6. Use the game-equivalent N·L and merged-normal outline preview from the first pass. Inspect at game size as well as close up. Make large likeness fixes before adding stitching or isolated hair strands.
7. Preserve the required animation pivots and prop parents. Export ordinary materials first. Do not export preview hulls, camera, scene lights or a skeleton unless the game's contract changes.
8. Render all four deliverables, record each review honestly, inspect the binary, check the budget and rebuild reproducibly. An attractive asset with the right clothes is not sufficient if the person still differs from the chosen reference.
