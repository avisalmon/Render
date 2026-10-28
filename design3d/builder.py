"""Building OpenSCAD code into an STL (REQ-D3.20, D3.43).

The code comes from a model that read a person's photo, so it is treated as
untrusted: anything that reads a file (`import`, `include`, `use`) is
refused before OpenSCAD sees it, every build has a time limit, and one build
runs at a time per process. OpenSCAD itself cannot reach the network or
write anywhere but the output it is told to write.

The binary is `settings.DESIGN3D_OPENSCAD`: on Render, the standalone Linux
build that build.sh unpacks into vendor/openscad; on a Windows PC, a
portable OpenSCAD folder at vendor/openscad-win.
"""

import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from django.conf import settings

FORBIDDEN = re.compile(r"\b(import|include|use)\s*[(<]")
_ONE_AT_A_TIME = threading.BoundedSemaphore(1)


class BuildError(Exception):
    pass


def binary():
    return settings.DESIGN3D_OPENSCAD


def available():
    b = binary()
    return bool(b) and Path(b).exists()


def check(code):
    if not (code or "").strip():
        raise BuildError("The code is empty.")
    if FORBIDDEN.search(code):
        raise BuildError("The code reads a file (import, include or use), which is not allowed. Write the whole part in this one file.")
    if len(code) > 60000:
        raise BuildError("The code is too long.")


def build(code):
    """STL bytes and seconds taken, or BuildError with OpenSCAD's message."""
    check(code)
    if not available():
        raise BuildError("OpenSCAD is not installed on this server.")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", HOME=tempfile.gettempdir())
    env.pop("DISPLAY", None)
    with _ONE_AT_A_TIME, tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "part.scad", Path(tmp) / "part.stl"
        src.write_text(code, encoding="utf-8")
        t = time.time()
        try:
            p = subprocess.run([binary(), "-o", str(out), str(src)], capture_output=True, text=True,
                               timeout=settings.DESIGN3D_BUILD_TIMEOUT, env=env, cwd=tmp)
        except subprocess.TimeoutExpired:
            raise BuildError(f"The build took longer than {settings.DESIGN3D_BUILD_TIMEOUT} seconds. Make the part simpler (fewer $fn, no minkowski).")
        took = time.time() - t
        log = (p.stdout + "\n" + p.stderr).strip()
        errors = [line for line in log.splitlines() if line.startswith(("ERROR", "WARNING: Ignoring unknown"))]
        if p.returncode != 0 or not out.exists() or out.stat().st_size == 0:
            raise BuildError("\n".join(errors[-8:]) or log[-1500:] or "OpenSCAD made no part.")
        if any(e.startswith("ERROR") for e in errors):
            raise BuildError("\n".join(errors[-8:]))
        data = out.read_bytes()
    if b"facet" not in data[:4096] and len(data) <= 84:
        raise BuildError("The part is empty: nothing to print.")
    return data, took
