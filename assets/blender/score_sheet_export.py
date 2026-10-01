"""Reimport any passenger's neutral GLB and score its delivered triangles.

blender -b --factory-startup --python score_sheet_export.py -- techbro \
  --report assets/blender/reviews/v6-fit.json
The data-only calibration declares the head node and any excluded staged props.
"""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anime  # noqa: F401 - Initializes Blender's Pillow user-site dependency.
import bpy
import common as C
import sheets as S

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("character")
parser.add_argument("--model", type=Path)
parser.add_argument("--report", type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
path = args.model or C.MODELS_DIR / f"{args.character}-apose.glb"
config = S.load(args.character)
C.reset_scene()
bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
objects = [
    o
    for o in bpy.context.scene.objects
    if o.type == "MESH" and o.name not in config.get("props", [])
]
head = bpy.data.objects[config.get("head_node", "head")]
report = {
    "asset": str(path.resolve().relative_to(C.REPO)),
    "asset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
}
with tempfile.TemporaryDirectory(prefix="sheet-export-") as tmp:
    for kind in ["body", "head"]:
        report[kind] = {}
        for view in config[kind]["views"]:
            mask = S.render_mask(
                args.character,
                kind,
                view,
                objects if kind == "body" else [head],
                Path(tmp) / f"{kind}-{view}.png",
            )
            report[kind][view] = S.overlay(
                args.character,
                kind,
                view,
                mask,
                C.RENDERS_DIR / f"{args.character}-fit-{kind}-{view}.png",
            )
args.report.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
assert min(report["body"].values()) >= 0.90, report
assert min(report["head"].values()) >= 0.88, report
