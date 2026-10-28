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

# The snapshot needs libOpenGL.so.0 (libglvnd), which Render's runtime does not
# have and AppImages leave out: on 2026-10-28 every design3d build failed with
# "libOpenGL.so.0: cannot open shared object file". So, on every deploy: if
# OpenSCAD cannot start, bring the two libraries along (Debian bullseye's
# libglvnd 1.3.2, old enough for this glibc, checksums pinned) and start it
# through a wrapper that puts them on the library path. If it still cannot
# start, install the 2021.01 release, which runs here. Never fatal.
( cd vendor 2>/dev/null && [ -e openscad/AppRun ] && {
    starts() { QT_QPA_PLATFORM=offscreen timeout 60 openscad/AppRun --version > /dev/null 2>&1; }
    if ! starts && [ ! -e openscad/AppRun.real ]; then
        python - <<'PY'
import hashlib, io, tarfile, urllib.request
from pathlib import Path
base = "http://deb.debian.org/debian/pool/main/libg/libglvnd/"
debs = {"libopengl0_1.3.2-1_amd64.deb": "4327a9f20b88e7bcb07af3b196121096877331b61eeed64467854eb0b525fc43",
        "libglvnd0_1.3.2-1_amd64.deb": "52a4464d181949f5ed8f7e55cca67ba2739f019e93fcfa9d14e8d65efe98fffc"}
out = Path("openscad/extra-libs")
out.mkdir(parents=True, exist_ok=True)
for name, sha in debs.items():
    b = urllib.request.urlopen(base + name, timeout=60).read()
    assert hashlib.sha256(b).hexdigest() == sha, name
    i = 8
    while i < len(b):  # a .deb is an ar archive; its libraries are in data.tar.xz
        member, size = b[i:i + 16].decode().strip(), int(b[i + 48:i + 58])
        if member.startswith("data.tar"):
            tar = tarfile.open(fileobj=io.BytesIO(b[i + 60:i + 60 + size]))
            for m in tar.getmembers():
                if m.isfile() and ".so." in m.name:
                    lib = Path(m.name).name                    # libOpenGL.so.0.0.0
                    data = tar.extractfile(m).read()
                    (out / lib).write_bytes(data)
                    (out / lib.rsplit(".", 2)[0]).write_bytes(data)  # libOpenGL.so.0
        i += 60 + size + size % 2
print("openscad: libOpenGL bundled")
PY
        mv openscad/AppRun openscad/AppRun.real
        printf '%s\n' '#!/bin/sh' 'HERE="$(dirname "$(readlink -f "$0")")"' \
            'export LD_LIBRARY_PATH="$HERE/extra-libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"' \
            'exec "$HERE/AppRun.real" "$@"' > openscad/AppRun
        chmod +x openscad/AppRun
    fi
    if starts; then echo "openscad: starts ($(cat openscad/ENGINE 2>/dev/null))"
    else
        echo "openscad: $(cat openscad/ENGINE 2>/dev/null) cannot start here, installing 2021.01"
        name=OpenSCAD-2021.01-x86_64.AppImage
        curl -fsSL -o openscad.AppImage https://files.openscad.org/$name && chmod +x openscad.AppImage &&
        ./openscad.AppImage --appimage-extract > /dev/null && rm -rf openscad && mv squashfs-root openscad &&
        rm -f openscad.AppImage && echo "$name" > openscad/ENGINE && echo "openscad: $name"
    fi
} ) || echo "openscad: start check failed"
