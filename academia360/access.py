"""The three circles, in one place (spec 1.3, 2.3, 4.9).

Every view, every API endpoint and, later, the AI retrieval ask here and
nowhere else. A model says which circle it sits in (`CIRCLE`), how a row
reaches its institution (`INSTITUTION_PATH`) and, when a person may read a
row about themselves, the path to them (`OWN_PATH`). Two refinements:
`PUBLIC_Q` (rows of a closed model that are public anyway), `INSTITUTION_Q`
(the institution rule opens only rows matching it, e.g. a sent letter), and
`CIRCLE = "private"` (owner and admin only).

The admin (a superuser, or a Role of kind admin) sees and does everything.
A committee member sees everything in every circle. A program leader sees the
public circle and the institution circle of their own institutions. Everyone
else sees the public circle. A person can hold several roles; the higher one
wins (spec 2.6.1).

Writing is decided by `may_write`, from one policy table, never in a view.
"""

from functools import wraps

from django.db.models import Q
from django.shortcuts import render

from .models import COMMITTEE, INSTITUTION, PUBLIC, CommitteeAttribute, LeaderOf, Role

PRIVATE = "private"


def _authenticated(user):
    return bool(user is not None and getattr(user, "is_authenticated", False))


def roles(user):
    """The active role kinds this person holds, as a set."""
    if not _authenticated(user):
        return set()
    cached = getattr(user, "_a360_roles", None)
    if cached is None:
        cached = set(Role.objects.filter(user=user, active=True).values_list("kind", flat=True))
        if user.is_superuser:
            cached.add(Role.ADMIN)
        user._a360_roles = cached
    return cached


def is_admin(user):
    return Role.ADMIN in roles(user)


def is_committee(user):
    """Admin counts: the higher role wins."""
    held = roles(user)
    return Role.ADMIN in held or Role.COMMITTEE_MEMBER in held


def is_chair(user):
    if is_admin(user):
        return True
    if Role.COMMITTEE_MEMBER not in roles(user):
        return False
    return CommitteeAttribute.objects.filter(user=user, kind=CommitteeAttribute.CHAIR).exists()


def is_leader(user):
    return bool(leader_institution_ids(user))


def leader_institution_ids(user):
    if not _authenticated(user) or Role.LEADER not in roles(user):
        return set()
    cached = getattr(user, "_a360_leads", None)
    if cached is None:
        cached = set(LeaderOf.objects.filter(user=user, active=True).values_list("institution_id", flat=True))
        user._a360_leads = cached
    return cached


def circle(user):
    """The widest circle this person is in."""
    if is_committee(user):
        return COMMITTEE
    if leader_institution_ids(user):
        return INSTITUTION
    return PUBLIC


def circle_of(model):
    return getattr(model, "CIRCLE", PUBLIC)


# ------------------------------------------------------------------ reading

def visible(queryset, user):
    """The rows of this queryset the person may read. The one filter."""
    model = queryset.model
    c = circle_of(model)
    if is_admin(user):
        return queryset
    if c == PUBLIC:
        return queryset
    if c == COMMITTEE and is_committee(user):
        return queryset
    if c == INSTITUTION and is_committee(user):
        return queryset
    conditions = Q(pk__in=[])  # nothing, until a rule below opens something
    public_q = getattr(model, "PUBLIC_Q", None)
    if public_q is not None:
        conditions |= public_q
    own = getattr(model, "OWN_PATH", None)
    if own and _authenticated(user):
        conditions |= Q(**{own: user})
    path = getattr(model, "INSTITUTION_PATH", None)
    mine = leader_institution_ids(user)
    if c != PRIVATE and path and mine:
        opened = Q(**{f"{path}__in": mine})
        inst_q = getattr(model, "INSTITUTION_Q", None)
        if inst_q is not None:
            opened &= inst_q
        conditions |= opened
    return queryset.filter(conditions)


def can_see(user, obj):
    """One row: the same rule as `visible`."""
    model = type(obj)
    if circle_of(model) == PUBLIC or is_admin(user):
        return True
    return visible(model._default_manager.filter(pk=obj.pk), user).exists()


def institution_id_of(obj):
    """Follow the model's INSTITUTION_PATH on a row; None when it has none."""
    path = getattr(type(obj), "INSTITUTION_PATH", None)
    if not path:
        return None
    parts = path.split("__")
    node = obj
    for part in parts[:-1]:
        node = getattr(node, part, None)
        if node is None:
            return None
    return getattr(node, parts[-1] + "_id", None)


def owner_id_of(obj):
    path = getattr(type(obj), "OWN_PATH", None)
    if not path:
        return None
    parts = path.split("__")
    node = obj
    for part in parts[:-1]:
        node = getattr(node, part, None)
        if node is None:
            return None
    return getattr(node, parts[-1] + "_id", None)


# ------------------------------------------------------------------ writing

ADMIN, CHAIR, COMMITTEE_W, LEADER_OR_COMMITTEE, OWN, SIGNED_IN_OWN = (
    "admin", "chair", "committee", "leader_or_committee", "own", "signed_in_own")

# Who may create, change or delete rows of each model through the API.
# Models not listed are the admin's (public knowledge, the program, roles).
WRITE_POLICY = {
    # a person's own things
    "PublicProfile": SIGNED_IN_OWN, "PublicComment": SIGNED_IN_OWN, "Like": SIGNED_IN_OWN,
    "RoleRequest": SIGNED_IN_OWN, "AiConversation": SIGNED_IN_OWN, "AiMessage": OWN,
    # what the institution submits: its leaders, and the committee side that extracts from files
    "Submission": LEADER_OR_COMMITTEE, "SubmittedFile": LEADER_OR_COMMITTEE,
    "GraduateProfile": LEADER_OR_COMMITTEE, "GraduateSkill": LEADER_OR_COMMITTEE,
    "Standard": LEADER_OR_COMMITTEE, "PlanProgram": LEADER_OR_COMMITTEE,
    "PlanComponent": LEADER_OR_COMMITTEE, "Governance": LEADER_OR_COMMITTEE,
    "KpiDefinition": LEADER_OR_COMMITTEE, "KpiValue": LEADER_OR_COMMITTEE, "TargetChoice": LEADER_OR_COMMITTEE,
    "BudgetLine": LEADER_OR_COMMITTEE, "Commitment": LEADER_OR_COMMITTEE, "CommunityShare": LEADER_OR_COMMITTEE,
    # the committee's work
    "Participation": COMMITTEE_W, "ContactPerson": COMMITTEE_W, "Analysis": COMMITTEE_W,
    "CriterionFinding": COMMITTEE_W, "Review": COMMITTEE_W, "ReviewAnswer": COMMITTEE_W,
    "Discussion": COMMITTEE_W, "DiscussionPost": COMMITTEE_W, "Meeting": COMMITTEE_W,
    "LetterTemplateSection": COMMITTEE_W, "ResponseLetter": COMMITTEE_W, "LetterSection": COMMITTEE_W,
    "IndexChunk": COMMITTEE_W,
    # the chair's
    "Decision": CHAIR, "CorrectionProposal": SIGNED_IN_OWN,  # anyone proposes; a chair decides (see guard)
}

# Fields only a chair (or the admin) may change, on models others may write.
CHAIR_ONLY_FIELDS = {
    "ResponseLetter": {"sent_at", "sent_by"},
    "CorrectionProposal": {"status", "decided_by", "decided_at"},
}


def may_write(user, model, obj=None):
    """Create (obj None) or change/delete (obj given). For creates under a
    leader policy the API saves inside a transaction and asks again with the
    row, so a leader cannot plant a row in another institution."""
    if is_admin(user):
        return True
    if not _authenticated(user):
        return False
    policy = WRITE_POLICY.get(model.__name__, ADMIN)
    # A row others write but a chair decides on (a correction's status, a
    # letter's sending): the chair may always change it.
    if obj is not None and model.__name__ in CHAIR_ONLY_FIELDS and is_chair(user):
        return True
    if policy == ADMIN:
        return False
    if policy == CHAIR:
        return is_chair(user)
    if policy == COMMITTEE_W:
        return is_committee(user)
    if policy == LEADER_OR_COMMITTEE:
        if is_committee(user):
            return True
        mine = leader_institution_ids(user)
        if not mine:
            return False
        if obj is None:
            return True  # checked again on the saved row
        inst = institution_id_of(obj)
        if inst is None:
            return False
        if inst not in mine:
            return False
        # A leader edits while the package is theirs to edit: drafts and
        # open submissions, never a package the committee already answered.
        sub = getattr(obj, "submission", None) or (obj if model.__name__ == "Submission" else None)
        if sub is not None and getattr(sub, "status", "draft") == "responded":
            return False
        return True
    if policy in (OWN, SIGNED_IN_OWN):
        if obj is None:
            return policy == SIGNED_IN_OWN or True
        return owner_id_of(obj) == user.pk
    return False


def chair_only_fields_touched(user, model, before, after):
    """The names of chair-only fields a non-chair is trying to change."""
    if is_chair(user):
        return set()
    guarded = CHAIR_ONLY_FIELDS.get(model.__name__, set())
    return {f for f in guarded if before.get(f) != after.get(f)}


# -------------------------------------------------------------------- pages

def no_access(request, status=403):
    """The plain 'no access' page in the app's own frame (spec 4.9): the app
    does not hide that it exists."""
    return render(request, "academia360/no_access.html", {"status": status}, status=status)


def committee_only(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_committee(request.user):
            return no_access(request)
        return view(request, *args, **kwargs)
    return wrapped


def chair_only(view):
    """The chair's acts (the decision, sending a letter): a chair or the admin."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_chair(request.user):
            return no_access(request)
        return view(request, *args, **kwargs)
    return wrapped


def admin_only(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_admin(request.user):
            return no_access(request)
        return view(request, *args, **kwargs)
    return wrapped
