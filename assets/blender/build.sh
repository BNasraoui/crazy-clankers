#!/usr/bin/env bash
# Rebuild Tech Bro v6 and its measured turnaround acceptance artifacts, the cab, the robotaxis,
# the San Francisco street kit or its landmarks.
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
  robotaxis)
    # Downloads the Sketchfab sources once (needs ~/.config/sketchfab/token).
    "$ASSET_PYTHON" fetch_sources.py
    for car in wayfarer cybercab lineup style; do
      "$BLENDER" --background --factory-startup --python-exit-code 1 --python robotaxis.py -- "$car"
    done
    exit ;;
  sheet-robotaxis)
    # Zoox and Apollo, modelled from docs/art/vehicles; no downloads. Scores each glb
    # against its sheet, then renders the four robotaxis together.
    for step in zoox apollo fit-zoox fit-apollo four; do
      "$BLENDER" --background --factory-startup --python-exit-code 1 --python sheet_robotaxis.py -- "$step"
    done
    exit ;;
  street)
    # Every street prop to public/models/street with a close-up sheet each, the strip
    # render with the Wayfarer for scale, then a reimport check of nodes and budgets.
    for step in all strip check; do
      "$BLENDER" --background --factory-startup --python-exit-code 1 --python street_kit.py -- "$step"
    done
    exit ;;
  landmarks)
    # Salesforce Tower, the Pyramid, the Ferry Building, Coit Tower and the Golden Gate to
    # public/models/landmarks with a toon sheet each, then a reimport check.
    for step in all check; do
      "$BLENDER" --background --factory-startup --python-exit-code 1 --python landmarks.py -- "$step"
    done
    exit ;;
  techbro) ;;
  *) echo 'Usage: build.sh [techbro|cab|robotaxis|sheet-robotaxis|street|landmarks]' >&2; exit 2 ;;
esac
"$ASSET_PYTHON" test_sheets.py
"$ASSET_PYTHON" test_profile.py
"$BLENDER" --background --factory-startup --python-exit-code 1 --python test_head_shape.py
"$BLENDER" --background --factory-startup --python-exit-code 1 --python test_sheets_blender.py
"$ASSET_PYTHON" sheets.py techbro --output reviews/v6-calibration.json
"$BLENDER" --background --factory-startup --python-exit-code 1 --python techbro_v6.py
"$ASSET_PYTHON" validate_techbro.py > reviews/v6-validation.json
"$ASSET_PYTHON" validate_techbro.py techbro-apose > reviews/v6-apose-validation.json
"$BLENDER" --background --factory-startup --python-exit-code 1 --python score_sheet_export.py -- techbro --report reviews/v6-fit.json
"$ASSET_PYTHON" test_fit_artifact.py
