# Character pipeline: Tech Bro v5

The acceptance reference is `cast.jpg` (far left), with `portraits.jpg` (top left) supplying facial detail. `scene-target.jpg` defines the flat, inked game presentation. The renders show the actual source geometry exported to GLB. V5 changes only the head and its neck connection; body, outfit, pose, original face decal and node/pivot contract are retained from merged v4 (`27ae3a4`).

## Rebuild

```sh
assets/blender/build.sh
npx --yes @gltf-transform/cli inspect public/models/techbro.glb
```

Tested with Blender 5.2.2. `BLENDER` overrides the executable; the build script also finds `~/.local/bin/blender`. Blender supplies numpy. Pillow is needed by Blender's Python and ordinary Python (comparison composition). The helper's import error prints the installation command using the actual Python executable. No generation service or downloaded model is needed to rebuild.

The committed transparent facial decal remains the v4 art input, byte-for-byte unchanged. Its original prompt and provenance are in [textures/README.md](../../assets/blender/textures/README.md). Rebuilding resamples this fixed source onto the curved head.

For quick review:

```sh
~/.local/bin/blender --background --factory-startup --python-exit-code 1 \
  --python assets/blender/techbro.py -- quick body
python3 assets/blender/head_compare.py
```

`-- quick` renders the head without exporting; adding `body` renders the full contact sheet. The ordinary build exports and renders everything, builds the head comparison, then checks the surface and binary contracts. Preview materials and hulls are created after export and never enter the GLB.

## Shared kit

| File | Responsibility |
| --- | --- |
| `assets/blender/head_shape.py` | Reusable parameterized egg cranium, smoothly tapered jaw, curved cheeks and understated nose |
| `assets/blender/anime_head.py` | Shared head mesh, cylindrical UVs, neck, ears, scalp and supplied hair paths; canonical export ordering and face normals |
| `assets/blender/techbro_head.py` | Tech Bro's shape settings, hair control paths and face/hair painting |
| `assets/blender/anime.py` | Coordinate conversion, lofts, clothing, painting, materials and unchanged cel preview |
| `assets/blender/techbro.py` | Character palette, unchanged body/clothing/pose, hierarchy, export and view framing |
| `assets/blender/head_compare.py` | Crops and arranges v4/v5 renders alongside both original references; generates no replacement art |
| `assets/blender/test_head_shape.py` | Regression checks for jaw taper, cheek curvature and nose projection |
| `assets/blender/validate_techbro.py` | Checks the actual binary hierarchy, bounds, triangles, normals, materials, embedded textures and cab hash |

`HeadShape(width=1, height=1, depth=1, jaw_width=1, nose=1)` is the common starting head for the remaining six passengers. Dimensions are multipliers, not metres. `sections` provides height/half-width/front-depth/rear-depth rings, `section(y)` interpolates them, and `surface(theta, y)` returns a point in metres relative to the eye line. Interpolation uses monotone cubic tangents to avoid sharp ring transitions and overshoot. Front and back use rounded elliptical arcs; a low Gaussian ridge/tip supplies the nose instead of a wedge.

Pass a shape and character-specific hair paths to `anime_head.build_head_mesh(A, C, mats, materials, root, centre, neck, tilt_spec, shape, locks)`. Each lock is `(control_points, half_width, depth)`, in metres relative to the eye centre. Roots should sit inside the scalp and the final point is the actual tip. The builder preserves loop UVs and the back seam, then canonicalizes mesh order for deterministic export. Keep hair and facial artwork character-specific; inherit the improved construction rather than copying the old v4 surface.

For example, `HeadShape(width=.96, height=1.03, jaw_width=.92, nose=.8)` changes proportions without replacing the topology. Supply matching hair control paths for that silhouette. The scalp follows the shape's sections; ears follow its width. Neck and hair thickness are metre-based art choices in the builder/paths, so review these when making large proportion changes.

Tech Bro's painter accepts `shape=SHAPE`. Its inverse sampling uses the same interpolated width field as the actual mesh, rather than a separate linear approximation. Scaled heads retain feature proportions by scaling decal sampling with shape width/height. Each passenger supplies their own ink and feature placement. The source's neutral whites and flat brow pigment treatment are unchanged.

## Geometry and animation contract

Work in metres, Y up, facing +Z. `g`/`gv` convert to Blender coordinates; the exporter converts back. Geometry is baked in the relaxed pose, relative to animation pivots:

```text
techbro                     origin between feet
├── legs
├── torso
├── head                    neck pivot (0, 1.44, -0.012)
├── arm_L                   shoulder pivot (-0.172, 1.402, -0.014)
└── arm_R                   shoulder pivot (+0.172, 1.414, -0.014)
    └── cup
```

V5 removes v4's global 15% head widening, narrows the mandibular rings and rounds the cheek turn. The eye centre is lowered 25 mm to shorten the visible neck, while the animation pivot and head tilt stay fixed. The new model is 1.7655 m tall; posed hair-top to chin is approximately 0.2314 m, or **1/7.63 of total height**. The bounds check is updated for this deliberate head/neck height change.

The head's UV seam remains at the back. `u = theta/(2*pi) + 0.5`; `v = (y + .115*height)/(.240*height)`. The original eyes, brows and grin are resampled around the new cheeks. In profile, the visible eye and grin foreshorten with the face; no front-facing plates are added. Face normals retain a modest stylized blend (25–35%) while letting actual cheek curvature drive the cel terminator; v4's 70–92% forward blend hid much of that turn.

Hair uses a skull-hugging scalp and closed curved clumps. V5 reduces rear depth, crown height and side width and folds smaller crown waves back into the main mass. The two narrow sideburn strips were removed after they intersected the narrower face and left isolated slivers. Head sampling uses 64 radial segments and 48 regular height intervals plus anatomical rings; hair tubes use eight sides and four curve steps per span.

## Preview and delivered comparisons

The cel preview is unchanged: a hard N·L step at 0.32, fixed sun orientation `(40, 0, 28)`, skin/face shadow multiplier `(0.70, 0.49, 0.40)`, hair `(0.55, 0.55, 0.70)`, other roles `(0.70, 0.68, 0.84)`. There are no scene-light, ambient-occlusion, cast-shadow or PBR contributions. Standard colour management converts to sRGB.

Every model mesh receives a reversed hull with position-merged normals, displaced by **2.2 actual image pixels** in each orthographic view. The small preview renders native pixels rather than downsampling a large image. Hulls never enter the GLB. Exported materials remain metallic 0, roughness 1, white textured base factors and embedded PNG albedo; no emissive or lighting extensions.

- `docs/renders/techbro-head.png`: front, three-quarter and profile close-ups.
- `docs/renders/techbro-head-compare.png`: rows for those same views; columns show the merged v4 head, v5 head, portrait crop and cast crop. Reference drawings retain their original angles: neither source supplies a true profile, so the reference columns are repeated honestly rather than inventing a side view.
- `docs/renders/techbro.png`: front, three-quarter, side and rear.
- `docs/renders/techbro-compare.png`: tight cast crop and rendered character at equal total height. The cast crop is explicitly mirrored for the required +X cup arm.
- `docs/renders/techbro-small.png`: four native-size game previews, approximately 160 pixels tall.

## V5 review passes

All passes were rendered and visually reviewed. `assets/blender/reviews/v5-passN-head.png` and `v5-passN-compare.png` retain passes 1–3. `v4-head.png` preserves the exact merged head sheet. The delivered files are the final cleanup after pass 3.

| Pass | Front silhouette | Three-quarter silhouette | Profile silhouette | Largest correction following review |
| --- | --- | --- | --- | --- |
| 1 | Removed broad square jaw/top width; chin tapers but ring transitions are angular. | Cheek now turns gradually and far eye/grin foreshorten; fringe/scalp gaps remain. | Beak is gone, jaw/chin clearer and neck shorter; back hair still heavy. | Smooth ring interpolation, fit atlas to the same width field, lower scalp hairline and tighten rear waves. |
| 2 | Smoother jaw taper, but crown still reads as one large swept dome. | Face decal follows curved cheek; gap near the left sweep and overly regular top remain. | Reduced bun, though the upper hair has a tall, blunt edge. | Lower broad crown paths and add a few smaller returning waves. |
| 3 | Smaller hair mass, but two added crown tips look like horns. | Narrower side silhouette; tips do not yet flow into the larger locks. | More compact round back; jaw-to-neck transition remains readable. | Fold tips back into the hair, tighten side paths, increase face ring sampling and remove intersecting sideburn slivers. |
| Final | Rounded, narrower cranium with tapered jaw and soft chin; no isolated sideburn marks. | Continuous cheek turn with readable eyes, brows and grin. | Small nose, visible chin, round back and shorter neck; no detached crown horns. | Checked full-body/reference/native-size renders, shared construction, binary scope and deterministic rebuild. |

Remaining art differences: the hair still uses broader and more controlled clumps than the finely messy illustrated reference. The orthographic profile is a construction choice because the provided references do not contain one. Body, cloth and cup simplifications from v4 are deliberately preserved. These technical checks do not replace Ben's visual acceptance.

## Validation

Final GLB: **28,762 triangles; 7 nodes; 6 meshes; 16 materials; 5 embedded textures; 1,132,260 bytes**. The face atlas is 2048²; shirt, hair, vest and pants are 1024². Feet are approximately 0.0002 m above the origin. No skeleton or animations.

`test_head_shape.py` first failed on the v4 jaw, cheek and nose, then passed on the shared surface. `validate_techbro.py` passes on the exported binary. Independent `npx --yes @gltf-transform/cli inspect public/models/techbro.glb` output is saved in `assets/blender/reviews/inspect.txt`; binary counts and bounds are in `validation.json`.

A v4/v5 accessor comparison confirms byte-identical positions, indices, normals and UVs for legs, torso, both arms and cup, with all seven node pivots unchanged (`v5-scope.txt`). The original decal, `common.py` and `cab.py` are untouched. Two full builds produce identical SHA-256 hashes for both models and all five delivered v5 previews (`rebuild-sha256.json`). The cab remains:

```text
c166f5c3f6e92ebd2c89c72f78c43c830ed1df1bf4c910afdd45353e2e40c33d
```

For every remaining passenger, start from `HeadShape`, tune proportions against the cast/portrait, supply their hair and face artwork, and inspect front/three-quarter/profile plus native game size. Preserve the hierarchy, export ordinary materials before preview setup, inspect the GLB and verify a repeatable build.
