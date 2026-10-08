"""SPR-I.2.2 improv: Style, Progression and Tag, the starter library, and their API.

What is load-bearing here:

* A groove is JSON, so its shape is checked in one place (improv/grooves.py) and
  that check guards the model, the admin and the API alike. A groove the band
  engine cannot read must be refused when it is saved, not when it is played.
* Presets are read-only through the API, a player's own rows are fully editable,
  and another player's rows do not exist as far as a player can tell.
* Every seeded progression parses with the real parser (run under Node), because
  the chart text is the only copy of the harmony.
* The seed adds what is missing and never overwrites an edit.

Traces: spec ch. 3, 7; data model sections 2 and 3; backlog SPR-I.2.2.
"""

import copy
import io
import json
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path
from unittest import mock

import pytest
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client

from improv.models import Progression, Style, Tag

pytestmark = pytest.mark.spri22

API = "/improv/api/"
PASSWORD = "spri22-pass-4417"
LIBRARY = Path("improv/seed_data/library.json")

STARTER_STYLES = {
    "medium-swing": ("jazz", "swing"),
    "blues-shuffle": ("blues", "shuffle"),
    "bossa-nova": ("latin", "straight"),
    "pop-ballad": ("pop", "straight"),
    "rock-straight": ("rock", "straight"),
    "gospel-shuffle": ("gospel", "shuffle"),
}


def seed():
    out = io.StringIO()
    call_command("seed_improv_library", stdout=out)
    return out.getvalue()


def good_groove(**over):
    groove = {
        "drums": {"kick": [1] + [0] * 15, "snare": [0] * 4 + [1] + [0] * 11, "hat": [0.5, 0] * 8},
        "bass": {"rule": "root_fifth", "range": [36, 55]},
        "comp": {"rhythm": [[0, 8], [8, 8]], "voicing": "triad", "register": [52, 76]},
    }
    groove.update(over)
    return groove


def make_style(**over):
    fields = {
        "name": "Test groove",
        "slug": "test-groove",
        "genre": "jazz",
        "feel": "swing",
        "swing_ratio": "0.60",
        "time_signature": "4/4",
        "default_tempo": 100,
        "min_tempo": 60,
        "max_tempo": 200,
        **good_groove(),
    }
    fields.update(over)
    return Style(**fields)


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    one = User.objects.create_user(username="pl-one", password=PASSWORD)
    two = User.objects.create_user(username="pl-two", password=PASSWORD)
    one.groups.add(group)
    two.groups.add(group)
    stranger = User.objects.create_user(username="pl-stranger", password=PASSWORD)
    admin = User.objects.create_superuser(username="pl-admin", password=PASSWORD, email="a@example.com")
    return {"one": one, "two": two, "stranger": stranger, "admin": admin}


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


def send(client, method, url, body=None):
    return getattr(client, method)(url, json.dumps(body or {}), content_type="application/json")


# ============================================================ the models


def test_a_groove_that_is_well_formed_saves(db):
    style = make_style()
    style.full_clean()
    style.save()
    assert str(style) == "Test groove"
    assert style.is_preset is False and style.owner is None


@pytest.mark.parametrize(
    "mutate, field",
    [
        (lambda g: g["drums"].update(cowbell=[0] * 16), "drums"),
        (lambda g: g["drums"].update(kick=[1] * 15), "drums"),
        (lambda g: g["drums"].update(kick=[2] + [0] * 15), "drums"),
        (lambda g: g["drums"].update(kick=["x"] + [0] * 15), "drums"),
        (lambda g: g.update(drums=[1, 2, 3]), "drums"),
        (lambda g: g.update(drums={}), "drums"),
        (lambda g: g["bass"].update(rule="oompah"), "bass"),
        (lambda g: g["bass"].update(range=[55, 36]), "bass"),
        (lambda g: g["bass"].update(range=[0, 200]), "bass"),
        (lambda g: g.update(bass={"range": [36, 55]}), "bass"),
        (lambda g: g["comp"].update(voicing="cluster"), "comp"),
        (lambda g: g["comp"].update(rhythm=[[0, 20]]), "comp"),
        (lambda g: g["comp"].update(rhythm=[[8, 4], [0, 4]]), "comp"),
        (lambda g: g["comp"].update(rhythm=[[0, 6], [4, 4]]), "comp"),
        (lambda g: g["comp"].update(rhythm=[[0, 0]]), "comp"),
        (lambda g: g["comp"].update(rhythm=[]), "comp"),
        (lambda g: g["comp"].update(register=[80, 60]), "comp"),
        (lambda g: g["bass"].update(range=[36, 44]), "bass"),
        (lambda g: g["comp"].update(register=[60, 72]), "comp"),
        (lambda g: g.update(comp="stabs"), "comp"),
    ],
)
def test_a_groove_the_engine_could_not_read_is_refused_at_save(db, mutate, field):
    groove = copy.deepcopy(good_groove())
    mutate(groove)
    style = make_style(**groove)
    with pytest.raises(ValidationError) as caught:
        style.full_clean()
    assert field in caught.value.message_dict, caught.value.message_dict


def test_a_waltz_needs_a_twelve_step_grid(db):
    waltz = make_style(
        time_signature="3/4",
        drums={"kick": [1] + [0] * 11, "hat": [0.5, 0, 0, 0] * 3},
        comp={"rhythm": [[0, 6], [6, 6]], "voicing": "triad", "register": [52, 76]},
    )
    waltz.full_clean()
    wrong = make_style(time_signature="3/4")
    with pytest.raises(ValidationError) as caught:
        wrong.full_clean()
    assert "drums" in caught.value.message_dict


def test_the_bar_cannot_be_asked_for_in_a_signature_the_band_cannot_play(db):
    for bad in ("4/16", "13/4", "1/4", "four", ""):
        with pytest.raises(ValidationError) as caught:
            make_style(time_signature=bad).full_clean()
        assert "time_signature" in caught.value.message_dict, bad


def test_tempo_and_swing_have_sane_limits(db):
    cases = {
        "swing_ratio": ["0.40", "0.80"],
        "default_tempo": [10, 400],
        "min_tempo": [10],
        "max_tempo": [400],
    }
    for field, values in cases.items():
        for value in values:
            with pytest.raises(ValidationError) as caught:
                make_style(**{field: value}).full_clean()
            assert field in caught.value.message_dict, (field, value)


def test_the_default_tempo_sits_between_the_minimum_and_the_maximum(db):
    for fields in ({"default_tempo": 50}, {"default_tempo": 210}, {"min_tempo": 150, "max_tempo": 100, "default_tempo": 120}):
        with pytest.raises(ValidationError):
            make_style(**fields).full_clean()


def test_a_style_slug_is_unique(db):
    make_style().save()
    with pytest.raises(IntegrityError), transaction.atomic():
        make_style().save()


def test_a_progression_needs_a_chart_a_key_and_a_difficulty_in_range(db):
    base = {"title": "T", "slug": "t", "genre": "jazz", "chart": "| C | G |", "home_key": "C", "difficulty": 2}
    Progression(**base).full_clean()
    for field, bad in (("chart", "   "), ("chart", ""), ("home_key", "H"), ("home_key", "Cmaj"), ("difficulty", 0), ("difficulty", 6)):
        with pytest.raises(ValidationError) as caught:
            Progression(**{**base, field: bad}).full_clean()
        assert field in caught.value.message_dict, (field, bad)


def test_a_progression_chart_has_a_size_limit(db):
    base = {"title": "T", "slug": "t", "genre": "jazz", "home_key": "C", "chart": "| C |" * 5000}
    with pytest.raises(ValidationError) as caught:
        Progression(**base).full_clean()
    assert "chart" in caught.value.message_dict


def test_home_key_accepts_the_ways_a_key_is_written(db):
    for key in ("C", "Eb", "F#", "Am", "F#m", "Bbm"):
        Progression(title="T", slug="t", genre="jazz", chart="| C |", home_key=key).full_clean()


def test_progression_tags_are_many_to_many_and_tag_slugs_are_unique(db):
    a = Tag.objects.create(name="turnaround", slug="turnaround")
    b = Tag.objects.create(name="blues", slug="blues")
    p = Progression.objects.create(title="T", slug="t", genre="jazz", chart="| C |", home_key="C")
    p.tags.set([a, b])
    assert sorted(t.slug for t in p.tags.all()) == ["blues", "turnaround"]
    with pytest.raises(IntegrityError), transaction.atomic():
        Tag.objects.create(name="Blues again", slug="blues")


def test_deleting_a_style_keeps_the_progressions_that_used_it(db):
    style = make_style()
    style.save()
    p = Progression.objects.create(title="T", slug="t", genre="jazz", chart="| C |", home_key="C", default_style=style)
    style.delete()
    p.refresh_from_db()
    assert p.default_style is None


def test_deleting_a_player_removes_their_own_rows_and_not_the_presets(db, people):
    mine = make_style(slug="mine", owner=people["one"])
    mine.save()
    preset = make_style(slug="preset", is_preset=True)
    preset.save()
    people["one"].delete()
    assert not Style.objects.filter(slug="mine").exists()
    assert Style.objects.filter(slug="preset").exists()


def test_a_progression_remembers_when_it_was_changed(db):
    p = Progression.objects.create(title="T", slug="t", genre="jazz", chart="| C |", home_key="C")
    first = p.updated_at
    with mock.patch("django.utils.timezone.now", return_value=first + timedelta(minutes=5)):
        p.chart = "| C | G |"
        p.save()
    p.refresh_from_db()
    assert p.updated_at == first + timedelta(minutes=5) and p.created_at == first


# ============================================================ the starter library


@pytest.fixture
def library(db):
    seed()


def test_the_seed_adds_the_six_starter_grooves(library):
    assert set(STARTER_STYLES) <= set(Style.objects.values_list("slug", flat=True))
    for slug, (genre, feel) in STARTER_STYLES.items():
        style = Style.objects.get(slug=slug)
        assert (style.genre, style.feel) == (genre, feel), slug
        assert style.is_preset and style.owner is None


def test_every_seeded_groove_passes_the_same_check_as_a_saved_one(library):
    for style in Style.objects.all():
        style.full_clean()


def test_a_swung_groove_swings_and_a_straight_one_does_not(library):
    for style in Style.objects.all():
        if style.feel == "straight":
            assert float(style.swing_ratio) == 0.5, style.slug
        else:
            assert float(style.swing_ratio) > 0.55, style.slug


def test_the_seed_adds_progressions_tags_and_links_them(library):
    assert Progression.objects.count() >= 10
    assert Tag.objects.count() >= 5
    for p in Progression.objects.all():
        p.full_clean()
        assert p.is_preset and p.owner is None
        assert p.default_style is not None, p.slug
        assert p.tags.exists(), p.slug
    assert Progression.objects.filter(tags__slug="minor-ii-v").exists()
    assert Progression.objects.filter(tags__slug="key-change").exists()


def test_the_library_is_generic_patterns_not_named_songs(library):
    banned = ("autumn leaves", "all the things", "giant steps", "blue bossa", "take the a train", "fly me", "misty")
    for p in Progression.objects.all():
        text = f"{p.title} {p.description}".lower()
        for name in banned:
            assert name not in text, f"{p.slug} names a song: {name}"


def test_the_seed_run_twice_changes_nothing(db):
    seed()
    counts = (Style.objects.count(), Progression.objects.count(), Tag.objects.count())
    second = seed()
    assert (Style.objects.count(), Progression.objects.count(), Tag.objects.count()) == counts
    assert "added 0" in second.lower()


def test_the_seed_never_overwrites_an_edit_or_a_deleted_tag_link(library):
    style = Style.objects.get(slug="medium-swing")
    style.default_tempo = 77
    style.save()
    p = Progression.objects.get(slug="ii-v-i-major")
    p.chart = "| C |"
    p.save()
    p.tags.clear()
    seed()
    style.refresh_from_db()
    p.refresh_from_db()
    assert style.default_tempo == 77
    assert p.chart == "| C |"
    assert not p.tags.exists(), "re-running the seed put a tag back the owner had removed"


def test_the_seed_fills_in_a_row_somebody_deleted(library):
    Progression.objects.filter(slug="twelve-bar-blues").delete()
    out = seed()
    assert Progression.objects.filter(slug="twelve-bar-blues").exists()
    assert "added 1" in out.lower()


def test_every_seeded_chart_parses_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run(
        [node, "--test", "tests/js/spri22.test.js"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


def test_the_seed_file_keeps_to_its_own_shape():
    data = json.loads(LIBRARY.read_text(encoding="utf-8"))
    slugs = [p["slug"] for p in data["progressions"]]
    assert len(slugs) == len(set(slugs)), "two progressions share a slug"
    tag_slugs = {t["slug"] for t in data["tags"]}
    style_slugs = {s["slug"] for s in data["styles"]}
    for p in data["progressions"]:
        assert set(p["tags"]) <= tag_slugs, p["slug"]
        assert p["default_style"] in style_slugs, p["slug"]


# ============================================================ the API: access


@pytest.mark.parametrize("path", ["styles", "progressions", "tags"])
def test_a_visitor_is_refused_and_anyone_signed_in_gets_the_list(people, path):
    assert Client().get(f"{API}{path}/").status_code in (401, 403)
    assert client_for(people["stranger"]).get(f"{API}{path}/").status_code == 200
    assert client_for(people["one"]).get(f"{API}{path}/").status_code == 200
    assert client_for(people["admin"]).get(f"{API}{path}/").status_code == 200


def test_a_visitor_cannot_write_and_a_person_without_a_group_writes_only_their_own(people):
    visitor = Client()
    assert send(visitor, "post", f"{API}styles/", {"name": "x"}).status_code in (401, 403)
    assert send(visitor, "post", f"{API}progressions/", {"title": "x"}).status_code in (401, 403)
    assert Style.objects.filter(name="x").count() == 0
    # A signed-in person with no group is a normal player now: a bad payload is a 400, not a 404.
    client = client_for(people["stranger"])
    assert send(client, "post", f"{API}styles/", {"name": "x"}).status_code == 400
    assert send(client, "post", f"{API}progressions/", {"title": "x"}).status_code == 400


# ============================================================ the API: styles


def style_body(**over):
    body = {
        "name": "My groove",
        "genre": "rock",
        "feel": "straight",
        "swing_ratio": "0.50",
        "time_signature": "4/4",
        "default_tempo": 110,
        "min_tempo": 70,
        "max_tempo": 180,
        **good_groove(),
    }
    body.update(over)
    return body


def test_the_list_shows_presets_and_my_own_and_nobody_elses(library, people):
    one = client_for(people["one"])
    assert send(one, "post", f"{API}styles/", style_body(name="Mine")).status_code == 201
    assert send(client_for(people["two"]), "post", f"{API}styles/", style_body(name="Theirs")).status_code == 201
    names = [s["name"] for s in one.get(f"{API}styles/").json()]
    assert "Mine" in names and "Medium swing" in names and "Theirs" not in names
    assert len(names) == len(STARTER_STYLES) + 1


def test_the_list_is_the_whole_visible_set_without_paging(library, people):
    body = client_for(people["one"]).get(f"{API}styles/").json()
    assert isinstance(body, list)


def test_creating_a_style_makes_it_mine_and_never_a_preset(people):
    client = client_for(people["one"])
    response = send(client, "post", f"{API}styles/", style_body(is_preset=True, owner=people["two"].pk, slug="evil"))
    assert response.status_code == 201, response.content
    body = response.json()
    row = Style.objects.get(pk=body["id"])
    assert row.owner == people["one"] and row.is_preset is False
    assert row.slug != "evil" and row.slug.startswith("my-groove")
    assert body["is_preset"] is False and body["is_mine"] is True
    assert "owner" not in body, "a player's id has no business in a style payload"


def test_two_styles_with_one_name_get_two_slugs(people):
    client = client_for(people["one"])
    a = send(client, "post", f"{API}styles/", style_body()).json()
    b = send(client, "post", f"{API}styles/", style_body()).json()
    assert a["slug"] != b["slug"]


def test_a_bad_groove_is_a_400_that_names_the_field(people):
    client = client_for(people["one"])
    bad = good_groove()
    bad["bass"]["rule"] = "oompah"
    response = send(client, "post", f"{API}styles/", style_body(bass=bad["bass"]))
    assert response.status_code == 400
    assert "bass" in response.json()
    assert Style.objects.count() == 0


def test_the_signature_and_the_grid_are_checked_together(people):
    client = client_for(people["one"])
    response = send(client, "post", f"{API}styles/", style_body(time_signature="3/4"))
    assert response.status_code == 400
    assert "drums" in response.json()


def test_i_can_change_and_delete_my_own_style(people):
    client = client_for(people["one"])
    made = send(client, "post", f"{API}styles/", style_body()).json()
    url = f"{API}styles/{made['id']}/"
    changed = send(client, "patch", url, {"default_tempo": 120})
    assert changed.status_code == 200 and changed.json()["default_tempo"] == 120
    full = send(client, "put", url, style_body(name="Renamed"))
    assert full.status_code == 200 and full.json()["name"] == "Renamed"
    assert full.json()["slug"] == made["slug"], "the slug does not follow the name, links would break"
    assert client.delete(url).status_code == 204
    assert not Style.objects.filter(pk=made["id"]).exists()


def test_a_patch_cannot_make_a_row_a_preset_or_give_it_away(people):
    client = client_for(people["one"])
    made = send(client, "post", f"{API}styles/", style_body()).json()
    send(client, "patch", f"{API}styles/{made['id']}/", {"is_preset": True, "owner": people["two"].pk, "slug": "taken"})
    row = Style.objects.get(pk=made["id"])
    assert row.is_preset is False and row.owner == people["one"] and row.slug == made["slug"]


@pytest.mark.parametrize("who", ["one", "admin"])
def test_a_preset_cannot_be_changed_or_deleted_through_the_api(library, people, who):
    """Presets are edited in the admin. A player who could rewrite one would change
    it for every player."""
    client = client_for(people[who])
    preset = Style.objects.get(slug="medium-swing")
    url = f"{API}styles/{preset.pk}/"
    before = (preset.name, preset.default_tempo)
    assert send(client, "patch", url, {"default_tempo": 1}).status_code == 403
    assert send(client, "put", url, style_body()).status_code == 403
    assert client.delete(url).status_code == 403
    preset.refresh_from_db()
    assert (preset.name, preset.default_tempo) == before


def test_another_players_style_does_not_exist_for_me(people):
    theirs = send(client_for(people["two"]), "post", f"{API}styles/", style_body()).json()
    mine = client_for(people["one"])
    url = f"{API}styles/{theirs['id']}/"
    assert mine.get(url).status_code == 404
    assert send(mine, "patch", url, {"name": "stolen"}).status_code == 404
    assert mine.delete(url).status_code == 404
    assert Style.objects.get(pk=theirs["id"]).name == "My groove"


def test_styles_filter_by_genre_and_feel_and_an_unknown_value_is_empty(library, people):
    client = client_for(people["one"])
    jazz = client.get(f"{API}styles/?genre=jazz").json()
    assert jazz and all(s["genre"] == "jazz" for s in jazz)
    shuffles = client.get(f"{API}styles/?feel=shuffle").json()
    assert shuffles and all(s["feel"] == "shuffle" for s in shuffles)
    assert client.get(f"{API}styles/?genre=polka").json() == []
    mine = client.get(f"{API}styles/?mine=1").json()
    assert mine == []


# ============================================================ the API: progressions


def prog_body(**over):
    body = {
        "title": "My changes",
        "genre": "jazz",
        "chart": "| Dm7 | G7 | Cmaj7 | % |",
        "home_key": "C",
        "time_signature": "4/4",
        "default_tempo": 120,
        "difficulty": 2,
        "description": "mine",
        "tags": [],
    }
    body.update(over)
    return body


def test_the_preset_progressions_are_listed_with_tags_and_style(library, people):
    rows = client_for(people["one"]).get(f"{API}progressions/").json()
    assert len(rows) == Progression.objects.count()
    row = next(r for r in rows if r["slug"] == "ii-v-i-major")
    assert row["tags"] and row["default_style"] and row["is_preset"] is True and row["is_mine"] is False
    assert "chart" in row and "home_key" in row and "difficulty" in row
    assert "owner" not in row


def test_i_can_create_a_progression_with_tags_and_a_style(library, people):
    client = client_for(people["one"])
    style = Style.objects.get(slug="bossa-nova")
    body = prog_body(tags=["turnaround", "blues"], default_style=style.pk)
    response = send(client, "post", f"{API}progressions/", body)
    assert response.status_code == 201, response.content
    row = Progression.objects.get(pk=response.json()["id"])
    assert row.owner == people["one"] and row.is_preset is False
    assert sorted(t.slug for t in row.tags.all()) == ["blues", "turnaround"]
    assert row.default_style == style
    assert row.slug.startswith("my-changes")


def test_an_unknown_tag_is_a_400_not_a_new_tag(library, people):
    before = Tag.objects.count()
    response = send(client_for(people["one"]), "post", f"{API}progressions/", prog_body(tags=["no-such-tag"]))
    assert response.status_code == 400 and "tags" in response.json()
    assert Tag.objects.count() == before


def test_a_style_that_is_not_visible_to_me_cannot_be_my_default(people):
    theirs = send(client_for(people["two"]), "post", f"{API}styles/", style_body()).json()
    response = send(client_for(people["one"]), "post", f"{API}progressions/", prog_body(default_style=theirs["id"]))
    assert response.status_code == 400 and "default_style" in response.json()


def test_a_progression_with_no_chart_or_a_wrong_key_is_a_400(people):
    client = client_for(people["one"])
    for field, bad in (("chart", "  "), ("home_key", "Q"), ("difficulty", 9), ("genre", "polka"), ("default_tempo", 5)):
        response = send(client, "post", f"{API}progressions/", prog_body(**{field: bad}))
        assert response.status_code == 400, (field, bad)
        assert field in response.json(), (field, bad)
    assert Progression.objects.count() == 0


def test_i_can_edit_and_delete_my_progression_but_not_a_preset(library, people):
    client = client_for(people["one"])
    made = send(client, "post", f"{API}progressions/", prog_body()).json()
    url = f"{API}progressions/{made['id']}/"
    assert send(client, "patch", url, {"chart": "| C | F |"}).json()["chart"] == "| C | F |"
    assert client.delete(url).status_code == 204
    preset = Progression.objects.get(slug="ii-v-i-major")
    purl = f"{API}progressions/{preset.pk}/"
    assert send(client, "patch", purl, {"chart": "| C |"}).status_code == 403
    assert client.delete(purl).status_code == 403
    preset.refresh_from_db()
    assert preset.chart != "| C |"


def test_another_players_progression_does_not_exist_for_me(people):
    theirs = send(client_for(people["two"]), "post", f"{API}progressions/", prog_body()).json()
    mine = client_for(people["one"])
    url = f"{API}progressions/{theirs['id']}/"
    assert mine.get(url).status_code == 404
    assert send(mine, "patch", url, {"title": "stolen"}).status_code == 404
    assert mine.delete(url).status_code == 404
    assert [r for r in mine.get(f"{API}progressions/").json() if r["title"] == "My changes"] == []


def test_progressions_filter_by_genre_tag_difficulty_mine_and_search(library, people):
    client = client_for(people["one"])
    send(client, "post", f"{API}progressions/", prog_body(title="Zebra pattern", genre="funk", difficulty=5, tags=["blues"]))

    def got(query):
        return [r["slug"] for r in client.get(f"{API}progressions/?{query}").json()]

    assert got("genre=blues") and all(
        r["genre"] == "blues" for r in client.get(f"{API}progressions/?genre=blues").json()
    )
    assert "ii-v-i-major" in got("tag=ii-v-i")
    assert all("zebra" not in s for s in got("tag=ii-v-i"))
    hardest = client.get(f"{API}progressions/?difficulty=5").json()
    assert "zebra-pattern" in [r["slug"] for r in hardest] and all(r["difficulty"] == 5 for r in hardest)
    assert [s for s in got("mine=1")] and all(s.startswith("zebra") for s in got("mine=1"))
    assert got("q=zebra") and all(s.startswith("zebra") for s in got("q=zebra"))
    assert got("q=BLUES")
    assert got("genre=polka") == [] and got("tag=nothing") == [] and got("difficulty=9") == []


def test_a_filter_that_is_not_a_number_is_an_empty_list_not_a_500(library, people):
    client = client_for(people["one"])
    assert client.get(f"{API}progressions/?difficulty=hard").json() == []


def test_progressions_come_back_easiest_first_then_by_title(library, people):
    rows = client_for(people["one"]).get(f"{API}progressions/").json()
    order = [(r["difficulty"], r["title"].lower()) for r in rows]
    assert order == sorted(order)


def test_deleting_my_style_leaves_my_progression_without_a_default(people):
    client = client_for(people["one"])
    style = send(client, "post", f"{API}styles/", style_body()).json()
    prog = send(client, "post", f"{API}progressions/", prog_body(default_style=style["id"])).json()
    assert client.delete(f"{API}styles/{style['id']}/").status_code == 204
    assert Progression.objects.get(pk=prog["id"]).default_style is None


# ============================================================ the API: tags


def test_tags_are_read_only_for_players(library, people):
    client = client_for(people["one"])
    tags = client.get(f"{API}tags/").json()
    assert tags and {"id", "name", "slug"} <= set(tags[0])
    tag = Tag.objects.first()
    before = Tag.objects.count()
    assert send(client, "post", f"{API}tags/", {"name": "x", "slug": "x"}).status_code == 405
    for method in ("put", "patch", "delete"):
        assert send(client, method, f"{API}tags/{tag.pk}/", {"name": "x"}).status_code == 405
    assert Tag.objects.count() == before


def test_a_tag_filter_for_the_screens_counts_what_it_filters(library, people):
    tags = client_for(people["one"]).get(f"{API}tags/").json()
    row = next(t for t in tags if t["slug"] == "ii-v-i")
    assert row["progressions"] == Progression.objects.filter(tags__slug="ii-v-i").count() > 0
