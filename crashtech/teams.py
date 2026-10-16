"""Joining, leaving, and who may be on a team (spec chapter 5).

Three rules live here, and two of them are the kind that a view forgets
and a database should not:

- **One team per person per event** (Rule 5.3). Enforced by a unique
  constraint on `TeamMembership`, and checked here first so a person gets
  a sentence rather than an `IntegrityError`.
- **Up to `team_size_max`** (Rule 5.2), which is an int with no ceiling
  and defaults to 2. `1` makes the event individual.
- **No captain** (Rule 5.4). Every member holds every authority, so there
  is no "owner" check anywhere in this file and that absence is
  deliberate.
"""

from django.db import transaction

from .models import Registration, Team, TeamMembership


class TeamError(Exception):
    """A refusal with a sentence somebody can read."""


def team_for(user, hackathon):
    if not getattr(user, "is_authenticated", False):
        return None
    membership = TeamMembership.objects.filter(hackathon=hackathon, user=user).first()
    return membership.team if membership else None


def is_accepted(user, hackathon):
    """Only somebody the admin let in may form or join a team.

    Checked against `Registration` rather than the participant role,
    because the registration is the record of the decision and the role is
    its consequence.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    return Registration.objects.filter(
        hackathon=hackathon, user=user, status=Registration.ACCEPTED,
    ).exists()


def teams_locked(hackathon):
    """Rule 5.5: who is on which team stops changing at kickoff.

    Before this lock existed, somebody could join the winning team after
    the event closed, or even after the results were published, and their
    name would appear on its certificate, since a certificate lists the
    members it has. Leaving mid-event was worse: the last member out
    dissolved the team and its submissions with it.
    """
    from .models import Hackathon

    return hackathon.status in (Hackathon.LIVE, Hackathon.CLOSED, Hackathon.MUSEUM)


def late_solo_allowed(hackathon):
    """The one change still allowed once the event is live.

    An accepted person who never formed a team would otherwise be stranded
    for twenty-four hours, unable to submit anything. Starting a team of
    their own, late, gives nobody an advantage: it joins nothing and
    nobody joins it.
    """
    from .models import Hackathon

    return hackathon.status == Hackathon.LIVE


def _guard(user, hackathon):
    if not is_accepted(user, hackathon):
        raise TeamError("You need to be accepted to the event first.")
    if team_for(user, hackathon):
        raise TeamError(
            "You are already on a team for this event. Leave it before joining another."
        )


@transaction.atomic
def create_team(user, hackathon, name):
    if teams_locked(hackathon) and not late_solo_allowed(hackathon):
        raise TeamError("Teams are fixed now. The event is over.")
    _guard(user, hackathon)
    name = (name or "").strip()
    if not name:
        raise TeamError("Give the team a name.")
    if Team.objects.filter(hackathon=hackathon, name__iexact=name).exists():
        raise TeamError("A team here already has that name.")

    # No anonymous label yet. It is handed out at the close, shuffled
    # (judging.assign_anonymous_labels). Assigning it here made "Entry 1"
    # mean "signed up first", which is exactly the information Rule 4.6
    # promises a judge does not have.
    team = Team.objects.create(hackathon=hackathon, name=name)
    TeamMembership.objects.create(team=team, user=user, hackathon=hackathon)
    return team


@transaction.atomic
def join_team(user, hackathon, team):
    if teams_locked(hackathon):
        raise TeamError(
            "Teams are fixed once the event starts. Nobody can join one now."
        )
    _guard(user, hackathon)
    if team.hackathon_id != hackathon.id:
        raise TeamError("That team is not in this event.")
    if team.memberships.count() >= hackathon.team_size_max:
        raise TeamError(
            f"{team.name} is full. Teams here hold up to "
            f"{hackathon.team_size_max}."
        )
    TeamMembership.objects.create(team=team, user=user, hackathon=hackathon)
    return team


@transaction.atomic
def leave_team(user, hackathon):
    """Leaving is allowed and uncomplicated, because there is no captain to
    hand anything over to.

    An empty team is deleted rather than left behind: a name nobody holds
    blocks the next person who wants it, and an empty team on the kit desk
    is a kit allocated to nobody.
    """
    if teams_locked(hackathon):
        raise TeamError(
            "Teams are fixed once the event starts. Your team keeps you, and "
            "everything it turned in."
        )
    membership = TeamMembership.objects.filter(hackathon=hackathon, user=user).first()
    if not membership:
        raise TeamError("You are not on a team.")
    team = membership.team
    membership.delete()
    if not team.memberships.exists():
        if team.kit_issues.filter(status="collected").exists():
            raise TeamError(
                "That team has already collected a kit. Give it back at the desk first."
            )
        team.delete()
    return team


def joinable_teams(hackathon):
    """Teams somebody could still join, newest last.

    An individual event (`team_size_max == 1`) has none by definition, and
    the screen says so rather than showing a list of full teams.
    """
    if hackathon.team_size_max <= 1 or teams_locked(hackathon):
        return Team.objects.none()
    full = [t.id for t in hackathon.teams.all() if t.memberships.count() >= hackathon.team_size_max]
    return hackathon.teams.exclude(id__in=full)
