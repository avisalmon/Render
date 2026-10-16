"""SPR-C.5 — CrashTech: judging, results, publishing.

The sprint that completes an event, and the one where the trust model is
most easily lost. In 2026 a submission was worth nothing until a judge
touched it, so judges touched everything, so nothing was judged well.
Three rules hold the line and each has tests here:

- **Judges do nothing during the event** (Rule 8.1). Grading live scores
  the first entry against a different field from the last.
- **Creativity is two steps** (Rule 8.2): shortlist, then grade the
  shortlist. Seventy entries get a rubber stamp; fifteen get attention.
- **Verification is a spot check and "left alone" is the normal answer**
  (Rule 8.3). The screen offers only the scores that decide the outcome,
  and says so, because a screen listing everything is read as an
  instruction to check everything.

Then the one click that cannot be walked back (Rule 8.5).
"""

import re
import uuid

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from crashtech import judging, scoring
from crashtech.models import (
    Certificate, Challenge, Deliverable, EventRole, Hackathon, JudgeGrade,
    Registration, Submission, Team, TeamMembership,
)

pytestmark = [pytest.mark.sprc5, pytest.mark.django_db]


def _event(**kwargs):
    now = timezone.now()
    defaults = dict(
        name="CrashTech VLSI 2027", status=Hackathon.CLOSED,
        starts_at=now - timezone.timedelta(hours=26),
        ends_at=now - timezone.timedelta(hours=2),
        submission_deadline=now - timezone.timedelta(hours=2),
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


def _team(event, email, name=None, ordinal=0):
    team = Team.objects.create(
        hackathon=event, name=name or email.split("@")[0].title(), anon_ordinal=ordinal,
    )
    user = _with_role(event, email, EventRole.PARTICIPANT)
    Registration.objects.create(hackathon=event, user=user, status=Registration.ACCEPTED)
    TeamMembership.objects.create(hackathon=event, team=team, user=user)
    return team


def _challenge(event, kind=Challenge.CREATIVITY, **kwargs):
    defaults = dict(
        hackathon=event, title="Most elegant", kind=kind, points=40,
        max_grade=10, visible=True, criteria="Does it do something nobody asked for?",
    )
    defaults.update(kwargs)
    return Challenge.objects.create(**defaults)


def _settled(event):
    """An event with nothing outstanding, which is what publishing needs."""
    challenge = _challenge(event)
    team = _team(event, "a@example.com", name="Alpha", ordinal=1)
    submission = Submission.objects.create(challenge=challenge, team=team, is_finalist=True)
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)
    JudgeGrade.objects.create(submission=submission, judge=judge, grade=8)
    return challenge, team, submission, judge


# ----------------------------------------------- F-C.5.1 locked during play


def test_judges_can_do_nothing_while_the_event_is_live(client):
    """Rule 8.1. Grading live would score the first submission against a
    different field from the last."""
    now = timezone.now()
    event = _event(
        status=Hackathon.LIVE,
        starts_at=now - timezone.timedelta(hours=2),
        ends_at=now + timezone.timedelta(hours=22),
        submission_deadline=now + timezone.timedelta(hours=22),
    )
    challenge = _challenge(event)
    team = _team(event, "a@example.com")
    submission = Submission.objects.create(challenge=challenge, team=team)
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)
    client.force_login(judge)

    client.post(f"/crashtech/e/{event.slug}/judging/{challenge.pk}/shortlist/", {
        "submission": submission.pk, "on": "1",
    })
    submission.refresh_from_db()
    assert submission.is_finalist is False


def test_the_locked_screen_says_what_it_is_waiting_for(client):
    """A locked screen that does not explain itself reads as broken, and
    "what am I waiting for" is the only thing a judge wants to know during
    the 24 hours."""
    now = timezone.now()
    event = _event(
        status=Hackathon.LIVE,
        starts_at=now - timezone.timedelta(hours=2),
        ends_at=now + timezone.timedelta(hours=22),
        submission_deadline=now + timezone.timedelta(hours=22),
    )
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)
    client.force_login(judge)

    body = client.get(f"/crashtech/e/{event.slug}/judging/").content.decode()
    assert "opens when the event closes" in body
    assert "different field" in body


def test_only_a_judge_reaches_the_judging_screens(client):
    event = _event()
    challenge = _challenge(event)
    participant = _with_role(event, "p@example.com", EventRole.PARTICIPANT)
    client.force_login(participant)
    for url in (
        f"/crashtech/e/{event.slug}/judging/",
        f"/crashtech/e/{event.slug}/judging/{challenge.pk}/shortlist/",
        f"/crashtech/e/{event.slug}/verify/",
    ):
        assert client.get(url).status_code == 403, url


# ------------------------------------------------------ F-C.5.2 shortlisting


def test_shortlisting_puts_every_entry_on_one_screen(client):
    """Rule 8.2 and user_journeys.md: shortlisting is a COMPARISON. One at
    a time turns it into seventy separate verdicts, which is the thing the
    two-step exists to avoid."""
    event = _event()
    challenge = _challenge(event)
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)
    for n in range(5):
        team = _team(event, f"p{n}@example.com", name=f"Team {n}", ordinal=n + 1)
        Submission.objects.create(challenge=challenge, team=team)
    client.force_login(judge)

    body = client.get(
        f"/crashtech/e/{event.slug}/judging/{challenge.pk}/shortlist/"
    ).content.decode()
    for n in range(5):
        assert f"Entry {n + 1}" in body


def test_judging_is_blind(client):
    """Rule 4.6. A team called "Dana and Yoav" decides it before the work
    does."""
    event = _event()
    challenge = _challenge(event)
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)
    team = _team(event, "p@example.com", name="Dana and Yoav", ordinal=3)
    submission = Submission.objects.create(challenge=challenge, team=team)
    client.force_login(judge)

    for url in (
        f"/crashtech/e/{event.slug}/judging/{challenge.pk}/shortlist/",
        f"/crashtech/e/{event.slug}/judging/entry/{submission.pk}/",
    ):
        body = client.get(url).content.decode()
        assert "Dana and Yoav" not in body, url
        assert "Entry 3" in body, url


def test_closing_the_event_hands_out_the_anonymous_labels(client):
    """Assigned at the close rather than at team creation, so the order
    carries no information about who signed up first either."""
    now = timezone.now()
    event = _event(
        status=Hackathon.LIVE,
        starts_at=now - timezone.timedelta(hours=26),
        ends_at=now - timezone.timedelta(hours=1),
        submission_deadline=now - timezone.timedelta(hours=1),
    )
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    for n in range(3):
        _team(event, f"p{n}@example.com", name=f"Team {n}")
    assert event.teams.filter(anon_ordinal=0).count() == 3

    client.force_login(admin)
    client.post(f"/crashtech/e/{event.slug}/advance/")

    event.refresh_from_db()
    assert event.status == Hackathon.CLOSED
    assert event.teams.filter(anon_ordinal=0).count() == 0
    assert sorted(event.teams.values_list("anon_ordinal", flat=True)) == [1, 2, 3]


def test_the_labels_do_not_move_if_they_are_assigned_twice():
    """A label that moved between two judging sessions would be worse than
    no label at all."""
    event = _event()
    for n in range(3):
        _team(event, f"p{n}@example.com", name=f"Team {n}")
    judging.assign_anonymous_labels(event)
    before = dict(event.teams.values_list("pk", "anon_ordinal"))

    _team(event, "late@example.com", name="Late")
    judging.assign_anonymous_labels(event)
    after = dict(event.teams.values_list("pk", "anon_ordinal"))

    for pk, ordinal in before.items():
        assert after[pk] == ordinal
    assert after[event.teams.get(name="Late").pk] == 4


def test_taking_a_team_off_the_shortlist_drops_its_grades():
    """Otherwise a later re-shortlist silently carries an old judgement."""
    event = _event()
    challenge, team, submission, judge = _settled(event)
    assert submission.grades.count() == 1

    judging.set_finalist(submission, judge, on=False)
    submission.refresh_from_db()
    assert submission.is_finalist is False
    assert submission.grades.count() == 0
    assert scoring.points_for(submission) == 0


def test_only_creativity_challenges_are_shortlisted():
    event = _event()
    challenge = _challenge(event, kind=Challenge.MEASURED, rank_points=[10])
    team = _team(event, "p@example.com")
    submission = Submission.objects.create(challenge=challenge, team=team, reported_value=5)
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)

    with pytest.raises(judging.JudgingError):
        judging.set_finalist(submission, judge)


# --------------------------------------------------------- F-C.5.3 grading


def test_a_grade_scores_the_submission(client):
    event = _event()
    challenge = _challenge(event, points=40, max_grade=10)
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)
    team = _team(event, "p@example.com", ordinal=1)
    submission = Submission.objects.create(challenge=challenge, team=team, is_finalist=True)
    client.force_login(judge)

    client.post(f"/crashtech/e/{event.slug}/judging/entry/{submission.pk}/", {
        "grade": "7", "note": "Genuinely surprising.",
    })
    submission.refresh_from_db()
    assert scoring.points_for(submission) == 28  # 7/10 of 40


def test_the_criteria_are_on_the_grading_screen(client):
    """A grade given against remembered criteria is a different grade from
    one given against the written ones, and the team was told what they
    were."""
    event = _event()
    challenge = _challenge(event, criteria="Does it do something nobody asked for?")
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)
    team = _team(event, "p@example.com", ordinal=1)
    submission = Submission.objects.create(challenge=challenge, team=team, is_finalist=True)
    client.force_login(judge)

    body = client.get(
        f"/crashtech/e/{event.slug}/judging/entry/{submission.pk}/"
    ).content.decode()
    assert "Does it do something nobody asked for?" in body


def test_something_not_shortlisted_cannot_be_graded():
    event = _event()
    challenge = _challenge(event)
    team = _team(event, "p@example.com")
    submission = Submission.objects.create(challenge=challenge, team=team, is_finalist=False)
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)

    with pytest.raises(judging.JudgingError):
        judging.grade(submission, judge, 8)


def test_a_grade_outside_the_range_is_refused_in_words():
    event = _event()
    challenge = _challenge(event, max_grade=10)
    team = _team(event, "p@example.com")
    submission = Submission.objects.create(challenge=challenge, team=team, is_finalist=True)
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)

    with pytest.raises(judging.JudgingError) as caught:
        judging.grade(submission, judge, 14)
    assert "0 to 10" in str(caught.value)


def test_a_judge_regrading_replaces_their_own_grade_and_not_anothers():
    event = _event()
    challenge = _challenge(event, points=10, max_grade=10)
    team = _team(event, "p@example.com")
    submission = Submission.objects.create(challenge=challenge, team=team, is_finalist=True)
    first = _with_role(event, "j1@example.com", EventRole.JUDGE)
    second = _with_role(event, "j2@example.com", EventRole.JUDGE)

    judging.grade(submission, first, 4)
    judging.grade(submission, second, 8)
    judging.grade(submission, first, 6)

    assert submission.grades.count() == 2
    assert scoring.points_for(submission) == 7  # (6 + 8) / 2


# ---------------------------------------------------- F-C.5.4 the spot check


def test_the_spot_check_offers_only_the_scores_that_decide_the_outcome():
    """Rule 8.3, and the single most important restraint in this sprint.
    A screen listing every submission is read as an instruction to check
    every submission, and the trust model collapses into the 2026 one."""
    event = _event()
    challenge = _challenge(event, kind=Challenge.MEASURED, rank_points=[50, 30, 20])
    for n in range(9):
        team = _team(event, f"p{n}@example.com", name=f"Team {n}", ordinal=n + 1)
        Submission.objects.create(challenge=challenge, team=team, reported_value=n * 10)

    queue = judging.spot_check_queue(event, per_challenge=3)
    assert len(queue) == 3
    # And they are the top three, not the first three entered.
    assert [int(s.reported_value) for s in queue] == [80, 70, 60]


def test_the_spot_check_screen_says_that_leaving_it_alone_is_normal(client):
    event = _event()
    challenge = _challenge(event, kind=Challenge.MEASURED, rank_points=[50])
    team = _team(event, "p@example.com", ordinal=1)
    Submission.objects.create(challenge=challenge, team=team, reported_value=100)
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)
    client.force_login(judge)

    body = client.get(f"/crashtech/e/{event.slug}/verify/").content.decode()
    assert "Leaving one alone is the normal answer" in body
    assert "own word" in body


def test_unverified_is_a_final_and_respectable_state():
    """It is not a gap in the record. Nothing anywhere treats it as
    unfinished, including the publish gate."""
    event = _event()
    challenge, team, submission, judge = _settled(event)
    measured = _challenge(event, kind=Challenge.MEASURED, title="Fmax", rank_points=[50])
    Submission.objects.create(challenge=measured, team=team, reported_value=100)

    assert judging.can_publish(event) is True


def test_a_dispute_needs_a_reason(client):
    """It takes points off a team in a way they can read later."""
    event = _event()
    challenge = _challenge(event, kind=Challenge.MEASURED, rank_points=[50])
    team = _team(event, "p@example.com", ordinal=1)
    submission = Submission.objects.create(challenge=challenge, team=team, reported_value=100)
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)

    with pytest.raises(judging.JudgingError) as caught:
        judging.verify(submission, judge, Submission.DISPUTED, note="")
    assert "reason" in str(caught.value)
    submission.refresh_from_db()
    assert submission.verification == Submission.UNVERIFIED


def test_verifying_a_submission_records_who_and_when(client):
    event = _event()
    challenge = _challenge(event, kind=Challenge.MEASURED, rank_points=[50])
    team = _team(event, "p@example.com", ordinal=1)
    submission = Submission.objects.create(challenge=challenge, team=team, reported_value=100)
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)
    client.force_login(judge)

    client.post(f"/crashtech/e/{event.slug}/verify/", {
        "submission": submission.pk, "outcome": Submission.VERIFIED,
    })
    submission.refresh_from_db()
    assert submission.verification == Submission.VERIFIED
    assert submission.verified_by == judge
    assert submission.verified_at is not None


# ----------------------------------------------------- F-C.5.6 the one click


def test_publishing_is_blocked_while_a_shortlisted_entry_has_no_grade():
    event = _event()
    challenge = _challenge(event)
    team = _team(event, "p@example.com", ordinal=1)
    Submission.objects.create(challenge=challenge, team=team, is_finalist=True)

    blockers = judging.publish_blockers(event)
    assert any("no grade" in b.text for b in blockers)
    assert judging.can_publish(event) is False


def test_publishing_is_blocked_while_a_creativity_challenge_has_no_shortlist():
    """Publishing then would mean nobody ever looked at them, which is
    worse than a low score."""
    event = _event()
    challenge = _challenge(event, title="Most elegant")
    team = _team(event, "p@example.com", ordinal=1)
    Submission.objects.create(challenge=challenge, team=team)

    blockers = judging.publish_blockers(event)
    assert any("Most elegant" in b.text for b in blockers)


def test_publishing_is_blocked_while_something_is_disputed():
    event = _event()
    challenge, team, submission, judge = _settled(event)
    measured = _challenge(event, kind=Challenge.MEASURED, title="Fmax", rank_points=[50])
    contested = Submission.objects.create(challenge=measured, team=team, reported_value=100)
    judging.verify(contested, judge, Submission.DISPUTED, note="The report does not match.")

    assert judging.can_publish(event) is False
    assert any("disputed" in b.text for b in judging.publish_blockers(event))


def test_publishing_is_blocked_before_the_event_closes():
    now = timezone.now()
    event = _event(
        status=Hackathon.LIVE,
        starts_at=now - timezone.timedelta(hours=2),
        ends_at=now + timezone.timedelta(hours=22),
        submission_deadline=now + timezone.timedelta(hours=22),
    )
    assert judging.can_publish(event) is False


def test_the_publish_screen_states_all_three_consequences_before_the_button(client):
    """Rule 11.7. "Are you sure" tells nobody anything."""
    event = _event()
    _settled(event)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)

    body = client.get(f"/crashtech/e/{event.slug}/publish/").content.decode()
    assert "permanent" in body
    assert "museum opens" in body
    assert "cannot be undone" in body
    assert "Publish, permanently" in body


def test_the_blockers_are_named_rather_than_counted(client):
    """Rule 11.6 again: the specific thing, not "3 items outstanding"."""
    event = _event()
    challenge = _challenge(event, title="Most elegant")
    team = _team(event, "p@example.com", ordinal=1)
    Submission.objects.create(challenge=challenge, team=team)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)

    body = client.get(f"/crashtech/e/{event.slug}/publish/").content.decode()
    assert "Most elegant" in body
    assert "Publish, permanently" not in body


def test_a_stale_tab_cannot_publish_half_judged_results(client):
    """The screen hiding the button is a courtesy to the person. The
    refusal has to live in the view too, or one open tab publishes
    permanent results."""
    event = _event()
    challenge = _challenge(event)
    team = _team(event, "p@example.com", ordinal=1)
    Submission.objects.create(challenge=challenge, team=team, is_finalist=True)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)

    client.post(f"/crashtech/e/{event.slug}/publish/")
    event.refresh_from_db()
    assert event.results_published_at is None
    assert event.status == Hackathon.CLOSED


def test_publishing_does_all_three_things_at_once(client):
    event = _event()
    challenge, team, submission, judge = _settled(event)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)

    client.post(f"/crashtech/e/{event.slug}/publish/")
    event.refresh_from_db()

    assert event.results_published_at is not None     # standings public
    assert event.status == Hackathon.MUSEUM           # museum open
    assert Certificate.objects.filter(hackathon=event).exists()  # certificates


def test_publishing_freezes_the_scores():
    """Up to this moment every score is computed, which is right while
    things can still move. From here the museum has to show the same
    numbers in five years whatever anybody later edits."""
    event = _event()
    challenge, team, submission, judge = _settled(event)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)

    judging.publish(event, by=admin)
    submission.refresh_from_db()
    assert submission.final_points == 32  # 8/10 of 40

    # Something changes afterwards. The frozen number must not.
    JudgeGrade.objects.filter(submission=submission).update(grade=2)
    submission.refresh_from_db()
    assert submission.final_points == 32


def test_publishing_twice_is_refused(client):
    event = _event()
    _settled(event)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)

    client.post(f"/crashtech/e/{event.slug}/publish/")
    event.refresh_from_db()
    first = event.results_published_at

    client.post(f"/crashtech/e/{event.slug}/publish/")
    event.refresh_from_db()
    assert event.results_published_at == first


def test_the_standings_become_public_on_publishing(client):
    event = _event(leaderboard_visibility=Hackathon.ADMINS_ONLY)
    challenge, team, submission, judge = _settled(event)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    judging.publish(event, by=admin)

    stranger = _user("stranger@example.com")
    client.force_login(stranger)
    response = client.get(f"/crashtech/e/{event.slug}/standings/")
    assert response.status_code == 200
    assert "Final" in response.content.decode()


# ----------------------------------------------------- F-C.5.7 certificates


def test_everybody_who_submitted_gets_a_certificate():
    """A participation certificate is not a consolation prize. It is the
    thing somebody puts on a CV two years later, which is most of what a
    hackathon is worth to most of the people in it."""
    event = _event()
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)
    # Distinct scores, so the places are distinct. Equal scores share a
    # place, and that has its own test; this one used to give five teams
    # level on points one winner and two runners-up by sign-up order.
    for n in range(5):
        challenge = _challenge(
            event, kind=Challenge.COMPLETION, points=50 - n * 10, title=f"Task {n}",
        )
        team = _team(event, f"p{n}@example.com", name=f"Team {n}", ordinal=n + 1)
        Submission.objects.create(
            challenge=challenge, team=team, claimed_complete=True,
        )
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    judging.publish(event, by=admin)

    assert Certificate.objects.filter(hackathon=event).count() == 5
    assert Certificate.objects.filter(type=Certificate.WINNER).count() == 1
    assert Certificate.objects.filter(type=Certificate.RUNNER_UP).count() == 2


def test_a_team_that_turned_in_nothing_gets_no_certificate():
    event = _event()
    challenge, team, submission, judge = _settled(event)
    _team(event, "ghost@example.com", name="Ghost", ordinal=9)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    judging.publish(event, by=admin)

    assert not Certificate.objects.filter(team__name="Ghost").exists()


def test_a_certificate_is_public_permanent_and_unguessable(client):
    """Rule 8.6. The person opening it is following a link on a CV two
    years later, and an account wall is how they decide it is not worth
    it."""
    event = _event()
    challenge, team, submission, judge = _settled(event)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    judging.publish(event, by=admin)
    certificate = Certificate.objects.get(team=team)

    # No session at all.
    anonymous = client.__class__()
    response = anonymous.get(f"/crashtech/c/{certificate.cert_id}/")
    assert response.status_code == 200
    body = response.content.decode()
    assert team.name in body
    assert event.name in body

    # And the id is a uuid4, not a sequence anybody can walk.
    assert certificate.cert_id.version == 4
    assert anonymous.get(f"/crashtech/c/{uuid.uuid4()}/").status_code == 404


def test_a_certificate_shows_the_frozen_score(client):
    event = _event()
    challenge, team, submission, judge = _settled(event)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    judging.publish(event, by=admin)
    certificate = Certificate.objects.get(team=team)

    body = client.__class__().get(f"/crashtech/c/{certificate.cert_id}/").content.decode()
    assert "32" in body


# ------------------------------------------------------- the seal, and dates


def test_every_c5_screen_refuses_a_signed_out_visitor_into_crashtechs_own_login(client):
    """The production seal (Rule 2.2.2). The assertion is on the
    DESTINATION, because a redirect to /accounts/login/ also contains the
    substring "/login/"."""
    event = _event()
    challenge, team, submission, judge = _settled(event)
    for url in (
        f"/crashtech/e/{event.slug}/judging/",
        f"/crashtech/e/{event.slug}/judging/{challenge.pk}/shortlist/",
        f"/crashtech/e/{event.slug}/judging/entry/{submission.pk}/",
        f"/crashtech/e/{event.slug}/verify/",
        f"/crashtech/e/{event.slug}/publish/",
    ):
        response = client.get(url)
        assert response.status_code == 302, url
        assert response.url.startswith("/crashtech/login/"), (url, response.url)


def test_the_certificate_is_the_one_screen_that_stays_open(client):
    """Deliberately not behind the seal, which is the whole point of it."""
    event = _event()
    challenge, team, submission, judge = _settled(event)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    judging.publish(event, by=admin)
    certificate = Certificate.objects.get(team=team)

    assert client.get(f"/crashtech/c/{certificate.cert_id}/").status_code == 200


def test_no_c5_screen_renders_a_hebrew_date(client):
    """Rule 2.2.4. The project's LANGUAGE_CODE is Hebrew and Django
    localises month names, so a template with no Hebrew in it still
    rendered Hebrew."""
    event = _event()
    challenge, team, submission, judge = _settled(event)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    judging.publish(event, by=admin)
    certificate = Certificate.objects.get(team=team)

    hebrew = "אבגדהוזחטיכלמנסעפצקרשת"
    client.force_login(admin)
    for url in (
        f"/crashtech/e/{event.slug}/publish/",
        f"/crashtech/c/{certificate.cert_id}/",
        f"/crashtech/e/{event.slug}/standings/",
    ):
        body = client.get(url).content.decode()
        assert not any(letter in body for letter in hebrew), url


def test_a_judge_has_a_way_into_their_own_screens(client):
    """A judge is not an admin, so `can_manage` does not reach the judging
    links and the navigation would leave them with no way in at all."""
    event = _event()
    _settled(event)
    judge = _with_role(event, "judge2@example.com", EventRole.JUDGE)
    client.force_login(judge)

    body = client.get(f"/crashtech/e/{event.slug}/").content.decode()
    assert f"/crashtech/e/{event.slug}/judging/" in body


# ------------------------------------- what a screenshot found (Rule 14.3)


def test_an_admin_can_follow_the_publish_screens_own_links(client):
    """The publish screen told an admin that three entries had no grade and
    linked them at the judging screen, which refused them.

    The one screen that tells an admin what is blocking publication was
    linking them somewhere they are forbidden. Reading judging is not
    judging: they can watch, they still cannot grade.
    """
    event = _event()
    challenge = _challenge(event, title="Most elegant")
    team = _team(event, "p@example.com", ordinal=1)
    Submission.objects.create(challenge=challenge, team=team, is_finalist=True)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)

    body = client.get(f"/crashtech/e/{event.slug}/publish/").content.decode()
    links = re.findall(r'href="(/crashtech/e/[^"]+)"', body)
    followed = [u for u in links if "/judging/" in u or "/shortlist/" in u]
    assert followed, "the blocker offered no way to the screen that clears it"
    for url in followed:
        assert client.get(url).status_code == 200, url


def test_an_admin_watching_judging_still_cannot_grade_or_shortlist(client):
    event = _event()
    challenge = _challenge(event)
    team = _team(event, "p@example.com", ordinal=1)
    submission = Submission.objects.create(challenge=challenge, team=team)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    client.force_login(admin)

    assert client.post(
        f"/crashtech/e/{event.slug}/judging/{challenge.pk}/shortlist/",
        {"submission": submission.pk, "on": "1"},
    ).status_code == 403
    submission.refresh_from_db()
    assert submission.is_finalist is False


def test_a_participant_still_cannot_read_the_judging_screens(client):
    """Widening a capability is where a wall quietly goes. Reading judging
    reached admins; it must not have reached everybody."""
    event = _event()
    challenge = _challenge(event)
    participant = _with_role(event, "p@example.com", EventRole.PARTICIPANT)
    client.force_login(participant)
    for url in (
        f"/crashtech/e/{event.slug}/judging/",
        f"/crashtech/e/{event.slug}/judging/{challenge.pk}/shortlist/",
        f"/crashtech/e/{event.slug}/verify/",
    ):
        assert client.get(url).status_code == 403, url


def test_the_ungraded_blocker_names_the_challenge_it_is_in(client):
    """"3 entries somewhere" is not something an admin can act on, and the
    whole point of that list is that each line leads to the screen that
    clears it."""
    event = _event()
    first = _challenge(event, title="Most elegant")
    second = _challenge(event, title="Best use of a spare pin")
    for n, challenge in enumerate((first, second)):
        team = _team(event, f"p{n}@example.com", name=f"Team {n}", ordinal=n + 1)
        Submission.objects.create(challenge=challenge, team=team, is_finalist=True)

    texts = [b.text for b in judging.publish_blockers(event)]
    assert any("Most elegant" in t for t in texts)
    assert any("Best use of a spare pin" in t for t in texts)


def test_a_shortlisted_card_is_marked_as_shortlisted(client):
    """With seventy entries, reading the button text on each one to find
    out which are in is not a comparison any more."""
    event = _event()
    challenge = _challenge(event)
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)
    chosen = _team(event, "in@example.com", name="In", ordinal=1)
    _team(event, "out@example.com", name="Out", ordinal=2)
    Submission.objects.create(challenge=challenge, team=chosen, is_finalist=True)
    Submission.objects.create(
        challenge=challenge, team=event.teams.get(name="Out"), is_finalist=False,
    )
    client.force_login(judge)

    body = client.get(
        f"/crashtech/e/{event.slug}/judging/{challenge.pk}/shortlist/"
    ).content.decode()
    assert "Shortlisted" in body
    assert "border-color:var(--ct-primary)" in body


def test_the_spot_check_shows_the_teams_own_note(client):
    """The first thing somebody checking a reported number wants to read,
    and it was missing from the first version."""
    event = _event()
    challenge = _challenge(event, kind=Challenge.MEASURED, rank_points=[50])
    team = _team(event, "p@example.com", ordinal=1)
    Submission.objects.create(
        challenge=challenge, team=team, reported_value=200,
        reported_note="Pipelined twice; the report is the screenshot.",
    )
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)
    client.force_login(judge)

    body = client.get(f"/crashtech/e/{event.slug}/verify/").content.decode()
    assert "Pipelined twice" in body


def test_the_spot_check_names_each_challenge_once(client):
    """Two measured challenges in a flat list repeated the same heading six
    times, which buries the one thing that distinguishes the rows."""
    event = _event()
    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)
    challenge = _challenge(
        event, kind=Challenge.MEASURED, title="Fastest multiplier", rank_points=[50, 30, 20],
    )
    for n in range(3):
        team = _team(event, f"p{n}@example.com", name=f"Team {n}", ordinal=n + 1)
        Submission.objects.create(challenge=challenge, team=team, reported_value=n * 10 + 5)
    client.force_login(judge)

    body = client.get(f"/crashtech/e/{event.slug}/verify/").content.decode()
    assert body.count("Fastest multiplier") == 1
