# Character turnarounds

Orthographic reference sheets for modelling the passengers in Blender. Generated
with Codex image generation from each character's crop of `../cast.jpg` and
`../portraits.jpg` (prompts in `prompts/`), then checked by hand for matching
features across views.

- `<id>-body.png`: front, right side and back in a neutral A-pose, all on one
  baseline, with horizontal guide lines at matching landmarks (top of head, eyes,
  chin, shoulders, waist, crotch, knees, soles). The signature prop is drawn on
  its own in the corner.
- `<id>-head.png`: front, three-quarter, right profile and back of the head, with
  guide lines at the hairline, brows, eyes, nose, mouth, chin and neck.

How to use them: load the front and side views as orthographic reference images
in Blender, scaled so the soles-to-crown distance matches the character's height,
and model to the silhouettes. Check the model by rendering it in the same
orthographic views and overlaying the render on the sheet. Model in this neutral
pose first, then pose it (cup raised, hand in pocket and so on) to match
`../cast.jpg`.

The sheets are drawn, so small mismatches between views exist. When views
disagree, the front view wins for widths and the side view wins for depths.

Characters: techbro, cmo, ceo, founder, sweater, rocket, safety.
