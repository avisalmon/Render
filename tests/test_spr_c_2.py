"""SPR-C.2 — CrashTech: the event, its lifecycle and its roles.

The chain an admin walks before anybody else can do anything: create an
event, shape it, put the milestones down, appoint the people, and move it
forward.

Two things here carry most of the weight. **The readiness checklist**,
because going live reveals every challenge at once and cannot be undone,
so the thing that decides whether it may happen has to be right. And
**invitation by email**, because it is the one mechanism standing between
an admin and the busy outsiders they need to appoint.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from crashtech import readiness
from crashtech.models import (
    Challenge, Deliverable, EventRole, Hackathon, KitItem, Milestone,
    Registration, RoleInvitation, Team,
)
from crashtech.next_actions import next_actions_for

pytestmark = [pytest.mark.sprc2, pytest.mark.django_db]


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


def _user(email, superuser=False):
    maker = User.objects.create_superuser if superuser else User.objects.create_user
    return maker(username=email.split("@")[0], email=email, password="crashtech-7781")


def _with_role(event, email, role):
    user = _user(email)
    EventRole.objects.create(hackathon=event, user=user, role=role)
    return user


def _ready_to_go_live(event):
    """Everything the checklist asks for before `live`, so a test can turn
    one thing off at a time and see the refusal."""
    event.status = Hackathon.KITS
    event.save(update_fields=["status"])
    challenge = Challenge.objects.create(hackathon=event, title="FP8 adder")
    Deliverable.objects.create(challenge=challenge, label="Quartus project", required=True)
    _with_role(event, "judge@example.com", EventRole.JUDGE)
    Milestone.objects.create(
        hackathon=event, kind=Milestone.KICKOFF, title="Kickoff",
        occurs_at=event.starts_at, order=0,
    )
    return event


# ------------------------------------------------------- creating an event


def test_a_superuser_creates_an_event_and_becomes_its_first_admin(client):
    """Rule 4.2: the only place the chain can start, because no admin
    exists yet to appoint one."""
    root = _user("root@example.com", superuser=True)
    client.force_login(root)
    response = client.post("/crashtech/create/", {
        "name": "CrashTech VLSI 2028",
        "starts_at": "2028-06-01T09:00",
        "ends_at": "2028-06-02T09:00",
    })
    assert response.status_code == 302
    event = Hackathon.objects.get(name="CrashTech VLSI 2028")
    assert EventRole.objects.filter(hackathon=event, user=root, role=EventRole.ADMIN).exists()


def test_an_ordinary_person_cannot_create_an_event(client):
    client.force_login(_user("nobody@example.com"))
    assert client.get("/crashtech/create/").status_code == 403
    assert client.post("/crashtech/create/", {
        "name": "Mine", "starts_at": "2028-06-01T09:00", "ends_at": "2028-06-02T09:00",
    }).status_code == 403
    assert Hackathon.objects.count() == 0


def test_an_event_cannot_end_before_it_starts(client):
    client.force_login(_user("root@example.com", superuser=True))
    response = client.post("/crashtech/create/", {
        "name": "Backwards", "starts_at": "2028-06-02T09:00", "ends_at": "2028-06-01T09:00",
    })
    assert response.status_code == 200
    assert Hackathon.objects.count() == 0


# ----------------------------------------------------------------- people


def test_granting_a_role_to_somebody_who_already_has_an_account(client):
    event = _event()
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    _user("known@example.com")
    client.force_login(admin)

    client.post(f"/crashtech/e/{event.slug}/people/", {
        "email": "known@example.com", "role": EventRole.JUDGE,
    })
    assert EventRole.objects.filter(hackathon=event, role=EventRole.JUDGE).count() == 1
    assert not RoleInvitation.objects.exists()


def test_inviting_somebody_who_has_no_account_yet_sends_a_link(client, mailoutbox):
    """Rule 4.3, the mechanism the admin's whole first hour depends on.

    From the admin's side this is the same action as the test above: they
    should not have to know or care whether this judge already has an
    account here.
    """
    event = _event()
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)

    client.post(f"/crashtech/e/{event.slug}/people/", {
        "email": "stranger@technion.ac.il", "role": EventRole.TECH_LEAD,
    })

    invitation = RoleInvitation.objects.get(email="stranger@technion.ac.il")
    assert invitation.is_pending
    assert invitation.sent_at is not None
    assert len(mailoutbox) == 1

    # Rule 12.3: an international audience, and somebody who competes three
    # years running has three events. The mail has to say which.
    assert event.name in mailoutbox[0].subject
    assert invitation.token in mailoutbox[0].body


def test_the_people_screen_shows_invited_but_not_joined(client):
    """The state that actually matters two days before an event when a
    judge has not turned up."""
    event = _event()
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    RoleInvitation.objects.create(hackathon=event, email="late@example.com", role=EventRole.JUDGE)
    client.force_login(admin)
    body = client.get(f"/crashtech/e/{event.slug}/people/").content.decode()
    assert "late@example.com" in body
    assert "Invited, not joined" in body


def test_the_invitation_link_grants_the_role_to_a_signed_in_match(client):
    event = _event()
    invitation = RoleInvitation.objects.create(
        hackathon=event, email="judge@example.com", role=EventRole.JUDGE,
    )
    judge = _user("judge@example.com")
    client.force_login(judge)

    response = client.get(f"/crashtech/invite/{invitation.token}/")
    assert response.status_code == 302
    assert EventRole.objects.filter(hackathon=event, user=judge, role=EventRole.JUDGE).exists()


def test_only_an_admin_may_open_the_people_screen(client):
    event = _event()
    for role in (EventRole.TECH_LEAD, EventRole.JUDGE, EventRole.PARTICIPANT, EventRole.RESEARCHER):
        person = _with_role(event, f"{role}@example.com", role)
        client.force_login(person)
        assert client.get(f"/crashtech/e/{event.slug}/people/").status_code == 403, role


def test_removing_a_role_leaves_the_person_and_their_other_roles(client):
    """One person may hold several (Rule 4.1), so removing one must not be
    read as removing them."""
    event = _event()
    admin = _with_role(event, "both@example.com", EventRole.ADMIN)
    lead_role = EventRole.objects.create(hackathon=event, user=admin, role=EventRole.TECH_LEAD)
    client.force_login(admin)

    client.post(f"/crashtech/e/{event.slug}/people/", {"remove_role": lead_role.pk})
    assert EventRole.objects.filter(hackathon=event, user=admin, role=EventRole.ADMIN).exists()
    assert not EventRole.objects.filter(pk=lead_role.pk).exists()
    assert User.objects.filter(pk=admin.pk).exists()


# ------------------------------------------------------------- readiness


def test_going_live_is_blocked_until_every_challenge_says_what_to_submit():
    """Rule 3.4, and the specific blocker that matters most: a challenge
    with no required deliverable cannot tell a team what is missing, which
    is the whole point of declaring them."""
    event = _ready_to_go_live(_event())
    assert readiness.can_advance(event) is True

    naked = Challenge.objects.create(hackathon=event, title="Make the room laugh")
    blockers = readiness.blockers_for(event)
    assert readiness.can_advance(event) is False
    assert any("Make the room laugh" in b.text for b in blockers)

    Deliverable.objects.create(challenge=naked, label="Demo video", required=True)
    assert readiness.can_advance(event) is True


def test_going_live_is_blocked_with_no_challenges_and_with_no_judges():
    event = _event(status=Hackathon.KITS)
    assert any("No challenges" in c.text for c in readiness.blockers_for(event))

    challenge = Challenge.objects.create(hackathon=event, title="Alive test")
    Deliverable.objects.create(challenge=challenge, label="Video", required=True)
    # No judges: a blocker rather than a warning, because creativity
    # challenges score only on a judge's grade, so the event could not
    # produce a result at all.
    assert any("judges" in c.text.lower() for c in readiness.blockers_for(event))


def test_uncollected_kits_are_a_warning_and_never_a_blocker():
    """A team that never turns up for a kit is probably not coming, and
    refusing to start the event for them punishes everybody who did."""
    event = _ready_to_go_live(_event())
    Team.objects.create(hackathon=event, name="Nova")
    checks = list(readiness.checks_for(event))
    kit_checks = [c for c in checks if "kit" in c.text.lower()]
    assert kit_checks
    assert all(not c.is_blocker for c in kit_checks)
    assert readiness.can_advance(event) is True


def test_milestones_out_of_order_block_the_advance():
    event = _ready_to_go_live(_event())
    Milestone.objects.create(
        hackathon=event, kind=Milestone.CLOSE, title="Close",
        occurs_at=event.starts_at - timezone.timedelta(days=5), order=1,
    )
    assert any("out of order" in b.text for b in readiness.blockers_for(event))


def test_readiness_is_computed_and_never_stored():
    """Rule 3.5. A stored flag would go stale the moment somebody deletes a
    challenge, which is exactly what this does."""
    event = _ready_to_go_live(_event())
    assert readiness.can_advance(event) is True
    event.challenges.all().delete()
    assert readiness.can_advance(event) is False


# ------------------------------------------------------------- advancing


def test_going_live_reveals_every_challenge_at_once(client):
    """Rule 3.2, the irreversible one."""
    event = _ready_to_go_live(_event())
    hidden = Challenge.objects.create(hackathon=event, title="Secret")
    Deliverable.objects.create(challenge=hidden, label="Video", required=True)
    assert not event.challenges.filter(visible=True).exists()

    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)
    response = client.post(f"/crashtech/e/{event.slug}/advance/")

    assert response.status_code == 302
    event.refresh_from_db()
    assert event.status == Hackathon.LIVE
    assert event.challenges.filter(visible=True).count() == event.challenges.count()


def test_the_advance_is_refused_server_side_even_from_a_stale_tab(client):
    """The checklist hiding the control is a courtesy, not a boundary. A
    tab left open from before somebody deleted a challenge must not be
    enough to open an event half-written."""
    event = _ready_to_go_live(_event())
    Challenge.objects.create(hackathon=event, title="No deliverables")

    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)
    client.post(f"/crashtech/e/{event.slug}/advance/")

    event.refresh_from_db()
    assert event.status == Hackathon.KITS


def test_only_an_admin_may_advance_the_lifecycle(client):
    event = _ready_to_go_live(_event())
    lead = _with_role(event, "lead@example.com", EventRole.TECH_LEAD)
    client.force_login(lead)
    assert client.post(f"/crashtech/e/{event.slug}/advance/").status_code == 403
    event.refresh_from_db()
    assert event.status == Hackathon.KITS


def test_the_readiness_screen_states_the_consequence_in_words(client):
    """Rule 11.7: irreversible actions say what they will do, not "are you
    sure"."""
    event = _ready_to_go_live(_event())
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)
    body = client.get(f"/crashtech/e/{event.slug}/readiness/").content.decode()
    assert "cannot be undone" in body
    assert "every challenge" in body.lower()


def test_publishing_stamps_the_time_the_results_became_public():
    event = _event(status=Hackathon.CLOSED)
    assert event.results_published_at is None
    assert event.next_status == Hackathon.MUSEUM


# ---------------------------------------------------------- next actions


def test_each_role_is_told_something_different_on_the_same_event():
    """Rule 11.3: five roles share an event and almost nothing they do
    overlaps, so a single generic page would make each of them hunt."""
    event = _ready_to_go_live(_event())
    people = {
        role: _with_role(event, f"{role}-na@example.com", role)
        for role, _label in EventRole.ROLES
    }
    texts = {}
    for role, person in people.items():
        actions = next_actions_for(person, event)
        texts[role] = " ".join(a.text for _label, items in actions for a, _u in items)
        assert texts[role], f"{role} was told nothing at all"

    assert len({t for t in texts.values()}) == len(texts), "two roles were told the same thing"


def test_a_judge_is_told_they_have_nothing_to_do_during_the_event():
    """Rule 8.1 said out loud. A judge with an empty screen and no
    explanation assumes something is broken."""
    event = _ready_to_go_live(_event())
    event.status = Hackathon.LIVE
    event.save(update_fields=["status"])
    judge = _with_role(event, "j2@example.com", EventRole.JUDGE)

    actions = next_actions_for(judge, event)
    text = " ".join(a.text for _l, items in actions for a, _u in items)
    assert "nothing to judge" in text.lower()


def test_somebody_holding_two_roles_sees_both_jobs_separately():
    """On a small event one person is often tech lead and admin, and they
    still need to see which hat each item belongs to."""
    event = _ready_to_go_live(_event())
    person = _with_role(event, "two@example.com", EventRole.ADMIN)
    EventRole.objects.create(hackathon=event, user=person, role=EventRole.TECH_LEAD)

    labels = [label for label, _items in next_actions_for(person, event)]
    assert "Admin" in labels and "Tech lead" in labels


def test_an_action_for_a_screen_that_does_not_exist_yet_still_says_its_piece():
    """Sprints C.3 to C.7 build the screens these point at. Until then the
    sentence is worth showing and the link is not, so an unbuilt route
    degrades to text rather than a NoReverseMatch in somebody's face."""
    event = _event(status=Hackathon.PUBLISHED)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    Registration.objects.create(hackathon=event, user=_user("applicant@example.com"))

    actions = next_actions_for(admin, event)
    pairs = [(a, u) for _l, items in actions for a, u in items]
    assert any("waiting on you" in a.text for a, _u in pairs)
    assert all(u == "" or u.startswith("/crashtech/") for _a, u in pairs)


def test_the_event_home_renders_for_every_role(client):
    event = _ready_to_go_live(_event())
    KitItem.objects.create(hackathon=event, name="DE10-Lite", quantity_total=30)
    for role, _label in EventRole.ROLES:
        person = _with_role(event, f"{role}-home@example.com", role)
        client.force_login(person)
        response = client.get(f"/crashtech/e/{event.slug}/")
        assert response.status_code == 200, role


# -------------------------------------------------------------- settings


def test_settings_say_what_each_choice_does(client):
    """Rule 11.5: "team size" means nothing on its own. "1 makes this an
    individual event" is what an organiser needs at the moment they are
    deciding."""
    event = _event()
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)
    body = client.get(f"/crashtech/e/{event.slug}/settings/").content.decode()
    assert "individual event" in body
    assert "own score" in body
    assert "Challenges never do" in body


def test_saving_settings_keeps_team_size_at_least_one(client):
    event = _event()
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)
    client.post(f"/crashtech/e/{event.slug}/settings/", {
        "name": event.name, "team_size_max": "0", "kits_per_team": "0",
        "leaderboard_visibility": Hackathon.ADMINS_ONLY,
    })
    event.refresh_from_db()
    assert event.team_size_max == 1
    assert event.kits_per_team == 1


def test_a_milestone_can_be_added_and_removed(client):
    event = _event()
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)

    client.post(f"/crashtech/e/{event.slug}/milestones/", {
        "title": "Kit pickup day", "kind": Milestone.HARDWARE,
        "occurs_at": "2027-05-20T10:00", "blurb": "Bring a bag.",
    })
    milestone = event.milestones.get()
    assert milestone.title == "Kit pickup day"

    client.post(f"/crashtech/e/{event.slug}/milestones/", {"delete": milestone.pk})
    assert event.milestones.count() == 0


def test_no_c2_screen_renders_hebrew(client):
    """Rule 2.2.4 again, on the rendered response, because that is where
    C.1 found it the first time."""
    import re

    event = _ready_to_go_live(_event())
    Milestone.objects.create(
        hackathon=event, kind=Milestone.HARDWARE, title="Kit day",
        occurs_at=timezone.now(), order=2,
    )
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)
    hebrew = re.compile(r"[֐-׿]")
    for path in ("", "settings/", "milestones/", "people/", "readiness/"):
        body = client.get(f"/crashtech/e/{event.slug}/{path}").content.decode()
        assert not hebrew.search(body), f"/{path} rendered Hebrew"


def test_the_checklist_does_not_say_one_judges(client):
    """"1 judges assigned" is the kind of thing that makes a product feel
    unfinished, and it is one line to not do. Caught by a screenshot."""
    event = _ready_to_go_live(_event())
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)
    body = client.get(f"/crashtech/e/{event.slug}/readiness/").content.decode()
    assert "1 judge assigned" in body
    assert "1 judges" not in body
    assert "1 challenges" not in body


def test_every_event_screen_keeps_its_navigation(client):
    """The nav is built from `can_manage`, and a view that forgets to pass
    it silently collapses the whole menu to one item. Also caught by a
    screenshot rather than by any assertion."""
    event = _event()
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)
    for path in ("", "settings/", "milestones/", "people/", "readiness/"):
        body = client.get(f"/crashtech/e/{event.slug}/{path}").content.decode()
        for item in ("People", "Timeline", "Settings", "Readiness"):
            assert f">{item}<" in body, f"/{path} lost {item} from the nav"


def test_a_signed_out_visitor_is_sent_to_crashtechs_own_login(client):
    """Rule 2.2.2, and a real seal break that reached production.

    Django's `login_required` redirects to the project-wide `LOGIN_URL`,
    which on this site is babook's allauth page. So a visitor halfway
    through a CrashTech flow landed on another product's branded sign-in,
    which is the one thing this app having its own front door exists to
    prevent.

    Every permission test used `force_login` and therefore never walked
    the signed-out path, which is why nothing caught it. memz made the
    same mistake once before.
    """
    event = _event()
    protected = [
        "/crashtech/create/",
        f"/crashtech/e/{event.slug}/settings/",
        f"/crashtech/e/{event.slug}/milestones/",
        f"/crashtech/e/{event.slug}/people/",
        f"/crashtech/e/{event.slug}/readiness/",
    ]
    for path in protected:
        response = client.get(path)
        assert response.status_code == 302, path
        # Assert the destination, not a substring: "/login/" alone would
        # pass happily on "/accounts/login/", which is the bug.
        assert response["Location"].startswith("/crashtech/login/"), (
            f"{path} redirected out of CrashTech to {response['Location']}"
        )
        assert path in response["Location"], f"{path} lost its next= on the way"
