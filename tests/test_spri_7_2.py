"""SPR-I.7.2 improv: every screen has a button the top piano key presses.

The browser behaviour is in test_spri_7_1_browser.py. Here: no screen with a button is left out.
Reference has only drop-downs and is the one exception.

Traces: spec ch. 8 "Two standing rules for every screen", backlog SPR-I.7.2.
"""

import io

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

pytestmark = pytest.mark.spri72

PASSWORD = "spri72-pass-9004"
WITH_A_PRIMARY = (
    "/improv/", "/improv/play/", "/improv/lessons/", "/improv/lessons/lesson-one/", "/improv/challenges/",
    "/improv/library/", "/improv/editor/", "/improv/takes/", "/improv/practice/", "/improv/progress/",
    "/improv/setup/", "/improv/spike/", "/improv/scales/", "/improv/chords/", "/improv/reading/",
)
NO_BUTTONS = ("/improv/reference/",)


@pytest.fixture
def member(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p72member", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.parametrize("path", WITH_A_PRIMARY)
def test_the_screen_has_a_primary_action(member, path):
    response = member.get(path)
    assert response.status_code == 200, path
    html = response.content.decode("utf-8")
    assert 'data-key-action="primary"' in html or 'data-key-in="primary"' in html, path


@pytest.mark.parametrize("path", NO_BUTTONS)
def test_a_screen_of_drop_downs_has_no_button_to_press(member, path):
    html = member.get(path).content.decode("utf-8")
    # The header carries the account's Log out button on every page, so look at the screen itself.
    screen = html[html.index("<main"):html.index("</main>")]
    assert "<button" not in screen
    assert "data-key-action" not in html


def test_no_screen_marks_a_destructive_button(member):
    for path in WITH_A_PRIMARY + NO_BUTTONS:
        html = member.get(path).content.decode("utf-8")
        for line in html.splitlines():
            if "data-key-action" in line:
                assert "Delete" not in line and "im-btn-danger" not in line, (path, line)
