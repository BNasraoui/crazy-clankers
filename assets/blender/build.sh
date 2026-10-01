#!/usr/bin/env bash
# Rebuild both models and their previews. Common/cab inputs are deliberately stable.
set -euo pipefail
cd "$(dirname "$0")"
if [[ -z "${BLENDER:-}" ]]; then
  BLENDER="$(command -v blender || true)"
  if [[ -z "$BLENDER" ]]; then BLENDER="$HOME/.local/bin/blender"; fi
fi
for model in cab techbro; do
  "$BLENDER" --background --factory-startup --python-exit-code 1 --python "$model.py"
done
python3 validate_techbro.py
