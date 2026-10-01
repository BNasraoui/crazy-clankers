#!/usr/bin/env bash
# Rebuild every model (public/models/*.glb) and preview (docs/renders/*.png) from scratch.
set -euo pipefail
cd "$(dirname "$0")"
BLENDER="${BLENDER:-blender}"
for model in cab techbro; do
  echo "== $model"
  "$BLENDER" --background --factory-startup --python-exit-code 1 --python "$model.py"
done
