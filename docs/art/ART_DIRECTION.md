# Art direction

Agreed with Ben on 2026-10-01 after four rounds of mockups. The images here are
AI-generated references for mood and treatment, not assets. Ignore any brand marks
on shoes and cups in them.

## World
- Crazy Taxi gameplay with a light Jet Set Radio influence.
- Cel-shaded, clean black outlines, flat colour with one shadow tone.
- Low fidelity: low-poly models, simple flat colours, rendered at low resolution
  with film grain (`world-fidelity.jpg` shows the fidelity, not the palette).
- Palette: San Francisco on a sunny day. Pastel Victorians (butter yellow, mint,
  dusty blue, cream, terracotta), white trim, green trees, deep blue sky.
- Graffiti only sparingly: a few small tags and stickers, at most the odd mural.
  No pink-and-blue graffiti on every wall; Ben found that tasteless and mobile-game-like.

## People
- Flat early-2000s anime cel style: clean outlines of even weight, flat fills with
  one soft shadow tone, natural friendly proportions (not chibi, not bobblehead),
  comfy everyday streetwear. See `cast.jpg` and `scene-target.jpg`.
- Each caricature reads from hair, outfit, one prop and a pose:
  Tech Bro (fleece vest, blue shirt, khakis, iced cold brew), ABG CMO (long black
  hair, pink top, cargo pants, phone), Psycho CEO (black turtleneck, grey slicked
  hair, pointing), The Founder (orange hoodie, stock certificates), The Sweater
  (small, grey crewneck, clasped hands), The Rocket Guy (tall, black tee and
  jacket, toy rocket), The Safety Guy (curly hair, glasses, blue sweater, long report).
- Speech bubbles use 2D anime-cel portraits (`portraits.jpg`).

## The cab
- White robotaxi SUV, black lidar puck on the roof, teal accent stripe.

## Decision (2026-10-01): people are sprites

Passengers and pedestrians are 2D anime sprites standing in the 3D world, not 3D
models. They always face the camera and show the drawing for the viewing angle.
Seven rounds of scripted Blender modelling (Opus, then Astra) never matched the
drawings; sprites are the drawings, so they stay on-model and read better at speed.

- Passengers: `docs/art/sprites/passengers/` (standing with prop, two hailing frames, side, back).
- Pedestrians: `docs/art/sprites/` (front/back/side walk cycles, dive).
- Recipe: generate a 5-pose sheet with Codex image generation, attaching the
  character's turnaround sheet and portrait, then cut it with the `slice.py` next to it.
  Ask for plain shoes; the image model adds brand marks otherwise.
- The 3D Tech Bro and the Blender pipeline stay in the repo for reference. The cab
  stays 3D.
