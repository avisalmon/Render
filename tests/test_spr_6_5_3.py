"""
EPIC-6.5 CrashTech — SPR-6.5.3 Live core: kickoff unlock + event main page,
submission (video link + zip code) → pending queue, QR phone-upload binding,
and the hard deadline gate.
"""
import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
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


def _live_hackathon(status="active", deadline_hours=5):
    from app.crashtech import grant_role
    from app.models import Challenge, Hackathon, Team
    org = _staff("owner")
    h = Hackathon.objects.create(
        name="CrashTech Live", organizer=org, status=status,
        start_at=timezone.now() - timezone.timedelta(hours=1),
        end_at=timezone.now() + timezone.timedelta(hours=deadline_hours),
        submission_deadline=timezone.now() + timezone.timedelta(hours=deadline_hours),
        team_size=3, hardware_stock=5,
    )
    grant_role(h, org, "organizer")
    ch = Challenge.objects.create(hackathon=h, title="Blink", description="blink",
                                  point_value=100, scoring_mode="pass_fail", visible=True)
    member = _user("racer")
    team = Team.objects.create(hackathon=h, name="Rockets", anon_ordinal=1)
    team.members.add(member)
    grant_role(h, member, "participant")
    return h, ch, team, member


def _zip():
    return SimpleUploadedFile("code.zip", b"PK\x03\x04 fake zip bytes",
                              content_type="application/zip")


# --- F-6.5.3.1: kickoff unlock ---

@pytest.mark.django_db
def test_challenges_visible_on_event_page_after_kickoff():
    h, ch, team, member = _live_hackathon(status="active")
    body = Client().get(f"/crashtech/{h.slug}/").content.decode()
    assert "Blink" in body                 # unlocked at kickoff
    # before kickoff they are secret
    h.status = "readiness"; h.save()
    body = Client().get(f"/crashtech/{h.slug}/").content.decode()
    assert "Blink" not in body


# --- F-6.5.3.2: submission ---

@pytest.mark.django_db
def test_team_member_submits_video_and_zip():
    from app.models import Submission
    h, ch, team, member = _live_hackathon()
    resp = _client(member).post(f"/crashtech/{h.slug}/challenges/{ch.pk}/submit/", {
        "video_url": "https://youtu.be/abc123",
        "source_code": _zip(),
    })
    assert resp.status_code == 302
    sub = Submission.objects.get(challenge=ch, team=team)
    assert sub.status == "pending"
    assert "youtu.be/abc123" in sub.video_url
    assert sub.source_code  # zip stored


@pytest.mark.django_db
def test_non_member_cannot_submit():
    from app.models import Submission
    h, ch, team, member = _live_hackathon()
    outsider = _user("outsider")
    resp = _client(outsider).post(f"/crashtech/{h.slug}/challenges/{ch.pk}/submit/", {
        "video_url": "https://youtu.be/x"})
    assert resp.status_code in (302, 403)
    assert not Submission.objects.filter(challenge=ch).exists()


@pytest.mark.django_db
def test_resubmit_updates_same_submission():
    from app.models import Submission
    h, ch, team, member = _live_hackathon()
    c = _client(member)
    c.post(f"/crashtech/{h.slug}/challenges/{ch.pk}/submit/", {"video_url": "https://youtu.be/v1"})
    c.post(f"/crashtech/{h.slug}/challenges/{ch.pk}/submit/", {"video_url": "https://youtu.be/v2"})
    assert Submission.objects.filter(challenge=ch, team=team).count() == 1
    assert "v2" in Submission.objects.get(challenge=ch, team=team).video_url


# --- F-6.5.3.4: deadline gate ---

@pytest.mark.django_db
def test_submission_blocked_before_kickoff():
    from app.models import Submission
    h, ch, team, member = _live_hackathon(status="readiness")
    _client(member).post(f"/crashtech/{h.slug}/challenges/{ch.pk}/submit/", {"video_url": "https://youtu.be/x"})
    assert not Submission.objects.filter(challenge=ch).exists()


@pytest.mark.django_db
def test_submission_blocked_after_deadline():
    from app.models import Submission
    h, ch, team, member = _live_hackathon(status="active", deadline_hours=5)
    h.submission_deadline = timezone.now() - timezone.timedelta(minutes=1)
    h.save()
    _client(member).post(f"/crashtech/{h.slug}/challenges/{ch.pk}/submit/", {"video_url": "https://youtu.be/x"})
    assert not Submission.objects.filter(challenge=ch).exists()


# --- F-6.5.3.3: QR phone-upload binding ---

@pytest.mark.django_db
def test_qr_token_upload_binds_team_and_challenge():
    from app.crashtech_models import QRToken
    from app.models import Submission
    h, ch, team, member = _live_hackathon()
    # member requests a QR token for this challenge
    _client(member).get(f"/crashtech/{h.slug}/challenges/{ch.pk}/qr/")
    tok = QRToken.objects.get(team=team, challenge=ch)
    # the phone (no login) uploads a video via the token
    video = SimpleUploadedFile("demo.mp4", b"fake mp4 bytes", content_type="video/mp4")
    resp = Client().post(f"/crashtech/u/{tok.token}/", {"video": video})
    assert resp.status_code in (200, 302)
    sub = Submission.objects.get(challenge=ch, team=team)
    assert sub.video_file  # bound to the right team+challenge
