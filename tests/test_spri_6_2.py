"""SPR-I.6.2 improv: unkept takes lose their notes after thirty days, and the deploy seeds everything.

A take not kept keeps its score and metrics, which is all the weakness report and the bests read,
and loses its events. The prune runs when the same player saves their next take, because Render's
scheduled jobs cannot see the SQLite disk. The seed commands for the lessons and the challenges
join the deploy with the same `|| true` pattern as the others.

Traces: spec ch. 6, ch. 7, data model section 11, backlog SPR-I.6.2.
"""

import datetime as dt
import io
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from improv import retention, weakness
from improv.models import Player, PracticeSession, Progression, Take

pytestmark = pytest.mark.spri62

PASSWORD = "spri62-pass-3318"
TAKES = "/improv/api/takes/"
SESSIONS = "/improv/api/sessions/"
EVENTS = [
    {"t_ms": 0, "type": "on", "note": 62, "velocity": 90},
    {"t_ms": 400, "type": "off", "note": 62, "velocity": 0},
]


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p62member", password=PASSWORD)
    member.groups.add(group)
    other = User.objects.create_user("p62other", password=PASSWORD)
    other.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    return {"member": member, "other": other}


def _client(user):
    client = Client()
    client.force_login(user)
    return client


def _old_take(user, days_ago, kept=False, events=None, score=70):
    player = Player.objects.get_or_create(user=user)[0]
    session = PracticeSession.objects.create(player=player, active_seconds=60)
    chart = Progression.objects.get(slug="ii-v-i-major")
    when = timezone.now() - dt.timedelta(days=days_ago)
    return Take.objects.create(
        player=player, session=session, progression=chart, chart=chart.chart, home_key=chart.home_key, key="C", tempo=90,
        loop_from=0, loop_to=4, started_at=when, duration_ms=10000, bars=4, events=EVENTS if events is None else events,
        score=score, metrics={"notes": 25, "chordTonePct": 60, "outsidePct": 10}, judge_version=1, is_kept=kept,
    )


def _post_next_take(client):
    session = client.post(SESSIONS, {}, content_type="application/json").json()
    chart = Progression.objects.get(slug="ii-v-i-major")
    body = {
        "session": session["id"], "progression": chart.pk, "chart": chart.chart, "home_key": chart.home_key, "key": "C",
        "tempo": 90, "loop_from": 0, "loop_to": 4, "started_at": timezone.now().isoformat(), "duration_ms": 10000,
        "bars": 4, "events": EVENTS, "score": None, "metrics": {"notes": 1}, "judge_version": 1,
    }
    reply = client.post(TAKES, body, content_type="application/json")
    assert reply.status_code == 201, reply.content
    return reply.json()


# ------------------------------------------------------------------ what is pruned


def test_an_unkept_take_older_than_thirty_days_loses_its_events_when_the_next_take_is_saved(people):
    old = _old_take(people["member"], 31)
    _post_next_take(_client(people["member"]))
    old.refresh_from_db()
    assert old.events == []


def test_the_score_and_the_metrics_stay(people):
    old = _old_take(people["member"], 45, score=82)
    _post_next_take(_client(people["member"]))
    old.refresh_from_db()
    assert old.score == 82
    assert old.metrics == {"notes": 25, "chordTonePct": 60, "outsidePct": 10}
    assert old.chart and old.key == "C" and old.judge_version == 1


def test_a_take_inside_thirty_days_keeps_its_events(people):
    young = _old_take(people["member"], 29)
    _post_next_take(_client(people["member"]))
    young.refresh_from_db()
    assert young.events == EVENTS


def test_a_kept_take_keeps_its_events_for_good(people):
    kept = _old_take(people["member"], 400, kept=True)
    _post_next_take(_client(people["member"]))
    kept.refresh_from_db()
    assert kept.events == EVENTS


def test_the_take_just_saved_is_not_pruned(people):
    saved = _post_next_take(_client(people["member"]))
    assert Take.objects.get(pk=saved["id"]).events == EVENTS


def test_my_next_take_never_touches_another_players_old_takes(people):
    theirs = _old_take(people["other"], 90)
    _post_next_take(_client(people["member"]))
    theirs.refresh_from_db()
    assert theirs.events == EVENTS


def test_nothing_runs_on_a_read(people):
    old = _old_take(people["member"], 90)
    client = _client(people["member"])
    assert client.get(TAKES).status_code == 200
    assert client.get("/improv/api/weakness/").status_code == 200
    old.refresh_from_db()
    assert old.events == EVENTS


def test_pruning_is_idempotent_and_counts_what_it_cleared(people):
    player = _old_take(people["member"], 31).player
    _old_take(people["member"], 60)
    _old_take(people["member"], 5)
    _old_take(people["member"], 90, kept=True)
    assert retention.prune(player) == 2
    assert retention.prune(player) == 0


def test_the_cutoff_is_thirty_days_before_now():
    now = timezone.now()
    assert retention.RETENTION_DAYS == 30
    assert retention.cutoff(now) == now - dt.timedelta(days=30)


def test_a_failed_save_prunes_nothing(people):
    old = _old_take(people["member"], 60)
    client = _client(people["member"])
    bad = client.post(TAKES, {"chart": ""}, content_type="application/json")
    assert bad.status_code == 400
    old.refresh_from_db()
    assert old.events == EVENTS


def test_the_weakness_report_reads_the_same_after_the_events_are_gone(people):
    player = Player.objects.get_or_create(user=people["member"])[0]
    for days in (3, 10, 20):
        _old_take(people["member"], days)
    before = weakness.report(player)
    Take.objects.filter(player=player).update(events=[])
    assert weakness.report(player) == before


# ------------------------------------------------------------------ a take whose notes are gone


def test_a_cleared_take_cannot_be_kept_because_there_is_nothing_to_replay(people):
    cleared = _old_take(people["member"], 31, events=[])
    reply = _client(people["member"]).patch(f"{TAKES}{cleared.pk}/", {"is_kept": True}, content_type="application/json")
    assert reply.status_code == 400
    assert "cleared after 30 days" in str(reply.json())
    cleared.refresh_from_db()
    assert cleared.is_kept is False


def test_a_take_with_notes_can_still_be_kept_and_unkept(people):
    take = _old_take(people["member"], 31)
    client = _client(people["member"])
    assert client.patch(f"{TAKES}{take.pk}/", {"is_kept": True}, content_type="application/json").status_code == 200
    assert client.patch(f"{TAKES}{take.pk}/", {"is_kept": False}, content_type="application/json").status_code == 200


def test_a_cleared_take_can_still_be_deleted(people):
    cleared = _old_take(people["member"], 31, events=[])
    assert _client(people["member"]).delete(f"{TAKES}{cleared.pk}/").status_code == 204


def test_the_takes_screen_words_pass_under_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [node, "--test", "tests/js/spri62.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ------------------------------------------------------------------ the deploy


def _start_command():
    text = Path("render.yaml").read_text(encoding="utf-8")
    return next(line for line in text.splitlines() if "startCommand" in line)


def test_every_improv_seed_is_in_the_deploy_with_the_or_true_pattern():
    command = _start_command()
    for name in ("seed_improv_theory", "seed_improv_library", "seed_improv_lessons", "seed_improv_challenges"):
        assert f"(python manage.py {name} || true)" in command, name


def test_the_seeds_run_in_the_order_their_rows_need_each_other():
    command = _start_command()
    order = [command.index(f"manage.py {n} ") for n in ("seed_improv_theory", "seed_improv_library", "seed_improv_lessons", "seed_improv_challenges")]
    assert order == sorted(order), "lessons and challenges point at progressions, which point at the theory"
    assert command.index("manage.py migrate") < order[0], "the tables exist before they are seeded"


def test_the_deploy_migrates_every_improv_table_through_the_ordinary_migrate():
    command = _start_command()
    assert command.strip().startswith("startCommand: python manage.py migrate")


def test_the_seeds_can_run_twice_and_a_second_deploy_changes_nothing(db):
    for name in ("seed_improv_theory", "seed_improv_library", "seed_improv_lessons", "seed_improv_challenges"):
        call_command(name, stdout=io.StringIO())
    from improv.models import Exercise, Lesson

    counts = (Lesson.objects.count(), Exercise.objects.count(), Progression.objects.count())
    for name in ("seed_improv_theory", "seed_improv_library", "seed_improv_lessons", "seed_improv_challenges"):
        call_command(name, stdout=io.StringIO())
    assert (Lesson.objects.count(), Exercise.objects.count(), Progression.objects.count()) == counts
    assert counts[0] >= 1 and counts[1] >= 1


# ------------------------------------------------------------------ the docs


def test_the_docs_say_how_pruning_works_and_the_backlog_row_is_done():
    spec = Path("docs/improv/spec.md").read_text(encoding="utf-8")
    assert "SPR-I.6.2" in spec
    api = Path("docs/improv/api.md").read_text(encoding="utf-8")
    assert "cleared after 30 days" in api
    backlog = Path("docs/improv/backlog.md").read_text(encoding="utf-8")
    row = next(line for line in backlog.splitlines() if line.startswith("| SPR-I.6.2 "))
    assert re.search(r"DONE \d{4}-\d{2}-\d{2}", row), row
