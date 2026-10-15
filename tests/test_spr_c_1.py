"""SPR-C.1 — CrashTech: the skeleton and the seal (docs/crashtech/backlog.md).

The app exists, is sealed in both directions, has its own front door, and
every model from the approved data model is real.

Most of this file is refusals and boundaries rather than features, which
is the right ratio for a sprint whose whole job is a wall. The two things
most likely to break silently (spec Rule 14.2) both get tested here even
though the screens that would expose them do not exist yet: **the seal**,
because an import added in a hurry looks exactly like one that was
thought about, and **the permission matrix**, because a view that forgets
a check looks exactly like a view that has one.
"""

import re
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from crashtech import roles
from crashtech.invitations import redeem_for
from crashtech.models import (
    Challenge, Deliverable, EventRole, Hackathon, Milestone, RoleInvitation, Team, TeamMembership,
)

pytestmark = [pytest.mark.sprc1, pytest.mark.django_db]


def _event(**kwargs):
    now = timezone.now()
    defaults = dict(
        name="CrashTech VLSI 2027",
        starts_at=now + timezone.timedelta(days=30),
        ends_at=now + timezone.timedelta(days=31),
        submission_deadline=now + timezone.timedelta(days=31),
    )
    defaults.update(kwargs)
    return Hackathon.objects.create(**defaults)


def _user(email=None):
    email = email or f"p{User.objects.count()}@example.com"
    return User.objects.create_user(username=email.split("@")[0], email=email, password="crashtech-7781")


# ------------------------------------------------------------- the seal


def test_crashtech_imports_nothing_from_another_app():
    """Rule 2.1.1 and 2.1.2. Cross-app reach is rare, deliberate and
    named: two adapters are permitted, for the site's safety check and for
    outbound email, and each must live in exactly one file. Anything else
    is the boundary being crossed by accident."""
    ADAPTERS = {"moderation.py", "mail.py"}
    offenders = []
    for path in sorted(Path("crashtech").rglob("*.py")):
        if path.name in ADAPTERS:
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"\s*(from|import)\s+(app|matazim|memz|ustrip|sensorlab|exo|blackjack|improv)(\.|\s|$)", line):
                offenders.append(f"{path}:{line_no}: {line.strip()}")
    assert not offenders, "CrashTech reached into another app:\n  " + "\n  ".join(offenders)


def test_no_crashtech_page_links_out_of_crashtech(client):
    """Rule 2.2.3: babook links *in*; CrashTech links nowhere out. A
    Technion participant has no reason to learn that babook exists.

    Static, media and font hosts are not links out of the product.
    """
    allowed = ("/static/", "/media/", "https://fonts.googleapis.com", "https://fonts.gstatic.com")
    for path in ("/crashtech/", "/crashtech/login/", "/crashtech/signup/"):
        body = client.get(path).content.decode()
        for href in re.findall(r'href="([^"]+)"', body):
            if href.startswith(("#", "mailto:")) or href.startswith(allowed):
                continue
            assert href.startswith("/crashtech/"), f"{path} links out to {href}"


def test_crashtech_never_extends_babooks_base_template():
    """Rule 2.2.1: its own base, its own header, its own footer."""
    for path in Path("templates/crashtech").rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        assert '{% extends "base.html" %}' not in text, f"{path} extends babook's base"
        # `_name.html` is a partial, included rather than rendered, so it
        # extends nothing by design.
        if path.name != "base.html" and not path.name.startswith("_"):
            assert '{% extends "crashtech/base.html" %}' in text, f"{path} extends nothing of ours"


def test_the_interface_carries_no_hebrew_and_is_ltr():
    """Rule 2.2.4, checked on the template source.

    This is the weaker half of the pair. It cannot catch Hebrew that the
    framework produces rather than the template, which is exactly what
    happened: see the test below.
    """
    hebrew = re.compile(r"[֐-׿]")
    for path in list(Path("templates/crashtech").rglob("*")) + [Path("static/crashtech/crashtech.css")]:
        if path.is_dir():
            continue
        text = path.read_text(encoding="utf-8")
        assert not hebrew.search(text), f"{path} contains Hebrew"
    base = Path("templates/crashtech/base.html").read_text(encoding="utf-8")
    assert 'lang="en"' in base and 'dir="ltr"' in base


def test_no_rendered_page_contains_hebrew(client):
    """Rule 2.2.4, checked on what a reader actually receives.

    The source-only test above passed while every date on the event page
    rendered as "14 אוק 2026", because this project's
    LANGUAGE_CODE is Hebrew and Django localises month names. The template
    contained no Hebrew; the response did.

    A screenshot caught it, which is methodology entry 6 earning its keep
    on the first sprint: HTML-reading tests cannot see what the framework
    adds after the template is done with it.
    """
    event = _event(status=Hackathon.KITS)
    Milestone.objects.create(
        hackathon=event, kind=Milestone.HARDWARE, title="Kit pickup day",
        occurs_at=timezone.now(), order=1,
    )
    hebrew = re.compile(r"[֐-׿]")
    for path in ("/crashtech/", "/crashtech/login/", "/crashtech/signup/", f"/crashtech/e/{event.slug}/"):
        body = client.get(path).content.decode()
        found = hebrew.findall(body)
        assert not found, f"{path} rendered Hebrew: {''.join(found)[:40]}"


# ------------------------------------------------------------- it serves


@pytest.mark.parametrize("path", [
    "/crashtech/", "/crashtech/login/", "/crashtech/signup/",
    "/crashtech/password/reset/",
])
def test_every_public_page_serves(client, path):
    assert client.get(path).status_code == 200


def test_an_unknown_crashtech_url_is_a_404(client):
    assert client.get("/crashtech/nowhere-at-all/").status_code == 404


def test_the_home_page_needs_no_account(client):
    """Rule 9.2: reading never needs an account. Requiring one to find out
    what the event *is* loses the people who would have come."""
    body = client.get("/crashtech/").content.decode()
    assert "CrashTech" in body
    assert "Sign in" in body


# ---------------------------------------------------------------- models


def test_migrations_are_complete():
    from django.core.management import call_command

    call_command("makemigrations", "crashtech", "--check", "--dry-run")


def test_a_person_can_only_be_on_one_team_per_event():
    """Rule 5.3, and the reason `TeamMembership` exists at all. A plain
    many-to-many would permit this silently, and the result is two scores
    for one person and a leaderboard nobody can read."""
    from django.db import IntegrityError

    event = _event()
    person = _user()
    first = Team.objects.create(hackathon=event, name="Nova")
    second = Team.objects.create(hackathon=event, name="Supernova")
    TeamMembership.objects.create(team=first, user=person, hackathon=event)

    with pytest.raises(IntegrityError):
        TeamMembership.objects.create(team=second, user=person, hackathon=event)


def test_the_same_person_may_be_on_a_team_in_every_event():
    """The other half of Rule 5.3, and the reason the constraint is on
    (hackathon, user) rather than on user alone. Somebody who competes
    three years running has three teams."""
    person = _user()
    for year in (2027, 2028, 2029):
        event = _event(name=f"CrashTech {year}")
        team = Team.objects.create(hackathon=event, name=f"Nova {year}")
        TeamMembership.objects.create(team=team, user=person, hackathon=event)
    assert TeamMembership.objects.filter(user=person).count() == 3


def test_one_person_may_hold_several_roles_on_one_event():
    """Rule 4.1 and 4.4: tech lead and admin are separate jobs, not
    necessarily separate people, and on a small event usually one."""
    event, person = _event(), _user()
    EventRole.objects.create(hackathon=event, user=person, role=EventRole.TECH_LEAD)
    EventRole.objects.create(hackathon=event, user=person, role=EventRole.ADMIN)
    assert roles.roles_for(person, event) == {EventRole.TECH_LEAD, EventRole.ADMIN}


def test_a_challenge_without_a_required_deliverable_is_not_finished():
    """Rule 3.4: the readiness checklist needs to tell an unfinished
    challenge from a finished one, rather than letting them look the
    same."""
    event = _event()
    challenge = Challenge.objects.create(hackathon=event, title="FP8 adder")
    assert challenge.is_finished is False
    Deliverable.objects.create(challenge=challenge, label="Quartus project", required=True)
    assert challenge.is_finished is True


def test_a_video_deliverable_is_a_link_and_never_an_upload():
    """Rule 7.5. The single decision that turns roughly 26 GB of phone
    video per event into nothing at all."""
    event = _event()
    challenge = Challenge.objects.create(hackathon=event, title="Demo it")
    video = Deliverable.objects.create(challenge=challenge, label="Demo video", kind=Deliverable.VIDEO)
    zipped = Deliverable.objects.create(challenge=challenge, label="Project", kind=Deliverable.FILE)
    assert video.is_link_only is True
    assert zipped.is_link_only is False


# ----------------------------------------------------------- the lifecycle


def test_challenges_are_invisible_until_kickoff():
    """Rule 7.1: not a hint, not a count, not a greyed-out list."""
    event = _event()
    for status in (Hackathon.SETUP, Hackathon.PUBLISHED, Hackathon.KITS):
        event.status = status
        assert event.challenges_visible is False, status
    for status in (Hackathon.LIVE, Hackathon.CLOSED, Hackathon.MUSEUM):
        event.status = status
        assert event.challenges_visible is True, status


def test_judging_is_only_possible_once_the_event_has_closed():
    """Rule 8.1: grading live would score the first submission against a
    different field from the last."""
    event = _event()
    for status in Hackathon.STATUS_ORDER:
        event.status = status
        assert event.accepts_judging is (status == Hackathon.CLOSED), status


def test_submissions_close_at_the_deadline_even_while_the_event_runs():
    """Rule 7.7: the deadline may fall before the event itself ends."""
    event = _event(status=Hackathon.LIVE)
    assert event.accepts_submissions is True
    event.submission_deadline = timezone.now() - timezone.timedelta(minutes=1)
    assert event.accepts_submissions is False


# ------------------------------------------------------------ permissions


def test_the_permission_matrix_matches_the_spec():
    """Rule 4.4, asserted row by row against the table in the spec rather
    than against whatever the code happens to say."""
    event = _event()
    holders = {}
    for role, _label in EventRole.ROLES:
        person = _user(f"{role}@example.com")
        EventRole.objects.create(hackathon=event, user=person, role=role)
        holders[role] = person

    expected = {
        "event_settings": {EventRole.ADMIN},
        "grant_roles": {EventRole.ADMIN},
        "define_kit": {EventRole.TECH_LEAD},
        "distribute_kits": {EventRole.ADMIN},
        "decide_registrations": {EventRole.ADMIN},
        "author_challenges": {EventRole.TECH_LEAD},
        "read_secret_challenges": {EventRole.TECH_LEAD, EventRole.ADMIN, EventRole.JUDGE},
        "submit": {EventRole.PARTICIPANT},
        "judge": {EventRole.JUDGE},
        # Added in C.5. Reading judging is not judging: an admin has to be
        # able to see whether grading is progressing, because their publish
        # button is waiting on it and the publish screen links them at it.
        "read_judging": {EventRole.JUDGE, EventRole.ADMIN},
        "advance_lifecycle": {EventRole.ADMIN},
        "manage_study": {EventRole.RESEARCHER},
        "read_research_data": {EventRole.RESEARCHER},
    }
    assert set(expected) == set(roles.MATRIX), "the matrix gained or lost a capability"

    for capability, allowed in expected.items():
        for role, person in holders.items():
            got = roles.can(person, event, capability)
            assert got is (role in allowed), f"{role} / {capability}: got {got}"


def test_a_participant_cannot_see_a_secret_challenge_but_a_judge_can():
    """Rule 4.5 against Rule 7.1, which is the pair most easily got wrong.
    A judge is not a participant and the secrecy rule is not about them."""
    event = _event()
    judge, participant = _user("j@example.com"), _user("c@example.com")
    EventRole.objects.create(hackathon=event, user=judge, role=EventRole.JUDGE)
    EventRole.objects.create(hackathon=event, user=participant, role=EventRole.PARTICIPANT)

    assert roles.may_see_challenges(judge, event) is True
    assert roles.may_see_challenges(participant, event) is False

    event.status = Hackathon.LIVE
    assert roles.may_see_challenges(participant, event) is True


def test_a_signed_out_visitor_holds_no_role_and_sees_no_secret():
    event = _event()
    from django.contrib.auth.models import AnonymousUser

    anon = AnonymousUser()
    assert roles.roles_for(anon, event) == set()
    assert roles.may_see_challenges(anon, event) is False


def test_standings_are_gated_but_published_results_are_public():
    """Rule 8.4. Note what this does *not* test: a team's own score, which
    is a different question and is never gated."""
    event = _event()
    participant = _user("p@example.com")
    EventRole.objects.create(hackathon=event, user=participant, role=EventRole.PARTICIPANT)
    admin = _user("a@example.com")
    EventRole.objects.create(hackathon=event, user=admin, role=EventRole.ADMIN)

    assert roles.may_see_standings(participant, event) is False
    assert roles.may_see_standings(admin, event) is True

    event.leaderboard_visibility = Hackathon.PARTICIPANTS
    assert roles.may_see_standings(participant, event) is True

    event.leaderboard_visibility = Hackathon.ADMINS_ONLY
    event.results_published_at = timezone.now()
    assert roles.may_see_standings(participant, event) is True


def test_a_superuser_is_an_admin_everywhere_and_that_is_deliberate():
    """Rule 4.2: the only way the first admin of an event can exist, and
    the reason locking the site owner out of their own app helps nobody.
    A named exception rather than an accident of the code."""
    event = _event()
    root = User.objects.create_superuser("root", "root@example.com", "crashtech-7781")
    assert roles.can(root, event, "grant_roles") is True


# ------------------------------------------------------------ invitations


def test_a_role_can_be_granted_to_an_email_with_no_account_yet(client):
    """Rule 4.3, and the whole point of `RoleInvitation`. The tech lead and
    the judges are busy outsiders; waiting for them to create an account
    before they can be appointed loses them."""
    event = _event()
    inviter = _user("admin@example.com")
    invitation = RoleInvitation.objects.create(
        hackathon=event, email="judge@technion.ac.il", role=EventRole.JUDGE, invited_by=inviter,
    )
    assert invitation.is_pending is True
    assert not User.objects.filter(email="judge@technion.ac.il").exists()

    response = client.post("/crashtech/signup/", {
        "email": "judge@technion.ac.il", "password": "crashtech-7781",
    })
    assert response.status_code == 302

    judge = User.objects.get(email="judge@technion.ac.il")
    assert roles.roles_for(judge, event) == {EventRole.JUDGE}

    invitation.refresh_from_db()
    assert invitation.is_pending is False
    assert invitation.accepted_user == judge


def test_redeeming_twice_does_not_duplicate_the_role():
    event = _event()
    RoleInvitation.objects.create(hackathon=event, email="x@example.com", role=EventRole.JUDGE)
    person = _user("x@example.com")
    redeem_for(person)
    redeem_for(person)
    assert EventRole.objects.filter(hackathon=event, user=person).count() == 1


def test_an_invitation_for_a_different_email_is_not_redeemed():
    event = _event()
    RoleInvitation.objects.create(hackathon=event, email="someone@example.com", role=EventRole.ADMIN)
    other = _user("other@example.com")
    assert redeem_for(other) == []
    assert roles.roles_for(other, event) == set()


# ------------------------------------------------------------------- auth


def test_signup_works_immediately_with_no_verification_mail(client, mailoutbox):
    response = client.post("/crashtech/signup/", {
        "email": "New.Person@Example.com", "password": "crashtech-7781",
    })
    assert response.status_code == 302
    user = User.objects.get(email="new.person@example.com")
    assert user.is_active
    assert len(mailoutbox) == 0


def test_signup_refuses_an_email_that_already_has_an_account(client):
    _user("taken@example.com")
    response = client.post("/crashtech/signup/", {
        "email": "taken@example.com", "password": "crashtech-7781",
    })
    assert response.status_code == 200
    assert "already" in response.content.decode().lower()
    assert User.objects.filter(email="taken@example.com").count() == 1


def test_signup_refuses_a_short_password(client):
    response = client.post("/crashtech/signup/", {"email": "a@example.com", "password": "short"})
    assert response.status_code == 200
    assert not User.objects.filter(email="a@example.com").exists()


def test_a_wrong_password_stays_on_crashtechs_own_login(client):
    _user("real@example.com")
    response = client.post("/crashtech/login/", {
        "username": "real@example.com", "password": "not-the-password",
    })
    assert response.status_code == 200
    assert response.request["PATH_INFO"] == "/crashtech/login/"


def test_signing_out_is_post_only(client):
    _user("out@example.com")
    client.login(username="out", password="crashtech-7781")
    assert client.get("/crashtech/logout/").status_code == 405
    assert client.post("/crashtech/logout/").status_code == 302


def test_the_password_reset_mail_links_back_inside_crashtech(client, mailoutbox):
    _user("reset@example.com")
    client.post("/crashtech/password/reset/", {"email": "reset@example.com"})
    assert len(mailoutbox) == 1
    body = mailoutbox[0].body
    assert "/crashtech/password/reset/" in body
    assert "babook" not in body.lower()


# ------------------------------------------------------------- event home


def test_the_event_home_names_the_current_milestone(client):
    """Rule 11.4: the current milestone is on screen on every page for
    every role. It is the one piece of context that changes what
    everything else means."""
    event = _event(status=Hackathon.KITS)
    body = client.get(f"/crashtech/e/{event.slug}/").content.decode()
    assert event.name in body
    assert "Kit distribution" in body


def test_the_event_home_tells_a_person_which_roles_they_hold(client):
    event = _event()
    person = _user("role@example.com")
    EventRole.objects.create(hackathon=event, user=person, role=EventRole.TECH_LEAD)
    client.force_login(person)
    body = client.get(f"/crashtech/e/{event.slug}/").content.decode()
    assert "Tech lead" in body


# -------------------------------------------------------------- the seed


def test_the_demo_seed_is_a_one_time_import(capsys):
    """building_an_app.md, "Data": a seed that imports from a static source
    is a one-time import, never a sync.

    This runs the **actual management command twice**, rather than a
    fixture standing in for it, because that is the only kind of test that
    catches "the seed deletes things it should not". On ustrip a seed wired
    into every deploy wholesale recreated its rows, which would have
    destroyed a real person's edits the first time the app let anybody make
    one.
    """
    from django.core.management import call_command

    from crashtech.models import ContentPage, Hackathon, KitItem, Milestone

    call_command("seed_crashtech")
    event = Hackathon.objects.get(slug="demo-vlsi")
    counts = (event.milestones.count(), event.kit_items.count(), event.pages.count())
    assert all(counts), counts

    # Something a person could plausibly have changed afterwards.
    event.tagline = "Edited by a human"
    event.save(update_fields=["tagline"])
    Milestone.objects.filter(hackathon=event).first().delete()
    edited_counts = (event.milestones.count(), event.kit_items.count(), event.pages.count())

    call_command("seed_crashtech")

    event.refresh_from_db()
    assert event.tagline == "Edited by a human", "the second run overwrote an edit"
    assert (event.milestones.count(), event.kit_items.count(), event.pages.count()) == edited_counts
    assert Hackathon.objects.filter(slug="demo-vlsi").count() == 1


def test_the_demo_event_is_obviously_a_demo():
    """It goes to production, where real people will see it. Nobody should
    have to guess whether it is a real hackathon they can enter."""
    from django.core.management import call_command

    from crashtech.models import Hackathon

    call_command("seed_crashtech")
    assert "DEMO" in Hackathon.objects.get(slug="demo-vlsi").name
