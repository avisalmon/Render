"""SL-C2 — SensorLab: asking, refusing, and being refused.

See docs/sensorlab/backlog.md (SL-C2) and spec §1, §2.

**The decision this sprint exists to honour.** On Android the browser does
not prompt for motion sensors at all: a page can read your accelerometer
the moment it loads, silently, and the spike proved it — no permission
gesture was demanded. That is the documented fingerprinting exposure spec
§2 names, and a native app never faces it because the store's install
screen handles consent once.

So SensorLab asks anyway. The gate below is one this app imposes on itself
when the platform imposes none, which makes it a promise rather than a
compliance step — and a promise is exactly the kind of thing that decays
silently unless something fails when it breaks.

The other half is refusal, and its wording. `probe()` in SL-C1 returns
three states for a reason: **"your phone does not have this sensor" and
"your phone has it but it is not answering" are different sentences**, and
a student trying to do a lab deserves the true one. spec §1 refuses a
degradation tier, so a lab that cannot run must say so plainly rather than
start and misbehave.
"""

import os
import re

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.sprsl7, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"
SENSORS_PAGE = "/sensorlab/sensors/"
CONSENT_API = "/sensorlab/api/sensor-consent/"

HEBREW = re.compile(r"[֐-׿]")
PHONE = {"width": 390, "height": 844}


def _user(django_user_model, name="ada"):
    return django_user_model.objects.create_user(name, password=PASSWORD)


# ------------------------------------------------------- consent as data


def test_consent_is_recorded_per_sensor_not_all_at_once(django_user_model):
    """spec §2 says *per-sensor*. Agreeing to let a lab read the
    accelerometer is not agreeing to let it open the camera."""
    from sensorlab.models import SensorConsent
    from sensorlab.profiles import profile_for

    profile = profile_for(_user(django_user_model))
    SensorConsent.objects.grant(profile, "accelerometer")

    assert SensorConsent.objects.granted(profile, "accelerometer") is True
    assert SensorConsent.objects.granted(profile, "camera") is False


def test_consent_can_be_withdrawn(django_user_model):
    """Consent that cannot be taken back is not consent."""
    from sensorlab.models import SensorConsent
    from sensorlab.profiles import profile_for

    profile = profile_for(_user(django_user_model))
    SensorConsent.objects.grant(profile, "accelerometer")
    SensorConsent.objects.revoke(profile, "accelerometer")
    assert SensorConsent.objects.granted(profile, "accelerometer") is False


def test_withdrawing_leaves_the_record_that_it_happened(django_user_model):
    """A revoked grant is not deleted. "This person agreed on Tuesday and
    withdrew on Friday" is the honest record; deleting the row would make it
    look as though they never agreed at all."""
    from sensorlab.models import SensorConsent
    from sensorlab.profiles import profile_for

    profile = profile_for(_user(django_user_model))
    SensorConsent.objects.grant(profile, "accelerometer")
    SensorConsent.objects.revoke(profile, "accelerometer")

    row = SensorConsent.objects.get(profile=profile, sensor="accelerometer")
    assert row.granted_at is not None
    assert row.revoked_at is not None


def test_one_persons_consent_is_not_anothers(django_user_model):
    from sensorlab.models import SensorConsent
    from sensorlab.profiles import profile_for

    a = profile_for(_user(django_user_model, "a"))
    b = profile_for(_user(django_user_model, "b"))
    SensorConsent.objects.grant(a, "accelerometer")
    assert SensorConsent.objects.granted(b, "accelerometer") is False


# --------------------------------------------------------------- the api


def test_an_anonymous_caller_cannot_grant_anything(client):
    response = client.post(CONSENT_API, {"sensor": "accelerometer"}, content_type="application/json")
    assert response.status_code in (401, 403)


def test_a_person_grants_and_withdraws_their_own(client, django_user_model):
    from sensorlab.models import SensorConsent
    from sensorlab.profiles import profile_for

    user = _user(django_user_model)
    client.force_login(user)

    assert client.post(CONSENT_API, {"sensor": "accelerometer"},
                       content_type="application/json").status_code in (200, 201)
    assert SensorConsent.objects.granted(profile_for(user), "accelerometer") is True

    assert client.delete(CONSENT_API + "accelerometer/").status_code in (200, 204)
    assert SensorConsent.objects.granted(profile_for(user), "accelerometer") is False


def test_the_api_refuses_a_sensor_the_app_does_not_know(client, django_user_model):
    """Otherwise the consent table fills with typos that nothing will ever
    match against."""
    client.force_login(_user(django_user_model))
    response = client.post(CONSENT_API, {"sensor": "flux-capacitor"}, content_type="application/json")
    assert response.status_code == 400


def test_consent_is_always_about_the_caller(client, django_user_model):
    """There is no route to grant on someone else's behalf — the endpoint
    resolves the profile from the session, same rule as profile/me/."""
    from sensorlab.models import SensorConsent
    from sensorlab.profiles import profile_for

    victim = _user(django_user_model, "victim")
    client.force_login(_user(django_user_model, "attacker"))
    client.post(CONSENT_API, {"sensor": "accelerometer", "profile": profile_for(victim).pk,
                              "user": victim.pk}, content_type="application/json")
    assert SensorConsent.objects.granted(profile_for(victim), "accelerometer") is False


# ------------------------------------------------------------ the screen


def test_the_sensors_screen_lists_what_this_device_can_do(client, django_user_model):
    client.force_login(_user(django_user_model))
    html = client.get(SENSORS_PAGE).content.decode()
    assert 'data-screen="sensors"' in html
    # The screen is rendered by the page; the states are filled in by the
    # browser, so what the server must ship is a slot per known sensor.
    assert html.count('data-sensor="') >= 3


def test_the_sensors_screen_is_behind_the_gate(client):
    response = client.get(SENSORS_PAGE)
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sensorlab/login/")


def test_the_screen_speaks_both_languages(client, django_user_model):
    client.force_login(_user(django_user_model))
    client.get("/sensorlab/language/he/")
    assert HEBREW.search(client.get(SENSORS_PAGE).content.decode())


# ---------------------------------------------- the gate, in a browser


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


def _signed_in(page, live_server, django_user_model):
    django_user_model.objects.filter(username="gate-tester").delete()
    django_user_model.objects.create_user("gate-tester", password=PASSWORD)
    page.goto(live_server.url + "/sensorlab/login/", wait_until="domcontentloaded")
    page.fill("#id_username", "gate-tester")
    page.fill("#id_password", PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_function("() => window.sensorlab && window.sensorlab.sensors")


def test_nothing_is_read_before_the_person_agrees(phone_page, live_server, django_user_model):
    """The promise in one assertion.

    The browser would hand over the accelerometer without asking. SensorLab
    does not take it. `request()` must refuse to start a sensor while
    consent is absent — otherwise the gate is decoration and the data was
    already read by the time anybody saw a dialog.
    """
    _signed_in(phone_page, live_server, django_user_model)
    result = phone_page.evaluate(
        """async () => {
            window.__slFakeMotion = {fires: true, hz: 50, magnitude: 9.81};
            window.sensorlab.sensors.__resetConsent();
            const attempt = await window.sensorlab.sensors.request('accelerometer',
                                                                   {ms: 300, autoPrompt: false});
            return {state: attempt.state, samples: (attempt.samples || []).length,
                    opened: window.sensorlab.sensors.openCount()};
        }"""
    )
    assert result["state"] == "needs-consent"
    assert result["samples"] == 0, "readings were taken before consent — the gate is decoration"
    assert result["opened"] == 0


def test_after_agreeing_the_sensor_runs(phone_page, live_server, django_user_model):
    _signed_in(phone_page, live_server, django_user_model)
    result = phone_page.evaluate(
        """async () => {
            window.__slFakeMotion = {fires: true, hz: 50, magnitude: 9.81};
            window.sensorlab.sensors.__resetConsent();
            await window.sensorlab.sensors.grant('accelerometer');
            const run = await window.sensorlab.sensors.request('accelerometer',
                                                               {ms: 400, autoPrompt: false});
            return {state: run.state, samples: (run.samples || []).length};
        }"""
    )
    assert result["state"] == "ok"
    assert result["samples"] > 0


def test_a_missing_sensor_and_a_silent_one_are_told_apart(phone_page, live_server, django_user_model):
    """spec §1 refuses a degradation tier, so the refusal has to carry the
    right reason. "Your phone does not have this" and "your phone has it and
    it is not answering" are different sentences and only one of them is
    true at a time."""
    _signed_in(phone_page, live_server, django_user_model)
    out = phone_page.evaluate(
        """async () => {
            window.sensorlab.sensors.__resetConsent();
            await window.sensorlab.sensors.grant('accelerometer');

            window.__slFakeMotion = {fires: false};          // present, silent
            const silent = await window.sensorlab.sensors.request('accelerometer',
                                                                  {ms: 300, autoPrompt: false});
            const absent = await window.sensorlab.sensors.request('flux-capacitor',
                                                                  {ms: 300, autoPrompt: false});
            return {silent: silent.state, absent: absent.state};
        }"""
    )
    assert out["silent"] == "silent"
    assert out["absent"] == "absent"


def test_a_sensor_we_cannot_check_is_never_called_missing(phone_page, live_server, django_user_model):
    """Found by looking at the rendered screen: it said "this phone does not
    have one" about a camera and a microphone on a machine that has both.

    The cause was a short list. The module knew four motion sensors; the
    model knows ten; anything unlisted fell through to `absent`. So the page
    reported a hardware fact it had never checked — the precise dishonesty
    this whole sprint is about, committed by the screen built to prevent it.

    Camera and microphone presence *is* knowable without reading anything:
    `enumerateDevices()` reports device kinds (videoinput, audioinput) with
    empty labels and no permission. But knowing the hardware exists is not
    knowing it works, so neither `working` nor `silent` would be true
    either. Hence a fourth state: **present** — it is there, we have not
    opened it, and saying more would be inventing.
    """
    _signed_in(phone_page, live_server, django_user_model)
    out = phone_page.evaluate(
        """async () => ({
            camera: (await window.sensorlab.sensors.probe('camera', {timeoutMs: 500})).state,
            microphone: (await window.sensorlab.sensors.probe('microphone', {timeoutMs: 500})).state,
            nonsense: (await window.sensorlab.sensors.probe('flux-capacitor', {timeoutMs: 200})).state
        })"""
    )
    # This browser reports a videoinput and an audioinput, so "absent" is a
    # claim about hardware that is simply untrue.
    assert out["camera"] == "present", f"camera reported as {out['camera']}"
    assert out["microphone"] == "present", f"microphone reported as {out['microphone']}"
    assert out["nonsense"] == "absent", "a sensor that genuinely is not a thing should be absent"


def test_hidden_really_hides(phone_page, live_server, django_user_model):
    """Found in the rendered screen: every sensor card showed an "Allow"
    button, including ones reported as present-but-not-answering, whose
    button carries the `hidden` attribute.

    `[hidden]` is `display: none` from the browser's own stylesheet, and any
    author rule that sets `display` outranks it — `.sl-button` sets
    `display: inline-flex`, so every button in this app was immune to being
    hidden. The same shape as SL-A4.1's invisible front door: a rule in our
    stylesheet quietly defeating what the markup said.

    Guarded here rather than on this one screen, because it applies to every
    element the app will ever try to hide.
    """
    _signed_in(phone_page, live_server, django_user_model)
    phone_page.goto(live_server.url + "/sensorlab/sensors/", wait_until="domcontentloaded")
    visible_but_hidden = phone_page.evaluate(
        """() => {
            const probe = document.createElement('button');
            probe.className = 'sl-button';
            probe.hidden = true;
            probe.textContent = 'x';
            document.body.appendChild(probe);
            const shown = getComputedStyle(probe).display !== 'none';
            probe.remove();
            return shown;
        }"""
    )
    assert visible_but_hidden is False, "a [hidden] element is still displayed"
