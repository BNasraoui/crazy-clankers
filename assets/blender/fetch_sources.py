"""Download the Sketchfab source models for the robotaxis into sources/ (git-ignored).

    python3 assets/blender/fetch_sources.py

Needs a Sketchfab API token in ~/.config/sketchfab/token (or $SKETCHFAB_TOKEN_FILE).
The token is only sent to api.sketchfab.com and is never printed. Each model lands in
sources/<name>/ as the unzipped glTF plus meta.json (name, author, licence, URL), which
docs/CREDITS.md is written from.
"""
import io
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = HERE / "sources"
TOKEN_FILE = Path(os.environ.get("SKETCHFAB_TOKEN_FILE", Path.home() / ".config/sketchfab/token"))
API = "https://api.sketchfab.com/v3/models/"

MODELS = {
    "cybercab": "45c25fd8442b45129e47be2e66449ca3",  # Tesla Cybercab 3D Model
    "ipace": "296a97a6c07041cf9c48f8a303315ed2",  # Jaguar I-Pace (Wayfarer base)
}


def api_get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Token {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch(name, uid, token):
    out = SOURCES / name
    if (out / "meta.json").exists() and any(out.rglob("*.gltf")):
        print(f"{name}: already downloaded")
        return
    info = api_get(API + uid, token)
    lic = info.get("license") or {}
    meta = {
        "uid": uid,
        "name": info["name"],
        "author": info["user"]["displayName"],
        "author_username": info["user"]["username"],
        "author_url": info["user"].get("profileUrl"),
        "url": info.get("viewerUrl") or f"https://sketchfab.com/3d-models/{uid}",
        "license": lic.get("label"),
        "license_url": lic.get("url"),
        "faces": info.get("faceCount"),
    }
    dl = api_get(API + uid + "/download", token)
    # The archive URL is pre-signed; it needs no token.
    with urllib.request.urlopen(dl["gltf"]["url"], timeout=600) as r:
        data = r.read()
    out.mkdir(parents=True, exist_ok=True)
    zipfile.ZipFile(io.BytesIO(data)).extractall(out)
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"{name}: {meta['name']} by {meta['author']} ({meta['license']}), {len(data) >> 20} MB")


def main():
    if not TOKEN_FILE.exists():
        sys.exit(f"missing Sketchfab token file {TOKEN_FILE}")
    token = TOKEN_FILE.read_text().strip()
    names = sys.argv[1:] or list(MODELS)
    for n in names:
        fetch(n, MODELS[n], token)


if __name__ == "__main__":
    main()
