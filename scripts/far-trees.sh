#!/usr/bin/env bash
# Far-away versions of the street trees: about a quarter of the triangles, for neighbourhoods
# more than 250 m from the camera (scenery.ts FAR), where a tree is ~20 px tall and the
# simplification error (5% of the tree's size) is about a pixel. Rerun after changing a tree:
#   scripts/far-trees.sh
set -euo pipefail
cd "$(dirname "$0")/../public/models/street"
tmp=$(mktemp -d)
for t in plane cypress palm; do
  npx -y @gltf-transform/cli@4 simplify "tree_$t.glb" "$tmp/$t.glb" --ratio 0.2 --error 0.05
  npx -y @gltf-transform/cli@4 meshopt "$tmp/$t.glb" "tree_${t}_far.glb"
done
rm -r "$tmp"
ls -l tree_*_far.glb
