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


def _guard(user, hackathon):
    if not is_accepted(user, hackathon):
        raise TeamError("You need to be accepted to the event first.")
    if team_for(user, hackathon):
        raise TeamError(
            "You are already on a team for this event. Leave it before joining another."
        )


@transaction.atomic
def create_team(user, hackathon, name):
    _guard(user, hackathon)
    name = (name or "").strip()
    if not name:
        raise TeamError("Give the team a name.")
    if Team.objects.filter(hackathon=hackathon, name__iexact=name).exists():
        raise TeamError("A team here already has that name.")

    team = Team.objects.create(
        hackathon=hackathon, name=name,
        # Stable, assigned once, and the label judges see instead of a name
        # (Rule 4.6).
        anon_ordinal=hackathon.teams.count() + 1,
    )
    TeamMembership.objects.create(team=team, user=user, hackathon=hackathon)
    return team


@transaction.atomic
def join_team(user, hackathon, team):
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
    if hackathon.team_size_max <= 1:
        return Team.objects.none()
    full = [t.id for t in hackathon.teams.all() if t.memberships.count() >= hackathon.team_size_max]
    return hackathon.teams.exclude(id__in=full)
