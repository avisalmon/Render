"""SPR-I.8.1 improv: the scale trainer's fingering data and layout.

The layout rules are proved under Node (tests/js/spri81.test.js). Here: the Node run is part of the
suite, the fingering table seeds once and never overwrites, it is served read-only behind the gate,
it matches the published fingerings, and the player's tempo is remembered.

Traces: spec ch. 10, data model section 6a, backlog SPR-I.8.1.
"""

import io
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client

from improv.models import Player, Scale, ScaleFingering

pytestmark = pytest.mark.spri81

API = "/improv/api/"
PASSWORD = "spri81-pass-5541"

# The one-octave ascending table from masterpiano.com/piano-scales, root_pc: (right hand, left hand).
PUBLISHED = {
    0: ("1-2-3-1-2-3-4-5", "5-4-3-2-1-3-2-1"),
    7: ("1-2-3-1-2-3-4-5", "5-4-3-2-1-3-2-1"),
    2: ("1-2-3-1-2-3-4-5", "5-4-3-2-1-3-2-1"),
    9: ("1-2-3-1-2-3-4-5", "5-4-3-2-1-3-2-1"),
    4: ("1-2-3-1-2-3-4-5", "5-4-3-2-1-3-2-1"),
    11: ("1-2-3-1-2-3-4-5", "4-3-2-1-4-3-2-1"),
    5: ("1-2-3-4-1-2-3-4", "5-4-3-2-1-3-2-1"),
    10: ("4-1-2-3-1-2-3-4", "3-2-1-4-3-2-1-3"),
    3: ("3-1-2-3-4-1-2-3", "3-2-1-4-3-2-1-3"),
    8: ("3-4-1-2-3-1-2-3", "3-2-1-4-3-2-1-3"),
    1: ("2-3-1-2-3-4-1-2", "3-2-1-4-3-2-1-3"),
    6: ("2-3-4-1-2-3-1-2", "4-3-2-1-3-2-1-4"),
}


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p81member", password=PASSWORD)
    member.groups.add(group)
    stranger = User.objects.create_user("p81stranger", password=PASSWORD)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_fingerings", stdout=io.StringIO())
    return {"member": member, "stranger": stranger}


def _client(user):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def _json(client, method, url, body=None):
    return getattr(client, method)(url, body if body is not None else {}, content_type="application/json")


def test_the_layout_rules_pass_under_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [node, "--test", "tests/js/spri81.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ------------------------------------------------------------------ the data


def test_the_seed_adds_a_fingering_for_every_key_and_hand(people):
    assert ScaleFingering.objects.count() == 24
    major = Scale.objects.get(slug="major")
    assert set(ScaleFingering.objects.values_list("scale_id", flat=True)) == {major.id}
    for pc in range(12):
        assert ScaleFingering.objects.filter(root_pc=pc, hand="R").count() == 1
        assert ScaleFingering.objects.filter(root_pc=pc, hand="L").count() == 1


def test_every_fingering_matches_the_published_table(people):
    for pc, (right, left) in PUBLISHED.items():
        for hand, expected in (("R", right), ("L", left)):
            row = ScaleFingering.objects.get(root_pc=pc, hand=hand)
            got = "-".join(str(n) for n in [*row.first_octave, row.last_note])
            assert got == expected, (pc, hand, got)


def test_the_seed_is_drafted_until_avi_reads_it(people):
    assert set(ScaleFingering.objects.values_list("authorship", flat=True)) == {"ai_drafted"}


def test_the_seed_never_overwrites_and_a_second_run_adds_nothing(people):
    row = ScaleFingering.objects.get(root_pc=0, hand="R")
    row.last_note = 4
    row.authorship = "reviewed"
    row.save()
    out = io.StringIO()
    call_command("seed_improv_fingerings", stdout=out)
    assert "added 0" in out.getvalue()
    row.refresh_from_db()
    assert row.last_note == 4 and row.authorship == "reviewed"
    assert ScaleFingering.objects.count() == 24


def test_the_seed_needs_the_theory_first(db):
    with pytest.raises(Exception, match="seed_improv_theory"):
        call_command("seed_improv_fingerings", stdout=io.StringIO())


def test_a_hand_in_a_key_has_one_fingering(people):
    major = Scale.objects.get(slug="major")
    with pytest.raises(IntegrityError), transaction.atomic():
        ScaleFingering.objects.create(
            scale=major, root_pc=0, hand="R", first_octave=[1, 2, 3, 1, 2, 3, 4], next_octaves=[1, 2, 3, 1, 2, 3, 4], last_note=5
        )


@pytest.mark.parametrize(
    "values",
    [
        {"first_octave": [1, 2, 3]},
        {"first_octave": [1, 2, 3, 1, 2, 3, 6]},
        {"next_octaves": [1, 2, 3, 1, 2, 3, 0]},
        {"next_octaves": "123"},
        {"last_note": 6},
        {"root_pc": 12},
        {"hand": "X"},
    ],
)
def test_a_fingering_that_makes_no_sense_is_refused(people, values):
    major = Scale.objects.get(slug="major")
    base = dict(scale=major, root_pc=0, hand="L", first_octave=[5, 4, 3, 2, 1, 3, 2], next_octaves=[1, 4, 3, 2, 1, 3, 2], last_note=1)
    row = ScaleFingering(**{**base, **values})
    # The base row exists already, so move it out of the way of the unique check.
    if "root_pc" not in values:
        ScaleFingering.objects.filter(root_pc=0, hand="L").delete()
    with pytest.raises(Exception):
        row.full_clean()


# ------------------------------------------------------------------ the API


def test_the_fingerings_are_served_read_only(people):
    client = _client(people["member"])
    rows = client.get(f"{API}scale-fingerings/").json()
    assert len(rows) == 24
    first = rows[0]
    assert set(first) >= {"id", "scale", "root_pc", "hand", "first_octave", "next_octaves", "last_note"}
    assert first["scale"] == "major"
    assert [r["root_pc"] for r in client.get(f"{API}scale-fingerings/?root_pc=7").json()] == [7, 7]
    assert {r["hand"] for r in client.get(f"{API}scale-fingerings/?hand=R").json()} == {"R"}
    assert client.get(f"{API}scale-fingerings/?root_pc=99").json() == []
    one = client.get(f"{API}scale-fingerings/{first['id']}/")
    assert one.status_code == 200
    for method in ("post", "put", "patch", "delete"):
        assert _json(client, method, f"{API}scale-fingerings/{first['id']}/", {"last_note": 1}).status_code == 405, method


def test_the_fingerings_are_behind_the_gate(people):
    assert _client(None).get(f"{API}scale-fingerings/").status_code == 404
    assert _client(people["stranger"]).get(f"{API}scale-fingerings/").status_code == 404


# ------------------------------------------------------------------ the tempo


def test_the_tempo_starts_at_sixty_and_is_remembered(people):
    client = _client(people["member"])
    assert client.get(f"{API}player/").json()["trainer_tempo"] == 60
    assert _json(client, "patch", f"{API}player/", {"trainer_tempo": 84}).status_code == 200
    assert client.get(f"{API}player/").json()["trainer_tempo"] == 84
    assert Player.objects.get(user=people["member"]).trainer_tempo == 84


@pytest.mark.parametrize("bad", [29, 161, 0, -5, "fast"])
def test_a_tempo_outside_thirty_to_one_sixty_is_refused(people, bad):
    client = _client(people["member"])
    assert _json(client, "patch", f"{API}player/", {"trainer_tempo": bad}).status_code == 400
    assert client.get(f"{API}player/").json()["trainer_tempo"] == 60


# ------------------------------------------------------------------ the deploy and the docs


def test_the_deploy_seeds_the_fingerings_after_the_theory():
    yaml = Path("render.yaml").read_text(encoding="utf-8")
    command = next(line for line in yaml.splitlines() if "startCommand" in line)
    assert "(python manage.py seed_improv_fingerings || true)" in command
    assert command.index("manage.py seed_improv_theory ") < command.index("manage.py seed_improv_fingerings ")
    assert command.index("manage.py migrate") < command.index("manage.py seed_improv_fingerings ")


def test_the_seed_file_is_the_one_the_command_reads():
    data = json.loads(Path("improv/seed_data/fingerings.json").read_text(encoding="utf-8"))
    assert data["scale"] == "major" and len(data["fingerings"]) == 24


def test_the_docs_name_the_table_and_the_tempo():
    model = Path("docs/improv/data_model.md").read_text(encoding="utf-8")
    api = Path("docs/improv/api.md").read_text(encoding="utf-8")
    assert "`ScaleFingering`" in model and "`trainer_tempo`" in model
    assert "/improv/api/scale-fingerings/" in api and "trainer_tempo" in api
