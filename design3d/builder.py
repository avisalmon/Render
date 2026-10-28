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

from .render import read_stl

FORBIDDEN = re.compile(r"\b(import|include|use)\s*[(<]")
_ONE_AT_A_TIME = threading.BoundedSemaphore(1)


class BuildError(Exception):
    pass


def binary():
    return settings.DESIGN3D_OPENSCAD


def available():
    b = binary()
    return bool(b) and Path(b).exists()


_ENGINE = {}


def engine():
    """The installed OpenSCAD's version, e.g. "2026.10.27" or "2021.01", or ""."""
    b = binary()
    if not _ENGINE.get(b):  # an empty answer is not kept: OpenSCAD may be installed later
        version = ""
        if available():
            try:
                p = subprocess.run([b, "--version"], capture_output=True, text=True, timeout=30,
                                   env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
                m = re.search(r"version\s+(\d{4}\.\d{2}(?:\.\d{2})?)", p.stdout + p.stderr)
                version = m.group(1) if m else ""
            except (OSError, subprocess.SubprocessError):
                version = ""
        _ENGINE[b] = version
    return _ENGINE[b]


def manifold():
    """True when the installed OpenSCAD has the fast Manifold engine (2024 and
    later): booleans, minkowski and hull in a second instead of minutes
    (engine evaluation, 2026-10-28)."""
    return engine()[:4] >= "2024"


def signed_volume(tris):
    """The mesh's volume in mm3; negative when its faces point inwards."""
    total = 0.0
    for (ax, ay, az), (bx, by, bz), (cx, cy, cz) in tris:
        total += ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
    return total / 6.0


def check(code):
    if not (code or "").strip():
        raise BuildError("The code is empty.")
    if FORBIDDEN.search(code):
        raise BuildError("The code reads a file (import, include or use), which is not allowed. Write the whole part in this one file.")
    if len(code) > 60000:
        raise BuildError("The code is too long.")


def _limit_memory():
    """In the child, before OpenSCAD starts: a memory ceiling, so a heavy
    part fails on its own instead of running the whole server out of memory
    (a 512 MB server restarts, and every turn on it is lost)."""
    import resource

    # RLIMIT_DATA counts what the program really allocates (not the address
    # space Qt reserves). The Manifold engine peaked at 70 MB over the engine
    # evaluation, and the site needs the rest of the 512 MB server.
    mb = getattr(settings, "DESIGN3D_BUILD_MEMORY_MB", 200)
    if mb:
        resource.setrlimit(resource.RLIMIT_DATA, (mb * 1024 * 1024, mb * 1024 * 1024))


def _run(cmd, env, cwd):
    """(stdout, stderr, returncode), or returncode None when the time ran
    out or the memory ceiling stopped it. OpenSCAD runs in its own process
    group and the whole group is killed at the time limit: the Linux build
    starts through a launcher, and killing only the launcher left OpenSCAD
    running, holding the CPU for every later build (Avi, 2026-10-28)."""
    posix = os.name == "posix"
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=cwd,
                         start_new_session=posix, preexec_fn=_limit_memory if posix else None)
    try:
        stdout, stderr = p.communicate(timeout=settings.DESIGN3D_BUILD_TIMEOUT)
    except subprocess.TimeoutExpired:
        if posix:
            import signal

            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        p.kill()
        p.communicate()
        return "", "", None
    if p.returncode < 0 or "std::bad_alloc" in stderr or "out of memory" in stderr.lower():
        return stdout, stderr, None
    return stdout, stderr, p.returncode


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
        cmd = [binary(), "-o", str(out), str(src)] + (["--backend=Manifold"] if manifold() else [])
        stdout, stderr, code_ = _run(cmd, env, tmp)
        took = time.time() - t
        log = (stdout + "\n" + stderr).strip()
        if code_ is None:
            raise BuildError(
                f"The build took longer than {settings.DESIGN3D_BUILD_TIMEOUT} seconds or ran out of memory. "
                "Make it simpler: round only the plain outer block and cut holes afterwards, never minkowski "
                "or hull a shape with holes, and use a lower $fn.")
        p = subprocess.CompletedProcess([], code_, stdout, stderr)
        errors = [line for line in log.splitlines() if line.startswith(("ERROR", "WARNING: Ignoring unknown"))]
        if p.returncode != 0 or not out.exists() or out.stat().st_size == 0:
            raise BuildError("\n".join(errors[-8:]) or log[-1500:] or "OpenSCAD made no part.")
        if any(e.startswith("ERROR") for e in errors):
            raise BuildError("\n".join(errors[-8:]))
        data = out.read_bytes()
    if b"facet" not in data[:4096] and len(data) <= 84:
        raise BuildError("The part is empty: nothing to print.")


    volume = signed_volume(read_stl(data))
    if volume < 0:
        raise BuildError("The part is inside out (its volume is negative). A polyhedron's faces are listed the wrong "
                         "way round: list each face's points clockwise when you look at that face from outside.")
    if abs(volume) < 1e-6:
        raise BuildError("The part is empty: nothing to print.")
    return data, took
