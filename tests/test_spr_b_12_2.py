"""SPR-B.12.2 — the lab keeps a small summary and nothing else.

Avi, 2026-10-16: "keep all the simulation in the user history, but don't bombard
the database with all the results ... just save the results: what was the
policy, the trending graph of the wins or loses, a minimum set of data, because I
don't want to overflow the database."

So the sharpest tests here are about what is *refused* and *bounded*: a summary
that is too big, a summary with a field nobody asked for, a person who keeps more
than their newest fifty. The second half is privacy: a saved run is the player's
own and nobody else's, and a run that is not yours is a 404.

Traces: REQ-B.11.7, B.11.9, B.11.11, B.11.24, B.11.25.
"""

import copy
import json
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

pytestmark = pytest.mark.sprblab

API = "/blackjack/api/lab-runs/"
PASSWORD = "sprb122-pass-7721"


def _policy():
    return {
        "start": 1000, "minBet": 15, "limit": 500, "ladder": [15, 50, 150, 500],
        "afterWin": "reset", "atLimit": "stay", "short": "rest",
        "freeze": [500, 500, 1000, 2000], "freezeAfter": "stop",
    }


def _days_summary():
    return {
        "days": 30, "handsPerDay": 100000, "start": 1000, "ahead": 6, "classicAhead": 6,
        "helped": 0, "hurt": 0, "avg": 834, "classicAvg": 834, "best": 4000, "worst": 12,
        "classicBest": 4000, "classicWorst": 12, "bust": 30, "classicBust": 30,
        "medianRounds": 39.5, "classicMedianRounds": 39.5, "frozenAvg": 833,
        "classicFrozenAvg": 833, "overrideFallbacks": 0, "changed": False,
        "curve": list(range(1000, 1060)), "classicCurve": list(range(1000, 1060)),
        "hist": {"lo": 0, "hi": 4000, "counts": [1] * 20, "classicCounts": [1] * 20},
    }


def _payload(**over):
    body = {
        "name": "בדיקה", "mode": "days", "rules_in": {},
        "settings": {"policy": _policy(), "overrides": {}, "handsPerDay": 100000,
                     "seed": 12345, "days": 30},
        "summary": _days_summary(),
    }
    body.update(over)
    return body


def _post(client, body):
    return client.post(API, json.dumps(body), content_type="application/json")


@pytest.fixture
def me(db, client):
    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username="lab@example.com", email="lab@example.com", password=PASSWORD)
    client.force_login(user)
    return user


# ------------------------------------------------------------ saving


def test_a_finished_run_is_saved_with_its_conditions_and_summary(client, me):
    """T-F-B.12.2-1: REQ-B.11.7."""
    response = _post(client, _payload())
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["mode"] == "days" and body["settings"]["policy"]["ladder"] == [15, 50, 150, 500]
    assert body["summary"]["ahead"] == 6
    assert body["rules"]["decks"] == 6
    from blackjack.models import LabRun

    run = LabRun.objects.get()
    assert run.player.user == me
    assert run.rule_set.decks == 6


def test_the_rules_are_stored_as_the_shared_rule_set(client, me):
    """T-F-B.12.2-2: REQ-B.2.1. A table somebody already plays is the same row."""
    from blackjack.models import LabRun, RuleSet

    before = RuleSet.objects.count()
    _post(client, _payload(rules_in={"decks": 8, "dealer_hits_soft_17": True, "blackjack_pays": "6:5"}))
    run = LabRun.objects.get()
    assert (run.rule_set.decks, run.rule_set.dealer_hits_soft_17, run.rule_set.blackjack_pays) == (8, True, "6:5")
    _post(client, _payload(rules_in={"decks": 8, "dealer_hits_soft_17": True, "blackjack_pays": "6:5"}))
    assert RuleSet.objects.count() == before + 1


def test_a_search_result_is_saved_too(client, me):
    """T-F-B.12.2-3: REQ-B.11.22."""
    score = {"value": 0.4, "ahead": 0.4, "avg": 900, "survive": 80}
    body = _payload(mode="search")
    body["settings"].update({"goal": "ahead", "holdoutDays": 100})
    body["summary"] = {
        "tries": 300, "ms": 20000, "improved": True,
        "baseline": {"train": score, "holdout": score},
        "best": {"policy": _policy(), "train": score, "holdout": score},
    }
    response = _post(client, body)
    assert response.status_code == 201, response.content
    assert response.json()["summary"]["best"]["policy"]["limit"] == 500


# ------------------------------------------------------------ what is kept is small


def test_a_summary_that_is_too_big_is_refused(client, me):
    """T-F-B.12.2-4: REQ-B.11.25. This is a summary, not a notebook."""
    body = _payload()
    body["summary"]["curve"] = list(range(5000))
    assert _post(client, body).status_code == 400
    body = _payload()
    body["settings"]["policy"]["ladder"] = list(range(1, 200))
    assert _post(client, body).status_code == 400


def test_a_field_nobody_asked_for_is_not_stored(client, me):
    """T-F-B.12.2-5: the shape is rebuilt field by field."""
    from blackjack.models import LabRun

    body = _payload()
    body["summary"]["notes"] = "x" * 500
    body["summary"]["everyHand"] = list(range(10000))
    body["settings"]["secret"] = "x" * 500
    assert _post(client, body).status_code == 201
    run = LabRun.objects.get()
    assert "notes" not in run.summary and "everyHand" not in run.summary
    assert "secret" not in run.settings
    assert len(json.dumps(run.summary)) < 3000


@pytest.mark.parametrize("mutate", [
    lambda b: b["summary"].__setitem__("curve", []),
    lambda b: b["summary"].__setitem__("ahead", "lots"),
    lambda b: b["summary"].__setitem__("days", 100000),
    lambda b: b["summary"]["hist"].__setitem__("counts", [1, 2, 3]),
    lambda b: b["settings"].__setitem__("days", 100000),
    lambda b: b["settings"].__setitem__("handsPerDay", 10 ** 7),
    lambda b: b["settings"]["policy"].__setitem__("afterWin", "double"),
    lambda b: b["settings"]["policy"].__setitem__("limit", 1),
    lambda b: b["settings"]["policy"].__setitem__("ladder", []),
    lambda b: b["settings"].__setitem__("overrides", {"hard|16|1": "S"}),
    lambda b: b["settings"].__setitem__("overrides", {"hard|16|10": "X"}),
    lambda b: b.__setitem__("mode", "lottery"),
    lambda b: b.__setitem__("rules_in", {"decks": 1}),
    lambda b: b.__setitem__("rules_in", {"blackjack_pays": "2:1"}),
])
def test_nonsense_is_refused_whole(client, me, mutate):
    """T-F-B.12.2-6: REQ-B.11.25."""
    from blackjack.models import LabRun

    body = copy.deepcopy(_payload())
    mutate(body)
    assert _post(client, body).status_code == 400
    assert LabRun.objects.count() == 0


def test_a_person_keeps_only_their_newest_fifty(client, me):
    """T-F-B.12.2-7: Avi, "I don't want to overflow the database"."""
    from blackjack.models import LabRun

    for i in range(55):
        assert _post(client, _payload(name=f"run {i}")).status_code == 201
    names = list(LabRun.objects.order_by("created_at", "id").values_list("name", flat=True))
    assert len(names) == 50
    assert names[0] == "run 5" and names[-1] == "run 54"


def test_pruning_one_person_never_touches_another(client, me, django_user_model):
    """T-F-B.12.2-8"""
    from blackjack.models import LabRun, Player

    other = django_user_model.objects.create_user(username="o@example.com", email="o@example.com", password=PASSWORD)
    _post(client, _payload(name="mine"))
    keep = LabRun.objects.get()
    client.force_login(other)
    for i in range(52):
        _post(client, _payload(name=f"theirs {i}"))
    client.force_login(me)
    assert LabRun.objects.filter(pk=keep.pk).exists()
    assert LabRun.objects.filter(player=Player.for_user(other)).count() == 50


def test_unsupported_rules_are_refused_with_a_reason(client, me):
    """T-F-B.12.2-9: REQ-B.2.5. No chart, no classic twin, so no run."""
    from blackjack import lab

    with pytest.raises(lab.Refused):
        lab.clean_rules({"decks": 2})
    response = client.get("/blackjack/lab/chart/?decks=5")
    assert response.status_code == 400 and response.json()["error"]


# ------------------------------------------------------------ the API


def test_the_api_is_closed_to_the_signed_out(client, db):
    """T-F-B.12.2-10: REQ-B.6.1."""
    assert client.get(API).status_code in (401, 403)
    assert _post(client, _payload()).status_code in (401, 403)
    assert client.get("/blackjack/lab/chart/").status_code == 403
    assert client.get("/blackjack/lab/").status_code == 302


def test_a_saved_run_is_the_players_own(client, me, django_user_model):
    """T-F-B.12.2-11: REQ-B.11.11. Private, and a stranger gets a 404."""
    run_id = _post(client, _payload()).json()["id"]
    other = django_user_model.objects.create_user(username="x@example.com", email="x@example.com", password=PASSWORD)
    client.force_login(other)
    assert client.get(API).json() in ([], {"count": 0, "next": None, "previous": None, "results": []})
    assert client.get(f"{API}{run_id}/").status_code == 404
    assert client.delete(f"{API}{run_id}/").status_code == 404
    assert client.get(f"/blackjack/lab/{run_id}/").status_code == 404
    client.force_login(me)
    assert client.get(f"{API}{run_id}/").status_code == 200
    assert client.get(f"/blackjack/lab/{run_id}/").status_code == 200


def test_the_player_is_the_session_never_a_field(client, me, django_user_model):
    """T-F-B.12.2-12"""
    from blackjack.models import LabRun, Player

    other = django_user_model.objects.create_user(username="y@example.com", email="y@example.com", password=PASSWORD)
    body = _payload()
    body["player"] = Player.for_user(other).pk
    _post(client, body)
    assert LabRun.objects.get().player.user == me


def test_a_saved_run_can_be_renamed_and_nothing_else(client, me):
    """T-F-B.12.2-13: a graph that can be rewritten is not a result."""
    from blackjack.models import LabRun

    run_id = _post(client, _payload()).json()["id"]
    patch = lambda data: client.patch(f"{API}{run_id}/", json.dumps(data), content_type="application/json")
    assert patch({"name": "שם חדש"}).status_code == 200
    assert LabRun.objects.get().name == "שם חדש"
    for stray in ({"summary": {}}, {"settings": {}}, {"mode": "search"}, {"name": "x", "summary": {}}):
        assert patch(stray).status_code == 400
    assert LabRun.objects.get().summary["ahead"] == 6


def test_a_run_can_be_deleted(client, me):
    """T-F-B.12.2-14"""
    from blackjack.models import LabRun

    run_id = _post(client, _payload()).json()["id"]
    assert client.delete(f"{API}{run_id}/").status_code == 204
    assert LabRun.objects.count() == 0


def test_the_new_model_is_routed():
    """T-F-B.12.2-15: Rule 6, beside the guard in test_spr_b_1_5."""
    from blackjack.api import ROUTES

    assert "lab-runs" in {prefix for prefix, _view, _model in ROUTES}


def test_the_lab_is_free_and_never_asks_the_gate(client, me):
    """T-F-B.12.2-16: REQ-B.11.9. A free player with no grant and no trial."""
    assert client.get("/blackjack/lab/").status_code == 200
    assert _post(client, _payload()).status_code == 201
    import inspect

    from blackjack import lab, views

    assert "paid_only" not in inspect.getsource(lab)
    for name in ("lab", "lab_run", "lab_chart"):
        assert "paid_only" not in inspect.getsource(getattr(views, name))
    assert "ai_chat" not in inspect.getsource(lab)


# ------------------------------------------------------------ the screens


def test_the_lab_screen_opens_with_avis_defaults(client, me):
    """T-F-B.12.2-17: REQ-B.11.18."""
    response = client.get("/blackjack/lab/")
    assert response.status_code == 200
    html = response.content.decode()
    assert 'id="labForm"' in html and "מעבדה" in html
    boot = response.context["boot"]
    policy = boot["settings"]["policy"]
    assert policy["start"] == 1000 and policy["minBet"] == 15 and policy["limit"] == 500
    assert policy["ladder"] == [15, 50, 150, 500]
    assert policy["freeze"] == [[500, 1000], [500, 500], [1000, 500], [2000, 1000]]
    assert policy["afterWin"] == "reset"
    assert boot["settings"]["handsPerDay"] == 400


def test_the_nav_links_to_the_lab(client, me):
    """T-F-B.12.2-18"""
    assert "/blackjack/lab/" in client.get("/blackjack/").content.decode()


def test_run_it_again_opens_the_form_with_the_saved_settings(client, me):
    """T-F-B.12.2-19"""
    body = _payload(rules_in={"decks": 8})
    body["settings"]["policy"]["ladder"] = [15, 45, 135]
    run_id = _post(client, body).json()["id"]
    response = client.get(f"/blackjack/lab/?from={run_id}")
    boot = response.context["boot"]
    assert boot["settings"]["policy"]["ladder"] == [15, 45, 135]
    assert boot["rules"]["decks"] == 8
    other = client.get("/blackjack/lab/?from=999999")
    assert other.context["boot"]["settings"]["policy"]["ladder"] == [15, 50, 150, 500]


def test_a_saved_run_page_shows_its_headline_and_conditions(client, me):
    """T-F-B.12.2-20"""
    run_id = _post(client, _payload(name="הריצה שלי")).json()["id"]
    html = client.get(f"/blackjack/lab/{run_id}/").content.decode()
    assert "הריצה שלי" in html and "6 מתוך 30" in html
    assert f"/blackjack/lab/?from={run_id}" in html


def test_the_past_runs_list_is_the_players_own(client, me, django_user_model):
    """T-F-B.12.2-21"""
    _post(client, _payload(name="שלי"))
    other = django_user_model.objects.create_user(username="z@example.com", email="z@example.com", password=PASSWORD)
    client.force_login(other)
    _post(client, _payload(name="של מישהו אחר"))
    client.force_login(me)
    html = client.get("/blackjack/lab/").content.decode()
    assert "שלי" in html and "של מישהו אחר" not in html


def test_the_chart_endpoint_serves_the_strategy_modules_own_cells(client, me):
    """T-F-B.12.2-22: the browser carries no idea of the right play of its own."""
    from blackjack import strategy

    body = client.get("/blackjack/lab/chart/?decks=8&dealer_hits_soft_17=1").json()
    rules = body["rules"]
    assert rules["decks"] == 8 and rules["dealer_hits_soft_17"] is True
    expected = [[k, p, d, a, f] for (k, p, d, a, f, _r) in strategy.every_cell(rules)]
    assert body["cells"] == expected
    assert len(body["cells"]) == 340

# ------------------------------------------------------------ SPR-B.12.8 and 12.9


def test_a_calculated_chart_allows_any_number_of_decks_and_a_classic_one_does_not(client, me):
    """T-F-B.12.2-23: REQ-B.11.26."""
    from blackjack import lab

    with pytest.raises(lab.Refused):
        lab.clean_rules({"decks": 1}, "classic")
    assert lab.clean_rules({"decks": 1}, "calculated")["decks"] == 1
    assert lab.clean_rules({"decks": 2}, "calculated")["decks"] == 2
    with pytest.raises(lab.Refused):
        lab.clean_rules({"decks": 9}, "calculated")
    fixed = lab.clean_rules({}, "calculated")
    assert fixed["surrender"] == "none" and fixed["double_any_two"] is True and fixed["dealer_peeks"] is True


def test_a_run_on_a_calculated_chart_is_saved_as_one(client, me):
    """T-F-B.12.2-24"""
    from blackjack.models import LabRun

    body = _payload(rules_in={"decks": 1})
    body["settings"]["chart"] = "calculated"
    body["summary"]["chart"] = "calculated"
    response = _post(client, body)
    assert response.status_code == 201, response.content
    run = LabRun.objects.get()
    assert run.rule_set.decks == 1
    assert run.settings["chart"] == "calculated" and run.summary["chart"] == "calculated"


def test_one_deck_on_the_classic_chart_is_refused(client, me):
    """T-F-B.12.2-25"""
    assert _post(client, _payload(rules_in={"decks": 1})).status_code == 400


def test_an_unknown_chart_is_refused(client, me):
    """T-F-B.12.2-26"""
    body = _payload()
    body["settings"]["chart"] = "magic"
    assert _post(client, body).status_code == 400


def _search_body(goal, mix=None):
    score = {"value": 0.4, "ahead": 0.4, "avg": 900, "survive": 80}
    body = _payload(mode="search")
    body["settings"].update({"goal": goal, "holdoutDays": 100})
    if mix is not None:
        body["settings"]["mix"] = mix
    body["summary"] = {
        "tries": 300, "ms": 20000, "improved": True,
        "baseline": {"train": score, "holdout": score},
        "best": {"policy": _policy(), "train": score, "holdout": score},
    }
    return body


def test_a_mixed_goal_is_saved_with_its_weights(client, me):
    """T-F-B.12.2-27: REQ-B.11.27."""
    from blackjack.models import LabRun

    assert _post(client, _search_body("mix", {"ahead": 5, "avg": 3, "survive": 2})).status_code == 201
    assert LabRun.objects.get().settings["mix"] == {"ahead": 5, "avg": 3, "survive": 2}


@pytest.mark.parametrize("mix", [
    None, {}, {"ahead": 0, "avg": 0, "survive": 0}, {"ahead": 11, "avg": 0, "survive": 0},
    {"ahead": -1, "avg": 1, "survive": 1}, {"ahead": "x", "avg": 1, "survive": 1},
])
def test_a_mixed_goal_needs_sensible_weights(client, me, mix):
    """T-F-B.12.2-28"""
    assert _post(client, _search_body("mix", mix)).status_code == 400

# ------------------------------------------------------------ two numbers to a freeze step


def test_a_freeze_step_is_two_numbers_and_is_stored_as_two(client, me):
    """T-F-B.12.2-29: REQ-B.11.16. The profit that sets it off, and what goes home."""
    from blackjack.models import LabRun

    body = _payload()
    body["settings"]["policy"]["freeze"] = [[500, 1000], [500, 400]]
    assert _post(client, body).status_code == 201
    assert LabRun.objects.get().settings["policy"]["freeze"] == [[500, 1000], [500, 400]]


def test_a_bare_number_is_the_old_form_of_a_step(client, me):
    """T-F-B.12.2-30: runs saved before a step had two numbers hold one."""
    from blackjack import lab

    cleaned = lab.clean_policy(_policy())
    assert cleaned["freeze"] == [[500, 500], [500, 500], [1000, 1000], [2000, 2000]]
    assert lab.clean_policy({**_policy(), "freeze": [[300, 100], 50]})["freeze"] == [[300, 100], [50, 50]]


@pytest.mark.parametrize("freeze", [
    [[500]], [[500, 0]], [[0, 500]], [[1, 2, 3]], [["a", 1]], [[-5, 5]], [[1.5, 2]],
    [[100, 100]] * 13, "500",
])
def test_a_freeze_step_needs_two_positive_whole_numbers(client, me, freeze):
    """T-F-B.12.2-31"""
    from blackjack.models import LabRun

    body = _payload()
    body["settings"]["policy"]["freeze"] = freeze
    assert _post(client, body).status_code == 400
    assert LabRun.objects.count() == 0
