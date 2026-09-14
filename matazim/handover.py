"""Handing an institution from one program manager to the next.

The review of 2026-09-14 named this the largest structural risk in the data
model: the tenancy root is a person, not an institution. `Leader`, `Event`,
`LeaderInvite` and `Post` all point at the `User` who runs the programme, and
`access.py` scopes every screen by that user. §4.8 argued that a second network
becomes a table on the day one exists, and never considered the day the first
manager leaves. On that day her successor signs in to an empty programme and
every row she owned is stranded.

The right fix is an `Institution` row, and that is a data-model change the
methodology reserves for Avi (`docs/matazim/data_model.md` §6 carries the
proposal). This is the fix that needs no approval: one command that moves
everything one manager owns to another, atomically, and writes down that it did.

**What moves and what does not.** Ownership moves: leaders, events, invites,
posts. Records of who did something do not: `Leader.approved_by`,
`Submission.decided_by`, `RetentionRun.ran_by` and the like are history, and
history is not reassigned when a person leaves. A leader approved by נעמי stays
approved by נעמי after she has gone.

**Requests stay with their author.** §4.11's log is her voice, and it belongs to
whoever spoke. A successor inherits the programme, not the things the previous
manager asked for on her own behalf.
"""

from django.db import transaction


OWNED = (
    ("matazim", "Leader", "program_manager"),
    ("matazim", "Event", "program_manager"),
    ("matazim", "LeaderInvite", "program_manager"),
    ("matazim", "Post", "program_manager"),
)


def owned_counts(user):
    """How many rows each table holds for this manager. For the report."""
    from django.apps import apps

    return {
        model_name: apps.get_model(app, model_name).objects.filter(**{field: user}).count()
        for app, model_name, field in OWNED
    }


@transaction.atomic
def hand_over(old, new, *, by=None):
    """Move everything `old` owns to `new`. Returns the per-table counts moved.

    Atomic, because a handover that moves the leaders and then fails on the
    events leaves an institution split between two people, which is worse
    than either state it was moving between.

    `new` is made a program manager if they are not one, through the same
    function the grant screen uses, so a pending leader row on the successor is
    approved the same way it would be from the screen (REQ-M.137).

    `old` keeps their role. Removing it is a separate decision that the screen
    handles (REQ-M.114), and a handover that quietly demoted somebody would be
    two decisions dressed as one.
    """
    from django.apps import apps

    from .roles import grant_program_manager

    if old.pk == new.pk:
        raise ValueError("handover to the same person is not a handover")

    grant_program_manager(new, by=by)

    moved = {}
    for app, model_name, field in OWNED:
        model = apps.get_model(app, model_name)
        moved[model_name] = model.objects.filter(**{field: old}).update(**{field: new})

    return moved
