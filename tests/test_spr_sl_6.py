"""SL-C1 — SensorLab: one way to open a sensor.

See docs/sensorlab/backlog.md (SL-C1) and spec §4.1, §9.3.

The spike (`/sensorlab/sensor-check/`) already answered the feasibility
question on a real device: |a| = 9.81 m/s² at rest, rotation live, camera
60 fps. This sprint turns that into a layer no lab has to think about, and
it exists in this shape because of three things the spike actually taught:

1. **The rate is not what the docs implied.** `devicemotion` delivered
   ~63 Hz, against the 200 Hz the spec had assumed and the mockups had
   drawn. So a rate is something a recording *measures*, never something
   the app declares.
2. **"Available" and "working" are different claims.** On a desktop with no
   accelerometer, `DeviceMotionEvent` reports available and then fires
   nothing, forever. A capability check that only asks "does the interface
   exist" would call that a working sensor.
3. **Two APIs, one shape.** The Generic Sensor API is the only route past
   ~60 Hz; `devicemotion` is the fallback that works everywhere. Analysis
   code must never branch on which one supplied a reading.

These run in a real browser against a page that injects fake sensor
sources, because the alternative — asserting about code that only behaves
on hardware no CI has — is how the earlier sprints' appearance bugs got
through.
"""

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.sprsl6, pytest.mark.django_db]

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "static" / "sensorlab" / "js" / "sensors.js"

PHONE = {"width": 390, "height": 844}


#: Django template comments, stripped before any source is scanned.
#:
#: **The second time this project has made the same mistake.** SL-A4's guard
#: against a parallel `--sl-dark-*` token set failed on the stylesheet
#: comment explaining why such a set is forbidden. This guard then failed on
#: the comment in `base.html` explaining why raw sensor APIs are forbidden —
#: prose written to document the very rule being enforced.
#:
#: The shape is worth naming because it will recur: **a guard that scans
#: source text will eventually scan the sentence describing it.** Explaining
#: a rule near the code it governs is good practice, so the fix belongs in
#: the guard, every time: read code, never prose.
TEMPLATE_COMMENT = re.compile(r"{%\s*comment\s*%}.*?{%\s*endcomment\s*%}|{#.*?#}", re.S)


def _markup_only(html):
    return TEMPLATE_COMMENT.sub("", html)


# ------------------------------------------------------- the module itself


def test_the_module_exists_and_is_the_only_door():
    """No lab should ever reach for `devicemotion` or `new Accelerometer`
    itself — that is what this module is for, and a second caller is how the
    rate-measuring and capability rules get quietly bypassed."""
    assert MODULE.is_file(), "static/sensorlab/js/sensors.js does not exist yet"
    source = MODULE.read_text(encoding="utf-8")
    assert "sensorlab.sensors" in source or "sensors" in source

    # The spike page is allowed to touch the raw APIs — it is a diagnostic
    # whose whole job is probing them. Nothing else may.
    templates = ROOT / "templates" / "sensorlab"
    offenders = []
    for path in templates.rglob("*.html"):
        if path.name == "sensor_check.html":
            continue
        text = _markup_only(path.read_text(encoding="utf-8"))
        for raw in ("devicemotion", "DeviceMotionEvent", "new Accelerometer", "new Gyroscope"):
            if raw in text:
                offenders.append(f"{path.name}: {raw}")
    assert offenders == [], f"raw sensor APIs used outside the module: {offenders}"


@pytest.fixture(scope="module")
def phone_page():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(viewport=PHONE, is_mobile=True, has_touch=True)
            yield context.new_page()
            browser.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


def _load(page, live_server):
    """The module, loaded in a real browser, on a real page of this app."""
    page.goto(live_server.url + "/sensorlab/", wait_until="domcontentloaded")
    page.wait_for_function("() => window.sensorlab && window.sensorlab.sensors")


# ------------------------------------------------------------ capability


def test_a_sensor_that_never_fires_is_not_a_working_sensor(phone_page, live_server):
    """The desktop case the spike exposed: `DeviceMotionEvent` exists, and
    nothing ever arrives. Three states, not two — present, absent, and
    present-but-silent — because only the third looks like success."""
    _load(phone_page, live_server)
    verdict = phone_page.evaluate(
        """async () => {
            // An interface that exists and never delivers.
            window.__slFakeMotion = {fires: false};
            return await window.sensorlab.sensors.probe('accelerometer', {timeoutMs: 400});
        }"""
    )
    assert verdict["available"] is True, "the interface is present, so `available` is true"
    assert verdict["working"] is False, "nothing arrived, so it is not working"
    assert verdict["state"] == "silent"


def test_a_sensor_that_delivers_is_reported_working(phone_page, live_server):
    _load(phone_page, live_server)
    verdict = phone_page.evaluate(
        """async () => {
            window.__slFakeMotion = {fires: true, hz: 50, magnitude: 9.81};
            return await window.sensorlab.sensors.probe('accelerometer', {timeoutMs: 600});
        }"""
    )
    assert verdict["state"] == "working"
    assert verdict["working"] is True


def test_a_sensor_this_device_lacks_is_absent_not_broken(phone_page, live_server):
    """spec §1 refuses a degradation tier, so a missing sensor has to be
    distinguishable in order to refuse the lab cleanly (SL-C2)."""
    _load(phone_page, live_server)
    verdict = phone_page.evaluate(
        """async () => await window.sensorlab.sensors.probe('barometer-that-does-not-exist',
                                                            {timeoutMs: 200})"""
    )
    assert verdict["available"] is False
    assert verdict["state"] == "absent"


# ----------------------------------------------------------- the readings


def test_readings_have_one_shape_whichever_api_supplied_them(phone_page, live_server):
    """Analysis code in Epic G must never branch on the source."""
    _load(phone_page, live_server)
    shapes = phone_page.evaluate(
        """async () => {
            const out = {};
            for (const source of ['generic', 'devicemotion']) {
                window.__slForceSource = source;
                window.__slFakeMotion = {fires: true, hz: 50, magnitude: 9.81};
                const run = await window.sensorlab.sensors.record('accelerometer',
                                                                  {ms: 400, requestHz: 50});
                out[source] = {
                    keys: Object.keys(run.samples[0]).sort(),
                    source: run.source,
                    count: run.samples.length,
                };
            }
            return out;
        }"""
    )
    expected = ["magnitude", "t", "x", "y", "z"]
    assert shapes["generic"]["keys"] == expected
    assert shapes["devicemotion"]["keys"] == expected
    assert shapes["generic"]["source"] != shapes["devicemotion"]["source"], "the source is recorded"


def test_the_recording_measures_the_rate_it_actually_got(phone_page, live_server):
    """§4.1's lesson as code. The spec assumed 200 Hz; the device gave 63.
    A recording that stores the *requested* rate is storing a wish."""
    _load(phone_page, live_server)
    run = phone_page.evaluate(
        """async () => {
            window.__slForceSource = 'devicemotion';
            window.__slFakeMotion = {fires: true, hz: 25, magnitude: 9.81};
            return await window.sensorlab.sensors.record('accelerometer',
                                                         {ms: 1000, requestHz: 200});
        }"""
    )
    assert run["requestedHz"] == 200, "what the lab asked for is kept"
    # What actually arrived was about 25 Hz, and that is what must be recorded.
    assert 15 <= run["achievedHz"] <= 40, f"achieved rate not measured honestly: {run['achievedHz']}"
    assert run["achievedHz"] != run["requestedHz"]


def test_the_generic_api_is_preferred_when_it_is_there(phone_page, live_server):
    """Not symmetry for its own sake: §4.1 measured devicemotion at ~63 Hz,
    and the Generic Sensor API is the only route to more."""
    _load(phone_page, live_server)
    source = phone_page.evaluate(
        """async () => {
            window.__slForceSource = null;          // let the module choose
            window.__slFakeGeneric = true;          // both available
            window.__slFakeMotion = {fires: true, hz: 50, magnitude: 9.81};
            const run = await window.sensorlab.sensors.record('accelerometer',
                                                              {ms: 300, requestHz: 100});
            return run.source;
        }"""
    )
    assert source == "generic"


def test_stopping_a_recording_releases_the_sensor(phone_page, live_server):
    """A lab that leaves the accelerometer running drains the battery of a
    phone that is meant to sit in a pocket between experiments."""
    _load(phone_page, live_server)
    leftover = phone_page.evaluate(
        """async () => {
            window.__slFakeMotion = {fires: true, hz: 50, magnitude: 9.81};
            await window.sensorlab.sensors.record('accelerometer', {ms: 300, requestHz: 50});
            return window.sensorlab.sensors.openCount();
        }"""
    )
    assert leftover == 0, "a sensor was left open after the recording finished"
