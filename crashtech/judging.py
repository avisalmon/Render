"""Judging, and the one click that makes it permanent (spec chapter 8).

The hard thing about this chapter is not the mechanics, it is keeping the
trust model from quietly collapsing back into the 2026 one. In 2026 a
submission was worth nothing until a judge touched it, so judges touched
everything, so nothing was judged well. Here:

- **Judges do nothing during the event** (Rule 8.1). Grading live scores
  the first submission against a different field from the last.
- **Creativity is two steps**, shortlist then grade (Rule 8.2). Seventy
  submissions get a rubber stamp; fifteen finalists get real attention.
- **Verification is a spot check and "left alone" is the normal answer**
  (Rule 8.3). The screen only ever offers the handful of scores that
  decide the outcome, because a screen listing everything is an
  instruction to check everything.

`publish` is the only irreversible act in the product that a human
presses on purpose, and it does three permanent things at once, so it is
gated on conditions it states in words rather than on a confirmation.
"""

from django.db import transaction
from django.utils import timezone

from .models import Certificate, Challenge, Hackathon, JudgeGrade, Submission, Team
from .scoring import standings as ranked_standings
from .scoring import (
    awaiting_judgement, disputed, leaderboard, points_for,
    recompute_challenge, top_measured, unshortlisted_creativity_challenges,
)


class JudgingError(Exception):
    pass


def judging_blocker(hackathon):
    """Why a judge cannot work yet, in words (Rule 8.1).

    A locked screen that does not say why reads as broken. This one says
    what is being waited for, which during a 24-hour event is the only
    thing a judge wants to know.
    """
    if hackathon.status in (Hackathon.SETUP, Hackathon.PUBLISHED, Hackathon.KITS):
        return (
            "The event has not started. Read the challenges now so you are not "
            "reading them for the first time at the end."
        )
    if hackathon.status == Hackathon.LIVE:
        return (
            "Judging opens when the event closes. Grading while teams are still "
            "submitting would score the first entry against a different field "
            "from the last."
        )
    return None


# ------------------------------------------------------------- shortlisting


@transaction.atomic
def set_finalist(submission, judge, on=True):
    """Rule 8.2, step one. Not a grade, a decision about where to spend
    attention."""
    if submission.challenge.kind != Challenge.CREATIVITY:
        raise JudgingError("Only creativity challenges are shortlisted.")
    submission.is_finalist = bool(on)
    submission.finalist_set_by = judge if on else None
    submission.finalist_set_at = timezone.now() if on else None
    submission.save(update_fields=["is_finalist", "finalist_set_by", "finalist_set_at"])
    if not on:
        # Dropping somebody off the shortlist drops the grades with them,
        # or a later re-shortlist would silently carry an old judgement.
        submission.grades.all().delete()
    recompute_challenge(submission.challenge)
    return submission


def shortlist_for(challenge):
    """Every submission to a creativity challenge, for the comparison.

    Shortlisting is a comparison, not a verdict on each one in isolation
    (user_journeys.md), so this returns them all together rather than one
    at a time.
    """
    return challenge.submissions.select_related("team").prefetch_related(
        "files__deliverable", "grades",
    ).exclude(verification=Submission.WITHDRAWN)


# -------------------------------------------------------------- the grading


@transaction.atomic
def grade(submission, judge, value, note=""):
    """One judge's number for one shortlisted entry (Rule 8.2)."""
    challenge = submission.challenge
    if challenge.kind != Challenge.CREATIVITY:
        raise JudgingError("Only creativity challenges are graded.")
    if not submission.is_finalist:
        raise JudgingError("Shortlist it before grading it.")
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise JudgingError("A grade is a whole number.")
    if not 0 <= value <= challenge.max_grade:
        raise JudgingError(f"A grade runs from 0 to {challenge.max_grade}.")

    row, _ = JudgeGrade.objects.update_or_create(
        submission=submission, judge=judge,
        defaults={"grade": value, "note": (note or "").strip()},
    )
    recompute_challenge(challenge)
    return row


def my_grade(submission, judge):
    return submission.grades.filter(judge=judge).first()


# ---------------------------------------------------------- the spot check


@transaction.atomic
def verify(submission, judge, outcome, note=""):
    """Rule 8.3. Three outcomes, and the third is doing nothing.

    `verified` and `disputed` are both acts. Leaving a submission
    `unverified` is not a gap in the record, it is the normal and final
    state of the great majority of them, and nothing anywhere treats it as
    unfinished.
    """
    if outcome not in (Submission.VERIFIED, Submission.DISPUTED, Submission.UNVERIFIED):
        raise JudgingError("That is not one of the three outcomes.")
    if outcome == Submission.DISPUTED and not (note or "").strip():
        # A dispute takes points off a team in a way they can read later.
        # It has to say why.
        raise JudgingError("A dispute needs a reason. The team will read it.")

    submission.verification = outcome
    submission.verified_by = judge if outcome != Submission.UNVERIFIED else None
    submission.verified_at = timezone.now() if outcome != Submission.UNVERIFIED else None
    submission.verification_note = (note or "").strip()
    submission.save(update_fields=[
        "verification", "verified_by", "verified_at", "verification_note",
    ])
    recompute_challenge(submission.challenge)
    return submission


def spot_check_queue(hackathon, per_challenge=3):
    """The handful of scores that decide the outcome, and nothing else.

    Deliberately not every submission. Rule 8.3 exists because a screen
    that lists everything is read as an instruction to check everything.
    """
    return top_measured(hackathon, per_challenge=per_challenge)


# -------------------------------------------------------------- publishing


class Blocker:
    """One reason publishing is not allowed yet, with a way to fix it."""

    def __init__(self, text, url_name=None, challenge=None):
        self.text = text
        self.url_name = url_name
        self.challenge = challenge


def publish_blockers(hackathon):
    """Rule 8.5, stated as the three things it actually requires.

    Everything here is computed on demand rather than tracked by a flag,
    for the same reason the leaderboard is: a stored "ready to publish"
    goes stale the moment a judge disputes something.
    """
    out = []
    if hackathon.status != Hackathon.CLOSED:
        out.append(Blocker(
            "The event has to be closed before its results can be published.",
            "crashtech:readiness",
        ))

    for challenge in unshortlisted_creativity_challenges(hackathon):
        out.append(Blocker(
            f'"{challenge.title}" has submissions and no shortlist. Publishing '
            f"now would mean nobody ever looked at them.",
            "crashtech:shortlist", challenge,
        ))

    waiting = {}
    for submission in awaiting_judgement(hackathon).select_related("challenge"):
        waiting.setdefault(submission.challenge, []).append(submission)
    for challenge, entries in waiting.items():
        # Named by challenge, because "3 entries somewhere" is not something
        # an admin can act on and the whole point of this list is that each
        # line leads to the screen that clears it.
        out.append(Blocker(
            f'"{challenge.title}": '
            + _plural(len(entries), "shortlisted entry", "shortlisted entries")
            + (" still has no grade." if len(entries) == 1 else " still have no grade."),
            "crashtech:shortlist", challenge,
        ))

    open_disputes = disputed(hackathon).count()
    if open_disputes:
        out.append(Blocker(
            _plural(open_disputes, "submission") + " left disputed. Settle each "
            "one as verified or leave it alone before the results become "
            "permanent.",
            "crashtech:verify",
        ))
    return out


def _plural(n, singular, plural_form=None):
    word = singular if n == 1 else (plural_form or singular + "s")
    return f"{n} {word}"


def can_publish(hackathon):
    return not publish_blockers(hackathon)


# The same phrase the lifecycle transitions use (readiness.CONSEQUENCES), on
# purpose: an irreversible act should read the same way everywhere in the
# product, so the words carry the weight rather than the screen.
PUBLISH_CONSEQUENCE = (
    "The standings become public and permanent, every score is frozen as it "
    "stands, the museum opens, and certificates are issued. This cannot be "
    "undone."
)


@transaction.atomic
def publish(hackathon, by=None):
    """The one gated click (Rule 8.5). Three permanent effects, together.

    `final_points` is written here and nowhere else. Up to this moment
    every score is computed, which is right while things can still move;
    from this moment the museum has to show the same numbers in five
    years whatever anybody later edits, so they are frozen.
    """
    if not can_publish(hackathon):
        raise JudgingError("Publishing is still blocked.")

    for submission in Submission.objects.filter(
        challenge__hackathon=hackathon,
    ).select_related("challenge").prefetch_related("grades"):
        Submission.objects.filter(pk=submission.pk).update(
            final_points=points_for(submission),
        )

    _issue_certificates(hackathon, ranked_standings(hackathon))

    hackathon.results_published_at = timezone.now()
    hackathon.status = Hackathon.MUSEUM
    hackathon.save(update_fields=["results_published_at", "status"])
    return hackathon


def _issue_certificates(hackathon, rows):
    """Rule 8.6. Everybody who turned something in gets one.

    A participation certificate is not a consolation prize, it is the
    thing somebody puts on a CV two years later, which is most of what a
    hackathon is worth to most of the people in it.

    By place, not by position in the list: teams level on points share a
    place and share the certificate that goes with it.
    """
    for place, team, _points in rows:
        if not team.submissions.exists():
            continue
        if place == 1:
            kind = Certificate.WINNER
        elif place in (2, 3):
            kind = Certificate.RUNNER_UP
        else:
            kind = Certificate.PARTICIPATION
        Certificate.objects.update_or_create(
            hackathon=hackathon, team=team, defaults={"type": kind},
        )


# ----------------------------------------------------------- blind judging


def assign_anonymous_labels(hackathon):
    """Stable "Entry 1..n" labels, assigned once, at the close (Rule 4.6).

    A judge should not know whose work they are grading, and a team name
    like "Dana and Yoav" defeats that by itself. Assigned at the close
    rather than at team creation so the order carries no information about
    who signed up first either.

    Idempotent: a team that already has an ordinal keeps it, because a
    label that moved between two judging sessions would be worse than no
    label at all.

    **Shuffled.** The first version walked teams in creation order, and
    team creation was also handing out ordinals in sign-up order, so
    "Entry 1" simply meant "signed up first". Both are fixed: nothing is
    assigned before the close, and the close shuffles.
    """
    import random

    taken = set(
        hackathon.teams.exclude(anon_ordinal=0).values_list("anon_ordinal", flat=True)
    )
    nxt = 1
    waiting = list(hackathon.teams.filter(anon_ordinal=0))
    random.shuffle(waiting)
    for team in waiting:
        while nxt in taken:
            nxt += 1
        Team.objects.filter(pk=team.pk).update(anon_ordinal=nxt)
        taken.add(nxt)
    return hackathon.teams.count()
