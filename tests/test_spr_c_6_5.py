"""SPR-C.6.5 — CrashTech: the checkpoint.

Everything a review of C.1 to C.6 found. The review put every role side
by side at every stage, on a phone, and read the code against the rules,
and it found more than any sprint suite had: correctness and privacy bugs,
gaps against what Avi dictated, and a role-aware home that routed people
correctly while telling them almost nothing.

The lesson is the last section of this file. No test ever asked whether a
role's next action leads somewhere that role can open, at each stage, and
that one question would have caught most of what the review found.
"""

import datetime
import re
import uuid

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone

from crashtech import judging, scoring, submissions, teams
from crashtech.models import (
    Certificate, Challenge, ContentPage, Deliverable, EventRole, Hackathon,
    JudgeGrade, KitIssue, Milestone, Registration, Submission, SubmissionFile,
    Team, TeamMembership,
)
from crashtech.next_actions import next_actions_for

pytestmark = [pytest.mark.sprc65, pytest.mark.django_db]


def _event(status=Hackathon.LIVE, **kwargs):
    now = timezone.now()
    defaults = dict(
        name="CrashTech VLSI 2027", status=status,
        starts_at=now - timezone.timedelta(hours=2),
        ends_at=now + timezone.timedelta(hours=22),
        submission_deadline=now + timezone.timedelta(hours=22),
        team_size_max=3,
    )
    defaults.update(kwargs)
    return Hackathon.objects.create(**defaults)


def _user(email, name=""):
    first, _, last = name.partition(" ")
    return User.objects.create_user(
        username=email.split("@")[0], email=email, password="crashtech-7781",
        first_name=first, last_name=last,
    )


def _with_role(event, email, role, name=""):
    user = _user(email, name)
    EventRole.objects.create(hackathon=event, user=user, role=role)
    return user


def _accepted(event, email, name=""):
    user = _with_role(event, email, EventRole.PARTICIPANT, name)
    Registration.objects.create(hackathon=event, user=user, status=Registration.ACCEPTED)
    return user


def _team(event, email, name, person_name=""):
    user = _accepted(event, email, person_name)
    team = Team.objects.create(hackathon=event, name=name, exhibition_consent=True)
    TeamMembership.objects.create(hackathon=event, team=team, user=user)
    return team, user


def _published(event, *pairs):
    """A closed event with these (team name, person name, points) published."""
    Hackathon.objects.filter(pk=event.pk).update(status=Hackathon.CLOSED)
    event.refresh_from_db()
    out = []
    for n, (team_name, person, points) in enumerate(pairs):
        challenge = Challenge.objects.create(
            hackathon=event, title=f"Task {n}", kind=Challenge.COMPLETION,
            points=points, visible=True,
        )
        team, user = _team(event, f"p{n}@example.com", team_name, person)
        Submission.objects.create(challenge=challenge, team=team, claimed_complete=True)
        out.append((team, user))
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    judging.publish(event, by=admin)
    event.refresh_from_db()
    return out, admin


# ------------------------------------------------- F-C.6.5.1 no emails public


def test_no_public_page_prints_a_participants_email_address(client):
    """The most serious finding. Sign-up asked for no name, so the museum,
    the certificate and the published standings fell back to the email
    address, on pages that are public and permanent by design."""
    event = _event()
    pairs, _admin = _published(event, ("Clockwise", "", 50))   # no name at all
    team, user = pairs[0]
    certificate = Certificate.objects.get(team=team)

    anonymous = Client()
    for url in (
        f"/crashtech/e/{event.slug}/museum/",
        f"/crashtech/e/{event.slug}/standings/",
        f"/crashtech/c/{certificate.cert_id}/",
        f"/crashtech/e/{event.slug}/",
    ):
        body = anonymous.get(url).content.decode()
        assert user.email not in body, url
        assert "@example.com" not in body, url


def test_a_person_with_no_name_is_called_a_participant_not_their_address(client):
    event = _event()
    pairs, _admin = _published(event, ("Clockwise", "", 50))
    certificate = Certificate.objects.get(team=pairs[0][0])
    body = Client().get(f"/crashtech/c/{certificate.cert_id}/").content.decode()
    assert "A participant" in body


def test_a_person_with_a_name_is_named(client):
    event = _event()
    pairs, _admin = _published(event, ("Clockwise", "Dana Levi", 50))
    certificate = Certificate.objects.get(team=pairs[0][0])
    body = Client().get(f"/crashtech/c/{certificate.cert_id}/").content.decode()
    assert "Dana Levi" in body


def test_sign_up_asks_for_a_name_and_stores_it(client):
    response = client.post("/crashtech/signup/", {
        "name": "Dana Levi", "email": "dana@example.com", "password": "crashtech-7781",
    })
    assert response.status_code == 302
    user = User.objects.get(email="dana@example.com")
    assert user.get_full_name() == "Dana Levi"


def test_sign_up_without_a_name_is_refused_in_words(client):
    response = client.post("/crashtech/signup/", {
        "email": "dana@example.com", "password": "crashtech-7781",
    })
    assert response.status_code == 200
    assert "certificate" in response.content.decode()
    assert not User.objects.filter(email="dana@example.com").exists()


def test_an_account_with_no_name_is_asked_for_one_when_it_applies(client):
    """An account from babook, or from before sign-up asked, may have none,
    and the name has to exist before anything public can carry it."""
    event = _event(status=Hackathon.PUBLISHED)
    person = _user("hopeful@example.com")
    client.force_login(person)

    assert 'name="name"' in client.get(f"/crashtech/e/{event.slug}/").content.decode()

    client.post(f"/crashtech/e/{event.slug}/apply/", {})
    assert not Registration.objects.filter(user=person).exists()

    client.post(f"/crashtech/e/{event.slug}/apply/", {"name": "Lior Ben Ami"})
    person.refresh_from_db()
    assert person.get_full_name() == "Lior Ben Ami"
    assert Registration.objects.filter(user=person).exists()


def test_participants_do_not_see_each_others_email_addresses(client):
    event = _event(status=Hackathon.PUBLISHED)
    team, mine = _team(event, "dana@example.com", "Clockwise", "Dana Levi")
    other = _accepted(event, "omer@example.com", "Omer Cohen")
    TeamMembership.objects.create(hackathon=event, team=team, user=other)
    client.force_login(mine)
    body = client.get(f"/crashtech/e/{event.slug}/teams/").content.decode()
    assert "Omer Cohen" in body
    assert "omer@example.com" not in body


# ---------------------------------------------- F-C.6.5.2 one door to publish


def test_readiness_cannot_publish_around_the_publish_screen(client):
    """It opened the museum without freezing the scores or issuing a single
    certificate. Rule 8.5 is one gated click, not two doors."""
    event = _event(status=Hackathon.CLOSED,
                   ends_at=timezone.now() - timezone.timedelta(minutes=1),
                   submission_deadline=timezone.now() - timezone.timedelta(minutes=1))
    challenge = Challenge.objects.create(hackathon=event, title="Go", points=50, visible=True)
    team, _user_ = _team(event, "p@example.com", "Clockwise", "Dana Levi")
    Submission.objects.create(challenge=challenge, team=team, claimed_complete=True)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)

    response = client.post(f"/crashtech/e/{event.slug}/advance/")
    assert response.status_code == 302
    assert response.url == f"/crashtech/e/{event.slug}/publish/"
    event.refresh_from_db()
    assert event.status == Hackathon.CLOSED
    assert event.results_published_at is None
    assert not Certificate.objects.exists()


def test_readiness_at_close_points_at_the_publish_screen(client):
    event = _event(status=Hackathon.CLOSED)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)
    body = client.get(f"/crashtech/e/{event.slug}/readiness/").content.decode()
    assert f'action="/crashtech/e/{event.slug}/advance/"' not in body
    assert f'href="/crashtech/e/{event.slug}/publish/"' in body


# ------------------------------------------------ F-C.6.5.3 teams lock


@pytest.mark.parametrize("status", [Hackathon.LIVE, Hackathon.CLOSED, Hackathon.MUSEUM])
def test_nobody_joins_a_team_once_the_event_has_started(status):
    """Somebody could join the winning team after the results were out, and
    appear on its certificate."""
    event = _event(status=status)
    team, _first = _team(event, "a@example.com", "Clockwise", "Dana Levi")
    late = _accepted(event, "late@example.com", "Late Comer")
    with pytest.raises(teams.TeamError):
        teams.join_team(late, event, team)
    assert team.memberships.count() == 1


@pytest.mark.parametrize("status", [Hackathon.LIVE, Hackathon.CLOSED, Hackathon.MUSEUM])
def test_nobody_leaves_a_team_once_the_event_has_started(status):
    """The last member out dissolved the team, and its submissions with it."""
    event = _event(status=status)
    team, member = _team(event, "a@example.com", "Clockwise", "Dana Levi")
    challenge = Challenge.objects.create(hackathon=event, title="Go", points=5, visible=True)
    Submission.objects.create(challenge=challenge, team=team)
    with pytest.raises(teams.TeamError):
        teams.leave_team(member, event)
    assert Team.objects.filter(pk=team.pk).exists()
    assert Submission.objects.filter(team=team).exists()


def test_a_stranded_person_can_still_start_a_team_of_their_own_during_the_event():
    """Locking everything would leave an accepted person with no team
    unable to submit for twenty-four hours. Starting their own joins
    nothing and nobody joins it."""
    event = _event(status=Hackathon.LIVE)
    person = _accepted(event, "late@example.com", "Late Comer")
    team = teams.create_team(person, event, "Late Start")
    assert team.memberships.count() == 1


def test_nobody_starts_a_team_once_submissions_are_closed():
    event = _event(status=Hackathon.CLOSED)
    person = _accepted(event, "late@example.com", "Late Comer")
    with pytest.raises(teams.TeamError):
        teams.create_team(person, event, "Too Late")


def test_teams_still_change_freely_before_kickoff():
    event = _event(status=Hackathon.KITS)
    team, _first = _team(event, "a@example.com", "Clockwise", "Dana Levi")
    second = _accepted(event, "b@example.com", "Omer Cohen")
    teams.join_team(second, event, team)
    teams.leave_team(second, event)
    assert team.memberships.count() == 1


# ----------------------------------------- blind labels carry no sign-up order


def test_a_new_team_has_no_anonymous_label_yet():
    """It used to get `teams.count() + 1`, so "Entry 1" meant "signed up
    first", the information Rule 4.6 promises a judge does not have."""
    event = _event(status=Hackathon.PUBLISHED)
    person = _accepted(event, "a@example.com", "Dana Levi")
    team = teams.create_team(person, event, "Clockwise")
    assert team.anon_ordinal == 0


def test_the_close_hands_out_labels_in_a_shuffled_order(monkeypatch):
    event = _event(status=Hackathon.CLOSED)
    for n in range(4):
        _team(event, f"p{n}@example.com", f"Team {n}", "Some One")
    monkeypatch.setattr("random.shuffle", lambda rows: rows.reverse())
    judging.assign_anonymous_labels(event)
    by_creation = list(event.teams.order_by("pk").values_list("anon_ordinal", flat=True))
    assert by_creation == [4, 3, 2, 1]


# ------------------------------------ F-C.6.5.4 a deliverable with work stays


def test_a_deliverable_somebody_has_turned_in_cannot_be_removed(client):
    """The cascade deleted every team's file for it, mid-event, silently."""
    event = _event()
    lead = _with_role(event, "lead@example.com", EventRole.TECH_LEAD)
    challenge = Challenge.objects.create(hackathon=event, title="Go", points=5, visible=True)
    item = Deliverable.objects.create(challenge=challenge, label="Notes", kind="text")
    team, _member = _team(event, "a@example.com", "Clockwise", "Dana Levi")
    submission = Submission.objects.create(challenge=challenge, team=team)
    SubmissionFile.objects.create(submission=submission, deliverable=item, text_value="ours")

    client.force_login(lead)
    response = client.post(
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/edit/",
        {"drop_deliverable": item.pk}, follow=True,
    )
    assert Deliverable.objects.filter(pk=item.pk).exists()
    assert SubmissionFile.objects.filter(submission=submission).exists()
    assert "delete their work" in response.content.decode()


def test_an_untouched_deliverable_can_still_be_removed(client):
    event = _event(status=Hackathon.SETUP)
    lead = _with_role(event, "lead@example.com", EventRole.TECH_LEAD)
    challenge = Challenge.objects.create(hackathon=event, title="Go", points=5)
    item = Deliverable.objects.create(challenge=challenge, label="Notes", kind="text")
    client.force_login(lead)
    client.post(f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/edit/",
                {"drop_deliverable": item.pk})
    assert not Deliverable.objects.filter(pk=item.pk).exists()


# ------------------------------------------- F-C.6.5.5 the phone and the clock


def _png():
    return SimpleUploadedFile(
        "bench.png",
        bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                      "1f15c4890000000d4944415478da63fcffff3f0300050001ff9d0e0d00"
                      "00000049454e44ae426082"),
        content_type="image/png",
    )


def test_the_phone_upload_stops_at_the_deadline():
    """Rule 7.7 on the one path with no account behind it. The token lives
    30 hours, which outlives the deadline."""
    event = _event()
    challenge = Challenge.objects.create(hackathon=event, title="Go", points=5, visible=True)
    photo = Deliverable.objects.create(challenge=challenge, label="Bench", kind="image")
    team, _member = _team(event, "a@example.com", "Clockwise", "Dana Levi")
    token = submissions.upload_token_for(team, challenge)

    Hackathon.objects.filter(pk=event.pk).update(
        submission_deadline=timezone.now() - timezone.timedelta(minutes=1),
    )
    response = Client().post(f"/crashtech/upload/{token.token}/", {f"d{photo.pk}": _png()})
    assert response.status_code == 410
    assert "closed" in response.content.decode().lower()
    assert not SubmissionFile.objects.exists()


# ------------------------------------------- F-C.6.5.6 who last saved


def test_last_saved_by_names_who_last_saved():
    event = _event()
    challenge = Challenge.objects.create(hackathon=event, title="Go", points=5, visible=True)
    team, dana = _team(event, "dana@example.com", "Clockwise", "Dana Levi")
    omer = _accepted(event, "omer@example.com", "Omer Cohen")
    TeamMembership.objects.create(hackathon=event, team=team, user=omer)

    submissions.save_submission(dana, team, challenge, data={"reported_note": "one"})
    submission, _ = submissions.save_submission(omer, team, challenge, data={"reported_note": "two"})
    assert submission.submitted_by == omer


# ------------------------------------------------- F-C.6.5.7 ties share a place


def test_equal_points_share_a_place():
    event = _event()
    pairs, _admin = _published(
        event, ("Clockwise", "A A", 50), ("Ripple", "B B", 50), ("Latch", "C C", 10),
    )
    places = {team.name: place for place, team, _pts in scoring.standings(event)}
    assert places == {"Clockwise": 1, "Ripple": 1, "Latch": 3}


def test_a_dead_heat_gives_both_teams_the_winners_certificate():
    """It used to crown one and make the other runner-up, by whoever formed
    their team first, on a permanent certificate."""
    event = _event()
    _published(event, ("Clockwise", "A A", 50), ("Ripple", "B B", 50), ("Latch", "C C", 10))
    kinds = {c.team.name: c.type for c in Certificate.objects.all()}
    assert kinds["Clockwise"] == Certificate.WINNER
    assert kinds["Ripple"] == Certificate.WINNER
    assert kinds["Latch"] == Certificate.RUNNER_UP  # place 3


def test_the_same_number_in_a_ranked_challenge_takes_the_same_tier():
    event = _event()
    challenge = Challenge.objects.create(
        hackathon=event, title="Fmax", kind=Challenge.MEASURED, points=0,
        rank_points=[60, 40, 25], visible=True,
    )
    subs = []
    for n, value in enumerate((200, 200, 150)):
        team, _u = _team(event, f"p{n}@example.com", f"Team {n}", "Some One")
        subs.append(Submission.objects.create(challenge=challenge, team=team, reported_value=value))
    assert [scoring.points_for(s) for s in subs] == [60, 60, 25]


# --------------------------------------------- F-C.6.5.8 certificates reachable


def test_a_participant_finds_their_certificate_on_their_home(client):
    event = _event()
    pairs, _admin = _published(event, ("Clockwise", "Dana Levi", 50))
    team, user = pairs[0]
    certificate = Certificate.objects.get(team=team)
    client.force_login(user)
    body = client.get(f"/crashtech/e/{event.slug}/").content.decode()
    assert f"/crashtech/c/{certificate.cert_id}/" in body
    assert "finished 1st" in body


def test_the_museum_links_each_teams_certificate(client):
    event = _event()
    pairs, _admin = _published(event, ("Clockwise", "Dana Levi", 50))
    certificate = Certificate.objects.get(team=pairs[0][0])
    body = Client().get(f"/crashtech/e/{event.slug}/museum/").content.decode()
    assert f"/crashtech/c/{certificate.cert_id}/" in body


# ------------------------------------------ F-C.6.5.9 who may compete


@pytest.mark.parametrize("role", [EventRole.ADMIN, EventRole.TECH_LEAD, EventRole.JUDGE])
def test_somebody_who_reads_the_challenges_early_cannot_apply(client, role):
    """The home offered every one of them "Apply to take part". A tech lead
    who competed would have had the tasks for days."""
    event = _event(status=Hackathon.PUBLISHED)
    person = _with_role(event, f"{role}@example.com", role, "Staff Person")
    client.force_login(person)
    assert "Apply to take part" not in client.get(f"/crashtech/e/{event.slug}/").content.decode()
    client.post(f"/crashtech/e/{event.slug}/apply/")
    assert not Registration.objects.filter(user=person).exists()


def test_a_researcher_may_still_compete(client):
    event = _event(status=Hackathon.PUBLISHED)
    person = _with_role(event, "r@example.com", EventRole.RESEARCHER, "Re Searcher")
    client.force_login(person)
    client.post(f"/crashtech/e/{event.slug}/apply/")
    assert Registration.objects.filter(user=person).exists()


def test_applying_by_get_does_nothing(client):
    """It was a GET with a side effect, so a link prefetch could apply
    somebody to an event."""
    event = _event(status=Hackathon.PUBLISHED)
    person = _user("p@example.com", "Some One")
    client.force_login(person)
    assert client.get(f"/crashtech/e/{event.slug}/apply/").status_code == 405
    assert not Registration.objects.exists()


def test_sign_up_will_not_redirect_off_the_site(client):
    response = client.post("/crashtech/signup/?next=https://evil.example.com/", {
        "name": "Dana Levi", "email": "dana@example.com", "password": "crashtech-7781",
    })
    assert response.status_code == 302
    assert "evil.example.com" not in response.url


# --------------------------------------------- F-C.6.5.10, 11 dates and zones


def test_the_dates_can_be_changed_after_creation(client):
    """Avi: "after we are live we will set dates". They could only ever be
    set when the event was created."""
    event = _event(status=Hackathon.PUBLISHED, timezone_name="Asia/Jerusalem")
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)
    client.post(f"/crashtech/e/{event.slug}/settings/", {
        "name": event.name, "team_size_max": "2", "kits_per_team": "1",
        "leaderboard_visibility": "admins", "timezone_name": "Asia/Jerusalem",
        "starts_at": "2027-03-04T10:00", "submission_deadline": "2027-03-05T09:00",
        "ends_at": "2027-03-05T10:00",
    })
    event.refresh_from_db()
    local = timezone.localtime(event.starts_at, event.tz)
    assert (local.year, local.month, local.day, local.hour) == (2027, 3, 4, 10)


def test_a_deadline_after_the_end_is_refused(client):
    event = _event(status=Hackathon.PUBLISHED)
    before = event.submission_deadline
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)
    client.post(f"/crashtech/e/{event.slug}/settings/", {
        "name": event.name, "team_size_max": "2", "kits_per_team": "1",
        "leaderboard_visibility": "admins", "timezone_name": "Asia/Jerusalem",
        "starts_at": "2027-03-04T10:00", "submission_deadline": "2027-03-06T10:00",
        "ends_at": "2027-03-05T10:00",
    })
    event.refresh_from_db()
    assert event.submission_deadline == before


def test_a_typed_time_means_that_time_where_the_event_is(client):
    """A browser's datetime field carries no zone. Reading it as UTC moved
    every milestone two or three hours for an event in Israel."""
    event = _event(status=Hackathon.SETUP, timezone_name="Asia/Jerusalem")
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)
    client.post(f"/crashtech/e/{event.slug}/milestones/", {
        "title": "Kickoff", "kind": "kickoff", "occurs_at": "2027-03-04T10:00",
    })
    milestone = Milestone.objects.get(hackathon=event)
    assert timezone.localtime(milestone.occurs_at, event.tz).hour == 10


def test_times_are_shown_in_the_events_zone_and_name_it(client):
    event = _event(status=Hackathon.PUBLISHED, timezone_name="Asia/Jerusalem")
    Hackathon.objects.filter(pk=event.pk).update(
        starts_at=datetime.datetime(2027, 3, 4, 8, 0, tzinfo=datetime.timezone.utc),  # 10:00 in Israel
    )
    body = Client().get(f"/crashtech/e/{event.slug}/").content.decode()
    assert "10:00" in body
    # Named by its city. "IST" is Israel to the organiser and India to
    # half the people reading it.
    assert "Jerusalem time" in body
    assert " IST" not in body and " IDT" not in body


# ----------------------------------- F-C.6.5.12, 13 repository, pages, facts


def test_the_repository_reaches_accepted_participants_at_kit_stage(client):
    """Avi's milestone 2. The link was stored and shown to nobody."""
    event = _event(status=Hackathon.KITS, repo_url="https://github.com/avisalmon/TechCrash2026")
    _team_, member = _team(event, "a@example.com", "Clockwise", "Dana Levi")
    client.force_login(member)
    assert "https://github.com/avisalmon/TechCrash2026" in client.get(
        f"/crashtech/e/{event.slug}/").content.decode()


def test_the_repository_waits_for_kit_stage_and_for_acceptance(client):
    event = _event(status=Hackathon.PUBLISHED, repo_url="https://github.com/x/y")
    _team_, member = _team(event, "a@example.com", "Clockwise", "Dana Levi")
    client.force_login(member)
    assert "github.com/x/y" not in client.get(f"/crashtech/e/{event.slug}/").content.decode()

    Hackathon.objects.filter(pk=event.pk).update(status=Hackathon.KITS)
    assert "github.com/x/y" not in Client().get(f"/crashtech/e/{event.slug}/").content.decode()


def test_the_events_own_pages_are_shown(client):
    """About and Rules were seeded with the text that explains trust scoring
    and shown nowhere."""
    event = _event(status=Hackathon.PUBLISHED)
    ContentPage.objects.create(hackathon=event, slug="rules", title="The rules",
                               body="**Scoring.** We trust you.", published=True)
    body = Client().get(f"/crashtech/e/{event.slug}/").content.decode()
    assert "The rules" in body
    assert "<strong>Scoring.</strong>" in body


def test_an_events_page_cannot_carry_raw_html():
    event = _event(status=Hackathon.PUBLISHED)
    ContentPage.objects.create(hackathon=event, slug="about", title="About",
                               body="<script>alert(1)</script>", published=True)
    body = Client().get(f"/crashtech/e/{event.slug}/").content.decode()
    assert "<script>alert(1)</script>" not in body


def test_a_page_waits_for_its_milestone():
    event = _event(status=Hackathon.PUBLISHED)
    ContentPage.objects.create(hackathon=event, slug="kit", title="About the kit",
                               body="Boards.", published=True, visible_from="hardware")
    assert "About the kit" not in Client().get(f"/crashtech/e/{event.slug}/").content.decode()
    Hackathon.objects.filter(pk=event.pk).update(status=Hackathon.KITS)
    assert "About the kit" in Client().get(f"/crashtech/e/{event.slug}/").content.decode()


# ------------------------------------------- F-C.6.5.14 to 16 every role's home


def test_during_the_event_everybody_sees_the_clock():
    """The most important fact of the night, which no screen showed."""
    event = _event(status=Hackathon.LIVE)
    body = Client().get(f"/crashtech/e/{event.slug}/").content.decode()
    assert "Submissions close in" in body
    assert "data-deadline=" in body


def test_a_participant_without_a_team_is_told_so_during_the_event(client):
    """They were told "The challenges are open" and then could not submit."""
    event = _event(status=Hackathon.LIVE)
    person = _accepted(event, "late@example.com", "Late Comer")
    client.force_login(person)
    body = client.get(f"/crashtech/e/{event.slug}/").content.decode()
    assert "not on a team" in body


def test_a_participant_without_a_team_is_told_to_form_one_before_kit_day(client):
    event = _event(status=Hackathon.KITS)
    person = _accepted(event, "a@example.com", "Some One")
    client.force_login(person)
    assert "Form a team" in client.get(f"/crashtech/e/{event.slug}/").content.decode()


def test_a_team_that_has_its_kit_is_told_so(client):
    event = _event(status=Hackathon.KITS)
    team, member = _team(event, "a@example.com", "Clockwise", "Dana Levi")
    KitIssue.objects.create(hackathon=event, team=team, status=KitIssue.COLLECTED)
    client.force_login(member)
    assert "has its kit" in client.get(f"/crashtech/e/{event.slug}/").content.decode()


def test_a_participant_sees_their_points_on_their_home_during_the_event(client):
    event = _event(status=Hackathon.LIVE)
    challenge = Challenge.objects.create(hackathon=event, title="Go", points=50, visible=True)
    team, member = _team(event, "a@example.com", "Clockwise", "Dana Levi")
    Submission.objects.create(challenge=challenge, team=team, claimed_complete=True)
    client.force_login(member)
    assert "50 points so far" in client.get(f"/crashtech/e/{event.slug}/").content.decode()


def test_the_results_are_the_first_thing_on_a_finished_events_page():
    """It used to be a list of past dates, for everybody, including the team
    that won."""
    event = _event()
    _published(event, ("Clockwise", "A A", 50), ("Ripple", "B B", 30))
    body = Client().get(f"/crashtech/e/{event.slug}/").content.decode()
    assert "The results" in body
    assert body.index("Clockwise") < body.index("Timeline")
    assert f"/crashtech/e/{event.slug}/museum/" in body


def test_the_judges_home_at_the_close_goes_to_judging_not_the_challenges():
    event = _event(status=Hackathon.CLOSED)
    challenge = Challenge.objects.create(hackathon=event, title="Elegant",
                                         kind=Challenge.CREATIVITY, points=40, visible=True)
    team, _u = _team(event, "a@example.com", "Clockwise", "Dana Levi")
    Submission.objects.create(challenge=challenge, team=team)
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE, "Ruth Judge")
    urls = [u for _l, items in next_actions_for(judge, event) for a, u in items if a.urgent]
    assert urls == [f"/crashtech/e/{event.slug}/judging/"]


def test_the_admins_home_at_the_close_goes_to_publish():
    event = _event(status=Hackathon.CLOSED)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    urls = [u for _l, items in next_actions_for(admin, event) for a, u in items if a.urgent]
    assert urls == [f"/crashtech/e/{event.slug}/publish/"]


def test_the_admins_home_in_the_museum_asks_for_the_paragraph():
    """It said "Nothing for you to do" while the museum waited on them."""
    event = _event()
    _pairs, admin = _published(event, ("Clockwise", "A A", 50))
    texts = [a.text for _l, items in next_actions_for(admin, event) for a, _u in items]
    assert any("paragraph" in t for t in texts)


def test_no_home_ever_has_more_than_one_next_thing():
    """`urgent` is for the one thing standing between the event and its next
    phase. Two of them on one screen means neither."""
    for status in (Hackathon.PUBLISHED, Hackathon.KITS, Hackathon.LIVE, Hackathon.CLOSED):
        event = _event(status=status, name=f"Event {status}")
        people = [
            _with_role(event, f"a-{status}@example.com", EventRole.ADMIN),
            _with_role(event, f"t-{status}@example.com", EventRole.TECH_LEAD),
            _with_role(event, f"j-{status}@example.com", EventRole.JUDGE),
            _accepted(event, f"p-{status}@example.com", "Some One"),
        ]
        for person in people:
            for _label, items in next_actions_for(person, event):
                urgent = [a for a, _u in items if a.urgent]
                assert len(urgent) <= 1, (status, person.email, [a.text for a in urgent])


# ------------------------------------------------- the lesson, as a test


ROLE_VIEWERS = [
    ("admin", EventRole.ADMIN), ("tech lead", EventRole.TECH_LEAD),
    ("judge", EventRole.JUDGE), ("participant", EventRole.PARTICIPANT),
]


@pytest.mark.parametrize("status", [
    Hackathon.SETUP, Hackathon.PUBLISHED, Hackathon.KITS,
    Hackathon.LIVE, Hackathon.CLOSED, Hackathon.MUSEUM,
])
def test_every_link_on_every_roles_home_opens_for_that_role(status):
    """The question no sprint suite asked, which the review answered by
    looking: at this stage, can this person open what their own home sends
    them to?

    It caught, among others, a judge sent to the challenges list when the
    work was on the judging screen, and an admin whose publish screen
    linked them at a page that refused them.
    """
    event = _event(status=Hackathon.PUBLISHED, repo_url="")
    challenge = Challenge.objects.create(hackathon=event, title="Elegant",
                                         kind=Challenge.CREATIVITY, points=40)
    Deliverable.objects.create(challenge=challenge, label="Notes", kind="text")
    team, member = _team(event, "member@example.com", "Clockwise", "Dana Levi")
    people = {label: _with_role(event, f"{label.replace(' ', '')}@example.com", role, "Staff Person")
              for label, role in ROLE_VIEWERS if role != EventRole.PARTICIPANT}
    people["participant"] = member

    if status == Hackathon.MUSEUM:
        Hackathon.objects.filter(pk=event.pk).update(status=Hackathon.CLOSED)
        challenge.visible = True
        challenge.save()
        submission = Submission.objects.create(challenge=challenge, team=team, is_finalist=True)
        JudgeGrade.objects.create(submission=submission, judge=people["judge"], grade=7)
        event.refresh_from_db()
        judging.publish(event, by=people["admin"])
    else:
        Hackathon.objects.filter(pk=event.pk).update(status=status)
        if status in (Hackathon.LIVE, Hackathon.CLOSED):
            event.challenges.update(visible=True)
    event.refresh_from_db()

    for label, person in people.items():
        client = Client()
        client.force_login(person)
        for _role, items in next_actions_for(person, event):
            for action, url in items:
                if not url or not url.startswith("/crashtech/"):
                    continue
                response = client.get(url)
                assert response.status_code == 200, (status, label, action.text, url, response.status_code)
