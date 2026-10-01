# Blockout assets

Set pieces and props are blockouts: simple shapes in the game's cel look, tuned
by playing. When we dress one in Blender, **keep the listed dimensions and
collision**. They are the gameplay; the mesh is decoration. Code lives in
`src/features.ts` (set pieces), `src/props.ts` (junk) and `src/traffic.ts` (carriers).
Units are metres; yaw 0 = +Z (south), π/2 = +X (east).

## Set pieces

| Name | Where | Shape the art must keep | Notes |
|---|---|---|---|
| Twin Peaks kicker | starts (-186, 192), faces east | 16 long, 10 wide, rises 0 → 10 linearly on top of the terrain | Launches ~2 s / ~150 m east over two steep blocks. Sutro Tower sits in the park block (1,8). |
| Sutro Tower | park block (1,8) centre | 3 legs from a 7 m radius, 75 m tall; solid circle r = 8 at the base | Landmark, collision only at the base. |
| Lombard lip | starts (-130, -256), faces west | 7 long, 12 wide, rises 0 → 1.8 | Sends you over the crooked block (-136 → -184). Hedges and flowers below are decoration with no collision. |
| Piers 1–3 | start (318, z) for z = -256, -192, -128, face east | 85 long, 12 wide, deck flat at the street height; last 14% rises 0 → 2.4 | Pilings every 10 m down to the sea floor. Launch into the bay. |
| Boat ramps | (380, -64) facing west; (192, -380) facing south | 54 long, 12 wide, sea floor (-14) → street height | The only way out of the bay. |
| Seabed | east and north of the city, out to 170 m | flat at -14, water surface at -2 | Rocks are solid (r ≈ 0.9 × size); kelp is decoration. Golden Gate towers are solid (r = 2.2). |

## Moving

| Name | Shape the art must keep | Notes |
|---|---|---|
| Car carrier truck | ramp from 4.6 m behind centre, 6.2 long, 2.6 wide, 0.35 → 2.65 high; solid cab only at 2.4 and 3.6 m ahead of centre, cab roof below 2.55 m | 6 in traffic. Drive up the back to launch over the cab. |

## Props (go flying when hit)

| Prop | Radius | Height | Notes |
|---|---|---|---|
| Hydrant | 0.35 | 0.9 | Hit it and a 9 m geyser runs for 10 s, launching anything inside it (vy 17). |
| Cone | 0.3 | 0.75 | Single cones and protest lines across streets. |
| Newspaper box | 0.4 | 1.05 | |
| Trash can | 0.35 | 1.0 | |
| Café table (with umbrella) | 0.6 | 0.8 | Downtown sidewalks. |
| Fruit stand | 0.85 | 1.0 | Pays a slightly bigger tip. |
| Sawhorse | 1.1 | 1.0 | Middle of a cone protest. |
| Protest placard ("NO ROBOTAXIS") | 0.5 | 2.4 | Ends of a cone protest. |
