"""SPR-C.3 — CrashTech: registration, teams, hardware.

Applying and being accepted, forming a team inside the rules, defining
what the kit is, and handing it out at a desk with a queue in front of it.

The two things carrying most of the weight: **the team rules**, because
one person on two teams means two scores and an unreadable leaderboard,
and **the kit desk**, because it is the only screen in the product with a
hard time budget and the only one that loses to a paper list if it misses.
"""

import re

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from crashtech import kit, teams
from crashtech.models import (
    EventRole, Hackathon, KitIssue, KitItem, Registration, Team, TeamMembership,
)

pytestmark = [pytest.mark.sprc3, pytest.mark.django_db]


def _event(**kwargs):
    now = timezone.now()
    defaults = dict(
        name="CrashTech VLSI 2027", status=Hackathon.PUBLISHED,
        starts_at=now + timezone.timedelta(days=30),
        ends_at=now + timezone.timedelta(days=31),
        submission_deadline=now + timezone.timedelta(days=31),
    )
    defaults.update(kwargs)
    return Hackathon.objects.create(**defaults)


def _user(email):
    return User.objects.create_user(username=email.split("@")[0], email=email, password="crashtech-7781")


def _with_role(event, email, role):
    user = _user(email)
    EventRole.objects.create(hackathon=event, user=user, role=role)
    return user


def _accepted(event, email):
    """Somebody the admin has let in, which is what team formation needs."""
    user = _with_role(event, email, EventRole.PARTICIPANT)
    Registration.objects.create(hackathon=event, user=user, status=Registration.ACCEPTED)
    return user


# ------------------------------------------------------------ registering


def test_applying_creates_a_record_separate_from_the_role(client):
    """Rule 5.1: people apply, they are not invited, and the application
    survives independently of the role it may later grant."""
    event = _event()
    person = _user("hopeful@example.com")
    client.force_login(person)

    client.post(f"/crashtech/e/{event.slug}/apply/", {"name": "Hopeful Person"})
    registration = Registration.objects.get(hackathon=event, user=person)
    assert registration.status == Registration.APPLIED
    assert not EventRole.objects.filter(hackathon=event, user=person).exists()


def test_accepting_an_application_is_what_grants_the_participant_role(client):
    event = _event()
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    person = _user("hopeful@example.com")
    registration = Registration.objects.create(hackathon=event, user=person)

    client.force_login(admin)
    client.post(f"/crashtech/e/{event.slug}/registrations/", {
        "registration": registration.pk, "decision": Registration.ACCEPTED,
    })

    registration.refresh_from_db()
    assert registration.status == Registration.ACCEPTED
    assert registration.decided_by == admin
    assert EventRole.objects.filter(
        hackathon=event, user=person, role=EventRole.PARTICIPANT,
    ).exists()


def test_declining_takes_the_role_away_and_keeps_the_record(client):
    event = _event()
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    person = _accepted(event, "changed@example.com")
    registration = Registration.objects.get(user=person)

    client.force_login(admin)
    client.post(f"/crashtech/e/{event.slug}/registrations/", {
        "registration": registration.pk, "decision": Registration.DECLINED,
    })

    assert not EventRole.objects.filter(hackathon=event, user=person).exists()
    registration.refresh_from_db()
    assert registration.status == Registration.DECLINED


def test_applying_twice_does_not_make_two_records(client):
    event = _event()
    person = _user("eager@example.com")
    client.force_login(person)
    client.post(f"/crashtech/e/{event.slug}/apply/", {"name": "Hopeful Person"})
    client.post(f"/crashtech/e/{event.slug}/apply/", {"name": "Hopeful Person"})
    assert Registration.objects.filter(hackathon=event, user=person).count() == 1


def test_applications_are_refused_once_the_event_is_live(client):
    event = _event(status=Hackathon.LIVE)
    person = _user("late@example.com")
    client.force_login(person)
    client.post(f"/crashtech/e/{event.slug}/apply/", {"name": "Hopeful Person"})
    assert not Registration.objects.filter(hackathon=event).exists()


def test_only_an_admin_may_decide_applications(client):
    event = _event()
    for role in (EventRole.TECH_LEAD, EventRole.JUDGE, EventRole.PARTICIPANT):
        person = _with_role(event, f"{role}@example.com", role)
        client.force_login(person)
        assert client.get(f"/crashtech/e/{event.slug}/registrations/").status_code == 403, role


# ----------------------------------------------------------------- teams


def test_a_person_cannot_be_on_two_teams_in_the_same_event():
    """Rule 5.3. Two teams for one person means two scores, two kits, and
    a leaderboard nobody can read. Refused with a sentence here, and by a
    database constraint underneath."""
    event = _event(team_size_max=3)
    person = _accepted(event, "both@example.com")
    teams.create_team(person, event, "Nova")

    with pytest.raises(teams.TeamError) as caught:
        teams.create_team(person, event, "Supernova")
    assert "already on a team" in str(caught.value)
    assert TeamMembership.objects.filter(hackathon=event, user=person).count() == 1


def test_the_same_person_may_have_a_team_in_every_event():
    """The other half of Rule 5.3, and why the constraint is on
    (hackathon, user)."""
    person = _user("regular@example.com")
    for year in (2027, 2028, 2029):
        event = _event(name=f"CrashTech {year}")
        Registration.objects.create(hackathon=event, user=person, status=Registration.ACCEPTED)
        teams.create_team(person, event, f"Nova {year}")
    assert TeamMembership.objects.filter(user=person).count() == 3


def test_a_team_fills_up_at_the_size_the_admin_set():
    event = _event(team_size_max=2)
    first = _accepted(event, "a@example.com")
    team = teams.create_team(first, event, "Nova")
    teams.join_team(_accepted(event, "b@example.com"), event, team)

    with pytest.raises(teams.TeamError) as caught:
        teams.join_team(_accepted(event, "c@example.com"), event, team)
    assert "full" in str(caught.value)
    assert "up to 2" in str(caught.value)


def test_an_individual_event_offers_no_team_to_join():
    """`team_size_max == 1` makes the event individual, and the screen
    should not show a list of teams that are all full by definition."""
    event = _event(team_size_max=1)
    person = _accepted(event, "solo@example.com")
    teams.create_team(person, event, "Solo")
    assert list(teams.joinable_teams(event)) == []


def test_somebody_not_accepted_cannot_form_a_team():
    event = _event()
    outsider = _user("outside@example.com")
    with pytest.raises(teams.TeamError) as caught:
        teams.create_team(outsider, event, "Gatecrash")
    assert "accepted" in str(caught.value)


def test_any_member_may_leave_because_there_is_no_captain():
    """Rule 5.4. The person who created the team has no special standing,
    and leaving needs nothing handed over."""
    event = _event(team_size_max=2)
    founder = _accepted(event, "founder@example.com")
    team = teams.create_team(founder, event, "Nova")
    joiner = _accepted(event, "joiner@example.com")
    teams.join_team(joiner, event, team)

    teams.leave_team(founder, event)
    assert Team.objects.filter(pk=team.pk).exists()
    assert [m.user for m in team.memberships.all()] == [joiner]


def test_the_last_person_leaving_takes_the_empty_team_with_them():
    """A name nobody holds blocks the next person who wants it, and an
    empty team on the kit desk is a kit allocated to nobody."""
    event = _event()
    person = _accepted(event, "only@example.com")
    team = teams.create_team(person, event, "Nova")
    teams.leave_team(person, event)
    assert not Team.objects.filter(pk=team.pk).exists()


def test_a_team_holding_a_kit_cannot_be_dissolved_by_walking_away():
    """Otherwise the board is unaccounted for and nobody knows who has
    it."""
    event = _event()
    person = _accepted(event, "holder@example.com")
    team = teams.create_team(person, event, "Nova")
    kit.give_kit(team, person, person)

    with pytest.raises(teams.TeamError) as caught:
        teams.leave_team(person, event)
    assert "give it back" in str(caught.value).lower()


def test_the_teams_screen_states_the_size_limit_as_a_fact(client):
    """user_journeys.md 2.3: shown as a fact, not discovered as an error
    on submit."""
    event = _event(team_size_max=3)
    person = _accepted(event, "reader@example.com")
    client.force_login(person)
    body = client.get(f"/crashtech/e/{event.slug}/teams/").content.decode()
    assert "up to 3" in body
    assert "no captain" in body.lower()


# ------------------------------------------------------------------- kit


def test_the_kit_is_a_list_an_organiser_edits(client):
    """Rule 6.1: FPGA and ESP32 today, a Raspberry Pi next time, with no
    code change. The 2026 platform had one integer and could express none
    of this."""
    event = _event()
    lead = _with_role(event, "lead@example.com", EventRole.TECH_LEAD)
    client.force_login(lead)

    client.post(f"/crashtech/e/{event.slug}/kit/", {
        "name": "Raspberry Pi 5", "description": "8 GB.",
        "quantity_total": "24", "is_returnable": "on",
    })
    item = KitItem.objects.get(hackathon=event)
    assert item.name == "Raspberry Pi 5"
    assert item.quantity_total == 24
    assert item.is_returnable is True


def test_only_the_tech_lead_defines_the_kit_and_only_the_admin_hands_it_out(client):
    """Rule 4.4: two different jobs, and the split is the main structural
    change from 2026."""
    event = _event()
    lead = _with_role(event, "lead@example.com", EventRole.TECH_LEAD)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)

    client.force_login(lead)
    assert client.get(f"/crashtech/e/{event.slug}/kit/").status_code == 200
    assert client.get(f"/crashtech/e/{event.slug}/kit-desk/").status_code == 403

    client.force_login(admin)
    assert client.get(f"/crashtech/e/{event.slug}/kit/").status_code == 403
    assert client.get(f"/crashtech/e/{event.slug}/kit-desk/").status_code == 200


def test_a_kit_goes_to_a_team_and_records_which_member_fetched_it():
    """Rule 6.2 and 6.3 together: allocation and collection are different
    facts and one row answers both. Which member turned up is a
    behavioural fact the research would otherwise lose."""
    event = _event()
    first = _accepted(event, "one@example.com")
    team = teams.create_team(first, event, "Nova")
    second = _accepted(event, "two@example.com")
    teams.join_team(second, event, team)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)

    issue = kit.give_kit(team, second, admin)
    assert issue.team == team
    assert issue.collected_by == second
    assert issue.confirmed_by == admin
    assert issue.status == KitIssue.COLLECTED
    assert issue.collected_at is not None


def test_a_team_cannot_collect_more_kits_than_it_is_allocated():
    event = _event(kits_per_team=1)
    person = _accepted(event, "greedy@example.com")
    team = teams.create_team(person, event, "Nova")
    kit.give_kit(team, person, person)

    with pytest.raises(kit.KitError) as caught:
        kit.give_kit(team, person, person)
    assert "already has" in str(caught.value)


def test_a_kit_cannot_be_handed_to_somebody_not_on_the_team():
    event = _event()
    member = _accepted(event, "member@example.com")
    team = teams.create_team(member, event, "Nova")
    stranger = _accepted(event, "stranger@example.com")

    with pytest.raises(kit.KitError) as caught:
        kit.give_kit(team, stranger, member)
    assert "not on this team" in str(caught.value)


def test_raising_the_allocation_lets_a_team_collect_again():
    event = _event(kits_per_team=2)
    person = _accepted(event, "two-kits@example.com")
    team = teams.create_team(person, event, "Nova")
    kit.give_kit(team, person, person)
    kit.give_kit(team, person, person)
    assert team.kit_issues.filter(status=KitIssue.COLLECTED).count() == 2


# -------------------------------------------------------------- the desk


def test_the_desk_finds_a_team_by_a_members_name_not_just_the_team_name():
    """An admin at a desk types three letters of whatever the person in
    front of them says, and that is as often their own name as the team's.
    """
    event = _event()
    person = _accepted(event, "yonatan@technion.ac.il")
    teams.create_team(person, event, "Nova Logic")

    assert kit.search_teams(event, "nova").count() == 1
    assert kit.search_teams(event, "yona").count() == 1
    assert kit.search_teams(event, "zzz").count() == 0


def test_the_desk_shows_every_team_before_anybody_has_typed():
    """An admin opening the desk before the queue arrives should see the
    room, not a blank page."""
    event = _event()
    for name in ("Nova", "Supernova"):
        person = _accepted(event, f"{name}@example.com")
        teams.create_team(person, event, name)
    assert kit.search_teams(event, "").count() == 2


def test_a_team_of_one_is_a_single_tap(client):
    """The common case, and the whole reason the desk can hit five
    seconds: a team of one needs no choice, so the desk does not ask for
    one."""
    event = _event()
    person = _accepted(event, "solo@example.com")
    team = teams.create_team(person, event, "Solo")
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)

    body = client.get(f"/crashtech/e/{event.slug}/kit-desk/").content.decode()
    assert "Give kit" in body

    client.post(f"/crashtech/e/{event.slug}/kit-desk/", {"team": team.pk, "member": person.pk})
    assert team.kit_issues.filter(status=KitIssue.COLLECTED, collected_by=person).exists()


def test_a_team_of_two_asks_which_member_is_standing_there(client):
    event = _event(team_size_max=2)
    first = _accepted(event, "dana@example.com")
    team = teams.create_team(first, event, "Nova")
    second = _accepted(event, "omri@example.com")
    teams.join_team(second, event, team)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)

    body = client.get(f"/crashtech/e/{event.slug}/kit-desk/").content.decode()
    assert "dana@example.com" in body and "omri@example.com" in body

    client.post(f"/crashtech/e/{event.slug}/kit-desk/", {"team": team.pk, "member": second.pk})
    issue = team.kit_issues.get()
    assert issue.collected_by == second


def test_handing_a_kit_over_returns_to_an_empty_search(client):
    """Ready for the next person in the queue, without the admin clearing
    anything."""
    event = _event()
    person = _accepted(event, "next@example.com")
    team = teams.create_team(person, event, "Nova")
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)

    response = client.post(
        f"/crashtech/e/{event.slug}/kit-desk/?q=nova",
        {"team": team.pk, "member": person.pk},
    )
    assert response.status_code == 302
    assert response["Location"].endswith("/kit-desk/")
    assert "q=" not in response["Location"]


def test_the_desk_works_without_javascript(client):
    """Rule 6.4: the corridor this runs in has the worst wifi of the
    event, and a plain form post is the thing most likely to survive it."""
    event = _event()
    person = _accepted(event, "nojs@example.com")
    teams.create_team(person, event, "Nova")
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)

    body = client.get(f"/crashtech/e/{event.slug}/kit-desk/").content.decode()
    assert "<script" not in body.lower()
    assert "onclick" not in body.lower()


def test_a_collected_kit_can_go_back_in_the_box(client):
    event = _event()
    person = _accepted(event, "returner@example.com")
    team = teams.create_team(person, event, "Nova")
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    kit.give_kit(team, person, admin)
    client.force_login(admin)

    client.post(f"/crashtech/e/{event.slug}/kit-desk/", {"team": team.pk, "take_back": "1"})
    assert team.kit_issues.filter(status=KitIssue.RETURNED).exists()
    assert kit.status_of(team) == "waiting"


def test_the_desk_counts_what_the_admin_needs_to_know():
    event = _event()
    done = _accepted(event, "done@example.com")
    collected = teams.create_team(done, event, "Done")
    waiting = _accepted(event, "waiting@example.com")
    teams.create_team(waiting, event, "Waiting")
    kit.give_kit(collected, done, done)

    counts = kit.counts_for(event)
    assert counts["teams"] == 2
    assert counts["collected_teams"] == 1
    assert counts["waiting"] == 1


# ------------------------------------------------------------- the screens


def test_no_c3_screen_renders_hebrew(client):
    event = _event()
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    EventRole.objects.create(hackathon=event, user=admin, role=EventRole.TECH_LEAD)
    Registration.objects.create(hackathon=event, user=_user("appl@example.com"))
    KitItem.objects.create(hackathon=event, name="DE10-Lite", quantity_total=30)
    client.force_login(admin)

    hebrew = re.compile(r"[֐-׿]")
    for path in ("registrations/", "teams/", "kit/", "kit-desk/"):
        body = client.get(f"/crashtech/e/{event.slug}/{path}").content.decode()
        assert not hebrew.search(body), f"/{path} rendered Hebrew"


def test_every_planning_screen_keeps_its_navigation(client):
    """Planning screens carry the full menu. The kit desk deliberately does
    not, because it is an event screen (see the test above), which is why
    it is absent from this list rather than failing it."""
    event = _event()
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    EventRole.objects.create(hackathon=event, user=admin, role=EventRole.TECH_LEAD)
    client.force_login(admin)
    for path in ("registrations/", "teams/", "kit/"):
        body = client.get(f"/crashtech/e/{event.slug}/{path}").content.decode()
        for item in ("Applications", "Kit desk", "People", "Settings"):
            assert f">{item}<" in body, f"/{path} lost {item} from the nav"


def test_a_signed_out_visitor_is_sent_to_crashtechs_own_login_from_c3(client):
    """The defect that reached production on C.2, checked on the new
    screens rather than assumed fixed."""
    event = _event()
    for path in ("apply/", "registrations/", "teams/", "kit/", "kit-desk/"):
        response = client.get(f"/crashtech/e/{event.slug}/{path}")
        assert response.status_code == 302, path
        assert response["Location"].startswith("/crashtech/login/"), path


def test_the_kit_desk_puts_the_search_field_near_the_top(client):
    """Rule 11.2. The desk is an event screen with a queue in front of it,
    and the full seven-item nav pushed the search field a third of the way
    down a phone before anything could be done. Caught by a screenshot.

    Checked structurally: the desk carries one way back and not the whole
    menu.
    """
    event = _event()
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)
    body = client.get(f"/crashtech/e/{event.slug}/kit-desk/").content.decode()

    for item in ("Applications", "People", "Timeline", "Settings", "Readiness"):
        assert f">{item}<" not in body, f"the kit desk is carrying {item} in its nav"
    assert "&larr;" in body, "the desk has no way back"
