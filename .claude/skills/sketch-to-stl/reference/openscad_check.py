"""Can OpenSCAD run on this Render server? (the sketch-to-STL experiment,
2026-10-28). Not an app yet: one hidden page that answers the question
with numbers.

build.sh downloads the standalone Linux build of OpenSCAD 2021.01 into
vendor/openscad (never fatal to a deploy). /internal/openscad-check/ is for
a superuser only (404 for anyone else). It reports whether the binary is
there and runs, then builds the test box (app/openscad_fixture.scad: the
part gpt-6.1-terra produced from Avi's sketch) and measures the time, the
build's peak memory, and the web process's own memory and the container's
limit, so we know the headroom.
"""

import os
import subprocess
import tempfile
import time
from pathlib import Path

from django.conf import settings
from django.http import Http404, JsonResponse

BIN = Path(settings.BASE_DIR) / "vendor" / "openscad" / "AppRun"
FIXTURE = Path(__file__).resolve().parent / "openscad_fixture.scad"
TIMEOUT = 90


def _read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def _mb(value):
    try:
        return round(int(value) / 1048576)
    except (TypeError, ValueError):
        return value


def _self_rss_mb():
    status = _read("/proc/self/status") or ""
    for line in status.splitlines():
        if line.startswith("VmRSS:"):
            return round(int(line.split()[1]) / 1024)
    return None


def _env():
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", HOME=tempfile.gettempdir())
    env.pop("DISPLAY", None)
    return env


def check(request):
    if not (request.user.is_authenticated and request.user.is_superuser):
        raise Http404
    report = {
        "binary": str(BIN), "installed": BIN.exists(),
        "web_process_rss_mb": _self_rss_mb(),
        "container_memory_limit_mb": _mb(_read("/sys/fs/cgroup/memory.max")),
        "container_memory_now_mb": _mb(_read("/sys/fs/cgroup/memory.current")),
    }
    if not BIN.exists():
        return JsonResponse(report)
    try:
        v = subprocess.run([str(BIN), "--version"], capture_output=True, text=True, timeout=30, env=_env())
        report["version"] = (v.stdout + v.stderr).strip()[-300:]
    except (OSError, subprocess.SubprocessError) as exc:
        report["version_error"] = repr(exc)[:300]
        return JsonResponse(report)

    import resource  # Linux only; this point is reached only where the Linux binary exists

    with tempfile.TemporaryDirectory() as tmp:
        stl = Path(tmp) / "box.stl"
        before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        t = time.time()
        try:
            p = subprocess.run([str(BIN), "-o", str(stl), str(FIXTURE)], capture_output=True, text=True,
                               timeout=TIMEOUT, env=_env())
            report["exit_code"] = p.returncode
            report["log_tail"] = (p.stdout + p.stderr).strip()[-800:]
        except subprocess.TimeoutExpired:
            report["error"] = f"timed out after {TIMEOUT}s"
        except OSError as exc:
            report["error"] = repr(exc)[:300]
        report["build_seconds"] = round(time.time() - t, 1)
        after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        report["build_peak_rss_mb"] = round(after / 1024)  # Linux reports KB; the largest child so far
        report["peak_grew_during_build"] = after > before
        report["stl_bytes"] = stl.stat().st_size if stl.exists() else 0
    report["container_memory_after_mb"] = _mb(_read("/sys/fs/cgroup/memory.current"))
    return JsonResponse(report)
