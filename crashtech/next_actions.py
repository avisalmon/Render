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


def _admin_actions(hackathon):
    status = hackathon.status

    if status == Hackathon.SETUP:
        if not hackathon.milestones.exists():
            yield Action("Put the milestones on the timeline", "crashtech:milestones", True)
        else:
            yield Action("Publish the event so people can apply", "crashtech:readiness", True)

    elif status == Hackathon.PUBLISHED:
        waiting = hackathon.registrations.filter(status="applied").count()
        if waiting:
            yield Action(f"{waiting} applications waiting on you", "crashtech:registrations", True)
        else:
            yield Action("No applications waiting", "crashtech:registrations")

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
            yield Action(f"{len(blockers)} things block going live", "crashtech:readiness")
        else:
            yield Action("Ready to go live when you are", "crashtech:readiness", True)

    elif status == Hackathon.LIVE:
        yield Action("The event is running. You are the only one who can see the standings.")

    elif status == Hackathon.CLOSED:
        yield Action("Judging is underway. Publish when it is finished", "crashtech:readiness")

    pending = hackathon.invitations.filter(accepted_at__isnull=True).count()
    if pending:
        yield Action(f"{pending} people invited but not joined", "crashtech:people")


def _tech_lead_actions(hackathon):
    challenges = list(hackathon.challenges.all())
    if not challenges:
        yield Action("No challenges written yet", "crashtech:challenges", True)
        return

    unfinished = [c for c in challenges if not c.is_finished]
    if unfinished and not hackathon.challenges_visible:
        yield Action(
            f"{len(unfinished)} of {len(challenges)} challenges do not say what to submit",
            "crashtech:challenges", True,
        )
    else:
        yield Action(f"{len(challenges)} challenges written", "crashtech:challenges")

    if not hackathon.kit_items.exists():
        yield Action("The kit has not been defined", "crashtech:kit", True)


def _judge_actions(hackathon):
    if hackathon.status in (Hackathon.SETUP, Hackathon.PUBLISHED, Hackathon.KITS):
        yield Action("Read the challenges before the event starts", "crashtech:challenges")
    elif hackathon.status == Hackathon.LIVE:
        # Rule 8.1, said out loud. A judge with an empty screen and no
        # explanation assumes something is broken.
        yield Action("Nothing to judge during the event. Grading starts when it closes.")
    elif hackathon.status == Hackathon.CLOSED:
        yield Action("Shortlist and grade the creativity challenges", "crashtech:challenges", True)


def _participant_actions(hackathon):
    status = hackathon.status
    if status in (Hackathon.PUBLISHED, Hackathon.KITS):
        kit_milestone = hackathon.milestones.filter(kind="hardware").first()
        if kit_milestone:
            yield Action(f"Kit pickup: {kit_milestone.occurs_at:%d %b}, in person")
        else:
            # Never nothing. A participant who lands on an empty screen
            # concludes the event has forgotten about them, and an event
            # whose organiser has not set a pickup date yet is exactly when
            # that is least true.
            yield Action("Kit collection is in person. The date will appear here.")
        if hackathon.repo_url:
            yield Action("Practise with the examples in the repository")
        yield Action("The challenges stay secret until the event starts.")
    elif status == Hackathon.LIVE:
        yield Action("The challenges are open", "crashtech:challenges", True)
    elif status == Hackathon.CLOSED:
        yield Action("Submissions are closed. Results when judging finishes.")
    elif status == Hackathon.MUSEUM:
        yield Action("Results are published", "crashtech:event_home")
    else:
        yield Action("This event has not opened yet.")


def _researcher_actions(hackathon):
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
            (a, resolve(a.url_name, hackathon)) for a in builder(hackathon)
        ]
        if actions:
            out.append((labels.get(role, role), actions))
    return out
