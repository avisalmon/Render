"""
EPIC-6.5 CrashTech — END-TO-END lifecycle test (the coherence guarantee).

Drives one full event through every phase and role — organizer setup → judge
assignment → team + hardware → kickoff → submit → blind judging → bonus →
anonymized leaderboard → deadline → certificates → Glory Page — asserting the
whole machine works together, not just each part in isolation.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone


def _staff(u="host"):
    user = User.objects.create_user(u, password="p", is_staff=True)
    user.profile.display_name = u; user.profile.save()
    return user


def _u(u):
    user = User.objects.create_user(u, password="p")
    user.profile.display_name = u; user.profile.save()
    return user


def _c(user):
    c = Client(); c.force_login(user); return c


@pytest.mark.django_db
def test_full_crashtech_lifecycle():
    from app.models import Certificate, Hackathon, Submission, Team

    # --- SETUP: staff creates a hackathon, becomes organizer ---
    host = _staff("host")
    oc = _c(host)
    oc.post("/crashtech/new/", {
        "name": "E2E Cup", "start_at": "2026-08-01T09:00", "end_at": "2026-08-02T09:00",
        "submission_deadline": "2026-08-02T09:00", "team_size": 2, "hardware_stock": 2,
    })
    h = Hackathon.objects.get(name="E2E Cup")
    assert h.status == "setup"

    # author a secret challenge + a creativity challenge, assign a judge
    oc.post(f"/crashtech/{h.slug}/challenges/new/", {
        "title": "Blink", "description": "blink an LED", "point_value": 100, "scoring_mode": "pass_fail"})
    oc.post(f"/crashtech/{h.slug}/challenges/new/", {
        "title": "Wow", "description": "impress", "point_value": 0,
        "scoring_mode": "performance_creativity", "top_submission_count": 2, "bonus_points_tiers": "50, 20"})
    judge = _u("judge"); oc.post(f"/crashtech/{h.slug}/judges/", {"username": "judge"})
    from app.crashtech import is_judge
    assert is_judge(judge, h)
    blink = h.challenges.get(title="Blink")
    wow = h.challenges.get(title="Wow")

    # secret before kickoff
    assert "Blink" not in Client().get(f"/crashtech/{h.slug}/").content.decode()

    # --- READINESS: invite + teams + hardware ---
    oc.post(f"/crashtech/{h.slug}/manage/", {"action": "advance"})   # → readiness
    h.refresh_from_db(); assert h.status == "readiness"
    racer1, racer2 = _u("racer1"), _u("racer2")
    oc.post(f"/crashtech/{h.slug}/teams/", {"name": "Rockets"})
    oc.post(f"/crashtech/{h.slug}/teams/", {"name": "Comets"})
    # third team blocked by stock=2
    oc.post(f"/crashtech/{h.slug}/teams/", {"name": "Nope"})
    assert Team.objects.filter(hackathon=h).count() == 2
    rockets = Team.objects.get(name="Rockets")
    comets = Team.objects.get(name="Comets")
    oc.post(f"/crashtech/{h.slug}/teams/{rockets.pk}/", {"action": "add_member", "username": "racer1"})
    oc.post(f"/crashtech/{h.slug}/teams/{comets.pk}/", {"action": "add_member", "username": "racer2"})
    oc.post(f"/crashtech/{h.slug}/teams/{rockets.pk}/", {"action": "hardware", "hardware_status": "received"})

    # --- KICKOFF: go live, challenges unlock ---
    oc.post(f"/crashtech/{h.slug}/manage/", {"action": "advance"})   # → active
    h.refresh_from_db(); assert h.status == "active" and h.accepts_submissions
    assert "Blink" in Client().get(f"/crashtech/{h.slug}/").content.decode()

    # --- SUBMIT: both teams submit ---
    _c(racer1).post(f"/crashtech/{h.slug}/challenges/{blink.pk}/submit/", {"video_url": "https://youtu.be/r1"})
    _c(racer1).post(f"/crashtech/{h.slug}/challenges/{wow.pk}/submit/", {"video_url": "https://youtu.be/r1w"})
    _c(racer2).post(f"/crashtech/{h.slug}/challenges/{blink.pk}/submit/", {"video_url": "https://youtu.be/r2"})
    assert Submission.objects.filter(challenge__hackathon=h, status="pending").count() == 3

    # --- JUDGING (blind) + BONUS ---
    jc = _c(judge)
    assert "Rockets" not in jc.get(f"/crashtech/{h.slug}/judge/").content.decode()  # blind
    s_r1 = Submission.objects.get(team=rockets, challenge=blink)
    s_r2 = Submission.objects.get(team=comets, challenge=blink)
    s_r1w = Submission.objects.get(team=rockets, challenge=wow)
    jc.post(f"/crashtech/{h.slug}/submissions/{s_r1.pk}/review/", {"action": "approve"})
    jc.post(f"/crashtech/{h.slug}/submissions/{s_r2.pk}/review/", {"action": "reject", "feedback_note": "blurry"})
    jc.post(f"/crashtech/{h.slug}/submissions/{s_r1w.pk}/review/", {"action": "approve"})
    # organizer awards creativity bonus (Rockets #1 → 50)
    oc.post(f"/crashtech/{h.slug}/challenges/{wow.pk}/bonus/", {f"rank_{s_r1w.pk}": "1"})
    s_r1.refresh_from_db(); s_r1w.refresh_from_db()
    assert s_r1.points_awarded == 100 and s_r1w.bonus_points_awarded == 50

    # rejected team resubmits → back to pending
    _c(racer2).post(f"/crashtech/{h.slug}/challenges/{blink.pk}/submit/", {"video_url": "https://youtu.be/r2b"})
    assert Submission.objects.get(pk=s_r2.pk).status == "pending"

    # --- LEADERBOARD (anonymized) ---
    lb = Client().get(f"/crashtech/{h.slug}/leaderboard/").content.decode()
    assert "Team 1" in lb and "Rockets" not in lb       # anonymized
    from app.crashtech import compute_leaderboard
    rows = compute_leaderboard(h)
    assert rows[0]["approved"] == 150                    # Rockets: 100 + 50 bonus

    # --- DEADLINE → CLOSE → GLORY ---
    oc.post(f"/crashtech/{h.slug}/manage/", {"action": "advance"})   # → closed
    h.refresh_from_db(); assert h.status == "closed" and not h.accepts_submissions
    # submissions now hard-blocked
    _c(racer1).post(f"/crashtech/{h.slug}/challenges/{blink.pk}/submit/", {"video_url": "https://youtu.be/late"})
    assert "youtu.be/late" not in Submission.objects.get(pk=s_r1.pk).video_url

    # certificates + glory page
    oc.post(f"/crashtech/{h.slug}/certificates/")
    assert Certificate.objects.get(team=rockets).type == "winner"
    assert Certificate.objects.get(team=comets).type == "runner_up"
    oc.post(f"/crashtech/{h.slug}/glory/edit/", {"highlights": "GG", "publish": "on"})
    oc.post(f"/crashtech/{h.slug}/manage/", {"action": "advance"})   # → glory
    h.refresh_from_db(); assert h.status == "glory"
    glory_body = Client().get(f"/crashtech/{h.slug}/glory/").content.decode()
    assert "Rockets" in glory_body                        # winner revealed on glory page
