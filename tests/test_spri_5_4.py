"""SPR-I.5.4 improv: the practice timer, the daily goal, the practice log and the streak.

The log is the PracticeSession table and the streak is a read over it, never a column. What this
file proves: a day is the player's own day (their timezone, not the server's), the goal is the
player's own number, today is pending until it is met and does not break the streak until the day
has ended, nothing another player did leaks in, and the page-side clock counts only time the band
ran or a note was played (the Node half, tests/js/spri54.test.js).

Traces: spec ch. 6 (streak, daily goal, the practice timer), data model sections 6 and 8, backlog
SPR-I.5.4.
"""

import datetime as dt
import re
import shutil
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import Group, User
from django.test import Client

from improv import practice
from improv.models import Player, PracticeSession

pytestmark = pytest.mark.spri54

PASSWORD = "spri54-pass-3381"
PRACTICE = "/improv/api/practice/"
UTC = dt.timezone.utc


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p54member", password=PASSWORD)
    member.groups.add(group)
    other = User.objects.create_user("p54other", password=PASSWORD)
    other.groups.add(group)
    stranger = User.objects.create_user("p54stranger", password=PASSWORD)
    return {"member": member, "other": other, "stranger": stranger}


def _client(user=None):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def _player(user, **fields):
    player, _ = Player.objects.get_or_create(user=user)
    for name, value in fields.items():
        setattr(player, name, value)
    player.save()
    return player


def _session(player, started, seconds):
    row = PracticeSession.objects.create(player=player, active_seconds=seconds)
    PracticeSession.objects.filter(pk=row.pk).update(started_at=started)
    return row


def _day(player, day, minutes, hour=12):
    """A sitting on `day` (a date in the player's own zone) of this many minutes."""
    zone = ZoneInfo(player.timezone)
    return _session(player, dt.datetime(day.year, day.month, day.day, hour, 0, tzinfo=zone), minutes * 60)


NOON = dt.datetime(2026, 10, 5, 12, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
TODAY = dt.date(2026, 10, 5)


def days_ago(n):
    return TODAY - dt.timedelta(days=n)


# ------------------------------------------------------------------ the streak rule


def test_the_streak_is_the_run_of_goal_days_ending_today():
    seconds = {days_ago(0): 900, days_ago(1): 900, days_ago(2): 1200}
    assert practice.streaks(seconds, 900, TODAY) == (3, 3)


def test_today_is_pending_and_does_not_break_the_streak():
    seconds = {days_ago(1): 900, days_ago(2): 900, days_ago(3): 900, days_ago(0): 60}
    current, best = practice.streaks(seconds, 900, TODAY)
    assert current == 3, "today has not met the goal yet, but the day is not over"
    assert best == 3


def test_a_missed_day_ends_the_streak():
    seconds = {days_ago(0): 900, days_ago(1): 899, days_ago(2): 900, days_ago(3): 900}
    assert practice.streaks(seconds, 900, TODAY) == (1, 2)


def test_yesterday_missed_and_today_empty_is_no_streak():
    seconds = {days_ago(2): 900, days_ago(3): 900}
    assert practice.streaks(seconds, 900, TODAY) == (0, 2)


def test_no_practice_at_all_is_no_streak():
    assert practice.streaks({}, 900, TODAY) == (0, 0)


def test_the_goal_is_met_at_exactly_the_goal():
    assert practice.streaks({TODAY: 900}, 900, TODAY)[0] == 1
    assert practice.streaks({TODAY: 899}, 900, TODAY)[0] == 0


def test_the_best_streak_can_be_older_than_the_current_one():
    seconds = {days_ago(0): 900}
    for n in range(10, 15):
        seconds[days_ago(n)] = 900
    assert practice.streaks(seconds, 900, TODAY) == (1, 5)


# ------------------------------------------------------------------ the player's own day


def test_a_sitting_after_midnight_in_the_players_zone_belongs_to_the_next_day(people):
    player = _player(people["member"], timezone="Asia/Jerusalem")
    # 22:30 UTC on 4 October is 01:30 on 5 October in Jerusalem (UTC+3 until the clocks change).
    _session(player, dt.datetime(2026, 10, 4, 22, 30, tzinfo=UTC), 600)
    by_day = practice.seconds_by_day(player)
    assert by_day == {dt.date(2026, 10, 5): 600}


def test_the_same_instant_is_the_earlier_day_for_a_player_in_utc(people):
    player = _player(people["member"], timezone="UTC")
    _session(player, dt.datetime(2026, 10, 4, 22, 30, tzinfo=UTC), 600)
    assert practice.seconds_by_day(player) == {dt.date(2026, 10, 4): 600}


def test_today_is_the_players_today_not_the_servers(people):
    player = _player(people["member"], timezone="Pacific/Auckland")
    now = dt.datetime(2026, 10, 5, 12, 0, tzinfo=UTC)  # 01:00 on 6 October in Auckland
    assert practice.report(player, now=now)["today"] == "2026-10-06"
    player.timezone = "America/Los_Angeles"
    player.save()
    assert practice.report(player, now=now)["today"] == "2026-10-05"


def test_two_sittings_on_one_day_add_up(people):
    player = _player(people["member"])
    _day(player, TODAY, 6, hour=8)
    _day(player, TODAY, 9, hour=20)
    report = practice.report(player, now=NOON)
    assert report["today_seconds"] == 900 and report["goal_met"] is True
    assert report["log"][0]["sessions"] == 2


def test_an_unknown_timezone_falls_back_to_utc_instead_of_breaking_the_page(people):
    player = _player(people["member"])
    Player.objects.filter(pk=player.pk).update(timezone="Not/AZone")
    player.refresh_from_db()
    assert practice.report(player, now=NOON)["timezone"] == "UTC"


# ------------------------------------------------------------------ the report


def test_the_report_says_where_today_stands_against_the_goal(people):
    player = _player(people["member"], daily_goal_minutes=20)
    _day(player, TODAY, 12)
    report = practice.report(player, now=NOON)
    assert report["goal_minutes"] == 20
    assert report["today_seconds"] == 720 and report["today_minutes"] == 12
    assert report["goal_met"] is False
    assert report["timezone"] == "Asia/Jerusalem" and report["today"] == "2026-10-05"


def test_the_goal_is_the_players_own_number_and_a_change_applies_to_every_day(people):
    player = _player(people["member"], daily_goal_minutes=15)
    for n in (0, 1, 2):
        _day(player, days_ago(n), 10)
    assert practice.report(player, now=NOON)["streak"] == 0
    player.daily_goal_minutes = 10
    player.save()
    assert practice.report(player, now=NOON)["streak"] == 3


def test_the_log_lists_days_with_practice_newest_first_and_always_today(people):
    player = _player(people["member"])
    _day(player, days_ago(2), 20)
    _day(player, days_ago(5), 5)
    log = practice.report(player, now=NOON)["log"]
    assert [row["date"] for row in log] == ["2026-10-05", "2026-10-03", "2026-09-30"]
    assert [row["minutes"] for row in log] == [0, 20, 5]
    assert [row["goal_met"] for row in log] == [False, True, False]


def test_the_log_window_is_the_last_days_asked_for_but_the_streak_reads_all_of_them(people):
    player = _player(people["member"])
    for n in range(0, 40):
        _day(player, days_ago(n), 15)
    report = practice.report(player, now=NOON, days=7)
    assert len(report["log"]) == 7
    assert report["streak"] == 40 and report["best_streak"] == 40


def test_a_session_that_never_got_a_second_of_practice_is_not_in_the_log(people):
    player = _player(people["member"])
    _day(player, days_ago(1), 0)
    assert [row["date"] for row in practice.report(player, now=NOON)["log"]] == ["2026-10-05"]


def test_another_players_practice_is_not_mine(people):
    mine = _player(people["member"])
    theirs = _player(people["other"])
    _day(theirs, TODAY, 60)
    assert practice.report(mine, now=NOON)["today_seconds"] == 0


# ------------------------------------------------------------------ the API


def test_the_practice_read_is_behind_the_gate(people):
    assert _client().get(PRACTICE).status_code == 404
    assert _client(people["stranger"]).get(PRACTICE).status_code == 404
    assert _client(people["member"]).get(PRACTICE).status_code == 200


def test_the_practice_read_is_read_only(people):
    client = _client(people["member"])
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(PRACTICE).status_code == 405


def test_the_page_reports_active_seconds_and_the_read_follows(people):
    client = _client(people["member"])
    opened = client.post("/improv/api/sessions/", {}, content_type="application/json").json()
    assert client.get(PRACTICE).json()["today_seconds"] == 0
    reply = client.patch(f"/improv/api/sessions/{opened['id']}/", {"active_seconds": 330}, content_type="application/json")
    assert reply.status_code == 200
    report = client.get(PRACTICE).json()
    assert report["today_seconds"] == 330 and report["today_minutes"] == 5
    assert report["goal_minutes"] == 15 and report["goal_met"] is False
    assert report["log"][0]["sessions"] == 1


def test_the_read_takes_the_window_from_the_query_and_ignores_nonsense(people):
    client = _client(people["member"])
    player = _player(people["member"])
    for n in range(0, 12):
        PracticeSession.objects.create(player=player, active_seconds=60)
        PracticeSession.objects.filter(player=player).update(started_at=dt.datetime.now(UTC) - dt.timedelta(days=n))
    assert len(client.get(PRACTICE + "?days=3").json()["log"]) <= 4
    assert client.get(PRACTICE + "?days=zebra").status_code == 200
    assert client.get(PRACTICE + "?days=-4").status_code == 200


def test_the_read_makes_a_profile_for_a_first_visit(people):
    assert not Player.objects.filter(user=people["member"]).exists()
    reply = _client(people["member"]).get(PRACTICE)
    assert reply.status_code == 200 and reply.json()["goal_minutes"] == 15


# ------------------------------------------------------------------ the pages and the docs


def test_the_practice_page_opens_for_a_player_and_not_for_a_stranger(people):
    assert _client(people["member"]).get("/improv/practice/").status_code == 200
    assert _client(people["stranger"]).get("/improv/practice/").status_code == 404
    assert _client().get("/improv/practice/").status_code == 404


def test_the_menu_names_the_practice_log(people):
    html = _client(people["member"]).get("/improv/").content.decode("utf-8")
    assert 'href="/improv/practice/"' in html


def test_the_play_screen_has_a_line_for_todays_practice(people):
    html = _client(people["member"]).get("/improv/play/").content.decode("utf-8")
    assert 'id="practice-line"' in html and "data-api-practice=" in html


def test_the_practice_page_has_what_it_shows(people):
    html = _client(people["member"]).get("/improv/practice/").content.decode("utf-8")
    for element_id in ("practice-goal", "practice-streak", "practice-log", "practice-empty"):
        assert f'id="{element_id}"' in html


def test_the_docs_describe_the_practice_read_and_the_rules():
    api = Path("docs/improv/api.md").read_text(encoding="utf-8")
    assert "/improv/api/practice/" in api
    spec = Path("docs/improv/spec.md").read_text(encoding="utf-8")
    assert "SPR-I.5.4" in spec
    model = Path("docs/improv/data_model.md").read_text(encoding="utf-8")
    assert "SPR-I.5.4" in model


def test_the_backlog_marks_this_sprint_done():
    backlog = Path("docs/improv/backlog.md").read_text(encoding="utf-8")
    row = next(line for line in backlog.splitlines() if line.startswith("| SPR-I.5.4 "))
    assert re.search(r"DONE \d{4}-\d{2}-\d{2}", row), row


def test_the_page_files_hold_no_unsafe_dom_use():
    for name in ("practice.js", "practice-page.js"):
        source = Path("static/improv", name).read_text(encoding="utf-8")
        assert "innerHTML" not in source and "eval(" not in source, name


# ------------------------------------------------------------------ the Node half


def test_the_timer_and_the_words_pass_under_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [node, "--test", "tests/js/spri54.test.js"], capture_output=True, text=True, timeout=120, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
