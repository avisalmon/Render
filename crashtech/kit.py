"""Handing out hardware (spec chapter 6).

The kit desk is the only physical queue in the whole product and the only
admin task done standing up with thirty people waiting. Everything in this
module is shaped by one number: **under five seconds per team.** Slower
than a paper list and it loses to the paper list, and then the data
arrives late or never (user_journeys.md R6).

What that means in practice, and why there is no cleverness here:

- **Search is one query over team names and member names**, because an
  admin at a desk types three letters of whatever the person in front of
  them says.
- **Allocation and collection are different facts** and `KitIssue`
  answers both: the kit belongs to the team, and a named member picked it
  up.
- **No JavaScript.** A corridor in a university building is the worst wifi
  of the event, and a plain form post is the thing most likely to survive
  it.
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import KitIssue


class KitError(Exception):
    pass


def search_teams(hackathon, query):
    """Teams matching a few letters of a team name or a member's name.

    Returns everything when the query is empty, because an admin opening
    the desk before anybody arrives should see the room, not a blank page.
    """
    teams = hackathon.teams.prefetch_related("memberships__user", "kit_issues")
    query = (query or "").strip()
    if not query:
        return teams
    return teams.filter(
        Q(name__icontains=query)
        | Q(memberships__user__username__icontains=query)
        | Q(memberships__user__email__icontains=query)
        | Q(memberships__user__first_name__icontains=query)
        | Q(memberships__user__last_name__icontains=query)
    ).distinct()


def status_of(team):
    """`collected`, `partial`, or `waiting`, for one glance at a row."""
    allocated = team.hackathon.kits_per_team
    collected = team.kit_issues.filter(status=KitIssue.COLLECTED).count()
    if collected >= allocated:
        return "collected"
    return "partial" if collected else "waiting"


def collectors_for(team):
    """Who may be handed the kit: any member, because there is no captain.

    A team of one needs no choice and the desk should not ask for one,
    which is what keeps the common case at a single tap.
    """
    return [m.user for m in team.memberships.select_related("user")]


@transaction.atomic
def give_kit(team, collected_by, confirmed_by):
    """Hand one kit over and record both halves of it."""
    hackathon = team.hackathon
    already = team.kit_issues.filter(status=KitIssue.COLLECTED).count()
    if already >= hackathon.kits_per_team:
        raise KitError(f"{team} already has all {hackathon.kits_per_team} of its kits.")
    if collected_by and not team.memberships.filter(user=collected_by).exists():
        raise KitError("That person is not on this team.")

    return KitIssue.objects.create(
        hackathon=hackathon, team=team, status=KitIssue.COLLECTED,
        collected_by=collected_by, collected_at=timezone.now(),
        confirmed_by=confirmed_by,
    )


@transaction.atomic
def take_back(issue):
    """A kit returned, or written off. The row stays, because "who had this
    board" is the question somebody asks in six months."""
    issue.status = KitIssue.RETURNED
    issue.save(update_fields=["status"])
    return issue


def counts_for(hackathon):
    teams = hackathon.teams.count()
    collected_teams = (
        hackathon.kit_issues.filter(status=KitIssue.COLLECTED)
        .values("team").distinct().count()
    )
    issued = hackathon.kit_issues.filter(status=KitIssue.COLLECTED).count()
    stock = sum(item.quantity_total for item in hackathon.kit_items.all())
    return {
        "teams": teams,
        "collected_teams": collected_teams,
        "waiting": max(0, teams - collected_teams),
        "issued": issued,
        # Sized against accepted registrations rather than teams, because
        # kits go to teams but people are what fills them. The 2026
        # platform computed `stock - teams.count()`, which is now the wrong
        # arithmetic by a factor of the team size.
        "stock": stock,
    }
