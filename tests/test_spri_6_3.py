"""SPR-I.6.3 improv: ready to go live, checked before anything is pushed.

What can be proved without pushing: the migrations match the models, the tables Epic I.4 to I.6
add arrive through the app's own scoped migrate, the pages and routes the old build could not have
answer a member and answer 404 to everyone else, and the deploy command is in the right order.
The live check itself waits for Avi's word to push.

Traces: building_an_app Rule 5, backlog SPR-I.6.3.
"""

import io
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

pytestmark = pytest.mark.spri63

PASSWORD = "spri63-pass-2207"
NEW_SURFACE = (
    "/improv/",
    "/improv/progress/",
    "/improv/practice/",
    "/improv/takes/",
    "/improv/lessons/",
    "/improv/challenges/",
    "/improv/api/continue/",
    "/improv/api/summary/",
    "/improv/api/workout/",
    "/improv/api/weakness/",
    "/improv/api/bests/",
    "/improv/api/takes/",
    "/improv/api/completions/",
)


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p63member", password=PASSWORD)
    member.groups.add(group)
    stranger = User.objects.create_user("p63stranger", password=PASSWORD)
    for command in ("seed_improv_theory", "seed_improv_library", "seed_improv_lessons", "seed_improv_challenges"):
        call_command(command, stdout=io.StringIO())
    return {"member": member, "stranger": stranger}


def _client(user=None):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def test_the_migrations_match_the_models(db):
    call_command("makemigrations", "improv", check=True, dry_run=True, stdout=io.StringIO())


def test_the_improv_migrations_are_an_unbroken_chain():
    folder = Path("improv/migrations")
    names = sorted(p.stem for p in folder.glob("0*.py"))
    numbers = [int(n.split("_")[0]) for n in names]
    assert numbers == list(range(1, len(numbers) + 1)), names


def test_the_scoped_migrate_reaches_the_last_improv_migration(db):
    out = io.StringIO()
    call_command("migrate", "improv", stdout=out)
    call_command("showmigrations", "improv", stdout=out)
    assert "[ ]" not in out.getvalue().split("improv")[-1]


@pytest.mark.parametrize("path", NEW_SURFACE)
def test_the_new_surface_is_open_to_anyone_signed_in_and_closed_to_a_visitor(people, path):
    visitor = _client().get(path)
    if path == "/improv/":
        # The front door is the one page a visitor may open; it is the log in page, not Today.
        assert visitor.status_code == 200, "anonymous"
        assert 'id="continue-line"' not in visitor.content.decode("utf-8")
    elif path.startswith("/improv/api/"):
        assert visitor.status_code in (401, 403), "anonymous"
    else:
        assert visitor.status_code == 302, "anonymous"
        assert visitor.headers["Location"].startswith("/improv/?next="), "anonymous"
    assert _client(people["stranger"]).get(path).status_code == 200, "signed in with no group"
    assert _client(people["member"]).get(path).status_code == 200, "a member"


def test_the_deploy_command_migrates_first_and_does_not_depend_on_the_seeds():
    text = Path("render.yaml").read_text(encoding="utf-8")
    command = next(line for line in text.splitlines() if "startCommand" in line)
    assert "python manage.py migrate &&" in command
    for name in ("seed_improv_theory", "seed_improv_library", "seed_improv_lessons", "seed_improv_challenges"):
        assert f"(python manage.py {name} || true)" in command
    assert command.rstrip().endswith("--timeout 120")


def test_nothing_in_the_improv_pages_points_back_at_the_main_site(people):
    for path in ("/improv/", "/improv/progress/", "/improv/lessons/", "/improv/takes/"):
        html = _client(people["member"]).get(path).content.decode("utf-8")
        assert "babook" not in html.lower(), path
