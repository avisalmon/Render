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


def _limit_memory():
    """In the child, before OpenSCAD starts: a memory ceiling, so a heavy
    part fails on its own instead of running the whole server out of memory
    (a 512 MB server restarts, and every turn on it is lost)."""
    import resource

    # RLIMIT_DATA counts what the program really allocates (not the address
    # space Qt reserves); a normal part peaks near 100 MB.
    mb = getattr(settings, "DESIGN3D_BUILD_MEMORY_MB", 350)
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
        stdout, stderr, code_ = _run([binary(), "-o", str(out), str(src)], env, tmp)
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
    return data, took
