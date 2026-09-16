"""Handing an institution from one program manager to the next.

The review of 2026-09-14 named the tenancy root being a person as the largest
structural risk in the data model, and the first version of this file was the
bandage: a command that re-pointed every leader, event, invite and post from
one `User` to another. Avi then said "Go" to the `Institution` row
(`data_model.md` §6, SPR-M.40), and with it the problem this solved mostly
dissolved: rows belong to the institution, and the institution's `managers`
are whoever runs it. Nothing has to move.

What is left of a handover is two facts about people: the successor becomes a
manager, and the predecessor stops being one. Both through `roles`, so a
pending leader row on the successor is approved the same way it would be from
the screen (REQ-M.137), and both in one transaction, because an institution
with no manager for a moment is an institution nobody can act for.

**Records of who did something do not change.** `Leader.approved_by`,
`Submission.decided_by`, `RetentionRun.ran_by` and the like are history, and a
leader approved by נעמי stays approved by נעמי after she has gone. **Requests
stay with their author** (§4.11): the log is her voice.
"""

from django.db import transaction

# What an institution owns, and the field that says so. For the report only:
# these rows do not move any more, they belong to the institution whoever runs
# it, but "what am I handing over" is still a fair question to want answered.
OWNED = (
    ("matazim", "Leader", "institution"),
    ("matazim", "Event", "institution"),
    ("matazim", "LeaderInvite", "institution"),
    ("matazim", "Post", "institution"),
)


def owned_counts(institution):
    """How many rows each table holds for this institution."""
    from django.apps import apps

    if institution is None:
        return {name: 0 for _app, name, _field in OWNED}
    return {
        name: apps.get_model(app, name).objects.filter(**{field: institution}).count()
        for app, name, field in OWNED
    }


@transaction.atomic
def hand_over(old, new, *, by=None):
    """Make `new` a manager of everything `old` manages, and `old` no longer one.

    Returns the per-table counts the successor now runs, for the report.

    Refuses a handover to yourself, and refuses when `old` manages nothing:
    handing over an institution somebody does not run is not a handover, it is
    a grant with a misleading name, and the grant screen exists for that.
    """
    from .models import Institution
    from .roles import grant_program_manager, revoke_program_manager

    if old.pk == new.pk:
        raise ValueError("handover to the same person is not a handover")

    theirs = list(Institution.objects.filter(managers=old))
    if not theirs:
        raise ValueError("that person manages no institution")

    # `institutions=theirs`, not the default. The first version of this called
    # `grant_program_manager(new, by=by)` with no argument, which joins
    # whatever institution `Institution.default()` finds (the earliest
    # created), and in a two-institution world that is not necessarily the one
    # being handed over. The successor ended up a manager of both, and
    # `institution_of()` picked the wrong one to scope their screens by.
    grant_program_manager(new, by=by, institutions=theirs)
    revoke_program_manager(old)

    counts = {name: 0 for _app, name, _field in OWNED}
    for inst in theirs:
        for name, n in owned_counts(inst).items():
            counts[name] += n
    return counts
