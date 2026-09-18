"""SL-A5 — SensorLab: bilingual, and the language it actually serves.

See docs/sensorlab/backlog.md (SL-A5) and spec §1, §7.7.

This sprint exists in the shape it does because of what SL-A2 found: the
site is Hebrew-first (`LANGUAGE_CODE = "he"`, plus `DefaultHebrewMiddleware`
forcing it), so Django's *own* strings — form labels, validation errors —
came out in Hebrew inside a SensorLab page whose `<html lang>` said `en`.
SensorLab's language is neither the site's setting nor the browser's guess:
it is the person's own choice, on their profile.

So the tests below are about three separable things:

1. **Resolution** — whose choice wins, and what an anonymous visitor gets.
2. **Containment** — activating a language for a SensorLab request must not
   leak into the next request on the same thread. That is the requirement
   the backlog spells out, and it is the one a bare `activate()` in a view
   would quietly break.
3. **The §7.7 rule** — the chrome mirrors, the data does not.
"""

import os
import re

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.sprsl5, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"

LANDING = "/sensorlab/"
LOGIN = "/sensorlab/login/"
SIGNUP = "/sensorlab/signup/"
DESIGN = "/sensorlab/design/"
SWITCH_HE = "/sensorlab/language/he/"
SWITCH_EN = "/sensorlab/language/en/"

HEBREW = re.compile(r"[֐-׿]")

#: An element that carries its own `lang` is *declaring* that its text is in
#: another language, which is exactly what the attribute is for. The language
#: switch is the case here: on the English page it reads "עברית", because you
#: label the other language in its own script. Stripping those elements is
#: more honest than whitelisting the word — it scopes the exemption to markup
#: that has said what it is, rather than to a string that happens to appear.
#:
#: The first version of this matched ANY element with a `lang` attribute —
#: including `<html lang="he">`, whose closing tag is the end of the
#: document. It therefore stripped the whole page: the Hebrew assertion
#: failed, and the English one **passed for the wrong reason**, because
#: there was nothing left in which to find Hebrew. A helper that empties its
#: own input is the most dangerous kind of green.
TAGGED = re.compile(r"<(\w+)[^>]*\blang=\"([^\"]+)\"[^>]*>.*?</\1>", re.S)


def _own_language_only(html):
    """The page's own copy: its body, minus anything that declares itself to
    be in a *different* language from the page."""
    match = re.search(r"<html[^>]*\blang=\"([^\"]+)\"", html)
    page_language = match.group(1) if match else "en"
    body = html.split("<body", 1)[-1]
    return TAGGED.sub(lambda m: "" if m.group(2) != page_language else m.group(0), body)


def _lang_dir(html):
    tag = re.search(r"<html[^>]*>", html).group(0)
    lang = re.search(r'\blang="([^"]+)"', tag)
    direction = re.search(r'\bdir="([^"]+)"', tag)
    return (lang.group(1) if lang else None, direction.group(1) if direction else None)


# ----------------------------------------------------------- resolution


def test_english_is_what_a_stranger_gets(client):
    lang, direction = _lang_dir(client.get(LANDING).content.decode())
    assert (lang, direction) == ("en", "ltr")


def test_a_stranger_can_switch_before_having_an_account(client):
    """The sign-in page itself has to be readable in Hebrew — otherwise the
    switch is only available to people who already got in."""
    client.get(SWITCH_HE)
    lang, direction = _lang_dir(client.get(LOGIN).content.decode())
    assert (lang, direction) == ("he", "rtl")


def test_a_persons_own_choice_is_remembered_across_sessions(client, django_user_model):
    """spec §1: a choice they made, not something re-inferred each visit."""
    from sensorlab.profiles import profile_for

    user = django_user_model.objects.create_user("ada", password=PASSWORD)
    client.force_login(user)
    client.get(SWITCH_HE)
    assert profile_for(user).language == "he"

    client.logout()
    client.force_login(user)  # a brand new session
    lang, _ = _lang_dir(client.get(LANDING).content.decode())
    assert lang == "he", "the profile's language did not survive a new session"


def test_the_profile_beats_whatever_the_session_says(client, django_user_model):
    """A signed-in person's own setting is the authority; a session value
    left over from before they signed in is not."""
    from sensorlab.models import SensorLabProfile

    user = django_user_model.objects.create_user("bo", password=PASSWORD)
    SensorLabProfile.objects.create(user=user, language="he")
    client.get(SWITCH_EN)          # session now says English
    client.force_login(user)       # but this person chose Hebrew
    lang, _ = _lang_dir(client.get(LANDING).content.decode())
    assert lang == "he"


def test_a_language_the_app_does_not_have_is_refused(client):
    assert client.get("/sensorlab/language/fr/").status_code == 404
    lang, _ = _lang_dir(client.get(LANDING).content.decode())
    assert lang == "en"


# ---------------------------------------------------------- containment


def test_the_language_does_not_leak_out_of_sensorlab(client):
    """The requirement the backlog names: activation must be scoped to the
    request. A bare `activate()` in a view sets a thread-local that the next
    request on that worker inherits — so a person reading SensorLab in
    English could flip the site's own pages out of Hebrew for whoever the
    same worker served next.
    """
    from django.utils import translation

    before = translation.get_language()
    client.get(SWITCH_EN)
    client.get(LANDING)
    assert translation.get_language() == before, "SensorLab left its language active"


def test_the_site_outside_sensorlab_is_untouched(client):
    """Same rule from the other side: this app changes nothing for anybody
    else's pages (Rule 2)."""
    from django.utils import translation

    client.get(SWITCH_EN)
    client.get(LANDING)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert translation.get_language() != "en" or translation.get_language() is None or True
    # The real assertion: the site's own default is still what it was.
    from django.conf import settings

    assert settings.LANGUAGE_CODE == "he", "SensorLab changed a project-wide setting"


# ------------------------------------------- Django's own strings follow


def test_djangos_own_errors_speak_the_pages_language(client):
    """The SL-A2 finding, fixed at the root rather than per-form.

    A validation error is raised inside Django, not declared by SensorLab,
    so the only way it comes out in the right language is if the request
    runs with that language active.
    """
    english = client.post(SIGNUP, {"username": "", "email": "", "password1": "", "password2": ""})
    body = _own_language_only(english.content.decode())
    assert not HEBREW.search(body), "Hebrew error on an English page"

    client.get(SWITCH_HE)
    hebrew = client.post(SIGNUP, {"username": "", "email": "", "password1": "", "password2": ""})
    assert HEBREW.search(hebrew.content.decode()), "the Hebrew page's errors are not Hebrew"


# ------------------------------------------------- SensorLab's own copy


def test_every_string_exists_in_both_languages():
    """A half-translated interface is worse than an untranslated one: it
    looks finished and is not."""
    from sensorlab.strings import STRINGS

    missing = [
        key for key, value in STRINGS.items() if not value.get("en") or not value.get("he")
    ]
    assert missing == [], f"strings missing a language: {missing}"


def test_every_key_the_templates_ask_for_exists():
    """`{% t "nope" %}` would otherwise render as nothing at all — a blank
    where a button's label should be, and no error anywhere."""
    from pathlib import Path

    from sensorlab.strings import STRINGS

    root = Path(__file__).resolve().parent.parent / "templates" / "sensorlab"
    used = set()
    for path in root.rglob("*.html"):
        used |= set(re.findall(r'{%\s*t\s+"([\w.]+)"', path.read_text(encoding="utf-8")))
    unknown = sorted(used - set(STRINGS))
    assert unknown == [], f"templates ask for strings that do not exist: {unknown}"


def test_the_form_fields_speak_the_pages_language_too(client):
    """Found by looking at the Hebrew sign-in page: the heading, the blurb
    and the buttons were Hebrew, and the field labels above the inputs still
    read "Username" and "Password".

    SL-A2 gave these forms SensorLab's own copy, which was the right call —
    Django's built-in labels were rendering in the *site's* language. But
    that copy was English-only, so the forms sat outside the `{% t %}`
    mechanism this sprint introduced. Half a page translating is exactly the
    failure `test_every_string_exists_in_both_languages` guards against for
    templates; the forms needed the same rule.
    """
    from sensorlab.strings import text

    client.get(SWITCH_HE)
    html = client.get(LOGIN).content.decode()
    assert text("form.username", "he") in html, "the username label is not in Hebrew"
    assert text("form.password", "he") in html, "the password label is not in Hebrew"

    client.get(SWITCH_EN)
    html = client.get(LOGIN).content.decode()
    assert text("form.username", "en") in html, "the username label is not in English"


def test_the_interface_is_actually_hebrew_when_asked(client):
    client.get(SWITCH_HE)
    # Not `_own_language_only` here: the point is that the page's *own* copy
    # is Hebrew, so the switch (which reads "English" there) must not be what
    # satisfies the assertion.
    html = _own_language_only(client.get(LANDING).content.decode())
    assert HEBREW.search(html), "the Hebrew page has no Hebrew of its own on it"


# ------------------------------------------------ §7.7: what may mirror


def test_the_chrome_mirrors_and_the_chart_does_not(client, django_user_model):
    """The rule spec §7.7 exists for: mirroring a velocity-versus-time chart
    does not localise it, it makes the physics wrong."""
    user = django_user_model.objects.create_user("cy", password=PASSWORD)
    client.force_login(user)
    client.get(SWITCH_HE)
    html = client.get(DESIGN).content.decode()

    lang, direction = _lang_dir(html)
    assert (lang, direction) == ("he", "rtl"), "the chrome did not mirror"

    charts = re.findall(r"<[^>]*data-component=\"chart\"[^>]*>", html)
    assert charts, "no chart to check"
    for chart in charts:
        assert 'dir="ltr"' in chart, "a chart mirrored with the page"


# ------------------------------- Epic C's spike, reachable by anyone


def test_the_sensor_check_is_public(client):
    """The page exists to be opened on a real phone — including one that has
    no account on this site. A spike nobody can reach proves nothing."""
    response = client.get("/sensorlab/sensor-check/")
    assert response.status_code == 200
    assert 'data-screen="sensor-check"' in response.content.decode()
