"""
EPIC-6.5 CrashTech — SPR-6.5.5 Glory: certificates (participation/winner/
runner-up), the permanent public Glory Page, post-event consent opt-out, and
the anonymized public video gallery (consented teams only).
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


def _closed_event():
    """Closed hackathon, 3 teams with approved points (team A > B > C), each with
    a member + a consented demo video on A and B, none on C."""
    from app.crashtech import grant_role
    from app.models import Challenge, Hackathon, Submission, Team
    org = _staff("owner")
    h = Hackathon.objects.create(
        name="CrashTech Glory", organizer=org, status="closed",
        start_at=timezone.now() - timezone.timedelta(days=1),
        end_at=timezone.now() - timezone.timedelta(hours=1),
        submission_deadline=timezone.now() - timezone.timedelta(hours=1),
        team_size=3, hardware_stock=5,
    )
    grant_role(h, org, "organizer")
    ch = Challenge.objects.create(hackathon=h, title="Blink", point_value=100,
                                  scoring_mode="pass_fail", visible=True)
    teams = {}
    for i, (tname, pts, consent) in enumerate(
            [("Alpha", 100, True), ("Beta", 50, True), ("Gamma", 0, False)], start=1):
        t = Team.objects.create(hackathon=h, name=tname, anon_ordinal=i,
                                glory_consent=consent)
        member = _user(f"member{i}")
        t.members.add(member)
        grant_role(h, member, "participant")
        Submission.objects.create(
            challenge=ch, team=t, status="approved" if pts else "pending",
            points_awarded=pts, video_url=f"https://youtu.be/clip{i}")
        teams[tname] = t
    return h, teams, ch


# --- F-6.5.5.1: certificates ---

@pytest.mark.django_db
def test_organizer_generates_ranked_certificates():
    from app.models import Certificate
    h, teams, ch = _closed_event()
    resp = _client(h.organizer).post(f"/crashtech/{h.slug}/certificates/")
    assert resp.status_code == 302
    assert Certificate.objects.get(team=teams["Alpha"]).type == "winner"
    assert Certificate.objects.get(team=teams["Beta"]).type == "runner_up"
    assert Certificate.objects.get(team=teams["Gamma"]).type == "participation"


@pytest.mark.django_db
def test_certificate_public_view():
    from app.models import Certificate
    h, teams, ch = _closed_event()
    _client(h.organizer).post(f"/crashtech/{h.slug}/certificates/")
    cert = Certificate.objects.get(team=teams["Alpha"])
    body = Client().get(f"/crashtech/cert/{cert.cert_id}/").content.decode()
    assert "Alpha" in body and h.name in body


@pytest.mark.django_db
def test_non_organizer_cannot_generate_certificates():
    from app.models import Certificate
    h, teams, ch = _closed_event()
    resp = _client(_user("rando")).post(f"/crashtech/{h.slug}/certificates/")
    assert resp.status_code in (302, 403)
    assert Certificate.objects.count() == 0


# --- F-6.5.5.2: Glory Page ---

@pytest.mark.django_db
def test_glory_page_unpublished_is_hidden_then_published_public():
    h, teams, ch = _closed_event()
    # not published yet → 404 for the public
    assert Client().get(f"/crashtech/{h.slug}/glory/").status_code == 404
    # organizer edits highlights + publishes
    _client(h.organizer).post(f"/crashtech/{h.slug}/glory/edit/", {
        "highlights": "אירוע מדהים!", "publish": "on"})
    resp = Client().get(f"/crashtech/{h.slug}/glory/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "אירוע מדהים" in body
    assert "Alpha" in body  # winner revealed on the glory page


# --- F-6.5.5.3: consent opt-out ---

@pytest.mark.django_db
def test_team_member_can_opt_out_post_event():
    from app.models import Team
    h, teams, ch = _closed_event()
    member = teams["Alpha"].members.first()
    _client(member).post(f"/crashtech/{h.slug}/consent/", {"glory_consent": ""})
    assert Team.objects.get(pk=teams["Alpha"].pk).glory_consent is False


# --- F-6.5.5.4: anonymized public gallery, consented only ---

@pytest.mark.django_db
def test_video_gallery_anonymized_consenting_only():
    h, teams, ch = _closed_event()
    body = Client().get(f"/crashtech/{h.slug}/gallery/").content.decode()
    # consenting teams' demos appear, anonymized
    assert "Team 1" in body            # Alpha's anon label (consented)
    assert "Alpha" not in body         # real name hidden in the public gallery
    assert "clip1" in body             # Alpha's (consented, approved) demo shown
    # non-consenting team's video excluded
    assert "clip3" not in body         # Gamma (no consent) excluded
