"""
EPIC-6.5 CrashTech — SPR-6.5.4 Judging & scoring: blind judge queue,
approve/reject pass-fail with feedback (points only after approval),
resubmission reopen, organizer-only bonus tiers, anonymized leaderboard.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone


def _staff(username="org"):
    u = User.objects.create_user(username, password="pass12345", is_staff=True)
    u.profile.display_name = username
    u.profile.save()
    return u


def _user(username="u"):
    u = User.objects.create_user(username, password="pass12345")
    u.profile.display_name = username
    u.profile.save()
    return u


def _client(user):
    c = Client()
    c.force_login(user)
    return c


def _setup():
    """Active hackathon with a judge, a team + member, a pass/fail challenge and
    a pending submission. Returns a bundle dict."""
    from app.crashtech import grant_role
    from app.models import Challenge, Hackathon, Submission, Team
    org = _staff("owner")
    h = Hackathon.objects.create(
        name="CrashTech Judge", organizer=org, status="active",
        start_at=timezone.now() - timezone.timedelta(hours=1),
        end_at=timezone.now() + timezone.timedelta(hours=5),
        submission_deadline=timezone.now() + timezone.timedelta(hours=5),
        team_size=3, hardware_stock=5,
    )
    grant_role(h, org, "organizer")
    judge = _user("judgey"); grant_role(h, judge, "judge")
    member = _user("builder"); grant_role(h, member, "participant")
    team = Team.objects.create(hackathon=h, name="SecretSquad", anon_ordinal=1)
    team.members.add(member)
    ch = Challenge.objects.create(hackathon=h, title="Blink", point_value=100,
                                  scoring_mode="pass_fail", visible=True)
    sub = Submission.objects.create(challenge=ch, team=team,
                                    video_url="https://youtu.be/x", status="pending")
    return dict(h=h, org=org, judge=judge, member=member, team=team, ch=ch, sub=sub)


# --- F-6.5.4.1: blind judging ---

@pytest.mark.django_db
def test_judge_queue_is_blind_to_team_identity():
    b = _setup()
    body = _client(b["judge"]).get(f"/crashtech/{b['h'].slug}/judge/").content.decode()
    assert "Blink" in body
    assert "SecretSquad" not in body          # real team name hidden (blind)


@pytest.mark.django_db
def test_judge_approves_awards_points_and_notifies():
    from app.models import Notification, Submission
    b = _setup()
    resp = _client(b["judge"]).post(
        f"/crashtech/{b['h'].slug}/submissions/{b['sub'].pk}/review/",
        {"action": "approve"})
    assert resp.status_code == 302
    sub = Submission.objects.get(pk=b["sub"].pk)
    assert sub.status == "approved" and sub.points_awarded == 100
    assert sub.reviewed_by == b["judge"]
    assert Notification.objects.filter(user=b["member"], verb="crashtech_review").exists()


@pytest.mark.django_db
def test_judge_rejects_with_feedback():
    from app.models import Submission
    b = _setup()
    _client(b["judge"]).post(
        f"/crashtech/{b['h'].slug}/submissions/{b['sub'].pk}/review/",
        {"action": "reject", "feedback_note": "הוידאו לא ברור"})
    sub = Submission.objects.get(pk=b["sub"].pk)
    assert sub.status == "rejected" and "ברור" in sub.feedback_note
    assert sub.points_awarded == 0            # points only after approval


@pytest.mark.django_db
def test_participant_cannot_review():
    b = _setup()
    resp = _client(b["member"]).post(
        f"/crashtech/{b['h'].slug}/submissions/{b['sub'].pk}/review/", {"action": "approve"})
    assert resp.status_code in (302, 403)
    from app.models import Submission
    assert Submission.objects.get(pk=b["sub"].pk).status == "pending"


# --- F-6.5.4.2: resubmission reopens ---

@pytest.mark.django_db
def test_resubmission_reopens_rejected_to_pending():
    from app.models import Submission
    b = _setup()
    b["sub"].status = "rejected"; b["sub"].feedback_note = "fix it"; b["sub"].save()
    _client(b["member"]).post(
        f"/crashtech/{b['h'].slug}/challenges/{b['ch'].pk}/submit/",
        {"video_url": "https://youtu.be/better"})
    sub = Submission.objects.get(pk=b["sub"].pk)
    assert sub.status == "pending" and "better" in sub.video_url


# --- F-6.5.4.3: organizer bonus tiers ---

@pytest.mark.django_db
def test_organizer_awards_bonus_tiers_judge_cannot():
    from app.models import Challenge, Submission, Team
    b = _setup()
    perf = Challenge.objects.create(hackathon=b["h"], title="Coolest", point_value=0,
                                    scoring_mode="performance_creativity",
                                    top_submission_count=3, bonus_points_tiers=[50, 30, 10],
                                    visible=True)
    t2 = Team.objects.create(hackathon=b["h"], name="Team2", anon_ordinal=2)
    sub1 = Submission.objects.create(challenge=perf, team=b["team"], status="approved")
    sub2 = Submission.objects.create(challenge=perf, team=t2, status="approved")
    # organizer assigns ranks (1 → 50, 2 → 30)
    resp = _client(b["org"]).post(
        f"/crashtech/{b['h'].slug}/challenges/{perf.pk}/bonus/",
        {f"rank_{sub1.pk}": "1", f"rank_{sub2.pk}": "2"})
    assert resp.status_code == 302
    sub1.refresh_from_db(); sub2.refresh_from_db()
    assert sub1.bonus_points_awarded == 50 and sub2.bonus_points_awarded == 30
    # a judge cannot award bonus
    resp = _client(b["judge"]).post(
        f"/crashtech/{b['h'].slug}/challenges/{perf.pk}/bonus/", {f"rank_{sub1.pk}": "2"})
    assert resp.status_code in (302, 403)


# --- F-6.5.4.4: anonymized leaderboard ---

@pytest.mark.django_db
def test_leaderboard_anonymized_with_pending():
    from app.crashtech import compute_leaderboard
    from app.models import Submission
    b = _setup()
    # approve the pending sub → 100 approved
    b["sub"].status = "approved"; b["sub"].points_awarded = 100; b["sub"].save()
    # a second pending sub on a new challenge
    from app.models import Challenge
    ch2 = Challenge.objects.create(hackathon=b["h"], title="Sensor", point_value=50,
                                   scoring_mode="pass_fail", visible=True)
    Submission.objects.create(challenge=ch2, team=b["team"], status="pending")
    rows = compute_leaderboard(b["h"])
    assert rows[0]["approved"] == 100 and rows[0]["pending"] == 50
    # public page shows the anon label, never the real name
    body = Client().get(f"/crashtech/{b['h'].slug}/leaderboard/").content.decode()
    assert "Team 1" in body and "SecretSquad" not in body
