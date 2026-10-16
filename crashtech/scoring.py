"""What a submission is worth (spec Rule 7.4, 8.4).

Three kinds of challenge, three different answers, and the differences are
the whole product:

- **Completion** pays a flat `points` the moment a team says it worked.
- **Measured** pays by *finishing position* against every other team, so a
  team's score for it moves when somebody else submits a better number.
  That is not a bug, it is what a ranked challenge means, and it is the
  kind the 2026 feedback asked for because a compiler cannot be talked
  into a number.
- **Creativity** pays nothing at all until a judge has graded it
  (Rule 8.2). It has no number to report and nothing a later spot check
  could compare against, so there is no honest tentative value. A team
  cannot report its own originality any more than its own final placing.

**Everything here is computed.** `Submission.tentative_points` exists as a
cache and is rewritten whenever a challenge's ranking could have moved,
because a stored total for a ranked challenge is stale the instant the
next team submits.
"""

from .models import Challenge, JudgeGrade, Submission


def _ranked_submissions(challenge):
    """Submissions to a measured challenge, best first.

    A submission with no reported number is not ranked at all rather than
    ranked last: it has not attempted the measurement, and giving it a
    position would push a real attempt down.
    """
    rows = [
        s for s in challenge.submissions.all()
        if s.reported_value is not None and s.verification != Submission.WITHDRAWN
    ]
    reverse = challenge.metric_direction == Challenge.HIGHER
    return sorted(rows, key=lambda s: (s.reported_value, -s.pk), reverse=reverse)


def points_for(submission):
    """What this submission is worth right now."""
    challenge = submission.challenge

    if submission.verification == Submission.WITHDRAWN:
        return 0

    if challenge.kind == Challenge.COMPLETION:
        return challenge.points if submission.claimed_complete else 0

    if challenge.kind == Challenge.MEASURED:
        tiers = challenge.rank_points or []
        if not tiers or submission.reported_value is None:
            return 0
        if submission.verification == Submission.WITHDRAWN:
            return 0
        # A shared place for a shared number. The position is how many
        # submissions are strictly better, so two teams reporting the same
        # Fmax both take the higher tier and the next one down skips a
        # place, which is how every race scores a dead heat. The first
        # version broke the tie on whoever submitted first.
        better = 0
        higher = challenge.metric_direction == Challenge.HIGHER
        for other in _ranked_submissions(challenge):
            if other.pk == submission.pk:
                continue
            if (other.reported_value > submission.reported_value) if higher \
                    else (other.reported_value < submission.reported_value):
                better += 1
        return tiers[better] if better < len(tiers) else 0

    if challenge.kind == Challenge.CREATIVITY:
        # Rule 8.2: nothing until a human has looked at it. Averaged across
        # judges, because more than one may grade the same submission and
        # the first one to arrive should not decide it.
        grades = [g.grade for g in submission.grades.all()]
        if not grades:
            return 0
        average = sum(grades) / len(grades)
        if challenge.points and challenge.max_grade:
            # The tech lead says what the challenge is worth; the judges
            # say what fraction of it this entry earned. Without the scale
            # a creativity challenge is silently worth `max_grade` and the
            # `points` field on it does nothing, which is the sort of
            # quiet inconsistency that shows up as an argument about the
            # results.
            return int(round(average / challenge.max_grade * challenge.points))
        return int(round(average))

    return 0


def recompute_challenge(challenge):
    """Rewrite the cached points for every submission to this challenge.

    Called after anything that could move a ranking: a new submission, a
    changed number, a withdrawal, a grade. Cheap, because a challenge has
    as many submissions as the event has teams.
    """
    for submission in challenge.submissions.all():
        value = points_for(submission)
        if submission.tentative_points != value:
            Submission.objects.filter(pk=submission.pk).update(tentative_points=value)


def team_score(team):
    """A team's own total, which they may **always** see (Rule 8.4).

    This is not the leaderboard and is not gated by it. "My points" and
    "where I rank" are different questions, and twenty-four hours of
    submitting into silence is a dropbox rather than a competition.
    """
    return sum(points_for(s) for s in team.submissions.select_related("challenge"))


def leaderboard(hackathon):
    """Every team, best first, as `[(team, points), ...]`.

    Computed, never stored (Rule 8.4): a stored total is a second source of
    truth and goes stale the moment a verification changes a score.

    Ties break on the team that got there first, so a leaderboard is
    stable rather than reshuffling between two equal scores on every
    refresh.
    """
    rows = []
    for team in hackathon.teams.prefetch_related("submissions__challenge", "submissions__grades"):
        rows.append((team, sum(points_for(s) for s in team.submissions.all())))
    return sorted(rows, key=lambda row: (-row[1], row[0].created_at, row[0].pk))


def standings(hackathon):
    """The leaderboard with places, as `[(place, team, points), ...]`.

    Competition ranking: equal points share a place and the next place is
    skipped (1, 1, 3). The order inside a tie is still stable, so the page
    does not reshuffle on refresh, but the order is no longer the result.
    It used to be: two teams level on points became "Winner" and
    "Runner-up" on permanent certificates, decided by who formed their team
    first.
    """
    rows = []
    place = 0
    previous = None
    for index, (team, points) in enumerate(leaderboard(hackathon)):
        if points != previous:
            place = index + 1
            previous = points
        rows.append((place, team, points))
    return rows


def awaiting_judgement(hackathon):
    """Creativity submissions that are shortlisted and not yet graded.

    The publish gate asks this question (Rule 8.5), and so does a judge's
    home screen, so it lives in one place.
    """
    return Submission.objects.filter(
        challenge__hackathon=hackathon,
        challenge__kind=Challenge.CREATIVITY,
        is_finalist=True,
    ).exclude(
        pk__in=JudgeGrade.objects.values("submission_id"),
    )


def unshortlisted_creativity_challenges(hackathon):
    """Creativity challenges with submissions but no shortlist at all.

    Publishing without one would mean nobody ever looked at them, which is
    worse than a low score.
    """
    out = []
    for challenge in hackathon.challenges.filter(kind=Challenge.CREATIVITY):
        if challenge.submissions.exists() and not challenge.submissions.filter(is_finalist=True).exists():
            out.append(challenge)
    return out


def disputed(hackathon):
    return Submission.objects.filter(
        challenge__hackathon=hackathon, verification=Submission.DISPUTED,
    )


def top_measured(hackathon, per_challenge=3):
    """The handful of scores that decide the outcome, for the spot check.

    Explicitly not everything: Rule 8.3 says verification is a spot check
    and **left alone is the normal answer**. A screen that lists every
    submission invites judges to check every submission, and then the
    trust model has quietly become the 2026 one it replaced.
    """
    out = []
    for challenge in hackathon.challenges.filter(kind=Challenge.MEASURED):
        for submission in _ranked_submissions(challenge)[:per_challenge]:
            out.append(submission)
    return out
