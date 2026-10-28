"""Bring along the system libraries the OpenSCAD AppImage needs but Render lacks.

The OpenSCAD snapshot that design3d uses (build.sh) leaves out the graphics,
X11 and font libraries a desktop always has: libOpenGL, libEGL, libGLX, libX11,
fontconfig, freetype and more. Render's runtime is not a desktop, so on
2026-10-28 every build failed with "libOpenGL.so.0: cannot open shared object
file". Rather than guess, this asks the server itself (ldd) which libraries
are missing, fetches exactly those from Debian bullseye (glibc 2.31, older than
the server's, so they load here), checks each package's SHA256 against
Debian's index, and puts the .so files in <app>/extra-libs, which the wrapper
in build.sh adds to the library path. It repeats, since a library brought
along can need another.

Usage: python scripts/openscad_libs.py vendor/openscad
Exit code 0 when nothing is missing at the end, 1 otherwise. Never touches
anything outside <app>.
"""

import hashlib
import io
import lzma
import os
import posixpath
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

MIRROR = "http://deb.debian.org/debian/"
INDEX = MIRROR + "dists/bullseye/main/binary-amd64/Packages.xz"

# Which Debian package carries each library. Only libraries a desktop has and
# a server may not; glibc, libstdc++ and libgcc are the server's own.
PACKAGE = {
    "libOpenGL.so.0": "libopengl0", "libGLdispatch.so.0": "libglvnd0",
    "libGLX.so.0": "libglx0", "libEGL.so.1": "libegl1", "libGL.so.1": "libgl1",
    "libX11.so.6": "libx11-6", "libX11-xcb.so.1": "libx11-xcb1",
    "libxcb.so.1": "libxcb1", "libXau.so.6": "libxau6", "libXdmcp.so.6": "libxdmcp6",
    "libbsd.so.0": "libbsd0", "libmd.so.0": "libmd0",
    "libICE.so.6": "libice6", "libSM.so.6": "libsm6", "libuuid.so.1": "libuuid1",
    "libfontconfig.so.1": "libfontconfig1", "libfreetype.so.6": "libfreetype6",
    "libpng16.so.16": "libpng16-16", "libbrotlidec.so.1": "libbrotli1",
    "libbrotlicommon.so.1": "libbrotli1", "libharfbuzz.so.0": "libharfbuzz0b",
    "libglib-2.0.so.0": "libglib2.0-0", "libgraphite2.so.3": "libgraphite2-3",
    "libpcre.so.3": "libpcre3", "libgmp.so.10": "libgmp10",
    "libexpat.so.1": "libexpat1", "libz.so.1": "zlib1g",
    "libdrm.so.2": "libdrm2", "libgbm.so.1": "libgbm1",
    "libwayland-client.so.0": "libwayland-client0",
    "libwayland-server.so.0": "libwayland-server0", "libffi.so.7": "libffi7",
    "libcom_err.so.2": "libcom-err2", "libgpg-error.so.0": "libgpg-error0",
}


def elf_files(app):
    """The program and its bundled libraries: what must load for it to start."""
    found = [app / "usr/bin/openscad"]
    found += sorted(p for p in (app / "usr/lib").glob("*.so*") if p.is_file())
    return [p for p in found if p.exists()]


def missing(app, extra):
    env = dict(os.environ, LD_LIBRARY_PATH=f"{extra}:{app / 'usr/lib'}")
    gone = set()
    for f in elf_files(app):
        try:
            out = subprocess.run(["ldd", str(f)], capture_output=True, text=True,
                                 timeout=60, env=env).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        for line in out.splitlines():
            if "not found" in line:
                gone.add(line.split("=>")[0].strip())
    return gone


def index():
    """Package name to (path, sha256) from Debian's bullseye index."""
    text = lzma.decompress(urllib.request.urlopen(INDEX, timeout=120).read()).decode()
    pkgs = {}
    for block in text.split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines()
                      if ": " in line and not line.startswith(" "))
        if "Package" in fields and "Filename" in fields:
            pkgs[fields["Package"]] = (fields["Filename"], fields.get("SHA256", ""))
    return pkgs


def unpack(deb, extra):
    """Copy every shared library out of a .deb (an ar archive) into extra."""
    i, saved = 8, []
    while i < len(deb):
        member, size = deb[i:i + 16].decode().strip(), int(deb[i + 48:i + 58])
        if member.startswith("data.tar"):
            tar = tarfile.open(fileobj=io.BytesIO(deb[i + 60:i + 60 + size]))
            files = {posixpath.normpath(m.name): m for m in tar.getmembers()}
            for name, m in files.items():
                base = posixpath.basename(name)
                if ".so" not in base or "/lib" not in "/" + name:
                    continue
                target, here = m, name
                for _ in range(5):  # libX.so.6 -> libX.so.6.4.0, written as a plain copy
                    if target is None or not target.issym():
                        break
                    here = posixpath.normpath(posixpath.join(posixpath.dirname(here), target.linkname))
                    target = files.get(here)
                if target is not None and target.isfile():
                    (extra / base).write_bytes(tar.extractfile(target).read())
                    saved.append(base)
        i += 60 + size + size % 2
    return saved


def main(app):
    app = Path(app).resolve()
    extra = app / "extra-libs"
    extra.mkdir(exist_ok=True)
    pkgs = None
    done = set()
    for round_ in range(5):
        gone = missing(app, extra)
        if not gone:
            print(f"openscad libs: nothing missing ({len(list(extra.iterdir()))} brought along)")
            return 0
        print(f"openscad libs: missing {sorted(gone)}")
        wanted = {PACKAGE[s] for s in gone if s in PACKAGE} - done
        unknown = sorted(s for s in gone if s not in PACKAGE)
        if unknown:
            print(f"openscad libs: no package known for {unknown}")
        if not wanted:
            break
        pkgs = pkgs or index()
        for name in sorted(wanted):
            done.add(name)
            if name not in pkgs:
                print(f"openscad libs: {name} not in the index")
                continue
            path, sha = pkgs[name]
            deb = urllib.request.urlopen(MIRROR + path, timeout=120).read()
            if hashlib.sha256(deb).hexdigest() != sha:
                print(f"openscad libs: {name} checksum mismatch, skipped")
                continue
            print(f"openscad libs: {name}: {', '.join(unpack(deb, extra))}")
    gone = missing(app, extra)
    print(f"openscad libs: still missing {sorted(gone)}" if gone else "openscad libs: nothing missing")
    return 1 if gone else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "vendor/openscad"))
