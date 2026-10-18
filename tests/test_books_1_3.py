"""SPR-BK1.3: two languages, two directions (docs/books/backlog.md).

The catalogue is complete in both languages, no interface copy is
hard-coded in a template, the language ladder (profile, session, browser,
Hebrew) is what decides, the page says its direction, and switching does
not leak to the next request on the worker."""

import re
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.utils import translation

from books.models import Profile
from books.strings import LANGUAGES, STRINGS, text

pytestmark = [pytest.mark.sprbk1_3, pytest.mark.django_db]
User = get_user_model()
HEBREW = re.compile(r"[֐-׿]")


def test_every_key_has_both_languages():
    missing = [k for k, v in STRINGS.items() if not all(v.get(code) for code in LANGUAGES)]
    assert not missing, missing


def test_a_missing_key_shows_itself():
    assert text("no.such.key", "he") == "no.such.key"


def test_format_arguments_apply_and_survive_a_bad_one():
    assert text("home.shelf_of", "en", name="Noa") == "Noa's shelf"
    assert "{name}" in text("home.shelf_of", "he")  # no args, no crash


def test_no_hebrew_is_hard_coded_in_any_template():
    for path in Path("templates/books").rglob("*.*"):
        text_ = path.read_text(encoding="utf-8")
        # Strings inside {% t %} tags come from the catalogue; anything else is a leak.
        stripped = re.sub(r"\{%.*?%\}", "", text_)
        found = HEBREW.findall(stripped)
        assert not found, f"{path}: hard-coded Hebrew"


def test_no_english_interface_copy_is_hard_coded_in_templates():
    """Visible English words outside tags, attributes and the catalogue."""
    for path in Path("templates/books").rglob("*.html"):
        text_ = path.read_text(encoding="utf-8")
        text_ = re.sub(r"<script[^>]*>.*?</script>", " ", text_, flags=re.S)
        text_ = re.sub(r"\{% comment %\}.*?\{% endcomment %\}", " ", text_, flags=re.S)
        text_ = re.sub(r"\{% block screen %\}.*?\{% endblock %\}", " ", text_, flags=re.S)
        text_ = re.sub(r"\{%.*?%\}|\{\{.*?\}\}|<[^>]+>|<!--.*?-->", " ", text_, flags=re.S)
        words = [w for w in re.findall(r"[A-Za-z]{4,}", text_) if w.lower() not in {"noa", "example", "com", "km", "rubik"}]
        assert not words, f"{path}: {words[:5]}"


@pytest.fixture
def reader(db):
    u = User.objects.create_user("noa", "noa@example.com", "pw-long-enough-1")
    Profile.objects.create(user=u, display_name="Noa", is_adult_confirmed=True, language="en")
    return u


def test_a_visitor_gets_the_browsers_language_then_hebrew(client):
    html = client.get("/books/login/", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9").content.decode()
    assert '<html lang="en" dir="ltr"' in html and "Continue with Google" in html
    html = client.get("/books/login/", HTTP_ACCEPT_LANGUAGE="fr").content.decode()
    assert '<html lang="he" dir="rtl"' in html and "המשך עם גוגל" in html


def test_the_profile_wins_over_the_browser(client, reader):
    client.force_login(reader)
    html = client.get("/books/", HTTP_ACCEPT_LANGUAGE="he").content.decode()
    assert '<html lang="en" dir="ltr"' in html
    assert "Your books will stand here" in html


def test_the_switch_saves_on_the_profile_and_stays_inside_books(client, reader):
    client.force_login(reader)
    r = client.post("/books/lang/he/", {"next": "/books/settings/"})
    assert r["Location"] == "/books/settings/"
    reader.books_profile.refresh_from_db()
    assert reader.books_profile.language == "he"
    r = client.post("/books/lang/en/", {"next": "/admin/"})
    assert r["Location"] == "/books/"
    assert client.post("/books/lang/xx/").status_code == 404


def test_a_visitors_switch_lives_in_the_session_until_onboarding(client, db):
    client.post("/books/lang/en/", {"next": "/books/login/"})
    html = client.get("/books/login/", HTTP_ACCEPT_LANGUAGE="he").content.decode()
    assert '<html lang="en"' in html
    assert 'lang="he"' in html  # the switch button offers the other language


def test_djangos_own_errors_follow_the_language(client, reader):
    client.force_login(reader)
    r = client.post("/books/settings/", {"display_name": "", "language": "en", "radius_km": 10,
                                         "theme": "light", "palette": "lamplit", "shelf_view": "lamp"})
    assert r.status_code == 200
    assert "This field is required." in r.content.decode()


def test_switching_does_not_leak_to_the_next_request(client, reader):
    client.force_login(reader)
    client.get("/books/")  # ran under English
    assert translation.get_language() in ("he", "he-il")


def test_content_language_header_is_set(client):
    r = client.get("/books/login/", HTTP_ACCEPT_LANGUAGE="en")
    assert r["Content-Language"] == "en"


def test_forms_speak_the_request_language(client, db):
    r = client.post("/books/signup/", {"email": "x@example.com", "password1": "a", "password2": "b"},
                    HTTP_ACCEPT_LANGUAGE="en")
    assert "The passwords do not match." in r.content.decode()
