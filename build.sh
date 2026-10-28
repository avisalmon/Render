#!/usr/bin/env bash
set -o errexit

python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input

# OpenSCAD for design3d (sketch-to-stl skill): the standalone Linux build,
# unpacked into vendor/openscad. A pinned development snapshot, for its fast
# Manifold engine (docs/design3d/spec.md, engine evaluation 2026-10-28); its
# checksum is checked. If it cannot be had, the 2021.01 release. vendor/openscad/ENGINE
# names what is installed, so a cached older build is replaced. Never fatal.
OPENSCAD_SNAP=OpenSCAD-2026.10.27-x86_64.AppImage
OPENSCAD_SHA=13be4bac3aa25fcb2b7065cef5a02a5bb258fdac65f4eb49399e529d3d9468e3
( mkdir -p vendor && cd vendor && if [ "$(cat openscad/ENGINE 2>/dev/null)" != "$OPENSCAD_SNAP" ]; then
    rm -f openscad.AppImage
    if curl -fsSL -o openscad.AppImage "https://files.openscad.org/snapshots/$OPENSCAD_SNAP" &&
       echo "$OPENSCAD_SHA  openscad.AppImage" | sha256sum -c - > /dev/null; then name=$OPENSCAD_SNAP
    else echo "openscad: snapshot unavailable, using 2021.01"; name=OpenSCAD-2021.01-x86_64.AppImage
       curl -fsSL -o openscad.AppImage https://files.openscad.org/$name; fi &&
    chmod +x openscad.AppImage && ./openscad.AppImage --appimage-extract > /dev/null &&
    rm -rf openscad && mv squashfs-root openscad && rm -f openscad.AppImage && echo "$name" > openscad/ENGINE &&
    echo "openscad: $name"; fi ) || echo "openscad: not installed"
