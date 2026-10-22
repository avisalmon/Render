"""The two material shelves (REQ-C.35, C.36), in one place.

The course shelf (owner is None) is Avi's: everybody inside sees it, only an
admin changes it or its order. A private shelf belongs to one member: they
alone see it, add to it, order it and delete from it. Nobody else sees a
private shelf, admins included, so "only you see this" stays true.
"""

from django.db import transaction
from django.db.models import Max, Q

from .models import Material

QUOTA_BYTES = 200 * 1024 * 1024     # per person, their private files together
FILE_BYTES = 25 * 1024 * 1024       # per file


class Refused(Exception):
    pass


def visible(member):
    """Everything this person may see: the course shelf and their own."""
    return Material.objects.filter(Q(owner__isnull=True) | Q(owner=member))


def course():
    return Material.objects.filter(owner__isnull=True)


def mine(member):
    return Material.objects.filter(owner=member)


def may_change(member, item):
    if item.owner_id is None:
        return member.admin
    return item.owner_id == member.pk


def next_position(owner):
    top = Material.objects.filter(owner=owner).aggregate(m=Max("position"))["m"] or 0
    return top + 10


def used_bytes(member, but=None):
    """Bytes of this person's own files. A copy kept from the course shelf
    shares the course's file, so it costs them nothing."""
    total = 0
    shared = course().exclude(file="").values("file")
    for m in mine(member).exclude(file="").exclude(file__in=shared).exclude(pk=getattr(but, "pk", None)):
        try:
            total += m.file.size
        except (OSError, ValueError):
            pass
    return total


def check_quota(member, new_bytes, but=None):
    if new_bytes > FILE_BYTES:
        raise Refused("הקובץ גדול מ-25MB.")
    if used_bytes(member, but=but) + new_bytes > QUOTA_BYTES:
        raise Refused("אין מספיק מקום בלוח הפרטי שלך (עד 200MB לכל הקבצים יחד). אפשר למחוק קובץ ישן.")


@transaction.atomic
def reorder(member, shelf, ids):
    """Put a shelf in the order given. Every item of the shelf, and nothing
    else, or nothing changes."""
    if shelf == "course":
        if not member.admin:
            raise Refused("רק אבי קובע את סדר חומרי ההשתלמות.")
        items = list(course())
    elif shelf == "mine":
        items = list(mine(member))
    else:
        raise Refused("לוח לא מוכר.")
    by_id = {m.pk: m for m in items}
    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        raise Refused("סדר לא תקין.")
    if sorted(ids) != sorted(by_id):
        raise Refused("הסדר לא תואם את הלוח. רעננו את הדף ונסו שוב.")
    for i, pk in enumerate(ids):
        m = by_id[pk]
        if m.position != (i + 1) * 10:
            m.position = (i + 1) * 10
            m.save(update_fields=["position"])
    return ids


def keep(member, item):
    """A copy of a course item on this person's shelf. Returns (copy, created)."""
    if item.owner_id is not None:
        raise Refused("אפשר לשמור אצלך רק חומר מחומרי ההשתלמות.")
    same = mine(member).filter(kind=item.kind, title=item.title, url=item.url, file=item.file.name or "").first()
    if same:
        return same, False
    copy = Material.objects.create(
        kind=item.kind, title=item.title, line=item.line, url=item.url, file=item.file.name or "",
        owner=member, position=next_position(member), created_by=member.user,
    )
    return copy, True


def remove(item):
    """Delete an item, and its file only if no other item points at it (a
    copy kept from the course shelf shares the course item's file)."""
    name = item.file.name if item.file else ""
    storage = item.file.storage if item.file else None
    item.delete()
    if name and not Material.objects.filter(file=name).exists():
        storage.delete(name)


def file_visible_to(member, name):
    """Whether a materials file may be handed to this person."""
    return visible(member).filter(file=name).exists()


def total(member):
    used = used_bytes(member)
    return {"used": used, "quota": QUOTA_BYTES, "used_mb": round(used / 1024 / 1024, 1)}

