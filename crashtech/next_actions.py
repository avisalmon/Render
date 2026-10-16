"""What this person should do next (spec Rule 11.3).

The organising idea of the whole product, from user_journeys.md §1.2:
**one role-aware home that answers "what do I do now".** Not a dashboard
of statistics. Five roles share an event and almost nothing they do
overlaps, so a single generic page would force each of them to hunt for
their own part.

Each action is a sentence a person could act on, not a label. "18 of 24
teams have not collected" beats "Hardware", because the first one tells
somebody whether to open the desk this afternoon.

Returning nothing is a real answer and a common one. A judge during the 24
hours has nothing to do, deliberately (Rule 8.1), and the honest thing is
to say so rather than invent busywork.
"""

from dataclasses import dataclass

from django.utils import timezone

from . import readiness
from .models import EventRole, Hackathon
from .roles import roles_for


@dataclass(frozen=True)
class Action:
    text: str
    url_name: str = ""
    # `urgent` is for the one thing standing between the event and its next
    # phase. More than one urgent item on a screen means none of them are.
    urgent: bool = False
    # A destination that is not one of our own named routes: the event's
    # repository on GitHub, or a certificate's permanent URL.
    href: str = ""


# Every builder takes the event **and the person**. The first version took
# only the event, which is why the homes could route people but could not
# tell a participant whether their own team had its kit, or how many points
# it had, or where it finished. A review that put every role side by side
# at every stage found that each home was correct and said almost nothing.


def _admin_actions(hackathon, user):
    from . import clock, judging, scoring
    from .models import MuseumPhoto, Submission

    status = hackathon.status

    if status == Hackathon.SETUP:
        if not hackathon.milestones.exists():
            yield Action("Put the milestones on the timeline", "crashtech:milestones", True)
        else:
            yield Action("Publish the event so people can apply", "crashtech:readiness", True)

    elif status == Hackathon.PUBLISHED:
        waiting = hackathon.registrations.filter(status="applied").count()
        accepted = hackathon.registrations.filter(status="accepted").count()
        if waiting:
            yield Action(
                f"{waiting} application{'s' if waiting != 1 else ''} waiting on you",
                "crashtech:registrations", True,
            )
        yield Action(
            f"{accepted} accepted so far, in {hackathon.teams.count()} teams",
            "crashtech:teams",
        )
        yield Action("Open kit collection when you are ready", "crashtech:readiness")

    elif status == Hackathon.KITS:
        teams = hackathon.teams.count()
        collected = hackathon.kit_issues.filter(status="collected").values("team").distinct().count()
        if teams and collected < teams:
            yield Action(
                f"{teams - collected} of {teams} teams still need a kit",
                "crashtech:kit_desk", True,
            )
        blockers = readiness.blockers_for(hackathon)
        if blockers:
            yield Action(
                f"{len(blockers)} thing{'s' if len(blockers) != 1 else ''} before you can start the event",
                "crashtech:readiness",
            )
        else:
            yield Action("Ready to start the event when you are", "crashtech:readiness", not (teams and collected < teams))

    elif status == Hackathon.LIVE:
        rows = Submission.objects.filter(challenge__hackathon=hackathon)
        latest = rows.order_by("-updated_at").values_list("updated_at", flat=True).first()
        teams_in = rows.values("team").distinct().count()
        # No "submissions close in" here: the clock is the first thing on
        # the page, and saying it twice made the second one noise.
        if latest:
            yield Action(
                f"{rows.count()} submissions from {teams_in} of {hackathon.teams.count()} "
                f"teams. The latest {clock.ago(latest)}",
                "crashtech:standings",
            )
        else:
            yield Action("Nothing submitted yet", "crashtech:standings")
        yield Action("Close the event when the time is up", "crashtech:readiness")

    elif status == Hackathon.CLOSED:
        blockers = judging.publish_blockers(hackathon)
        if blockers:
            yield Action(
                f"{len(blockers)} thing{'s' if len(blockers) != 1 else ''} before the results can be published",
                "crashtech:publish", True,
            )
        else:
            yield Action("Judging is finished. Publish the results", "crashtech:publish", True)
        yield Action("Watch how judging is going", "crashtech:judging")

    elif status == Hackathon.MUSEUM:
        page = getattr(hackathon, "museum_page", None)
        if not (page and page.highlights):
            yield Action("Write a paragraph for the museum", "crashtech:museum_edit", True)
        pending = MuseumPhoto.objects.filter(
            museum_page__hackathon=hackathon, moderation_status=MuseumPhoto.PENDING,
        ).count()
        if pending:
            yield Action(
                f"{pending} photo{'s' if pending != 1 else ''} waiting on you",
                # Urgent only once the paragraph is done, so there is never
                # more than one "next" on the screen.
                "crashtech:museum_edit", bool(page and page.highlights),
            )
        yield Action("The museum, as everybody sees it", "crashtech:museum")

    pending = hackathon.invitations.filter(accepted_at__isnull=True).count()
    if pending:
        yield Action(f"{pending} people invited but not joined", "crashtech:people")


def _tech_lead_actions(hackathon, user):
    from .models import Submission

    challenges = list(hackathon.challenges.all())
    if hackathon.status in (Hackathon.SETUP, Hackathon.PUBLISHED, Hackathon.KITS):
        challenge_work = False
        if not challenges:
            challenge_work = True
            yield Action("No challenges written yet", "crashtech:challenges", True)
        else:
            unfinished = [c for c in challenges if not c.is_finished]
            if unfinished:
                challenge_work = True
                yield Action(
                    f"{len(unfinished)} of {len(challenges)} challenges do not say what to submit",
                    "crashtech:challenges", True,
                )
            else:
                yield Action(
                    f"{len(challenges)} challenges written, sealed until kickoff",
                    "crashtech:challenges",
                )
        if not hackathon.kit_items.exists():
            # Next only when the challenges are done: one "Next" per screen,
            # and the challenges are the harder of the two to leave late.
            yield Action("The kit has not been defined", "crashtech:kit", not challenge_work)
        else:
            n = hackathon.kit_items.count()
            yield Action(f"The kit: {n} item{'s' if n != 1 else ''}", "crashtech:kit")

    elif hackathon.status == Hackathon.LIVE:
        count = Submission.objects.filter(challenge__hackathon=hackathon).count()
        yield Action(
            f"{count} submissions so far, across {len(challenges)} challenges",
            "crashtech:challenges",
        )

    elif hackathon.status == Hackathon.CLOSED:
        yield Action("Submissions are closed. The judges have it from here.")

    elif hackathon.status == Hackathon.MUSEUM:
        yield Action("The museum", "crashtech:museum")


def _judge_actions(hackathon, user):
    from . import judging
    from .models import Challenge, Submission

    if hackathon.status in (Hackathon.SETUP, Hackathon.PUBLISHED, Hackathon.KITS):
        yield Action("Read the challenges before the event starts", "crashtech:challenges")
    elif hackathon.status == Hackathon.LIVE:
        # Rule 8.1, said out loud. A judge with an empty screen and no
        # explanation assumes something is broken.
        yield Action("Nothing to judge during the event. Grading starts when it closes.")
    elif hackathon.status == Hackathon.CLOSED:
        creative = Submission.objects.filter(
            challenge__hackathon=hackathon, challenge__kind=Challenge.CREATIVITY,
        ).exclude(verification=Submission.WITHDRAWN)
        shortlisted = creative.filter(is_finalist=True)
        ungraded = shortlisted.exclude(grades__judge=user).count()
        if creative.exists() and not shortlisted.exists():
            yield Action(
                f"{creative.count()} creativity entries to shortlist",
                "crashtech:judging", True,
            )
        elif ungraded:
            yield Action(
                f"{ungraded} shortlisted entr{'ies' if ungraded != 1 else 'y'} you have not graded",
                "crashtech:judging", True,
            )
        else:
            yield Action("You have graded everything on the shortlist", "crashtech:judging")
        checks = len(judging.spot_check_queue(hackathon))
        if checks:
            yield Action(
                f"{checks} top numbers you may look at. Leaving them alone is fine.",
                "crashtech:verify",
            )
    elif hackathon.status == Hackathon.MUSEUM:
        yield Action("Judging is finished. The results are public", "crashtech:museum")


def _participant_actions(hackathon, user):
    from . import clock, scoring
    from .models import Certificate, KitIssue
    from .teams import team_for

    status = hackathon.status
    team = team_for(user, hackathon)
    tz = hackathon.tz

    if status in (Hackathon.PUBLISHED, Hackathon.KITS):
        if team is None:
            if hackathon.team_size_max <= 1:
                yield Action(
                    "Register your entry. This event is individual, so it takes one name.",
                    "crashtech:teams", True,
                )
            else:
                yield Action(
                    "Form a team or join one. Kits go to teams, so you need one before kit day.",
                    "crashtech:teams", True,
                )
        else:
            size = team.memberships.count()
            yield Action(
                f"You are on {team.name}"
                + ("" if hackathon.team_size_max <= 1 else f", {size} of {hackathon.team_size_max}"),
                "crashtech:teams",
            )
            kit_milestone = hackathon.milestones.filter(kind="hardware").first()
            if team.kit_issues.filter(status=KitIssue.COLLECTED).exists():
                yield Action("Your team has its kit")
            elif kit_milestone:
                when = timezone.localtime(kit_milestone.occurs_at, tz)
                yield Action(
                    f"Kit pickup: {when:%a %d %b, %H:%M}, in person. Any of you can collect it.",
                    urgent=status == Hackathon.KITS,
                )
            else:
                # Never nothing. A participant who lands on an empty screen
                # concludes the event has forgotten about them.
                yield Action("Kit collection is in person. The date will appear here.")
        kickoff = timezone.localtime(hackathon.starts_at, tz)
        yield Action(
            f"The challenges stay sealed until kickoff, {kickoff:%a %d %b, %H:%M} "
            f"{(hackathon.timezone_name or '').split('/')[-1].replace('_', ' ')} time."
        )

    elif status == Hackathon.LIVE:
        if team is None:
            # Teams lock at kickoff, except for starting one of your own,
            # which is exactly what this person needs (teams.late_solo_allowed).
            yield Action(
                "You are not on a team, so you cannot submit yet. Start one now: a team of one is fine.",
                "crashtech:teams", True,
            )
        else:
            # The clock above says how long. This says where to go.
            yield Action("The challenges, and what each one still needs", "crashtech:challenges", True)
            from .submissions import team_card

            card = team_card(team)
            total = hackathon.challenges.count()
            yield Action(
                f"{card['total']} points so far. Something in for {len(card['rows'])} of {total} challenges",
                "crashtech:challenges",
            )

    elif status == Hackathon.CLOSED:
        if team is not None:
            from .submissions import team_card

            points = team_card(team)["total"]
            yield Action(
                f"Submissions are closed. {team.name} has {points} points on its own "
                "word, and the judges are looking at the rest."
            )
        else:
            yield Action("Submissions are closed. Results when judging finishes.")

    elif status == Hackathon.MUSEUM:
        if team is not None:
            rows = scoring.standings(hackathon)
            mine = next(((p, pts) for p, t, pts in rows if t.pk == team.pk), None)
            if mine:
                place, points = mine
                joint = sum(1 for p, _, _ in rows if p == place) > 1
                yield Action(
                    f"{team.name} finished {'joint ' if joint else ''}{clock.ordinal(place)} "
                    f"of {len(rows)}, with {points} points",
                    "crashtech:museum", True,
                )
            cert = Certificate.objects.filter(hackathon=hackathon, team=team).first()
            if cert:
                yield Action(
                    f"Your certificate: {cert.get_type_display().lower()}",
                    href=f"/crashtech/c/{cert.cert_id}/",
                )
            yield Action(
                "Your work is in the museum" if team.exhibition_consent
                else "Your work is not shown in the museum. You can change that",
                "crashtech:teams",
            )
        else:
            yield Action("The results are published", "crashtech:museum")
    else:
        yield Action("This event has not opened yet.")


def _researcher_actions(hackathon, user):
    yield Action("Studies and questionnaires arrive in sprint C.7")


_BY_ROLE = {
    EventRole.ADMIN: _admin_actions,
    EventRole.TECH_LEAD: _tech_lead_actions,
    EventRole.JUDGE: _judge_actions,
    EventRole.PARTICIPANT: _participant_actions,
    EventRole.RESEARCHER: _researcher_actions,
}


def resolve(url_name, hackathon):
    """A URL if that screen exists yet, otherwise nothing.

    Sprints C.3 to C.7 add the screens these actions point at. Until then
    the sentence is still worth showing and the link is not, so an
    unbuilt route degrades to plain text instead of a NoReverseMatch in
    somebody's face.
    """
    if not url_name:
        return ""
    from django.urls import NoReverseMatch, reverse

    for args in ((), (hackathon.slug,)):
        try:
            return reverse(url_name, args=args)
        except NoReverseMatch:
            continue
    return ""


def next_actions_for(user, hackathon):
    """`[(role label, [Action, ...]), ...]` for every role this person holds.

    Grouped by role rather than merged, because somebody holding two roles
    is doing two jobs and the screen should not pretend otherwise. On a
    small event one person is often both tech lead and admin, and they
    still need to see which hat each item belongs to.
    """
    labels = dict(EventRole.ROLES)
    out = []
    for role in sorted(roles_for(user, hackathon)):
        builder = _BY_ROLE.get(role)
        if not builder:
            continue
        actions = [
            (a, a.href or resolve(a.url_name, hackathon))
            for a in builder(hackathon, user)
        ]
        if actions:
            out.append((labels.get(role, role), actions))
    return out
