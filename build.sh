#!/usr/bin/env bash
set -o errexit

python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input

# OpenSCAD for design3d (sketch-to-stl skill): the standalone Linux build,
# unpacked into vendor/openscad. Never fatal to a deploy.
( mkdir -p vendor && cd vendor && if [ ! -x openscad/AppRun ]; then
    curl -fsSL -o openscad.AppImage https://files.openscad.org/OpenSCAD-2021.01-x86_64.AppImage &&
    chmod +x openscad.AppImage && ./openscad.AppImage --appimage-extract > /dev/null &&
    rm -rf openscad && mv squashfs-root openscad && rm -f openscad.AppImage; fi ) || echo "openscad: not installed"
