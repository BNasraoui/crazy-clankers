"""Camera registration checked against the analytic projection of a metric cube."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anime as A
import bpy
import common as C
import numpy as np
import sheets as S

C.reset_scene()
point = np.array([0.025, 1.66, 0.04])
half = 0.008
bpy.ops.mesh.primitive_cube_add(size=half * 2, location=A.gv(point))
cube = bpy.context.object
for kind in ["body", "head"]:
    k = S.load("techbro")[kind]
    scale = k["metres_per_pixel"]
    for view, v in k["views"].items():
        mask = S.render_mask(
            "techbro",
            kind,
            view,
            [cube],
            Path("/tmp") / f"camera-test-{kind}-{view}.png",
        )
        x0, y0, x1, y1 = v["crop"]
        cx = v["axis"] + np.dot(point, np.array(v["right"])) / scale - x0
        cy = (k["world_y_at_zero"] - point[1]) / scale - y0
        expected = [
            cx - half / scale,
            cy - half / scale,
            cx + half / scale,
            cy + half / scale,
        ]
        actual = S.bounds(mask)
        assert max(abs(a - b) for a, b in zip(expected, actual)) < 1.1, (
            kind,
            view,
            expected,
            actual,
        )
        print("PASS orthographic cube:", kind, view)
