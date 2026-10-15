"""One event, start to finish, through the screens (SPR-C.1 to C.6).

Every other CrashTech test takes one rule and holds it still. This one
does the opposite: it drives a whole event from "an admin creates it" to
"a stranger reads the museum", clicking the same URLs a person clicks, in
the same order, with nothing reached into directly.

It exists because the sprints were built one at a time and each was
verified on its own. The failure this catches is the one none of them can:
a step that works in isolation and does not hand the next step what it
needs. It is also exactly the walkthrough in the demo guide, so if the
guide stops being true, this goes red.
"""

import re

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from crashtech.models import (
    Certificate, Challenge, EventRole, Hackathon, MuseumPhoto, Registration,
    Submission, Team,
)

pytestmark = [pytest.mark.crashtech_e2e, pytest.mark.django_db]


def _png():
    data = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d4944415478da63fcffff3f0300050001ff9d0e0d00"
        "00000049454e44ae426082"
    )
    return SimpleUploadedFile("bench.png", data, content_type="image/png")


def _person(email, **flags):
    user = User.objects.create_user(
        username=email.split("@")[0], email=email, password="crashtech-7781", **flags
    )
    return user


def test_one_whole_event_from_setup_to_museum(client):
    now = timezone.now()

    # --- 1. A site admin creates the event -----------------------------
    # Rule 4.2: a superuser is the only way a first admin can exist, since
    # granting roles needs an admin and there is not one yet.
    organiser = _person("organiser@example.com", is_superuser=True, is_staff=True)
    client.force_login(organiser)

    response = client.post("/crashtech/create/", {
        "name": "CrashTech End To End",
        "tagline": "One board, one night",
        "starts_at": (now + timezone.timedelta(days=10)).strftime("%Y-%m-%dT%H:%M"),
        "ends_at": (now + timezone.timedelta(days=11)).strftime("%Y-%m-%dT%H:%M"),
        "submission_deadline": (now + timezone.timedelta(days=11)).strftime("%Y-%m-%dT%H:%M"),
        "team_size_max": "2",
    })
    assert response.status_code == 302
    event = Hackathon.objects.get(name="CrashTech End To End")
    assert event.status == Hackathon.SETUP
    slug = event.slug

    # --- 2. The people who run it --------------------------------------
    for email, role in (
        ("lead@example.com", EventRole.TECH_LEAD),
        ("judge@example.com", EventRole.JUDGE),
    ):
        _person(email)
        client.post(f"/crashtech/e/{slug}/people/", {"email": email, "role": role}, follow=True)
    assert event.roles.filter(role=EventRole.TECH_LEAD).exists()
    assert event.roles.filter(role=EventRole.JUDGE).exists()

    # --- 3. A tech lead writes the challenges, still sealed -------------
    lead = User.objects.get(username="lead")
    client.force_login(lead)
    for payload in (
        {"title": "Get it working", "kind": Challenge.COMPLETION, "points": "50"},
        {"title": "Fastest adder", "kind": Challenge.MEASURED, "points": "0",
         "metric_name": "Fmax", "metric_unit": "MHz", "rank_points": "60, 40, 25"},
        {"title": "Most elegant", "kind": Challenge.CREATIVITY, "points": "40",
         "max_grade": "10", "criteria": "Would you show it to somebody?"},
    ):
        client.post(f"/crashtech/e/{slug}/challenges/new/", payload, follow=True)
    assert event.challenges.count() == 3
    assert event.challenges.filter(visible=True).count() == 0

    # Each needs something to turn in, or the event cannot go live.
    for challenge in event.challenges.all():
        client.post(f"/crashtech/e/{slug}/challenges/{challenge.pk}/edit/", {
            "add_deliverable": "1", "label": "Source files",
            "kind": "file", "purpose": "artifact", "required": "1",
        }, follow=True)
    assert all(c.is_finished for c in event.challenges.all())

    # --- 4. The kit ----------------------------------------------------
    client.post(f"/crashtech/e/{slug}/kit/", {
        "name": "DE10-Lite", "description": "MAX 10 FPGA board",
        "quantity_total": "30", "is_returnable": "1",
    }, follow=True)
    assert event.kit_items.count() == 1

    # --- 5. Publish, so people can apply -------------------------------
    client.force_login(organiser)
    client.post(f"/crashtech/e/{slug}/advance/", follow=True)
    event.refresh_from_db()
    assert event.status == Hackathon.PUBLISHED

    # --- 6. Two people apply and are accepted --------------------------
    entrants = []
    for email in ("dana@example.com", "yoav@example.com"):
        person = _person(email)
        entrants.append(person)
        client.force_login(person)
        client.post(f"/crashtech/e/{slug}/apply/", follow=True)
    assert event.registrations.filter(status=Registration.APPLIED).count() == 2

    client.force_login(organiser)
    for registration in event.registrations.all():
        client.post(f"/crashtech/e/{slug}/registrations/", {
            "registration": registration.pk, "decision": Registration.ACCEPTED,
        }, follow=True)
    assert event.roles.filter(role=EventRole.PARTICIPANT).count() == 2

    # --- 7. A team of two ----------------------------------------------
    client.force_login(entrants[0])
    client.post(f"/crashtech/e/{slug}/teams/", {"name": "Clockwise"}, follow=True)
    team = Team.objects.get(hackathon=event, name="Clockwise")
    client.force_login(entrants[1])
    client.post(f"/crashtech/e/{slug}/teams/", {"join": team.pk}, follow=True)
    assert team.memberships.count() == 2

    # And the exhibition consent they will be judged on later.
    client.post(f"/crashtech/e/{slug}/consent/", {"on": "1"}, follow=True)
    team.refresh_from_db()
    assert team.exhibition_consent is True

    # --- 8. Kit distribution, at the desk ------------------------------
    client.force_login(organiser)
    client.post(f"/crashtech/e/{slug}/advance/", follow=True)
    event.refresh_from_db()
    assert event.status == Hackathon.KITS

    client.post(f"/crashtech/e/{slug}/kit-desk/", {
        "team": team.pk, "member": entrants[0].pk,
    }, follow=True)
    assert team.kit_issues.filter(status="collected").count() == 1

    # Before kickoff a participant can see nothing at all.
    client.force_login(entrants[0])
    sealed = client.get(f"/crashtech/e/{slug}/challenges/").content.decode()
    assert "Get it working" not in sealed
    assert "sealed until the event starts" in sealed

    # --- 9. Kickoff ----------------------------------------------------
    Hackathon.objects.filter(pk=event.pk).update(
        starts_at=now - timezone.timedelta(hours=1),
        ends_at=now + timezone.timedelta(hours=23),
        submission_deadline=now + timezone.timedelta(hours=23),
    )
    client.force_login(organiser)
    client.post(f"/crashtech/e/{slug}/advance/", follow=True)
    event.refresh_from_db()
    assert event.status == Hackathon.LIVE
    assert event.challenges.filter(visible=False).count() == 0

    # --- 10. The team submits to all three ------------------------------
    client.force_login(entrants[1])
    open_now = client.get(f"/crashtech/e/{slug}/challenges/").content.decode()
    assert "Get it working" in open_now

    completion = event.challenges.get(kind=Challenge.COMPLETION)
    measured = event.challenges.get(kind=Challenge.MEASURED)
    creativity = event.challenges.get(kind=Challenge.CREATIVITY)

    source = completion.deliverables.get()
    client.post(f"/crashtech/e/{slug}/challenges/{completion.pk}/submit/", {
        f"d{source.pk}": SimpleUploadedFile("src.txt", b"it works", content_type="text/plain"),
        "claimed_complete": "1",
    }, follow=True)
    done = Submission.objects.get(team=team, challenge=completion)
    assert done.claimed_complete is True
    assert done.tentative_points == 50  # on trust, straight away

    client.post(f"/crashtech/e/{slug}/challenges/{measured.pk}/submit/", {
        f"d{measured.deliverables.get().pk}": SimpleUploadedFile(
            "hdl.txt", b"module mult;", content_type="text/plain",
        ),
        "reported_value": "212.5",
        "reported_note": "Pipelined twice.",
    }, follow=True)
    ranked = Submission.objects.get(team=team, challenge=measured)
    assert str(ranked.reported_value) == "212.5000"
    assert ranked.tentative_points == 60  # first, and the only entrant

    client.post(f"/crashtech/e/{slug}/challenges/{creativity.pk}/submit/", {
        f"d{creativity.deliverables.get().pk}": SimpleUploadedFile(
            "what.txt", b"a chord", content_type="text/plain",
        ),
    }, follow=True)
    creative = Submission.objects.get(team=team, challenge=creativity)
    assert creative.tentative_points == 0  # nothing until a judge looks

    # The team sees its own score; the standings are still shut.
    mine = client.get(f"/crashtech/e/{slug}/challenges/").content.decode()
    assert "Your points" in mine
    assert "110" in mine  # 50 + 60, and the creativity one pending
    assert client.get(f"/crashtech/e/{slug}/standings/").status_code == 403

    # --- 11. Close, and the blind labels --------------------------------
    Hackathon.objects.filter(pk=event.pk).update(
        ends_at=now - timezone.timedelta(minutes=1),
        submission_deadline=now - timezone.timedelta(minutes=1),
    )
    client.force_login(organiser)
    client.post(f"/crashtech/e/{slug}/advance/", follow=True)
    event.refresh_from_db()
    assert event.status == Hackathon.CLOSED
    team.refresh_from_db()
    assert team.anon_ordinal == 1

    # --- 12. Judging ----------------------------------------------------
    judge = User.objects.get(username="judge")
    client.force_login(judge)
    board = client.get(f"/crashtech/e/{slug}/judging/").content.decode()
    assert "Most elegant" in board

    shortlist = client.get(
        f"/crashtech/e/{slug}/judging/{creativity.pk}/shortlist/"
    ).content.decode()
    assert "Entry 1" in shortlist
    assert "Clockwise" not in shortlist  # blind

    client.post(f"/crashtech/e/{slug}/judging/{creativity.pk}/shortlist/", {
        "submission": creative.pk, "on": "1",
    }, follow=True)
    client.post(f"/crashtech/e/{slug}/judging/entry/{creative.pk}/", {
        "grade": "8", "note": "Would show it to somebody.",
    }, follow=True)
    creative.refresh_from_db()
    assert creative.tentative_points == 32  # 8/10 of 40

    # The spot check: looked at, and it holds.
    client.post(f"/crashtech/e/{slug}/verify/", {
        "submission": ranked.pk, "outcome": Submission.VERIFIED,
    }, follow=True)
    ranked.refresh_from_db()
    assert ranked.verification == Submission.VERIFIED

    # --- 13. Publish ----------------------------------------------------
    client.force_login(organiser)
    page = client.get(f"/crashtech/e/{slug}/publish/").content.decode()
    assert "Publish, permanently" in page  # nothing outstanding

    client.post(f"/crashtech/e/{slug}/publish/", follow=True)
    event.refresh_from_db()
    assert event.results_published_at is not None
    assert event.status == Hackathon.MUSEUM
    assert Submission.objects.get(pk=done.pk).final_points == 50
    certificate = Certificate.objects.get(hackathon=event, team=team)
    assert certificate.type == Certificate.WINNER

    # --- 14. A stranger reads the museum --------------------------------
    stranger = client.__class__()  # no session at all
    museum_page = stranger.get(f"/crashtech/e/{slug}/museum/")
    assert museum_page.status_code == 200
    body = museum_page.content.decode()
    assert "Clockwise" in body
    assert "Fmax 212.5 MHz" in body
    assert "142" in body  # 50 + 60 + 32

    # And the certificate, which is the link that ends up on a CV.
    cert_page = stranger.get(f"/crashtech/c/{certificate.cert_id}/")
    assert cert_page.status_code == 200
    assert "Clockwise" in cert_page.content.decode()

    # --- 15. Consent still works, years later ---------------------------
    client.force_login(entrants[0])
    client.post(f"/crashtech/e/{slug}/consent/", {}, follow=True)
    withdrawn = stranger.get(f"/crashtech/e/{slug}/museum/").content.decode()
    exhibition = withdrawn.split("What was built", 1)[1]
    assert "Clockwise" not in exhibition
    # Still in the standings, and nothing was deleted.
    assert Submission.objects.filter(team=team).count() == 3


def test_the_seeded_demo_event_can_be_driven_forward(client):
    """The demo guide tells Avi to start from the seeded event, so the
    seed has to leave it in a state he can actually move."""
    from django.core.management import call_command

    call_command("seed_crashtech")
    event = Hackathon.objects.get(slug="demo-vlsi")

    assert event.status == Hackathon.KITS
    assert event.challenges.count() == 3
    assert {c.kind for c in event.challenges.all()} == {
        Challenge.COMPLETION, Challenge.MEASURED, Challenge.CREATIVITY,
    }
    # Sealed, like every challenge, whatever the event's status.
    assert event.challenges.filter(visible=True).count() == 0
    # And every one of them says what to turn in, or it would block going
    # live for a reason that looks like a bug.
    assert all(c.is_finished for c in event.challenges.all())

    from crashtech import readiness

    blockers = [c.text for c in readiness.blockers_for(event)]
    # Exactly one thing stands between the seed and a running event, and
    # it is the one the guide asks him to do first.
    assert blockers == ["No judges assigned"]
