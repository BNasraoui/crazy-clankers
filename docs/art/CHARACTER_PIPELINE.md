# Character pipeline (anime cel passengers)

How the Tech Bro v3 (`assets/blender/techbro.py`) was built, written so the other six
passengers can be made the same way. Shared code lives in `assets/blender/anime.py`
(character kit) and `assets/blender/common.py` (mesh builder, export, outlines).

## Setup

- Blender 5.2 (`~/.local/bin/blender` on mint). Run headless:
  `blender --background --factory-startup --python assets/blender/<name>.py`
  (`assets/blender/build.sh` rebuilds everything).
- Pillow for face painting, installed into Blender's own Python once:
  `~/.local/opt/blender-5.2.2/5.2/python/bin/python3.13 -m pip install --user pillow`.
  `anime.py` adds the user site to `sys.path` itself.
- Fast iteration: `... --python techbro.py -- quick` skips the export and renders only the
  head close-up (add `body` for the contact sheet, or `wave` to check the arm_R wave).

## Targets

| | |
|---|---|
| Style | flat early-2000s anime cel: smooth forms, flat colour, one shadow tone, even ink outlines (the game draws shading and outlines) |
| Height | from `cast.jpg`; adult men about 1.75 to 1.8 m, 7 to 7.5 heads |
| Budget | up to 15,000 triangles. Roughly: head and hair 5.5k, torso 3.5k, legs 2.3k, arms and hands 3k, props 0.3k |
| Textures | `face` 1024x1024 (required), plus optional 1024 detail textures for clothing (zips, plackets, pockets, logos). PNG, embedded in the glb |
| Materials | named by role (`skin`, `face`, `hair`, `vest`, `shirt`, `pants`, `shoes`, `sole`, props...). Metallic 0, roughness 1, flat base colour, no baked lighting |
| Units | metres, Y up, facing +Z, origin between the feet |

Model in game coordinates and convert with `anime.g()` / `gv()`. Blender is Z-up and faces
-Y; the glTF exporter converts back.

## Nodes and pivots

`<id>` (root empty) > `legs`, `torso`, `head` (pivot at the neck), `arm_L` and `arm_R`
(pivots at the shoulders), with props parented under the hand that holds them. Pivots are
object origins with identity rotation; the pose is baked into the meshes. `arm_R` must sit
on +X: the game waves it by setting `rotation.z = 2.6`. Check that with `-- wave`.

`cast.jpg` is drawn with the prop in the character's screen-left hand. In the game that
hand is `arm_R` on +X, which is screen right from the front, so **mirror the reference**:
put every asymmetry (part, cocked brow, smirk, weight leg) on the opposite side, and
compare against a mirrored crop.

## Body

- **Torso and clothing**: `anime.loft` over `anime.ring`s (superellipse sections,
  `p` of about 2.3 gives a soft-boxy chest). Garments worn over others (vests, jackets,
  hoodies) are `anime.shell` grids: rows from hem to neckline, columns round the body,
  given a real thickness. Open fronts use `wrap=False` and a per-row angle range (see
  `opening()` in techbro.py). Collars are short shells round the neck. Add a rolled edge
  (`anime.limb` along the opening) so the hem and edges get an outline.
- **Limbs**: `anime.limb` through 4 to 7 control points with per-point radii; it
  Catmull-Rom interpolates both, so a few numbers give a smooth tapered tube. Use 12 to 16
  sides. `anime.knee_ik` places knees and elbows.
- **Contrapposto**: build the torso straight, then apply a `sway()` that rolls each slice
  between a hip roll and an opposite shoulder roll and shifts the pelvis over the standing
  leg. Apply the same function to the pelvis and the hip joints.
- **Hands**: a palm `blob` plus finger `limb`s. For a held prop, run the fingers along
  arcs round the prop's axis (`around()` in techbro.py), with the thumb round the other
  way. A hand in a pocket is a bulge in the trouser material that swallows the wrist.
- **Shading**: `smooth_angle=70` on every part. Hard edges only where the design has them
  (`anime.set_flat` on soles, lids).

## Head (`anime.HeadSpec`, `anime.build_head`)

The skull is a deformed UV sphere (32x24) around `centre`, which sits **at eye level**, so
the eyes land on the vertical middle of the head:

- upper half: ellipsoid (`rx`, `ry_up`, `rz_f` front, `rz_b` back, which is larger so the
  cranium is round);
- lower half: rings narrow from `jaw_start` down to a small chin (`chin_w`), more at
  the front than the back, and the back of the jaw tucks towards the neck (`jaw_back`);
- a small Gaussian nose bump, flattened ears, and a neck tube.

Faces facing forward below the brow get the `face` material; the rest is `skin` (same
colour). After the head tilt, `anime.soften_face_normals` bends the skull normals towards
a smooth ellipsoid. That gives the toon shader one clean, rounded face shadow instead of
facet blotches. **Keep this step.**

Typical adult male: `rx 0.084, ry_up 0.122, ry_lo 0.11, rz_f 0.094, rz_b 0.112,
chin_w 0.32, jaw_start 0.32`. For women and softer faces use a smaller `chin_w` (0.2), a
lower `jaw_start` (0.18) and a slightly larger `ry_up`.

## Hair (`anime.hair_cap`, `anime.hair_lock`)

1. `hair_cap`: a scalp shell following the skull, lifted by `lift + top * up`. Below a
   `hairline(theta)` function it tucks inside the skull. Theta is the azimuth (0 = front,
   +90 = +X); the hairline is high at the forehead, clear of the ears, and low at the nape.
2. `hair_lock`: each lock is a list of `(theta, phi, lift)` control points over the
   skull (phi = elevation above the eye line, lift = metres off the surface), plus a half
   width and thickness. It is lofted with a 6-sided lens section, flat against the scalp
   with sharp side edges, widest just after the root, tapering to a pointed tip. The root
   sinks into the cap.
3. Build the style in layers, about 20 to 25 locks (about 200 triangles each):
   fringe (4 to 5 locks falling from phi about 80 to 25 to 35, swept to one side),
   quiff and crown (long locks from the front over the top to the back, lift 0.04 to 0.05),
   temple volume (widens the silhouette), sides (short, flicking out above the ears),
   sideburns, nape (pointed tips at phi about -10 to -15), and 1 or 2 messy wisps.
4. Tips pointing radially at high phi read as spikes or a pineapple. Point them sideways or
   back unless the design is spiky.

## Face texture (`anime.FaceSpec`, `anime.paint_face`)

Painted with Pillow at 4x and downsampled, in **head-local metres** as seen from the
front (+X is screen right). The texture window is `face_half` square around the head
centre, and `anime.front_uv` projects the face faces orthographically onto it, so painted
coordinates match the model. The background is the skin colour.

- Eyes (`EyeSpec`): width about 0.04, height 0.022 to 0.026, centres at x = +-0.038 on the
  eye line. You get a thick upper lash line (heaviest at the outer corner, with a short
  flick), a large iris with a darker top band, a pupil, two white highlights, a thin lower
  line on the outer two thirds, and a lid crease. `lid` closes the eye (0.1 to 0.3 for
  smug), `look` shifts the iris, `tilt` lifts the outer corner.
- Brows: tapered `stroke`s 0.006 to 0.009 wide, about 0.025 to 0.045 above the eye line.
  Raise one for attitude.
- Nose: one small hooked tick at about y -0.035.
- Mouth: an upper and a lower curve sharing end points. `teeth` fills the gap white with a
  dark interior band, and `ticks` adds smirk corners. Put the mouth around y -0.06, the
  chin at -0.11.
- `extras` covers stubble, freckles, glasses arms and similar. `blush` adds a faint
  cheek hatch.

`anime.Painter` works the same way for clothing. Give it a window (`half`, `y0`), paint
in body-space metres, then call `front_uv(obj, role, half, y0, fallback=..., min_nz=0.05)`.
Faces looking backwards and parts without details (`fill_uv`, for sleeves) map to a
plain texel.

## Preview and review

`anime.Preview(root)` rewrites the materials into a two-tone N.L toon ramp (textures
kept, no self-shadowing, like a game shader), adds inverted-hull outlines, a sun, a ground
shadow and an orthographic camera. Then:

- `sheet("<id>", views, centre, height, size, aspect)` renders the 4-view contact sheet
  (front, 3/4, side, back), the head close-up (`height` about 0.42) and the small check
  (`size=200`, height 2.2 m, so the character is about 160 px tall);
- `anime.compare("<id>-compare", cast.jpg, crop_box, render, mirror_ref=True)` puts the
  3/4 render next to the reference crop at the same height.

Review loop, at least three passes. Each time, compare the side-by-side honestly and list
every difference: face (eye shape, brows, mouth, jaw), hair silhouette, head shape and
size, neck, proportions (shoulder width, crotch height, stance), clothing shapes (open or
closed, hem heights, collars, sleeves), colours and props. Fix the biggest first. Check
the 160 px render still reads as the character from outfit, hair and prop.

## Validate

```sh
npx --yes @gltf-transform/cli inspect public/models/<id>.glb
```

Check the triangle count (the script also asserts the budget), the 7 nodes and their
parents, the role materials (metallic 0, roughness 1), and that the 1024x1024 textures are
embedded. Builds are deterministic: rebuild twice and compare hashes. Do not touch
`cab.py`; `cab.glb` must stay byte-identical.
