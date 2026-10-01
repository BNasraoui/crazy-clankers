"""Validate the delivered binary contract, not the implementation's intermediates.

Run with ordinary Python after building. Also run gltf-transform inspect for an
independent report. This script needs no Blender, numpy or network access.
"""
import hashlib
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
CAB_SHA256 = 'c166f5c3f6e92ebd2c89c72f78c43c830ed1df1bf4c910afdd45353e2e40c33d'
raw = (ROOT / 'public/models/techbro.glb').read_bytes()
magic, version, length = struct.unpack_from('<III', raw)
assert magic == 0x46546C67 and version == 2 and length == len(raw)
json_length, chunk_type = struct.unpack_from('<II', raw, 12)
assert chunk_type == 0x4E4F534A
model = json.loads(raw[20:20 + json_length])
bin_start = 20 + json_length + 8
assert struct.unpack_from('<I', raw, bin_start - 4)[0] == 0x004E4942
nodes = model['nodes']
by_name = {n['name']: i for i, n in enumerate(nodes)}
assert set(by_name) == {'techbro', 'legs', 'torso', 'head', 'arm_L', 'arm_R', 'cup'}
root = nodes[by_name['techbro']]
assert root.get('translation', [0, 0, 0]) == [0, 0, 0]
assert set(root['children']) == {by_name[n] for n in ('legs', 'torso', 'head', 'arm_L', 'arm_R')}
assert nodes[by_name['arm_R']]['children'] == [by_name['cup']]
assert nodes[by_name['arm_R']]['translation'][0] > 0
assert abs(nodes[by_name['head']]['translation'][1] - 1.44) < .001
assert not model.get('skins') and not model.get('animations')
assert len(model['meshes']) == 6
parents = {child: i for i, n in enumerate(nodes) for child in n.get('children', [])}

def world_origin(i):
    n = nodes[i]
    assert 'rotation' not in n and 'matrix' not in n and 'scale' not in n
    local = n.get('translation', [0, 0, 0])
    parent = world_origin(parents[i]) if i in parents else [0, 0, 0]
    return [a + b for a, b in zip(local, parent)]


def values(index):
    a = model['accessors'][index]
    view = model['bufferViews'][a['bufferView']]
    components = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[a['type']]
    code = {5121: 'B', 5123: 'H', 5125: 'I', 5126: 'f'}[a['componentType']]
    fmt = '<' + code * components
    stride = view.get('byteStride', struct.calcsize(fmt))
    start = bin_start + view.get('byteOffset', 0) + a.get('byteOffset', 0)
    return [struct.unpack_from(fmt, raw, start + i * stride) for i in range(a['count'])]

triangles = 0
bounds = [[math.inf] * 3, [-math.inf] * 3]
for i, node in enumerate(nodes):
    if 'mesh' not in node:
        continue
    origin = world_origin(i)
    for primitive in model['meshes'][node['mesh']]['primitives']:
        assert primitive.get('mode', 4) == 4
        positions = values(primitive['attributes']['POSITION'])
        normals = values(primitive['attributes']['NORMAL'])
        assert len(positions) == len(normals)
        for normal in normals:
            assert all(math.isfinite(v) for v in normal)
            assert abs(sum(v*v for v in normal) - 1) < .01, normal
        for point in positions:
            assert all(math.isfinite(v) for v in point)
            for axis in range(3):
                v = point[axis] + origin[axis]
                bounds[0][axis] = min(bounds[0][axis], v)
                bounds[1][axis] = max(bounds[1][axis], v)
        indices = values(primitive['indices'])
        assert len(indices) % 3 == 0
        assert max(v[0] for v in indices) < len(positions)
        triangles += len(indices) // 3
assert triangles <= 30000, triangles
assert 1.78 <= bounds[1][1] <= 1.82, bounds
assert abs(bounds[0][1]) < .002, bounds
required = {'skin', 'face', 'hair', 'vest', 'shirt', 'pants', 'shoes', 'sole', 'cup', 'coffee', 'straw'}
assert required <= {m['name'] for m in model['materials']}
for material in model['materials']:
    pbr = material['pbrMetallicRoughness']
    assert pbr.get('metallicFactor', 1) == 0
    assert pbr.get('roughnessFactor', 1) == 1
    assert not material.get('emissiveFactor')
    if 'baseColorTexture' in pbr:
        assert pbr.get('baseColorFactor', [1, 1, 1, 1]) == [1, 1, 1, 1]
images = []
for img in model['images']:
    assert 'uri' not in img and img['mimeType'] == 'image/png'
    view = model['bufferViews'][img['bufferView']]
    start = bin_start + view.get('byteOffset', 0)
    width, height = struct.unpack_from('>II', raw, start + 16)
    assert max(width, height) <= 2048
    images.append({'name': img['name'], 'width': width, 'height': height})
assert hashlib.sha256((ROOT / 'public/models/cab.glb').read_bytes()).hexdigest() == CAB_SHA256
print(json.dumps({'triangles': triangles, 'nodes': len(nodes), 'meshes': len(model['meshes']),
                  'materials': len(model['materials']), 'textures': images,
                  'bounds': bounds, 'bytes': len(raw), 'cab_sha256': CAB_SHA256}, indent=2))
