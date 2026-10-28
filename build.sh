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

# The snapshot leaves out the graphics, X11 and font libraries a desktop has
# (libOpenGL, libEGL, libGLX, libX11, fontconfig...), and Render's runtime is
# not a desktop: on 2026-10-28 every design3d build failed with "libOpenGL.so.0:
# cannot open shared object file". So, on every deploy, build a 1 mm cube the
# way design3d does. If that fails, start OpenSCAD through a wrapper that adds
# vendor/openscad/extra-libs to the library path, and let
# scripts/openscad_libs.py ask this server (ldd) what is missing and fetch
# exactly that from Debian, checksums checked. Only if the cube still cannot be
# built, the 2021.01 release (slow engine, but it runs here). Never fatal.
( cd vendor 2>/dev/null && [ -e openscad/AppRun ] && {
    starts() {
        t=$(mktemp -d) && echo 'cube(1);' > "$t/t.scad" &&
        if [ "$(cat openscad/ENGINE 2>/dev/null)" = OpenSCAD-2021.01-x86_64.AppImage ]; then b=""; else b="--backend=Manifold"; fi &&
        QT_QPA_PLATFORM=offscreen HOME="$t" timeout 120 openscad/AppRun -o "$t/t.stl" "$t/t.scad" $b > "$t/log" 2>&1 &&
        [ -s "$t/t.stl" ]; r=$?; [ $r -ne 0 ] && tail -3 "$t/log" 2>/dev/null; rm -rf "$t"; return $r
    }
    if ! starts; then
        if [ ! -e openscad/AppRun.real ]; then
            mv openscad/AppRun openscad/AppRun.real
            printf '%s\n' '#!/bin/sh' 'HERE="$(dirname "$(readlink -f "$0")")"' \
                'export LD_LIBRARY_PATH="$HERE/extra-libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"' \
                'exec "$HERE/AppRun.real" "$@"' > openscad/AppRun
            chmod +x openscad/AppRun
        fi
        python ../scripts/openscad_libs.py openscad || true
    fi
    if starts; then echo "openscad: builds a cube ($(cat openscad/ENGINE 2>/dev/null))"
    else
        echo "openscad: $(cat openscad/ENGINE 2>/dev/null) cannot build here, installing 2021.01"
        name=OpenSCAD-2021.01-x86_64.AppImage
        curl -fsSL -o openscad.AppImage https://files.openscad.org/$name && chmod +x openscad.AppImage &&
        ./openscad.AppImage --appimage-extract > /dev/null && rm -rf openscad && mv squashfs-root openscad &&
        rm -f openscad.AppImage && echo "$name" > openscad/ENGINE && echo "openscad: $name"
    fi
} ) || echo "openscad: start check failed"
