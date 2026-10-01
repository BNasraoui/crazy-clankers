#!/usr/bin/env bash
# Rebuild Tech Bro v7 and its measured turnaround acceptance artifacts.
set -euo pipefail
cd "$(dirname "$0")"
if [[ -z "${BLENDER:-}" ]]; then
  BLENDER="$(command -v blender || true)"
  if [[ -z "$BLENDER" ]]; then BLENDER="$HOME/.local/bin/blender"; fi
fi
# Blender's Python already supplies numpy. Pillow is the only additional package.
ASSET_PYTHON="${ASSET_PYTHON:-$(dirname "$(readlink -f "$BLENDER")")/5.2/python/bin/python3.13}"
case "${1:-techbro}" in
  cab) "$BLENDER" --background --factory-startup --python-exit-code 1 --python cab.py; exit ;;
  techbro) ;;
  *) echo 'Usage: build.sh [techbro|cab]' >&2; exit 2 ;;
esac
"$ASSET_PYTHON" test_sheets.py
"$ASSET_PYTHON" test_profile.py
"$ASSET_PYTHON" test_region_checks.py
"$BLENDER" --background --factory-startup --python-exit-code 1 --python test_head_shape.py
"$BLENDER" --background --factory-startup --python-exit-code 1 --python test_sheets_blender.py
"$ASSET_PYTHON" sheets.py techbro --output reviews/v7-calibration.json
"$BLENDER" --background --factory-startup --python-exit-code 1 --python techbro_v7.py
"$ASSET_PYTHON" validate_techbro.py > reviews/v7-validation.json
"$ASSET_PYTHON" validate_techbro.py techbro-apose > reviews/v7-apose-validation.json
"$BLENDER" --background --factory-startup --python-exit-code 1 --python score_sheet_export.py -- techbro --report reviews/v7-fit.json
"$ASSET_PYTHON" test_fit_artifact.py
"$BLENDER" --background --factory-startup --python-exit-code 1 --python score_diagnostics.py -- techbro --output reviews/v7-diagnostics
"$ASSET_PYTHON" compare_v7.py
