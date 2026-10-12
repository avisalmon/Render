"""Open classes: the limits, the one door in, and the lens (SPR-M.60).

Everything an open class *does* lives here so the screens and the REST API ask
the same functions and cannot drift (RULE-3 for scope, the same habit as
`access.py` for who may see what).

Three things are worth reading before changing anything.

**`join_class` is the only inserter of `OpenClassMember`.** It takes the user it
is given and nothing else, and every caller passes `request.user`. An owner
adding somebody is therefore not a check somebody has to remember, it is a
function that does not exist (REQ-M.168).

**The lens is a list of fields, and the list is the privacy promise.** What an
owner may see about a member is written once in `LENS` and rendered both on the
page the person sees before joining and on the owner's page. A field that is not
in it cannot be on either (REQ-M.169, REQ-M.170).

**Nothing here writes to a learner's data.** Progress is read through
`cohort_progress`, certificates and activity are read from babook's tables by
account, and only for the open courses.
"""

import secrets

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

# REQ-M.174 — defaults from Q20, in one place so changing one is one line.
MAX_LIVE_CLASSES = 10
MAX_MEMBERS = 100

# What an owner can read about a member, in the words the joiner is shown.
LENS = [
    "השם שלכם כפי שהוא מופיע באתר",
    "אילו הדרכות פתוחות התחלתם",
    "כמה אחוזים סיימתם בכל אחת",
    "אילו תעודות סיום יש לכם",
    "מתי למדתם לאחרונה",
]

# What an owner never sees, shown next to the lens so the line is explicit.
NEVER = [
    "כתובת מייל",
    "שנת לידה ופרטי הורה",
    "מבחן הכניסה, הגשות ומשובים",
    "כיתות אחרות, או מוביל/ה אם יש",
]


class ClassFull(Exception):
    pass


class ClassClosed(Exception):
    pass


def live_classes(user):
    from .models import OpenClass

    return OpenClass.objects.filter(owner=user, archived_at__isnull=True)


def can_open_another(user):
    return live_classes(user).count() < MAX_LIVE_CLASSES


def display_name(user):
    """A name for a person, never their address.

    A profile with no name reads as a placeholder rather than falling back to
    the email, because the email is exactly what the lens promises not to show.
    """
    profile = getattr(user, "profile", None)
    name = (getattr(profile, "display_name", "") or "").strip()
    return name or "משתמש/ת ללא שם"


def create_class(owner, name):
    from .models import OpenClass

    return OpenClass.objects.create(
        owner=owner, name=name.strip()[:80], terms_accepted_at=timezone.now()
    )


@transaction.atomic
def join_class(open_class, user):
    """Make `user` a member. The only place a membership row is created.

    Idempotent: somebody already in is left alone, and somebody who left or was
    removed comes back on their old row, so a person is never listed twice and
    the owner cannot count them twice. Returns `(member, created)`.
    """
    from .models import OpenClass, OpenClassMember

    locked = OpenClass.objects.select_for_update().get(pk=open_class.pk)
    if not locked.is_open or locked.archived_at is not None:
        raise ClassClosed
    row = OpenClassMember.objects.filter(open_class=locked, user=user).first()
    if row is not None and row.ended_at is None:
        return row, False
    active = OpenClassMember.objects.filter(open_class=locked, ended_at__isnull=True).count()
    if active >= MAX_MEMBERS:
        raise ClassFull
    now = timezone.now()
    if row is None:
        row = OpenClassMember.objects.create(open_class=locked, user=user, joined_at=now)
    else:
        row.joined_at = now
        row.ended_at = None
        row.ended_by = None
        row.save(update_fields=["joined_at", "ended_at", "ended_by"])
    return row, True


def end_membership(member, by):
    """Leaving and being removed are the same row change, told apart by `ended_by`."""
    if member.ended_at is None:
        member.ended_at = timezone.now()
        member.ended_by = by
        member.save(update_fields=["ended_at", "ended_by"])
    return member


def replace_code(open_class):
    from .models import new_class_code

    open_class.code = new_class_code()
    open_class.save(update_fields=["code"])
    return open_class


def archive(open_class):
    if open_class.archived_at is None:
        open_class.archived_at = timezone.now()
        open_class.is_open = False
        open_class.save(update_fields=["archived_at", "is_open"])
    return open_class


def lens_rows(open_class):
    """The owner's view of the members, and the only one (REQ-M.169).

    A fixed number of queries however large the class is. Progress is limited to
    `open_slugs()`: a member's work in a leader's course is not the owner's to
    see, even when the same person is doing both.
    """
    members = list(
        open_class.members.filter(ended_at__isnull=True)
        .select_related("user", "user__profile")
        .order_by("joined_at")
    )
    return lens_for(members)


def lens_for(members):
    """The lens over any list of memberships, in the order given.

    Split out so the REST payload and the page are built by one function: a
    field added here shows up in both or neither (REQ-M.169).
    """
    from app.models import CourseCertificate, UserVideoProgress

    from .access import open_slugs
    from .progress import JustAUser, cohort_progress

    if not members:
        return []
    ids = [m.user_id for m in members]
    slugs = sorted(open_slugs())
    progress = cohort_progress([JustAUser(i) for i in ids], slugs)

    certs = {}
    for row in CourseCertificate.objects.filter(
        user_id__in=ids, course__slug__in=slugs
    ).values("user_id", "course__title", "course__slug"):
        certs.setdefault(row["user_id"], []).append(row["course__title"] or row["course__slug"])

    last = dict(
        UserVideoProgress.objects.filter(user_id__in=ids, video__course__slug__in=slugs)
        .values("user_id")
        .annotate(last=Max("updated_at"))
        .values_list("user_id", "last")
    )

    out = []
    for m in members:
        per = progress.get(m.user_id, {})
        started = [
            {"title": r["title"], "pct": r["pct"]} for r in per.values() if r["done"] > 0
        ]
        out.append(
            {
                "member": m,
                "name": display_name(m.user),
                "joined_at": m.joined_at,
                "started": started,
                "certificates": sorted(certs.get(m.user_id, [])),
                "last_active": last.get(m.user_id),
            }
        )
    return out


def code_matches(candidate, actual):
    """Constant-time, because a code is a secret typed into a box."""
    return secrets.compare_digest(candidate.encode("utf-8"), actual.encode("utf-8"))


def announce_join(open_class, user):
    """The bell for the owner when somebody joins. No email (REQ-M.173)."""
    from .models import Notification
    from .notify import notify

    notify(
        open_class.owner,
        Notification.OPEN_JOINED,
        f"{display_name(user)} הצטרף/ה לכיתה {open_class.name}",
        url=f"/matazim/classes/open/{open_class.pk}/",
        actor=user,
    )


GUESS_TRIES = 8
GUESS_WINDOW = 15 * 60


def guessing_rested(key):
    from django.core.cache import cache

    return (cache.get(key) or 0) >= GUESS_TRIES


def note_wrong_guess(key):
    from django.core.cache import cache

    if cache.add(key, 1, GUESS_WINDOW) is False:
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, GUESS_WINDOW)
