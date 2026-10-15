"""What is outstanding before an event may move on (spec Rule 3.4, 3.5).

**Advancing is a checklist, not a button.** Going live reveals every
challenge to everybody at once and cannot be undone; publishing makes the
standings permanent. Those are not things to put behind a control that
looks like any other control.

Every check here is **computed, never stored**. A stored "ready" flag is a
second source of truth and goes stale the moment somebody deletes a
challenge, which is the same reason the leaderboard is computed.

A check is one of three things, and the difference matters:

- **blocker** — the advance is refused. Something would be broken or
  unfair for participants if it went ahead.
- **warning** — shown, counted, and does not stop anything. "Six teams
  have not collected a kit" is worth knowing and is not a reason to
  refuse to start an event those teams may simply not attend.
- **ok** — done, shown so the list reads as progress rather than as a
  list of complaints.
"""

from dataclasses import dataclass

from .models import EventRole, Hackathon

BLOCKER, WARNING, OK = "blocker", "warning", "ok"


def plural(n, singular, plural_form=None):
    """"1 judges assigned" is the kind of thing that makes a product feel
    unfinished, and it is one line to not do."""
    word = singular if n == 1 else (plural_form or singular + "s")
    return f"{n} {word}"


@dataclass(frozen=True)
class Check:
    level: str
    text: str
    # Where to go and fix it. A checklist that tells you something is
    # wrong and not where to deal with it is only half a feature.
    fix_url_name: str = ""

    @property
    def is_blocker(self):
        return self.level == BLOCKER


def _challenge_checks(hackathon):
    challenges = list(hackathon.challenges.all())
    if not challenges:
        yield Check(BLOCKER, "No challenges have been written", "crashtech:challenges")
        return

    yield Check(OK, plural(len(challenges), "challenge") + " written", "crashtech:challenges")

    unfinished = [c for c in challenges if not c.is_finished]
    if unfinished:
        names = ", ".join(c.title for c in unfinished[:3])
        more = f" and {len(unfinished) - 3} more" if len(unfinished) > 3 else ""
        yield Check(
            BLOCKER,
            f"No required deliverable on: {names}{more}",
            "crashtech:challenges",
        )
    else:
        yield Check(OK, "Every challenge says what to submit")


def _people_checks(hackathon):
    judges = hackathon.roles.filter(role=EventRole.JUDGE).count()
    if judges:
        yield Check(OK, plural(judges, "judge") + " assigned", "crashtech:people")
    else:
        # A blocker rather than a warning: creativity challenges score only
        # on a judge's grade, so an event with none cannot produce a
        # result at all.
        yield Check(BLOCKER, "No judges assigned", "crashtech:people")

    pending = hackathon.invitations.filter(accepted_at__isnull=True).count()
    if pending:
        yield Check(
            WARNING,
            plural(pending, "person", "people") + " invited but not joined yet",
            "crashtech:people",
        )


def _milestone_checks(hackathon):
    milestones = list(hackathon.milestones.all())
    if not milestones:
        yield Check(WARNING, "No milestones on the timeline", "crashtech:milestones")
        return

    dates = [m.occurs_at for m in milestones]
    if dates != sorted(dates):
        yield Check(BLOCKER, "Milestone dates are out of order", "crashtech:milestones")
    else:
        yield Check(OK, plural(len(milestones), "milestone") + ", in order", "crashtech:milestones")


def _kit_checks(hackathon):
    teams = hackathon.teams.count()
    if not teams:
        return
    collected = hackathon.kit_issues.filter(status="collected").values("team").distinct().count()
    if collected >= teams:
        yield Check(OK, f"All {plural(teams, 'team')} have collected a kit")
    else:
        # Deliberately a warning. A team that never turns up for a kit is
        # a team that is probably not coming, and refusing to start the
        # event for them punishes everybody who did.
        yield Check(
            WARNING,
            f"{collected} of {teams} teams have collected a kit",
            "crashtech:kit_desk",
        )


def resolve(url_name, hackathon, challenge=None):
    """See `next_actions.resolve`: a checklist item for a screen that does
    not exist yet still says the true thing, it just does not link.

    `challenge` is for the publish blockers, where "this challenge has no
    shortlist" should land on *that* challenge rather than on a list.
    """
    if not url_name:
        return ""
    from django.urls import NoReverseMatch, reverse

    attempts = [(), (hackathon.slug,)]
    if challenge is not None:
        attempts.insert(0, (hackathon.slug, challenge.pk))
    for args in attempts:
        try:
            return reverse(url_name, args=args)
        except NoReverseMatch:
            continue
    return ""


def checks_for(hackathon):
    """Everything outstanding before this event's **next** transition.

    Each status has its own list, because what matters before opening
    registration is not what matters before revealing the challenges.
    """
    status = hackathon.status

    if status == Hackathon.SETUP:
        if hackathon.starts_at >= hackathon.ends_at:
            yield Check(BLOCKER, "The event ends before it starts", "crashtech:settings")
        else:
            yield Check(OK, "Dates are set")
        yield from _milestone_checks(hackathon)

    elif status == Hackathon.PUBLISHED:
        accepted = hackathon.registrations.filter(status="accepted").count()
        if accepted:
            yield Check(OK, plural(accepted, "person", "people") + " accepted", "crashtech:registrations")
        else:
            yield Check(WARNING, "Nobody has been accepted yet", "crashtech:registrations")
        if hackathon.kit_items.exists():
            yield Check(OK, "The kit is defined", "crashtech:kit")
        else:
            yield Check(BLOCKER, "The kit has not been defined", "crashtech:kit")

    elif status == Hackathon.KITS:
        # The big one. Entering `live` reveals every challenge at once and
        # cannot be undone.
        yield from _challenge_checks(hackathon)
        yield from _people_checks(hackathon)
        yield from _milestone_checks(hackathon)
        yield from _kit_checks(hackathon)

    elif status == Hackathon.LIVE:
        yield Check(OK, "Closing locks submissions and lets judges start")

    elif status == Hackathon.CLOSED:
        # The last transition is publishing, and it has its own screen and
        # its own gate (Rule 8.5), because its three effects are permanent
        # and it is the one click in the product that cannot be walked
        # back. This checklist reflects that gate rather than restating it.
        from .judging import publish_blockers

        blockers = publish_blockers(hackathon)
        for blocker in blockers:
            yield Check(BLOCKER, blocker.text, blocker.url_name)
        if not blockers:
            yield Check(OK, "Judging is finished. Results can be published", "crashtech:publish")


def blockers_for(hackathon):
    return [c for c in checks_for(hackathon) if c.is_blocker]


def can_advance(hackathon):
    """Rule 3.4: the control appears only when the blockers clear."""
    if hackathon.next_status is None:
        return False
    return not blockers_for(hackathon)


# What each transition actually does to the world, in words, for the
# confirmation (Rule 11.7). "Are you sure" tells nobody anything.
CONSEQUENCES = {
    Hackathon.PUBLISHED: (
        "The event page becomes public and anyone may apply. "
        "Challenges stay hidden."
    ),
    Hackathon.KITS: (
        "Kit collection opens and the supporting repository is shown to "
        "the people you have accepted. Challenges stay hidden."
    ),
    Hackathon.LIVE: (
        "Every challenge becomes visible to every participant, at once, "
        "and submissions open. This cannot be undone."
    ),
    Hackathon.CLOSED: (
        "Submissions lock immediately. Judges can begin shortlisting and "
        "grading."
    ),
    Hackathon.MUSEUM: (
        "The final standings become public and the museum opens. Both are "
        "permanent. This happens on the publish screen, where the list of "
        "what is still outstanding is."
    ),
}


def consequence_of_advancing(hackathon):
    return CONSEQUENCES.get(hackathon.next_status, "")
