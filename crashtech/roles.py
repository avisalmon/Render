"""Who may do what, in one place (spec Rule 4.4).

The permission matrix is the thing most likely to break silently
(Rule 14.2): a view that forgets a check looks exactly like a view that
has one, and the failure is somebody seeing a challenge before kickoff or
grading an event they have nothing to do with.

So every check routes through this module rather than being written out at
each call site, and the matrix below is the single statement of it that
the tests assert against.
"""

from .models import EventRole, Hackathon

TECH_LEAD = EventRole.TECH_LEAD
ADMIN = EventRole.ADMIN
JUDGE = EventRole.JUDGE
PARTICIPANT = EventRole.PARTICIPANT
RESEARCHER = EventRole.RESEARCHER

# Rule 4.4, as data. Each capability names the roles that hold it.
MATRIX = {
    "event_settings": {ADMIN},
    "grant_roles": {ADMIN},
    "define_kit": {TECH_LEAD},
    "distribute_kits": {ADMIN},
    "decide_registrations": {ADMIN},
    "author_challenges": {TECH_LEAD},
    # Rule 4.5: judges may read the challenges before the event. They are
    # not participants and the secrecy rule is not about them.
    "read_secret_challenges": {TECH_LEAD, ADMIN, JUDGE},
    "submit": {PARTICIPANT},
    "judge": {JUDGE},
    # Reading judging is not judging. An admin has to be able to see
    # whether grading is progressing, because they are the one whose
    # publish button is waiting on it, and the publish screen links
    # them straight at it. They still cannot shortlist or grade.
    "read_judging": {JUDGE, ADMIN},
    "advance_lifecycle": {ADMIN},
    "manage_study": {RESEARCHER},
    "read_research_data": {RESEARCHER},
}


def roles_for(user, hackathon):
    """Every role this person holds on this event, as a set of strings.

    A superuser is treated as an admin everywhere (Rule 4.2): they are the
    only way the first admin of an event can exist, and locking the site
    owner out of their own app helps nobody. It is a named exception, not
    an accident of how the check happens to be written.
    """
    if not getattr(user, "is_authenticated", False):
        return set()
    held = set(
        EventRole.objects.filter(hackathon=hackathon, user=user).values_list("role", flat=True)
    )
    if user.is_superuser:
        held.add(ADMIN)
    return held


def can(user, hackathon, capability):
    """Does this person hold a role that grants `capability` on this event?"""
    if capability not in MATRIX:
        raise KeyError(f"no such capability: {capability!r}")
    return bool(roles_for(user, hackathon) & MATRIX[capability])


def may_compete(user, hackathon):
    """Whether this person may apply to take part.

    Not if they can read the challenges before kickoff (Rule 4.5): a tech
    lead, an admin or a judge who also competed would have had the tasks
    for days. The review found the event home offering every one of them
    an "Apply to take part" button.

    A researcher may compete; they never see a challenge early.
    """
    return not can(user, hackathon, "read_secret_challenges")


def may_see_challenges(user, hackathon):
    """Rule 7.1 and 4.5 together, which is the pair most easily got wrong.

    Challenges are invisible until kickoff, to everyone except the people
    running the event. Not a hint, not a count, not a greyed-out list.
    """
    if hackathon.challenges_visible:
        return True
    return can(user, hackathon, "read_secret_challenges")


def may_see_standings(user, hackathon):
    """Rule 8.4: the *standings*, which is not the same question as a team
    seeing its own score.

    A team always sees its own points, whatever this returns. Twenty-four
    hours of submitting into silence is a dropbox, not a competition.
    """
    if hackathon.results_published_at:
        return True
    visibility = hackathon.leaderboard_visibility
    if visibility == Hackathon.PUBLIC:
        return True
    held = roles_for(user, hackathon)
    if visibility == Hackathon.PARTICIPANTS:
        return bool(held)
    return ADMIN in held
