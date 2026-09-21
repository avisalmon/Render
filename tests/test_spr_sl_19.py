"""SL-F2 — SensorLab: the phone becomes an instrument.

See docs/sensorlab/backlog.md (SL-F2) and spec §9.6 F.2.

This is the screen the app exists for. Everything before it is a course with
a quiz in front of it; here a student points their own phone at the world
and gets a number nobody gave them.

**The test that matters is the round trip**, and it runs in a real browser
against `sensors.js`'s documented `window.__slFake*` seam (SL-C1). That seam
exists precisely so this can be proven without hardware: no CI machine has
an accelerometer, and "it works on my phone" is not a test. The fake stands
in for the source; everything above it — consent gate, capture, rate
measurement, POST, the row in the database — is the real thing.

**The refusals are as much of this screen as the success.** spec §1 refuses
a degradation tier, so a lab that cannot run must say *which* wall it hit:
permission not given, no such sensor on this phone, or a sensor that is
there and answering nothing. SL-C1 already returns those three states
separately; this is where a person finally reads them.

**And the achieved rate is shown, not hidden.** §4.1 is the reason this app
is honest about its own instrument: a phone asked for 200 Hz and gave 63. A
capture screen that displays the requested figure would be lying in the one
place the app claims to be a measuring device.
"""

import os
import re

import pytest
from sensorlab_phone import MIN_TAP_PX, OVERFLOW_JS, PHONE, TAP_JS

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.sprsl19, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"
LAB = "measuring-g"
RUN = f"/sensorlab/lab/{LAB}/run/"
EXPERIMENT = f"{RUN}experiment/"

HEBREW = re.compile(r"[֐-׿]")
TEMPLATE_SYNTAX = re.compile(r"\{%|\{\{|\{#")


def _seed():
    from io import StringIO

    from django.core.management import call_command

    call_command("seed_sensorlab", stdout=StringIO())


def _on_experiment(django_user_model, name="ada", language="en", consent=True):
    from sensorlab.models import Lab, LabAttempt, PredictionAnswer, SensorConsent
    from sensorlab.profiles import profile_for

    _seed()
    user = django_user_model.objects.create_user(name, password=PASSWORD)
    profile = profile_for(user)
    profile.language = language
    profile.save(update_fields=["language"])
    if consent:
        SensorConsent.objects.grant(profile, "accelerometer")

    attempt = LabAttempt.objects.start(user=user, lab=Lab.objects.get(slug=LAB))
    while attempt.current_step != "predict":
        attempt.advance()
    for question in attempt.lab.prediction_questions.all():
        if question.kind == "multiple_choice":
            PredictionAnswer.objects.record(attempt=attempt, question=question,
                                            selected_choice=question.choices.first())
        elif question.kind == "numeric":
            PredictionAnswer.objects.record(attempt=attempt, question=question,
                                            numeric_value=9.5)
    attempt.advance()
    return user, attempt


def _body(html):
    match = re.search(r"<main[^>]*>(.*)</main>", html, re.S)
    return match.group(1) if match else html


def _markup(html):
    """The page with its scripts removed.

    Written after two assertions in a row matched the JavaScript that
    *manipulates* the very attributes they were checking for — a guard
    tripping over its own mechanism, which is the same shape as SL-A4's
    guard matching the comment that documented it. The rule this project
    keeps rediscovering: **anything that greps rendered source must first
    remove the source that is about the rule.**
    """
    return re.sub(r"<script[^>]*>.*?</script>", "", _body(html), flags=re.S)


# ------------------------------------------------------------ the screen


def test_the_placeholder_is_gone(client, django_user_model):
    """SL-D2 shipped this step saying it was not built. Epic F is what it was
    waiting for, so the waiting message must not outlive it."""
    from sensorlab.strings import text

    user, _ = _on_experiment(django_user_model)
    client.force_login(user)
    html = _body(client.get(EXPERIMENT).content.decode())

    assert text("run.experiment_not_built", "en") not in html
    assert 'data-capture' in html, "no capture UI on the experiment step"


def test_the_screen_carries_what_the_lab_asked_for(client, django_user_model):
    """The config is authored (SL-B1) and the browser needs it. Rendered as
    data attributes rather than hardcoded in JavaScript, so changing a lab in
    the admin changes the capture — which is the whole point of having
    authored configs at all."""
    user, attempt = _on_experiment(django_user_model)
    client.force_login(user)
    html = client.get(EXPERIMENT).content.decode()

    config = attempt.lab.experiment
    assert f'data-requested-hz="{config.requested_hz}"' in html
    assert f'data-duration-ms="{config.max_duration_ms}"' in html
    assert 'data-sensor="accelerometer"' in html


def test_the_instructions_are_shown_before_the_button(client, django_user_model):
    """"Lay the phone flat and do not touch it" is useless after you have
    pressed record."""
    user, _ = _on_experiment(django_user_model)
    client.force_login(user)
    html = _body(client.get(EXPERIMENT).content.decode())

    assert "Lay the phone flat" in html
    assert html.index("Lay the phone flat") < html.index("data-record")


def test_the_step_uses_instrument_mode(client, django_user_model):
    """spec §7.1 and §7.6: the instrument is never gamified, and the capture
    screen is the instrument."""
    user, _ = _on_experiment(django_user_model)
    client.force_login(user)
    assert "sl-instrument" in client.get(EXPERIMENT).content.decode()


# ------------------------------------------------------------ the refusals


def test_without_consent_the_screen_says_so_and_offers_it(client, django_user_model):
    """SL-C2 made consent this app's own promise. Here is where it is kept:
    no reading is taken, and the person is told why rather than watching a
    button do nothing."""
    user, _ = _on_experiment(django_user_model, consent=False)
    client.force_login(user)
    html = _body(client.get(EXPERIMENT).content.decode())
    text = re.sub(r"<[^>]+>", " ", html).lower()

    assert "permission" in text or "allow" in text
    assert "data-consent-needed" in html


def test_with_consent_the_screen_does_not_nag(client, django_user_model):
    user, _ = _on_experiment(django_user_model, consent=True)
    client.force_login(user)
    html = _markup(client.get(EXPERIMENT).content.decode())

    opening = re.search(r"<section[^>]*data-capture[^>]*>", html)
    assert opening, "no capture section rendered"
    assert "data-consent-needed" not in opening.group(0)
    assert "data-consent-block" not in html


def test_every_refusal_has_its_own_words(client, django_user_model):
    """Three walls, three sentences (spec §1, SL-C1's three probe states).
    "Your phone does not have this" and "your phone has it and is not
    answering" are different problems and a student deserves the true one."""
    from sensorlab.strings import STRINGS

    for key in ("capture.no_sensor", "capture.silent_sensor", "capture.needs_consent"):
        assert key in STRINGS, f"{key} has no copy"
        assert STRINGS[key]["en"] != STRINGS[key]["he"], f"{key} is untranslated"

    user, _ = _on_experiment(django_user_model)
    client.force_login(user)
    html = client.get(EXPERIMENT).content.decode()
    for key in ("capture.no_sensor", "capture.silent_sensor"):
        assert STRINGS[key]["en"] in html, f"{key} is not on the page to be shown"


# ------------------------------------------------- you cannot skip the step


def test_continuing_without_a_recording_is_refused_and_says_why(
    client, django_user_model
):
    """Symmetric with Predict (SL-E2). A lab you can walk past without
    measuring anything is a slideshow."""
    user, attempt = _on_experiment(django_user_model)
    client.force_login(user)

    response = client.post(EXPERIMENT, follow=True)
    attempt.refresh_from_db()
    assert attempt.current_step == "experiment", "Continue skipped the capture"

    text = re.sub(r"<[^>]+>", " ", _body(response.content.decode())).lower()
    assert "record" in text or "measure" in text


def test_continuing_works_once_something_has_been_recorded(client, django_user_model):
    from sensorlab.models import SensorRecording

    user, attempt = _on_experiment(django_user_model)
    SensorRecording.objects.record(
        attempt=attempt, sensor="accelerometer", requested_hz=60,
        samples=[{"t": i * 16.0, "x": 0, "y": 0, "z": 9.8} for i in range(60)],
        duration_ms=1000,
    )

    client.force_login(user)
    client.post(EXPERIMENT)
    attempt.refresh_from_db()
    assert attempt.current_step == "analysis"


def test_a_previous_capture_is_shown_when_you_come_back(client, django_user_model):
    from sensorlab.models import SensorRecording

    user, attempt = _on_experiment(django_user_model)
    SensorRecording.objects.record(
        attempt=attempt, sensor="accelerometer", requested_hz=200,
        samples=[{"t": i * 16.0, "x": 0, "y": 0, "z": 9.8} for i in range(64)],
        duration_ms=1000,
    )

    client.force_login(user)
    html = _body(client.get(EXPERIMENT).content.decode())
    assert "64" in html, "the sample count is not shown"
    # §4.1: the achieved rate, not the requested one.
    assert "62.5" in html or "62" in html


# ------------------------------------------------------------ both languages


@pytest.mark.parametrize("language,direction", [("en", "ltr"), ("he", "rtl")])
def test_the_step_renders_in_each_language(client, django_user_model, language, direction):
    user, _ = _on_experiment(django_user_model, name=f"u-{language}", language=language)
    client.force_login(user)
    html = client.get(EXPERIMENT).content.decode()

    assert f'lang="{language}"' in html
    assert f'dir="{direction}"' in html
    assert not TEMPLATE_SYNTAX.search(_body(html))
    if language == "he":
        assert HEBREW.search(_body(html))
        assert "הניחו את הטלפון" in html, "the instructions are not in Hebrew"


# ------------------------------------------------- the round trip, for real


@pytest.fixture(scope="module")
def phone_page():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(
                viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True
            )
            yield context.new_page()
            browser.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


def _sign_in(page, live_server, username):
    page.goto(live_server.url + "/sensorlab/login/", wait_until="domcontentloaded")
    page.fill("#id_username", username)
    page.fill("#id_password", PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_load_state("domcontentloaded")


def test_a_capture_reaches_the_database(phone_page, live_server, django_user_model):
    """The round trip, in a real browser, end to end.

    `window.__slFakeMotion` stands in for the hardware — SL-C1 documented
    that seam for exactly this, because no CI machine has an accelerometer
    and "it works on my phone" is not a test. Everything above the source is
    real: the consent gate, the capture loop, the rate measured from the
    samples' own timestamps, the POST, and the row that comes out.
    """
    from sensorlab.models import SensorRecording

    user, attempt = _on_experiment(django_user_model, name="phone-f2")
    _sign_in(phone_page, live_server, "phone-f2")

    phone_page.add_init_script(
        "window.__slFakeMotion = {fires: true, hz: 50, magnitude: 9.81};"
    )
    phone_page.goto(live_server.url + EXPERIMENT, wait_until="domcontentloaded")

    phone_page.click("[data-record]")
    # Wait for the BUTTON to come back, not for the result panel to appear.
    # The panel is already visible whenever an earlier recording exists, so
    # waiting on it returns instantly and reads a screen still mid-capture —
    # a wait that passes before the thing it waits for has happened.
    phone_page.wait_for_function(
        "() => !document.querySelector('[data-record]').disabled", timeout=30_000
    )

    row = SensorRecording.objects.filter(attempt=attempt).first()
    assert row is not None, "pressing record produced no recording"
    assert row.sample_count > 10, f"only {row.sample_count} samples arrived"
    assert 40 < row.achieved_hz < 60, f"achieved rate looks wrong: {row.achieved_hz}"

    shown = phone_page.inner_text("[data-result]")
    assert str(row.sample_count) in shown
    # The achieved rate, not the requested one — §4.1's whole point.
    assert str(int(row.achieved_hz)) in shown.replace(".0", "")


def test_a_silent_sensor_is_named_as_such(phone_page, live_server, django_user_model):
    """The wall a student is most likely to hit and least able to diagnose:
    the interface exists and delivers nothing. SL-C1 returns that state
    separately; this proves a person actually reads it."""
    from sensorlab.models import SensorRecording
    from sensorlab.strings import text

    _user, attempt = _on_experiment(django_user_model, name="phone-silent")
    _sign_in(phone_page, live_server, "phone-silent")

    phone_page.add_init_script("window.__slFakeMotion = {fires: false};")
    phone_page.goto(live_server.url + EXPERIMENT, wait_until="domcontentloaded")

    phone_page.click("[data-record]")
    phone_page.wait_for_selector("[data-refusal]:not([hidden])", timeout=20_000)

    shown = phone_page.inner_text("[data-refusal]")
    assert text("capture.silent_sensor", "en")[:30] in shown
    assert not SensorRecording.objects.filter(attempt=attempt).exists()


def test_the_capture_screen_holds_up_on_a_phone(phone_page, live_server, django_user_model):
    _on_experiment(django_user_model, name="phone-f2-size")
    _sign_in(phone_page, live_server, "phone-f2-size")

    failures = {}
    for language in ("en", "he"):
        phone_page.goto(live_server.url + f"/sensorlab/language/{language}/",
                        wait_until="domcontentloaded")
        phone_page.goto(live_server.url + EXPERIMENT, wait_until="domcontentloaded")
        small = phone_page.evaluate(TAP_JS, MIN_TAP_PX)
        if small:
            failures[f"{language} taps"] = small
        spill = phone_page.evaluate(OVERFLOW_JS)
        if spill["overflow"]:
            failures[f"{language} overflow"] = spill

    assert failures == {}, f"on a 390px phone: {failures}"
