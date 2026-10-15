"""SPR-C.4 — CrashTech: challenges and submitting.

Three kinds of challenge, what each one is worth, and the twenty-four
hours in which a team turns work in.

Two things carry most of the weight here.

**Secrecy** (Rule 7.1). A challenge is invisible before kickoff, and not
as a hint, a count, or a greyed-out row. The leak that matters is the
cheap one: a participant who learns there are seven challenges has learned
something, and a count is the easiest thing to leave in by accident. So
the tests check the rendered bytes, not just the queryset.

**Trust, and the one exception to it** (Rule 7.4, 8.2). Completion and
measured challenges score the instant a team reports; creativity scores
only when a judge has graded it, and until then it must never render as
`0`, because a zero reads as a failed attempt rather than a pending one.
"""

import re

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from crashtech import scoring, submissions
from crashtech.models import (
    Challenge, Deliverable, EventRole, Hackathon, JudgeGrade, Milestone,
    Registration, Submission, SubmissionFile, Team, TeamMembership,
    UploadToken,
)

pytestmark = [pytest.mark.sprc4, pytest.mark.django_db]


def _event(**kwargs):
    now = timezone.now()
    defaults = dict(
        name="CrashTech VLSI 2027", status=Hackathon.LIVE,
        starts_at=now - timezone.timedelta(hours=2),
        ends_at=now + timezone.timedelta(hours=22),
        submission_deadline=now + timezone.timedelta(hours=22),
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


def _team(event, *emails, name=""):
    """A team with its people, accepted, which is the state submitting needs."""
    team = Team.objects.create(hackathon=event, name=name or f"Team {emails[0][:4]}")
    for email in emails:
        user = _with_role(event, email, EventRole.PARTICIPANT)
        Registration.objects.create(hackathon=event, user=user, status=Registration.ACCEPTED)
        TeamMembership.objects.create(hackathon=event, team=team, user=user)
    return team


def _challenge(event, kind=Challenge.COMPLETION, **kwargs):
    defaults = dict(
        hackathon=event, title="Make the LED blink", kind=kind, points=50,
        visible=event.status == Hackathon.LIVE,
    )
    defaults.update(kwargs)
    return Challenge.objects.create(**defaults)


def _deliverable(challenge, **kwargs):
    defaults = dict(challenge=challenge, label="Source files", kind=Deliverable.FILE, required=True)
    defaults.update(kwargs)
    return Deliverable.objects.create(**defaults)


def _member(team):
    return team.memberships.first().user


# ------------------------------------------------------------ F-C.4.1 kinds


def test_a_tech_lead_can_write_a_challenge_of_each_kind(client):
    event = _event(status=Hackathon.SETUP)
    lead = _with_role(event, "lead@example.com", EventRole.TECH_LEAD)
    client.force_login(lead)

    for kind in (Challenge.COMPLETION, Challenge.MEASURED, Challenge.CREATIVITY):
        response = client.post(f"/crashtech/e/{event.slug}/challenges/new/", {
            "title": f"A {kind} challenge", "kind": kind, "points": "40",
        })
        assert response.status_code == 302

    assert set(event.challenges.values_list("kind", flat=True)) == {
        Challenge.COMPLETION, Challenge.MEASURED, Challenge.CREATIVITY,
    }


def test_the_kind_picker_explains_each_kind_on_the_screen(client):
    """Rule 7.2: the choice between the three is the most consequential one
    a tech lead makes and three words do not carry it. A lead who picks
    completion for everything has rebuilt the event the feedback
    complained about."""
    event = _event(status=Hackathon.SETUP)
    lead = _with_role(event, "lead@example.com", EventRole.TECH_LEAD)
    client.force_login(lead)

    body = client.get(f"/crashtech/e/{event.slug}/challenges/new/").content.decode()
    # Not the labels, which are one word each: the explanation of what the
    # choice means.
    assert "finishing position" in body
    assert "judged later" in body or "judges" in body.lower()
    assert "straight away" in body


def test_only_a_tech_lead_may_author_challenges(client):
    """Rule 4.1: authoring is the tech lead's, and an admin running the
    event is not automatically the person writing the tasks."""
    event = _event(status=Hackathon.SETUP)
    participant = _with_role(event, "p@example.com", EventRole.PARTICIPANT)
    client.force_login(participant)
    assert client.get(f"/crashtech/e/{event.slug}/challenges/new/").status_code == 403


def test_a_newly_written_challenge_is_never_visible_yet(client):
    """Rule 7.1. The default has to be invisible whatever the event's
    status, because a challenge written during a live event would
    otherwise appear the instant it was saved."""
    event = _event(status=Hackathon.LIVE)
    lead = _with_role(event, "lead@example.com", EventRole.TECH_LEAD)
    client.force_login(lead)

    client.post(f"/crashtech/e/{event.slug}/challenges/new/", {
        "title": "Written late", "kind": Challenge.COMPLETION, "points": "10",
    })
    assert event.challenges.get(title="Written late").visible is False


def test_rank_points_survive_being_typed_either_way(client):
    """A tech lead types this once, under time pressure. A comma instead of
    a space is not a validation error worth having."""
    event = _event(status=Hackathon.SETUP)
    lead = _with_role(event, "lead@example.com", EventRole.TECH_LEAD)
    client.force_login(lead)

    client.post(f"/crashtech/e/{event.slug}/challenges/new/", {
        "title": "Fastest", "kind": Challenge.MEASURED, "points": "0",
        "rank_points": "50, 30 20,10",
    })
    assert event.challenges.get().rank_points == [50, 30, 20, 10]


# ----------------------------------------------------- F-C.4.2 deliverables


def test_deliverables_are_declared_per_challenge(client):
    """Rule 7.3. In 2026 every submission was one zip field, identical for
    every challenge, which is why nothing could say what was missing."""
    event = _event(status=Hackathon.SETUP)
    lead = _with_role(event, "lead@example.com", EventRole.TECH_LEAD)
    challenge = _challenge(event)
    client.force_login(lead)

    client.post(f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/edit/", {
        "add_deliverable": "1", "label": "Timing report", "kind": Deliverable.IMAGE,
        "purpose": Deliverable.PROOF, "required": "1",
    })
    item = challenge.deliverables.get()
    assert item.label == "Timing report"
    assert item.purpose == Deliverable.PROOF
    assert item.required is True


def test_a_challenge_with_no_required_deliverable_is_not_finished():
    """Rule 3.4: it must not look identical to one that is, which is what
    the readiness checklist reads."""
    event = _event()
    challenge = _challenge(event)
    assert challenge.is_finished is False
    _deliverable(challenge)
    assert challenge.is_finished is True


def test_a_challenge_with_submissions_cannot_be_deleted(client):
    """Deleting it would delete somebody's night."""
    event = _event()
    lead = _with_role(event, "lead@example.com", EventRole.TECH_LEAD)
    challenge = _challenge(event)
    team = _team(event, "a@example.com")
    Submission.objects.create(challenge=challenge, team=team)

    client.force_login(lead)
    client.post(f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/edit/", {"delete": "1"})
    assert Challenge.objects.filter(pk=challenge.pk).exists()


def test_a_video_deliverable_is_link_only():
    """Rule 7.5, the single decision that turns roughly 26 GB of phone
    video per event into nothing at all on our disk."""
    event = _event()
    challenge = _challenge(event)
    video = _deliverable(challenge, label="Demo video", kind=Deliverable.VIDEO)
    assert video.is_link_only is True
    assert _deliverable(challenge, label="Photo", kind=Deliverable.IMAGE).is_link_only is False


# --------------------------------------------------------- F-C.4.3 preview


def test_a_tech_lead_can_see_exactly_the_participants_screen(client):
    """user_journeys.md 2.2. A challenge is written days early and read
    once, at speed. This is the only chance to notice the brief never says
    what to actually turn in."""
    event = _event(status=Hackathon.SETUP)
    lead = _with_role(event, "lead@example.com", EventRole.TECH_LEAD)
    challenge = _challenge(event, kind=Challenge.MEASURED, metric_name="Fmax", metric_unit="MHz")
    _deliverable(challenge, label="Timing report")
    client.force_login(lead)

    body = client.get(
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/preview/"
    ).content.decode()
    assert "Timing report" in body
    assert "Fmax" in body
    # And it says, unmistakably, that it is the preview.
    assert "Nothing you type here is saved" in body


def test_the_preview_cannot_actually_save_anything(client):
    event = _event(status=Hackathon.SETUP)
    lead = _with_role(event, "lead@example.com", EventRole.TECH_LEAD)
    challenge = _challenge(event)
    client.force_login(lead)

    client.post(f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/preview/", {
        "claimed_complete": "1",
    })
    assert not Submission.objects.exists()


# --------------------------------------------------------- F-C.4.4 secrecy


def test_a_participant_sees_nothing_before_kickoff(client):
    """Rule 7.1 and 14.2. Not a hint, not a count, not a greyed-out list.

    The assertion is on the rendered bytes, because a queryset returning
    nothing while the template prints `{{ challenges.count }}` is exactly
    the leak this rule exists to stop.
    """
    event = _event(status=Hackathon.KITS)
    for n in range(7):
        _challenge(event, title=f"Secret task {n}", visible=False)
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    body = client.get(f"/crashtech/e/{event.slug}/challenges/").content.decode()
    assert "Secret task" not in body
    assert "sealed until the event starts" in body


def test_the_sealed_screen_is_identical_however_many_challenges_exist(client):
    """The sharper form of Rule 7.1, and the one worth having.

    "No count" is hard to assert by looking for a digit: this event is
    called "VLSI 2027" and the first attempt at this test tripped over the
    7 in the year. The real property is stronger and exact: the page a
    participant gets before kickoff must not depend in any way on how many
    challenges have been written. So render it with none, render it with
    seven, and require the two to be the same bytes.
    """
    event = _event(status=Hackathon.KITS)
    team = _team(event, "p@example.com")
    client.force_login(_member(team))
    url = f"/crashtech/e/{event.slug}/challenges/"

    def rendered():
        # The CSRF token rotates on every response and is the one byte
        # sequence that legitimately differs, so it is masked rather than
        # letting it weaken the assertion to something vaguer.
        return re.sub(
            r'name="csrfmiddlewaretoken" value="[^"]+"',
            'name="csrfmiddlewaretoken" value="MASKED"',
            client.get(url).content.decode(),
        )

    empty = rendered()

    for n in range(7):
        challenge = _challenge(event, title=f"Secret task {n}", visible=False)
        _deliverable(challenge)
    assert rendered() == empty


def test_a_participant_cannot_reach_a_challenge_by_guessing_its_id(client):
    """The list screen hiding them is a courtesy. The refusal has to live
    on the challenge itself or the secrecy is cosmetic."""
    event = _event(status=Hackathon.KITS)
    challenge = _challenge(event, visible=False)
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    response = client.get(f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/")
    assert response.status_code == 403


def test_the_people_running_the_event_do_see_them_before_kickoff(client):
    """Rule 4.5. Writing them in advance is the entire point, and a judge
    reads them to prepare."""
    event = _event(status=Hackathon.KITS)
    _challenge(event, title="Secret task", visible=False)

    for role in (EventRole.TECH_LEAD, EventRole.ADMIN, EventRole.JUDGE):
        person = _with_role(event, f"{role}@example.com", role)
        client.force_login(person)
        body = client.get(f"/crashtech/e/{event.slug}/challenges/").content.decode()
        assert "Secret task" in body, role


def test_the_navigation_hides_the_challenges_link_before_kickoff(client):
    """Rule 11.5: never show a control that cannot be used yet. A link that
    403s is worse than no link, and on this screen it also confirms there
    is something behind it."""
    event = _event(status=Hackathon.KITS)
    _challenge(event, visible=False)
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    body = client.get(f"/crashtech/e/{event.slug}/teams/").content.decode()
    assert f"/crashtech/e/{event.slug}/challenges/" not in body


# --------------------------------------------------------- F-C.4.5 kickoff


def test_going_live_reveals_every_challenge_at_once(client):
    """Rule 3.2. All of them, one click, irreversible."""
    now = timezone.now()
    event = _event(
        status=Hackathon.KITS,
        starts_at=now + timezone.timedelta(hours=1),
        ends_at=now + timezone.timedelta(hours=25),
        submission_deadline=now + timezone.timedelta(hours=25),
    )
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    _with_role(event, "judge@example.com", EventRole.JUDGE)
    for n in range(3):
        challenge = _challenge(event, title=f"Task {n}", visible=False)
        _deliverable(challenge)
    team = _team(event, "p@example.com")
    team.kit_issues.create(hackathon=event, status="collected")

    client.force_login(admin)
    client.post(f"/crashtech/e/{event.slug}/advance/")

    event.refresh_from_db()
    assert event.status == Hackathon.LIVE
    assert event.challenges.filter(visible=False).count() == 0


def test_the_kickoff_click_states_its_consequence_before_it_is_pressed():
    """Rule 11.7. "This cannot be undone" has to be on the screen, in
    words, not implied by the button's colour."""
    from crashtech.readiness import consequence_of_advancing

    event = _event(status=Hackathon.KITS)
    words = consequence_of_advancing(event)
    assert "at once" in words
    assert "cannot be undone" in words


# ------------------------------------------------------- F-C.4.6 checklist


def test_the_checklist_names_what_is_missing_rather_than_saying_incomplete(client):
    """Rule 11.6, and the 2026 complaint restated: "it was never clear
    whether a submission had actually gone through"."""
    event = _event()
    challenge = _challenge(event)
    _deliverable(challenge, label="Source files")
    _deliverable(challenge, label="Bench photo", kind=Deliverable.IMAGE)
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    body = client.get(
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/"
    ).content.decode()
    assert "Source files" in body
    assert "Bench photo" in body
    assert "incomplete" not in body.lower()


def test_a_partial_save_is_normal_and_keeps_what_was_given(client):
    """A team photographs the bench at 2am and types the number at 7am.
    Refusing anything until everything is in pushes both into the last ten
    minutes, which is when the wifi is worst."""
    event = _event()
    challenge = _challenge(event)
    notes = _deliverable(challenge, label="Approach", kind=Deliverable.TEXT)
    _deliverable(challenge, label="Source files")
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    client.post(f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/", {
        f"d{notes.pk}": "We pipelined the multiplier.",
    })
    submission = Submission.objects.get(team=team, challenge=challenge)
    assert submission.files.get(deliverable=notes).text_value == "We pipelined the multiplier."
    assert [d.label for d in submission.missing_deliverables] == ["Source files"]


def test_claiming_it_worked_is_refused_while_something_required_is_missing(client):
    """Rule 7.3. This is the claim the points are paid on and the one a
    judge may later spot-check, so it is the one thing that cannot be
    made early."""
    event = _event()
    challenge = _challenge(event)
    _deliverable(challenge, label="Source files")
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    client.post(f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/", {
        "claimed_complete": "1",
    })
    submission = Submission.objects.get(team=team, challenge=challenge)
    assert submission.claimed_complete is False
    assert scoring.points_for(submission) == 0


def test_the_refusal_says_which_deliverable_is_missing(client):
    event = _event()
    challenge = _challenge(event)
    _deliverable(challenge, label="Timing report")
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    response = client.post(
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/",
        {"claimed_complete": "1"}, follow=True,
    )
    assert "Timing report" in response.content.decode()


def test_one_submission_per_team_per_challenge_however_many_times_they_save(client):
    event = _event()
    challenge = _challenge(event)
    team = _team(event, "a@example.com", "b@example.com")
    first, second = [m.user for m in team.memberships.all()]

    client.force_login(first)
    client.post(f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/", {"reported_note": "one"})
    client.force_login(second)
    client.post(f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/", {"reported_note": "two"})

    assert Submission.objects.filter(team=team, challenge=challenge).count() == 1


def test_somebody_with_no_team_is_told_what_to_do_about_it(client):
    """Not a disabled button with no explanation beside it."""
    event = _event()
    challenge = _challenge(event)
    person = _with_role(event, "p@example.com", EventRole.PARTICIPANT)
    Registration.objects.create(hackathon=event, user=person, status=Registration.ACCEPTED)
    client.force_login(person)

    body = client.get(
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/"
    ).content.decode()
    assert "need a team" in body
    assert "team of one is fine" in body


# ---------------------------------------------------------- F-C.4.7 points


def test_a_completion_challenge_scores_the_moment_a_team_says_it_worked(client):
    """Rule 7.4, the inversion from 2026, where nothing scored until a
    judge acted."""
    event = _event()
    challenge = _challenge(event, points=50)
    _deliverable(challenge, label="Source files", kind=Deliverable.TEXT)
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    challenge_url = f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/"
    client.post(challenge_url, {
        f"d{challenge.deliverables.get().pk}": "here it is", "claimed_complete": "1",
    })
    submission = Submission.objects.get(team=team, challenge=challenge)
    assert submission.claimed_complete is True
    assert scoring.points_for(submission) == 50
    assert submission.verification == Submission.UNVERIFIED  # and that is final and fine


def test_a_measured_challenge_pays_by_finishing_position():
    event = _event()
    challenge = _challenge(
        event, kind=Challenge.MEASURED, points=0,
        metric_direction=Challenge.HIGHER, rank_points=[50, 30, 20],
    )
    scores = {}
    for name, value in (("fast", 180), ("mid", 120), ("slow", 90), ("last", 10)):
        team = _team(event, f"{name}@example.com", name=name)
        scores[name] = Submission.objects.create(
            challenge=challenge, team=team, reported_value=value,
        )
    scoring.recompute_challenge(challenge)

    assert scoring.points_for(scores["fast"]) == 50
    assert scoring.points_for(scores["mid"]) == 30
    assert scoring.points_for(scores["slow"]) == 20
    # Past the end of the list, which is a real outcome and not an error.
    assert scoring.points_for(scores["last"]) == 0


def test_lower_is_better_reverses_the_ranking():
    event = _event()
    challenge = _challenge(
        event, kind=Challenge.MEASURED, points=0,
        metric_direction=Challenge.LOWER, rank_points=[50, 30],
    )
    small = Submission.objects.create(
        challenge=challenge, team=_team(event, "s@example.com", name="small"), reported_value=12,
    )
    large = Submission.objects.create(
        challenge=challenge, team=_team(event, "l@example.com", name="large"), reported_value=900,
    )
    assert scoring.points_for(small) == 50
    assert scoring.points_for(large) == 30


def test_a_new_number_reorders_teams_who_did_nothing():
    """The consequence of ranked scoring, stated as a test so nobody later
    "fixes" it: a team's score moves when somebody else beats it."""
    event = _event()
    challenge = _challenge(
        event, kind=Challenge.MEASURED, points=0, rank_points=[50, 30],
    )
    sitting = Submission.objects.create(
        challenge=challenge, team=_team(event, "a@example.com", name="a"), reported_value=100,
    )
    scoring.recompute_challenge(challenge)
    assert scoring.points_for(sitting) == 50

    Submission.objects.create(
        challenge=challenge, team=_team(event, "b@example.com", name="b"), reported_value=150,
    )
    scoring.recompute_challenge(challenge)
    sitting.refresh_from_db()
    assert scoring.points_for(sitting) == 30


def test_a_measured_challenge_with_no_number_is_not_ranked_last():
    """It has not attempted the measurement. Ranking it would push a real
    attempt down a place."""
    event = _event()
    challenge = _challenge(event, kind=Challenge.MEASURED, points=0, rank_points=[50, 30])
    blank = Submission.objects.create(
        challenge=challenge, team=_team(event, "a@example.com", name="a"), reported_value=None,
    )
    real = Submission.objects.create(
        challenge=challenge, team=_team(event, "b@example.com", name="b"), reported_value=5,
    )
    assert scoring.points_for(blank) == 0
    assert scoring.points_for(real) == 50


def test_a_reported_number_is_a_decimal_and_not_a_float(client):
    """This number decides who wins. A float makes 10.1 unequal to 10.1."""
    event = _event()
    challenge = _challenge(event, kind=Challenge.MEASURED, points=0, rank_points=[10])
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    client.post(f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/", {
        "reported_value": "123.4500",
    })
    from decimal import Decimal
    assert Submission.objects.get().reported_value == Decimal("123.4500")


def test_a_number_that_is_not_a_number_is_refused_in_words(client):
    event = _event()
    challenge = _challenge(event, kind=Challenge.MEASURED, metric_name="Fmax", rank_points=[10])
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    response = client.post(
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/",
        {"reported_value": "quite fast"}, follow=True,
    )
    assert "Fmax has to be a number" in response.content.decode()
    assert Submission.objects.get().reported_value is None


def test_a_creativity_challenge_scores_nothing_until_a_judge_grades_it():
    """Rule 8.2. Not an exception to trust: there is no number to report
    and nothing a later spot check could compare against. A team cannot
    report its own originality any more than its own final placing."""
    event = _event()
    challenge = _challenge(event, kind=Challenge.CREATIVITY, points=40, max_grade=10)
    team = _team(event, "p@example.com")
    submission = Submission.objects.create(
        challenge=challenge, team=team, claimed_complete=True,
    )
    assert scoring.points_for(submission) == 0

    judge = _with_role(event, "judge@example.com", EventRole.JUDGE)
    JudgeGrade.objects.create(submission=submission, judge=judge, grade=8)
    assert scoring.points_for(submission) == 32  # 8/10 of 40


def test_two_judges_on_one_submission_are_averaged():
    """More than one may grade the same entry, and the first one to arrive
    should not decide it."""
    event = _event()
    challenge = _challenge(event, kind=Challenge.CREATIVITY, points=10, max_grade=10)
    team = _team(event, "p@example.com")
    submission = Submission.objects.create(challenge=challenge, team=team)
    for n, grade in enumerate((4, 8)):
        JudgeGrade.objects.create(
            submission=submission,
            judge=_with_role(event, f"j{n}@example.com", EventRole.JUDGE),
            grade=grade,
        )
    assert scoring.points_for(submission) == 6


def test_an_ungraded_creativity_submission_never_renders_as_zero(client):
    """Rule 11.8. A zero reads as a failed attempt, and this is a pending
    one. Found by looking at the screen, which is why the assertion is on
    the rendered page and not on the number."""
    event = _event()
    challenge = _challenge(event, kind=Challenge.CREATIVITY, points=40, title="Most elegant")
    team = _team(event, "p@example.com")
    Submission.objects.create(challenge=challenge, team=team, claimed_complete=True)
    client.force_login(_member(team))

    body = client.get(f"/crashtech/e/{event.slug}/challenges/").content.decode()
    assert "Judged later" in body
    assert "0 pts" not in body


def test_a_withdrawn_submission_scores_nothing():
    event = _event()
    challenge = _challenge(event, points=50)
    team = _team(event, "p@example.com")
    submission = Submission.objects.create(
        challenge=challenge, team=team, claimed_complete=True,
    )
    assert scoring.points_for(submission) == 50
    submissions.withdraw(submission)
    submission.refresh_from_db()
    assert scoring.points_for(submission) == 0


# ------------------------------------------------------------ F-C.4.8 video


def test_a_video_is_a_url_and_there_is_no_upload_control_for_one(client):
    """Rule 7.5. The sentence saying so is on the screen, so nobody spends
    ten minutes at 3am looking for a file picker that does not exist."""
    event = _event()
    challenge = _challenge(event)
    video = _deliverable(challenge, label="Demo video", kind=Deliverable.VIDEO)
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    body = client.get(
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/"
    ).content.decode()
    assert f'name="d{video.pk}" type="url"' in body
    assert f'name="d{video.pk}" type="file"' not in body
    assert "Videos are not uploaded here" in body


def test_a_video_link_satisfies_its_deliverable(client):
    event = _event()
    challenge = _challenge(event)
    video = _deliverable(challenge, label="Demo video", kind=Deliverable.VIDEO)
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    client.post(f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/", {
        f"d{video.pk}": "https://youtu.be/abc123",
    })
    submission = Submission.objects.get()
    assert submission.files.get(deliverable=video).url == "https://youtu.be/abc123"
    assert submission.is_complete is True


def test_something_that_is_not_a_link_is_refused_in_words(client):
    event = _event()
    challenge = _challenge(event)
    video = _deliverable(challenge, label="Demo video", kind=Deliverable.VIDEO)
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    response = client.post(
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/",
        {f"d{video.pk}": "its on my laptop"}, follow=True,
    )
    assert "has to be a link" in response.content.decode()


# ------------------------------------------------------- F-C.4.9 QR upload


def test_the_phone_gets_an_upload_link_that_needs_no_sign_in(client):
    """Rule 7.6. The laptop is signed in; the phone holding the camera is
    not, and nobody is typing a password into a phone at 3am."""
    event = _event()
    challenge = _challenge(event)
    photo = _deliverable(challenge, label="Bench photo", kind=Deliverable.IMAGE)
    team = _team(event, "p@example.com")
    client.force_login(_member(team))
    client.get(f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/")

    token = UploadToken.objects.get(team=team, challenge=challenge)
    anonymous = client.__class__()  # no session at all
    response = anonymous.get(f"/crashtech/upload/{token.token}/")
    assert response.status_code == 200
    assert "Bench photo" in response.content.decode()


def test_a_photo_posted_with_the_token_lands_on_the_right_team_and_challenge(client):
    event = _event()
    challenge = _challenge(event)
    photo = _deliverable(challenge, label="Bench photo", kind=Deliverable.IMAGE)
    other_team = _team(event, "other@example.com", name="Other")
    team = _team(event, "p@example.com", name="Ours")
    token = submissions.upload_token_for(team, challenge)

    anonymous = client.__class__()
    response = anonymous.post(f"/crashtech/upload/{token.token}/", {
        f"d{photo.pk}": SimpleUploadedFile("bench.jpg", b"\xff\xd8\xff", content_type="image/jpeg"),
    })
    assert response.status_code == 200
    submission = Submission.objects.get()
    assert submission.team == team
    assert submission.challenge == challenge
    assert Submission.objects.filter(team=other_team).count() == 0


def test_the_phone_is_told_what_landed_rather_than_just_success(client):
    """Rule 11.6, on the smallest screen in the product. This phone has no
    session to go and check with."""
    event = _event()
    challenge = _challenge(event)
    photo = _deliverable(challenge, label="Bench photo", kind=Deliverable.IMAGE)
    team = _team(event, "p@example.com")
    token = submissions.upload_token_for(team, challenge)

    anonymous = client.__class__()
    body = anonymous.post(f"/crashtech/upload/{token.token}/", {
        f"d{photo.pk}": SimpleUploadedFile("bench.jpg", b"\xff\xd8\xff", content_type="image/jpeg"),
    }).content.decode()
    assert "Bench photo" in body
    assert "Ours" in body or team.name in body


def test_an_expired_token_says_so_and_does_not_accept_anything(client):
    event = _event()
    challenge = _challenge(event)
    _deliverable(challenge, label="Bench photo", kind=Deliverable.IMAGE)
    team = _team(event, "p@example.com")
    token = submissions.upload_token_for(team, challenge)
    UploadToken.objects.filter(pk=token.pk).update(
        expires_at=timezone.now() - timezone.timedelta(hours=1),
    )

    anonymous = client.__class__()
    response = anonymous.get(f"/crashtech/upload/{token.token}/")
    assert response.status_code == 410
    assert "expired" in response.content.decode().lower()


def test_the_token_is_reused_so_a_refresh_does_not_break_the_qr_on_screen():
    event = _event()
    challenge = _challenge(event)
    team = _team(event, "p@example.com")
    first = submissions.upload_token_for(team, challenge)
    second = submissions.upload_token_for(team, challenge)
    assert first.token == second.token


# ----------------------------------------------- F-C.4.10 score visibility


def test_a_team_always_sees_its_own_score_even_while_standings_are_hidden(client):
    """Rule 8.4. "My points" and "where I rank" are different questions,
    and conflating them is what made 2026 feel like submitting into
    silence."""
    event = _event(leaderboard_visibility=Hackathon.ADMINS_ONLY)
    challenge = _challenge(event, points=50)
    team = _team(event, "p@example.com", name="Ours")
    Submission.objects.create(challenge=challenge, team=team, claimed_complete=True)
    client.force_login(_member(team))

    body = client.get(f"/crashtech/e/{event.slug}/challenges/").content.decode()
    assert "Your points" in body
    assert "50" in body


def test_the_standings_are_refused_to_a_participant_by_default(client):
    event = _event(leaderboard_visibility=Hackathon.ADMINS_ONLY)
    team = _team(event, "p@example.com")
    client.force_login(_member(team))
    assert client.get(f"/crashtech/e/{event.slug}/standings/").status_code == 403


def test_an_admin_can_see_the_standings_during_the_event(client):
    event = _event(leaderboard_visibility=Hackathon.ADMINS_ONLY)
    admin = _with_role(event, "admin@example.com", EventRole.ADMIN)
    challenge = _challenge(event, points=50)
    team = _team(event, "p@example.com", name="Ours")
    Submission.objects.create(challenge=challenge, team=team, claimed_complete=True)

    client.force_login(admin)
    body = client.get(f"/crashtech/e/{event.slug}/standings/").content.decode()
    assert "Ours" in body
    assert "Provisional" in body


def test_the_standings_open_to_everybody_once_results_are_published(client):
    event = _event(
        status=Hackathon.MUSEUM, leaderboard_visibility=Hackathon.ADMINS_ONLY,
        results_published_at=timezone.now(),
    )
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    response = client.get(f"/crashtech/e/{event.slug}/standings/")
    assert response.status_code == 200
    assert "Final" in response.content.decode()


def test_the_leaderboard_is_computed_and_not_read_from_a_stored_total():
    """Rule 8.4. A stored total is a second source of truth and goes stale
    the moment a verification changes a score."""
    event = _event()
    challenge = _challenge(event, points=50)
    team = _team(event, "p@example.com", name="Ours")
    submission = Submission.objects.create(
        challenge=challenge, team=team, claimed_complete=True,
    )
    # Poison the cache. The leaderboard must ignore it.
    Submission.objects.filter(pk=submission.pk).update(tentative_points=9999)

    assert scoring.leaderboard(event) == [(team, 50)]


def test_the_leaderboard_breaks_ties_stably():
    """Otherwise two equal scores reshuffle on every refresh, which looks
    like the numbers are moving when they are not."""
    event = _event()
    challenge = _challenge(event, points=10)
    first = _team(event, "a@example.com", name="First")
    second = _team(event, "b@example.com", name="Second")
    for team in (first, second):
        Submission.objects.create(challenge=challenge, team=team, claimed_complete=True)

    assert [t for t, _ in scoring.leaderboard(event)] == [first, second]
    assert [t for t, _ in scoring.leaderboard(event)] == [first, second]


# ------------------------------------------------------ the deadline, closing


def test_submissions_stop_at_the_deadline(client):
    """Rule 7.7: separate from the event ending, because a deadline before
    the close is a real organiser's choice."""
    now = timezone.now()
    event = _event(
        starts_at=now - timezone.timedelta(hours=25),
        ends_at=now + timezone.timedelta(hours=1),
        submission_deadline=now - timezone.timedelta(minutes=5),
    )
    challenge = _challenge(event)
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    client.post(f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/", {
        "reported_note": "late",
    })
    assert not Submission.objects.exists()


def test_a_closed_event_locks_submitting_and_says_why(client):
    event = _event(status=Hackathon.CLOSED)
    challenge = _challenge(event, visible=True)
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    body = client.get(
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/"
    ).content.decode()
    assert "closed when the event ended" in body


# ------------------------------------------------------- the seal, and dates


def test_every_c4_screen_refuses_a_signed_out_visitor_into_crashtechs_own_login(client):
    """The production seal (Rule 2.2.2), which has now broken twice on this
    site: a signed-out visitor must never be handed to babook's login.

    The assertion is on the DESTINATION, because a redirect to
    /accounts/login/ also contains the substring "/login/".
    """
    event = _event()
    challenge = _challenge(event)
    for url in (
        f"/crashtech/e/{event.slug}/challenges/",
        f"/crashtech/e/{event.slug}/challenges/new/",
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/edit/",
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/preview/",
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/",
        f"/crashtech/e/{event.slug}/standings/",
    ):
        response = client.get(url)
        assert response.status_code == 302, url
        assert response.url.startswith("/crashtech/login/"), (url, response.url)


def test_no_c4_screen_renders_a_hebrew_date(client):
    """Rule 2.2.4. The project's LANGUAGE_CODE is Hebrew, so Django
    localises month names and a template containing not one Hebrew
    character still rendered "14 אוק 2026". A screenshot caught it; this
    asserts on the rendered response, which is the only place it shows."""
    event = _event(status=Hackathon.SETUP)
    lead = _with_role(event, "lead@example.com", EventRole.TECH_LEAD)
    Milestone.objects.create(
        hackathon=event, kind=Milestone.KICKOFF, title="Kickoff",
        occurs_at=timezone.now(),
    )
    challenge = _challenge(event)
    client.force_login(lead)

    hebrew = "אבגדהוזחטיכלמנסעפצקרשת"
    for url in (
        f"/crashtech/e/{event.slug}/challenges/",
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/edit/",
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/preview/",
    ):
        body = client.get(url).content.decode()
        assert not any(letter in body for letter in hebrew), url


def test_every_c4_planning_screen_keeps_its_navigation(client):
    """The event screens strip the nav on purpose (the kit desk, the submit
    screen). The planning screens must not, because that is how somebody
    gets stranded."""
    event = _event(status=Hackathon.SETUP)
    lead = _with_role(event, "lead@example.com", EventRole.TECH_LEAD)
    challenge = _challenge(event)
    client.force_login(lead)

    for url in (
        f"/crashtech/e/{event.slug}/challenges/",
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/edit/",
    ):
        body = client.get(url).content.decode()
        assert f"/crashtech/e/{event.slug}/" in body, url
        assert "Overview" in body, url


# ------------------------------------- what a screenshot found (Rule 14.3)


def test_a_crashtech_refusal_renders_crashtechs_own_page_not_babooks(client):
    """Rule 2.2.1, and a break that had been live since C.1.

    Django's error handlers are project-wide, so every PermissionDenied
    under /crashtech/ was rendering babook's 403: its title, its chrome,
    its Hebrew. Every permission test asserted on the status code, and
    403 is 403 whichever page it is, so nothing caught it until a
    screenshot of one.
    """
    event = _event(leaderboard_visibility=Hackathon.ADMINS_ONLY)
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    response = client.get(f"/crashtech/e/{event.slug}/standings/")
    assert response.status_code == 403
    body = response.content.decode()
    assert "CRASHTECH" in body
    assert "babook" not in body.lower()


def test_a_missing_crashtech_page_renders_crashtechs_own_404(client):
    response = client.get("/crashtech/e/no-such-event/")
    assert response.status_code == 404
    assert "babook" not in response.content.decode().lower()


def test_a_reported_number_is_shown_as_it_was_typed(client):
    """`reported_value` is stored with four decimal places, so 188.5 comes
    back as 188.5000 and the field a team reopens at 3am shows a number
    they did not type. On the one field that decides the ranking, that
    reads as the system having changed their result."""
    event = _event()
    challenge = _challenge(event, kind=Challenge.MEASURED, metric_name="Fmax", rank_points=[10])
    team = _team(event, "p@example.com")
    client.force_login(_member(team))
    url = f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/"

    client.post(url, {"reported_value": "188.5"})
    body = client.get(url).content.decode()
    assert 'value="188.5"' in body
    assert "188.5000" not in body


def test_the_phone_upload_is_a_scannable_code_and_not_a_url_to_type(client):
    """Rule 7.6. Printing the link as text expects somebody to type forty
    characters of random token on a phone, which is not the feature."""
    event = _event()
    challenge = _challenge(event)
    _deliverable(challenge, label="Bench photo", kind=Deliverable.IMAGE)
    team = _team(event, "p@example.com")
    client.force_login(_member(team))

    body = client.get(
        f"/crashtech/e/{event.slug}/challenges/{challenge.pk}/submit/"
    ).content.decode()
    assert 'src="data:image/png;base64,' in body
    assert "QR code" in body


def test_emphasis_inside_a_row_does_not_break_the_sentence():
    """A CSS descendant selector made every nested <b> inside a row a
    block, so emphasis mid-sentence broke the line and left the next
    clause starting with a colon. Asserting on the stylesheet because
    that is where the bug was and a rendered page cannot see it."""
    css = open("static/crashtech/crashtech.css", encoding="utf-8").read()
    assert ".ct-row-main > b { display: block;" in css
    assert ".ct-row-main b { display: block;" not in css


def test_no_crashtech_route_shadows_the_2026_platform(client):
    """Rule 13.1: the old platform is reference and keeps working until
    C.8 retires it.

    This app is mounted **before** `app.urls`, so a path we claim that it
    already owns does not error, it silently takes a working route away
    from it. That has now happened twice: `/crashtech/new/` in C.1, and
    `/crashtech/u/<token>/` in C.4, where the new QR upload swallowed the
    old one and its own test was the only thing that noticed.

    So this asserts the general rule rather than those two cases: every
    route the 2026 platform declares still resolves to the 2026 platform.
    """
    # The one route CrashTech takes from the old platform on purpose.
    # Rule 2.1.3 mounts this app at /crashtech/ and C.8 retires the old
    # front door; everything else is an accident until then.
    DELIBERATE = {"/crashtech/"}

    stolen = []

    # The old platform's routes all live in `app.urls` and all point at
    # `app.crashtech_views`. Walk them, build a concrete path for each,
    # and check who actually answers it.
    import re as _re

    from django.urls import resolve

    from app import urls as app_urls

    samples = {
        "slug": "some-2026-event",
        "token": "aaaabbbbccccddddeeeeffff00001111",
        "challenge_id": "1", "team_id": "1", "submission_id": "1",
        "cert_id": "4f22a017-32c2-4c76-90eb-e634671fdbee",
    }
    for entry in app_urls.urlpatterns:
        route = getattr(getattr(entry, "pattern", None), "_route", "")
        if not route.startswith("crashtech/"):
            continue
        callback = getattr(entry, "callback", None)
        if callback is None:
            continue
        path = "/" + _re.sub(
            r"<[^:>]+:([^>]+)>",
            lambda m: samples.get(m.group(1), "1"),
            route,
        )
        if path in DELIBERATE:
            continue
        match = resolve(path)
        if match.func.__module__ != callback.__module__:
            stolen.append(f"{path} -> {match.func.__module__}, not {callback.__module__}")

    assert not stolen, "CrashTech has shadowed the 2026 platform: " + "; ".join(stolen)
