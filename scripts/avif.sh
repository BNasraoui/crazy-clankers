#!/usr/bin/env bash
# Convert public/ JPG and PNG art to AVIF in place (originals removed). Quality 60 matches the originals by eye.
set -euo pipefail
cd "${1:-$(dirname "$0")/..}"
find public -type f \( -name '*.jpg' -o -name '*.png' \) -print0 | xargs -0 -P 4 -I{} sh -c 'f="{}"; o="${f%.*}.avif"; magick "$f" -quality 60 "$o" && rm "$f"'
