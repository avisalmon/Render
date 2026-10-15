"""SPR-C.6 — CrashTech: the museum, and where media lives.

The page an event ends in, and the only screen in the product written for
a stranger. Years later somebody lands here from a link and decides
whether the next one is worth a weekend, so it needs no account at all.

Two things carry the sprint.

**It assembles itself** (Rule 9.1). The standings, the numbers and the
exhibition all come from what the event already produced. A human adds a
paragraph and some photographs. Opening a blank page after a sleepless
night is how a museum never gets published, which is what happened in
2026.

**The exhibition is computed from consent, not copied** (Rule 9.4). A team
that withdraws disappears from the page on the next request and nothing is
deleted, which is why they can change their mind again in three years.
"""

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from crashtech import judging, museum
from crashtech.models import (
    Challenge, Deliverable, EventRole, Hackathon, JudgeGrade, MuseumPage,
    MuseumPhoto, Registration, Submission, SubmissionFile, Team,
    TeamMembership,
)

pytestmark = [pytest.mark.sprc6, pytest.mark.django_db]


def _event(**kwargs):
    now = timezone.now()
    defaults = dict(
        name="CrashTech VLSI 2027", status=Hackathon.MUSEUM,
        tagline="24 hours, one board, no excuses",
        starts_at=now - timezone.timedelta(days=30),
        ends_at=now - timezone.timedelta(days=29),
        submission_deadline=now - timezone.timedelta(days=29),
        results_published_at=now - timezone.timedelta(days=28),
    )
    defaults.update(kwargs)
    return Hackathon.objects.create(**defaults)


def _user(email):
    return User.objects.create_user(
        username=email.split("@")[0], email=email, password="crashtech-7781",
    )


def _with_role(event, email, role):
    user = _user(email)
    EventRole.objects.create(hackathon=event, user=user, role=role)
    return user


def _team(event, email, name=None, consent=True):
    team = Team.objects.create(
        hackathon=event, name=name or email.split("@")[0].title(),
        exhibition_consent=consent,
    )
    user = _with_role(event, email, EventRole.PARTICIPANT)
    Registration.objects.create(hackathon=event, user=user, status=Registration.ACCEPTED)
    TeamMembership.objects.create(hackathon=event, team=team, user=user)
    return team


def _exhibit(event, team, title="Get the board talking"):
    """A team with something actually on show."""
    challenge = Challenge.objects.create(
        hackathon=event, title=title, kind=Challenge.COMPLETION, points=50, visible=True,
    )
    deliverable = Deliverable.objects.create(
        challenge=challenge, label="Demo video", kind=Deliverable.VIDEO,
    )
    submission = Submission.objects.create(
        challenge=challenge, team=team, claimed_complete=True,
    )
    SubmissionFile.objects.create(
        submission=submission, deliverable=deliverable, url="https://youtu.be/demo",
    )
    return challenge, submission


def _image(name="bench.png"):
    """A real 1x1 PNG, because the moderation path decodes it."""
    data = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d4944415478da63fcffff3f0300050001ff9d0e0d00"
        "00000049454e44ae426082"
    )
    return SimpleUploadedFile(name, data, content_type="image/png")


# ------------------------------------------------- F-C.6.1 public, no account


def test_the_museum_needs_no_account(client):
    """Rule 9.2, and the whole reason the page exists. This is where
    somebody who has never heard of CrashTech lands, and an account wall is
    how they decide it is not worth it."""
    event = _event()
    team = _team(event, "p@example.com", name="Clockwise")
    _exhibit(event, team)

    anonymous = client.__class__()  # no session at all
    response = anonymous.get(f"/crashtech/e/{event.slug}/museum/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "Clockwise" in body
    assert event.name in body


def test_the_museum_index_is_public_too(client):
    event = _event()
    anonymous = client.__class__()
    body = anonymous.get("/crashtech/museum/").content.decode()
    assert event.name in body


def test_an_unfinished_event_says_so_rather_than_pretending_not_to_exist(client):
    """The event exists and is public. A 404 for a link that will work
    later is a worse answer than the true one."""
    now = timezone.now()
    event = _event(
        status=Hackathon.LIVE, results_published_at=None,
        starts_at=now, ends_at=now + timezone.timedelta(hours=24),
        submission_deadline=now + timezone.timedelta(hours=24),
    )
    anonymous = client.__class__()
    response = anonymous.get(f"/crashtech/e/{event.slug}/museum/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "has not finished" in body
    assert "keep working" in body


def test_an_unstarted_event_has_no_museum_at_all(client):
    """A `setup` event is not public (Rule 3.1), so its museum must not be
    a confirmation that it exists."""
    now = timezone.now()
    event = _event(
        status=Hackathon.SETUP, results_published_at=None,
        starts_at=now + timezone.timedelta(days=40),
        ends_at=now + timezone.timedelta(days=41),
        submission_deadline=now + timezone.timedelta(days=41),
    )
    assert client.get(f"/crashtech/e/{event.slug}/museum/").status_code == 404


# --------------------------------------------------- F-C.6.2 it assembles itself


def test_the_museum_assembles_itself_from_the_event(client):
    """Rule 9.1. Nobody typed any of this in."""
    event = _event()
    for name in ("Clockwise", "Ripple"):
        team = _team(event, f"{name.lower()}@example.com", name=name)
        _exhibit(event, team, title=f"{name} task")

    body = client.__class__().get(f"/crashtech/e/{event.slug}/museum/").content.decode()
    assert "Clockwise" in body
    assert "Ripple" in body
    assert "How it finished" in body
    assert "What was built" in body


def test_the_numbers_are_computed_and_cannot_disagree_with_the_event():
    event = _event()
    for n in range(3):
        team = _team(event, f"p{n}@example.com", name=f"Team {n}")
        _exhibit(event, team, title=f"Task {n}")

    figures = museum.numbers(event)
    assert figures["teams"] == 3
    assert figures["people"] == 3
    assert figures["submissions"] == 3
    assert figures["hours"] == 24


def test_the_paragraph_is_the_only_prose_a_human_writes(client):
    event = _event()
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)

    client.post(f"/crashtech/e/{event.slug}/museum/edit/", {
        "highlights": "Somebody made a ring oscillator play a chord.",
    })
    body = client.__class__().get(f"/crashtech/e/{event.slug}/museum/").content.decode()
    assert "ring oscillator play a chord" in body


# -------------------------------------------------------- F-C.6.3 consent


def test_only_consenting_teams_appear_in_the_exhibition(client):
    """Rule 9.4."""
    event = _event()
    shown = _team(event, "yes@example.com", name="Willing", consent=True)
    hidden = _team(event, "no@example.com", name="Private", consent=False)
    _exhibit(event, shown)
    _exhibit(event, hidden, title="Also built something")

    body = client.__class__().get(f"/crashtech/e/{event.slug}/museum/").content.decode()
    exhibition = body.split("What was built", 1)[1]
    assert "Willing" in exhibition
    assert "Private" not in exhibition


def test_withdrawing_consent_removes_the_work_and_deletes_nothing():
    """The entire reason the exhibition is computed rather than copied: a
    team that changes its mind in three years changes one boolean."""
    event = _event()
    team = _team(event, "p@example.com", name="Willing", consent=True)
    challenge, submission = _exhibit(event, team)
    assert len(museum.exhibition(event)) == 1

    museum.set_consent(team, False)
    assert museum.exhibition(event) == []
    assert Submission.objects.filter(pk=submission.pk).exists()
    assert SubmissionFile.objects.filter(submission=submission).exists()

    # And back again, equally cheaply.
    museum.set_consent(team, True)
    assert len(museum.exhibition(event)) == 1


def test_a_team_changes_its_own_consent(client):
    event = _event()
    team = _team(event, "p@example.com", consent=False)
    member = team.memberships.first().user
    client.force_login(member)

    client.post(f"/crashtech/e/{event.slug}/consent/", {"on": "1"})
    team.refresh_from_db()
    assert team.exhibition_consent is True

    client.post(f"/crashtech/e/{event.slug}/consent/", {})
    team.refresh_from_db()
    assert team.exhibition_consent is False


def test_somebody_else_cannot_change_a_teams_consent(client):
    event = _event()
    team = _team(event, "p@example.com", consent=False)
    stranger = _user("stranger@example.com")
    client.force_login(stranger)

    assert client.post(f"/crashtech/e/{event.slug}/consent/", {"on": "1"}).status_code == 403
    team.refresh_from_db()
    assert team.exhibition_consent is False


def test_a_team_still_appears_in_the_standings_without_consent(client):
    """Consent governs showing their *work*, not erasing them from the
    result. The standings are the public record of what happened."""
    event = _event()
    team = _team(event, "p@example.com", name="Private", consent=False)
    _exhibit(event, team)

    body = client.__class__().get(f"/crashtech/e/{event.slug}/museum/").content.decode()
    standings = body.split("How it finished", 1)[1].split("What was built", 1)[0]
    assert "Private" in standings


# ------------------------------------------------------ F-C.6.4 moderation


def test_an_uploaded_photo_is_checked_on_the_way_in(client):
    """Rule 9.3. A permanent public page anyone may post to is a permanent
    public page anyone may post anything to."""
    event = _event()
    person = _user("visitor@example.com")
    client.force_login(person)

    client.post(f"/crashtech/e/{event.slug}/museum/", {
        "photo": _image(), "caption": "The bench at 3am",
    })
    photo = MuseumPhoto.objects.get()
    assert photo.caption == "The bench at 3am"
    assert photo.moderation_status in (
        MuseumPhoto.APPROVED, MuseumPhoto.PENDING, MuseumPhoto.REJECTED,
    )


def test_moderation_fails_closed(monkeypatch):
    """The opposite of the site's own default, and on purpose. A bad image
    sitting on a page that is public forever is worse than one that waits a
    day."""
    from crashtech import moderation

    def exploding(*args, **kwargs):
        raise RuntimeError("the moderation service is down")

    monkeypatch.setattr("app.safety.image_is_safe", exploding)
    status, note = moderation.check_image(_image())
    assert status == MuseumPhoto.PENDING
    assert status != MuseumPhoto.APPROVED


def test_only_approved_photos_are_public(client):
    event = _event()
    page = MuseumPage.objects.create(hackathon=event)
    for status in (MuseumPhoto.APPROVED, MuseumPhoto.PENDING, MuseumPhoto.REJECTED):
        MuseumPhoto.objects.create(
            museum_page=page, image=_image(f"{status}.png"),
            caption=f"caption-{status}", moderation_status=status,
        )

    public = museum.photos(event)
    assert public.count() == 1
    body = client.__class__().get(f"/crashtech/e/{event.slug}/museum/").content.decode()
    assert "caption-approved" in body
    assert "caption-pending" not in body
    assert "caption-rejected" not in body


def test_an_admin_sees_the_pending_ones_so_a_false_rejection_can_be_rescued(client):
    event = _event()
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    page = MuseumPage.objects.create(hackathon=event)
    photo = MuseumPhoto.objects.create(
        museum_page=page, image=_image(), caption="waiting",
        moderation_status=MuseumPhoto.PENDING,
    )
    client.force_login(admin)

    body = client.get(f"/crashtech/e/{event.slug}/museum/edit/").content.decode()
    assert "waiting" in body

    client.post(f"/crashtech/e/{event.slug}/museum/edit/", {
        "photo_id": photo.pk, "decision": MuseumPhoto.APPROVED,
    })
    photo.refresh_from_db()
    assert photo.moderation_status == MuseumPhoto.APPROVED


def test_deleting_a_photo_deletes_its_file(client):
    """Rule 9.5: a row removed without its file leaves the file paid for
    and unreachable forever."""
    event = _event()
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    page = MuseumPage.objects.create(hackathon=event)
    photo = MuseumPhoto.objects.create(museum_page=page, image=_image())
    path = photo.image.path
    import os

    assert os.path.exists(path)

    client.force_login(admin)
    client.post(f"/crashtech/e/{event.slug}/museum/edit/", {
        "photo_id": photo.pk, "decision": "drop",
    })
    assert not MuseumPhoto.objects.filter(pk=photo.pk).exists()
    assert not os.path.exists(path)


def test_a_signed_out_visitor_cannot_post_a_photo(client):
    """Reading needs no account. Adding does, which is the one thing
    signing in buys."""
    event = _event()
    anonymous = client.__class__()
    response = anonymous.post(f"/crashtech/e/{event.slug}/museum/", {"photo": _image()})
    assert response.status_code == 302
    assert response.url.startswith("/crashtech/login/")
    assert not MuseumPhoto.objects.exists()


def test_only_an_admin_edits_the_museum(client):
    event = _event()
    team = _team(event, "p@example.com")
    client.force_login(team.memberships.first().user)
    assert client.get(f"/crashtech/e/{event.slug}/museum/edit/").status_code == 403


# ---------------------------------------------- F-C.6.5 where media lives


def test_user_uploads_go_through_one_switchable_storage():
    """Rule 9.5 is built and not switched on, which is deliberate: the
    bucket does not exist yet. The indirection is here so turning it on is
    an environment variable rather than a migration."""
    from crashtech import storage

    assert storage.is_remote() is False  # no bucket configured in dev or tests

    field = MuseumPhoto._meta.get_field("image")
    assert field.storage is not None
    submission_field = SubmissionFile._meta.get_field("file")
    assert submission_field.storage is not None


def test_the_migration_records_the_callable_and_not_a_backend():
    """A migration that baked in GoogleCloudStorage would fail on a laptop
    with no credentials, and one that baked in the local disk would have to
    be rewritten to switch."""
    source = open(
        "crashtech/migrations/0002_alter_museumphoto_image_alter_submissionfile_file.py",
        encoding="utf-8",
    ).read()
    assert "crashtech.storage.media_storage" in source
    assert "GoogleCloudStorage" not in source


# ----------------------------------------------------- opening, and the seal


def test_the_museum_opens_on_publishing_and_not_on_a_separate_flag(client):
    """Rule 8.5 and 9.1 together: one click does all of it. A second flag
    somebody has to remember to set is how a museum never opens."""
    now = timezone.now()
    event = _event(
        status=Hackathon.CLOSED, results_published_at=None,
        starts_at=now - timezone.timedelta(hours=26),
        ends_at=now - timezone.timedelta(hours=2),
        submission_deadline=now - timezone.timedelta(hours=2),
    )
    challenge = Challenge.objects.create(
        hackathon=event, title="Most elegant", kind=Challenge.CREATIVITY,
        points=40, max_grade=10, visible=True,
    )
    team = _team(event, "p@example.com", name="Clockwise")
    submission = Submission.objects.create(challenge=challenge, team=team, is_finalist=True)
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)
    JudgeGrade.objects.create(submission=submission, judge=judge, grade=8)
    assert museum.is_open(event) is False

    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    judging.publish(event, by=admin)
    event.refresh_from_db()

    assert museum.is_open(event) is True
    assert client.__class__().get(
        f"/crashtech/e/{event.slug}/museum/"
    ).status_code == 200


def test_the_museum_is_the_other_screen_that_stays_open(client):
    """Deliberately outside the seal, along with the certificate. Those two
    are the product's public face."""
    event = _event()
    for url in (f"/crashtech/e/{event.slug}/museum/", "/crashtech/museum/"):
        assert client.get(url).status_code == 200, url


def test_the_admin_museum_screen_is_behind_the_seal(client):
    event = _event()
    response = client.get(f"/crashtech/e/{event.slug}/museum/edit/")
    assert response.status_code == 302
    assert response.url.startswith("/crashtech/login/")


def test_the_museum_renders_no_hebrew(client):
    """Rule 2.2.4, on the one page a stranger sees."""
    event = _event()
    team = _team(event, "p@example.com", name="Clockwise")
    _exhibit(event, team)

    hebrew = "אבגדהוזחטיכלמנסעפצקרשת"
    for url in (f"/crashtech/e/{event.slug}/museum/", "/crashtech/museum/"):
        body = client.__class__().get(url).content.decode()
        assert not any(letter in body for letter in hebrew), url


def test_the_museum_does_not_link_back_into_babook(client):
    """Rule 2.2.3. This is the page most likely to be shared, so it is the
    one where a leak out of the walls would travel furthest."""
    event = _event()
    team = _team(event, "p@example.com")
    _exhibit(event, team)

    body = client.__class__().get(f"/crashtech/e/{event.slug}/museum/").content.decode()
    import re

    for href in re.findall(r'href="(/[^"]*)"', body):
        assert href.startswith("/crashtech/") or href.startswith("/static/"), href


def test_a_measured_entry_shows_its_result_in_the_exhibition(client):
    """Found by looking at the page. A ranked challenge has no file to
    link, so the exhibition rendered the team's best achievement as a
    heading with nothing under it. The number IS the achievement."""
    event = _event()
    team = _team(event, "p@example.com", name="Clockwise")
    challenge = Challenge.objects.create(
        hackathon=event, title="Fastest 8-bit multiplier", kind=Challenge.MEASURED,
        points=0, visible=True, metric_name="Fmax", metric_unit="MHz",
        rank_points=[60],
    )
    Submission.objects.create(challenge=challenge, team=team, reported_value="212.5000")

    rows = museum.exhibition(event)
    assert rows[0]["pieces"][0]["result"] == "Fmax 212.5 MHz"

    body = client.__class__().get(f"/crashtech/e/{event.slug}/museum/").content.decode()
    assert "Fmax 212.5 MHz" in body
    assert "212.5000" not in body
