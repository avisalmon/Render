"""
EPIC-6.5 CrashTech — SPR-6.5.1 Foundations: Hackathon + HackRole + Challenge
models, the lifecycle state machine, organizer setup, challenge authoring
(secret until kickoff), and judge assignment.
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


def _hackathon(organizer=None, **kw):
    from app.models import Hackathon
    organizer = organizer or _staff("owner")
    kw.setdefault("name", "CrashTech 2026")
    kw.setdefault("start_at", timezone.now() + timezone.timedelta(days=14))
    kw.setdefault("submission_deadline", timezone.now() + timezone.timedelta(days=15))
    kw.setdefault("end_at", timezone.now() + timezone.timedelta(days=15))
    kw.setdefault("team_size", 3)
    kw.setdefault("hardware_stock", 10)
    h = Hackathon.objects.create(organizer=organizer, **kw)
    from app.crashtech import grant_role
    grant_role(h, organizer, "organizer")
    return h


# --- F-6.5.1.1: lifecycle state machine ---

@pytest.mark.django_db
def test_lifecycle_advances_in_order():
    h = _hackathon()
    assert h.status == "setup"
    order = ["setup", "readiness", "active", "closed", "glory"]
    seen = [h.status]
    while h.advance():
        seen.append(h.status)
    assert seen == order


@pytest.mark.django_db
def test_challenges_hidden_until_kickoff_and_submissions_gated():
    h = _hackathon(submission_deadline=timezone.now() + timezone.timedelta(hours=1))
    assert h.challenges_visible is False        # setup
    assert h.accepts_submissions is False
    h.status = "active"; h.save()
    assert h.challenges_visible is True          # unlocked at kickoff
    assert h.accepts_submissions is True
    # past the deadline → gate closes even while active
    h.submission_deadline = timezone.now() - timezone.timedelta(minutes=1); h.save()
    assert h.accepts_submissions is False


# --- F-6.5.1.2: roles + permission helpers ---

@pytest.mark.django_db
def test_roles_are_per_hackathon_and_multi():
    from app.crashtech import grant_role, is_judge, is_organizer, roles_of
    h = _hackathon()
    judge = _user("judge1")
    grant_role(h, judge, "judge")
    grant_role(h, judge, "participant")          # multi-role allowed
    assert roles_of(judge, h) == {"judge", "participant"}
    assert is_judge(judge, h) and not is_organizer(judge, h)
    # organizer-only power stays with the organizer
    assert is_organizer(h.organizer, h)


# --- F-6.5.1.3: organizer setup (staff-gated creation) ---

@pytest.mark.django_db
def test_only_staff_can_create_hackathon():
    plain = _user("plain")
    resp = _client(plain).get("/crashtech/new/")
    assert resp.status_code in (302, 403)        # walled
    staff = _staff("creator")
    resp = _client(staff).post("/crashtech/new/", {
        "name": "Robot Rumble",
        "start_at": "2026-07-01T09:00",
        "end_at": "2026-07-02T09:00",
        "submission_deadline": "2026-07-02T09:00",
        "team_size": 3, "hardware_stock": 8,
        "github_repo_url": "https://github.com/babook/crashtech-starter",
    })
    assert resp.status_code == 302
    from app.crashtech import is_organizer
    from app.models import Hackathon
    h = Hackathon.objects.get(name="Robot Rumble")
    assert h.status == "setup" and h.team_size == 3 and h.hardware_stock == 8
    assert is_organizer(staff, h)                # creator becomes organizer


# --- F-6.5.1.4: challenge authoring (secret, two scoring modes) ---

@pytest.mark.django_db
def test_organizer_authors_challenges_secret_by_default():
    h = _hackathon()
    c = _client(h.organizer)
    resp = c.post(f"/crashtech/{h.slug}/challenges/new/", {
        "title": "Blink an LED", "description": "Make it blink",
        "point_value": 100, "scoring_mode": "pass_fail",
    })
    assert resp.status_code == 302
    from app.models import Challenge
    ch = Challenge.objects.get(hackathon=h, title="Blink an LED")
    assert ch.visible is False                    # secret until kickoff
    assert ch.scoring_mode == "pass_fail" and ch.point_value == 100
    # performance/creativity challenge with bonus tiers
    c.post(f"/crashtech/{h.slug}/challenges/new/", {
        "title": "Coolest hack", "description": "Wow us",
        "point_value": 0, "scoring_mode": "performance_creativity",
        "top_submission_count": 3, "bonus_points_tiers": "50, 30, 10",
    })
    perf = Challenge.objects.get(hackathon=h, title="Coolest hack")
    assert perf.scoring_mode == "performance_creativity"
    assert perf.bonus_points_tiers == [50, 30, 10] and perf.top_submission_count == 3


@pytest.mark.django_db
def test_non_organizer_cannot_author_challenges():
    h = _hackathon()
    intruder = _user("intruder")
    resp = _client(intruder).post(f"/crashtech/{h.slug}/challenges/new/", {
        "title": "Hack", "description": "x", "point_value": 10, "scoring_mode": "pass_fail",
    })
    assert resp.status_code in (302, 403)
    from app.models import Challenge
    assert not Challenge.objects.filter(title="Hack").exists()


# --- F-6.5.1.5: judge assignment ---

@pytest.mark.django_db
def test_organizer_assigns_judge():
    from app.crashtech import is_judge
    h = _hackathon()
    judge = _user("judgecandidate")
    resp = _client(h.organizer).post(f"/crashtech/{h.slug}/judges/", {"username": "judgecandidate"})
    assert resp.status_code == 302
    assert is_judge(judge, h)
    # a non-organizer cannot assign judges
    other = _user("other")
    resp = _client(other).post(f"/crashtech/{h.slug}/judges/", {"username": "other"})
    assert resp.status_code in (302, 403)
