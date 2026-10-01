"""Measure any calibrated character's neutral exported GLB; preserve audit renders."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import anime
import bpy
import common as C
import sheets as S

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('character')
p.add_argument('--model', type=Path)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args(sys.argv[sys.argv.index('--')+1:])
model = a.model or C.MODELS_DIR / f'{a.character}-apose.glb'
C.reset_scene()
bpy.ops.import_scene.gltf(filepath=str(model.resolve()))
cfg = S.load(a.character)
objects = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name not in cfg.get('props', [])]
report = {'asset_sha256': hashlib.sha256(model.read_bytes()).hexdigest(),
          'colour_regions': S.colour_region_fit(a.character, objects, a.output),
          'shadows': S.face_shadow_fit(a.character, bpy.data.objects[cfg['head_node']], a.output)}
(a.output / 'diagnostics.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
