"""The two material shelves (REQ-G.120 to G.126), in one place. Copied from
cohort/shelves.py (Rule 2: copied, not shared).

The shared shelf (owner is None) is Avi's: every signed-in person sees it, only
an admin changes it or its order. A private shelf belongs to one person: they
alone see it, add to it, order it and delete from it. Nobody else sees a
private shelf, admins included, so "only you see this" stays true.
Refusals carry a strings key, so each says itself in the reader's language.
"""

from django.db import transaction
from django.db.models import Max, Q

from .models import Material

QUOTA_BYTES = 200 * 1024 * 1024     # per person, their private files together
FILE_BYTES = 25 * 1024 * 1024       # per file


class Refused(Exception):
    """`str()` is a key in gallery/strings.py."""


def visible(person):
    """Everything this person may see: the shared shelf and their own."""
    return Material.objects.filter(Q(owner__isnull=True) | Q(owner=person))


def shared():
    return Material.objects.filter(owner__isnull=True)


def mine(person):
    return Material.objects.filter(owner=person)


def may_change(person, item):
    if item.owner_id is None:
        return person.admin
    return item.owner_id == person.pk


def next_position(owner):
    top = Material.objects.filter(owner=owner).aggregate(m=Max("position"))["m"] or 0
    return top + 10


def used_bytes(person, but=None):
    """Bytes of this person's own files. A copy kept from the shared shelf
    shares its file, so it costs them nothing."""
    total = 0
    common = shared().exclude(file="").values("file")
    for m in mine(person).exclude(file="").exclude(file__in=common).exclude(pk=getattr(but, "pk", None)):
        try:
            total += m.file.size
        except (OSError, ValueError):
            pass
    return total


def check_quota(person, new_bytes, but=None):
    if new_bytes > FILE_BYTES:
        raise Refused("materials.file_big")
    if used_bytes(person, but=but) + new_bytes > QUOTA_BYTES:
        raise Refused("materials.no_room")


@transaction.atomic
def reorder(person, shelf, ids):
    """Put a shelf in the order given: every item of the shelf, and nothing
    else, or nothing changes."""
    if shelf == "shared":
        if not person.admin:
            raise Refused("materials.only_avi_orders")
        items = list(shared())
    elif shelf == "mine":
        items = list(mine(person))
    else:
        raise Refused("materials.bad_order")
    by_id = {m.pk: m for m in items}
    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        raise Refused("materials.bad_order") from None
    if sorted(ids) != sorted(by_id):
        raise Refused("materials.stale_order")
    for i, pk in enumerate(ids):
        m = by_id[pk]
        if m.position != (i + 1) * 10:
            m.position = (i + 1) * 10
            m.save(update_fields=["position"])
    return ids


def keep(person, item):
    """A copy of a shared item on this person's shelf. Returns (copy, created)."""
    if item.owner_id is not None:
        raise Refused("materials.keep_shared_only")
    same = mine(person).filter(kind=item.kind, title=item.title, url=item.url, file=item.file.name or "").first()
    if same:
        return same, False
    copy = Material.objects.create(
        kind=item.kind, title=item.title, line=item.line, url=item.url, file=item.file.name or "",
        owner=person, position=next_position(person), created_by=person.user,
    )
    return copy, True


def remove(item):
    """Delete an item, and its file only if no other item points at it (a
    kept copy shares the shared item's file)."""
    name = item.file.name if item.file else ""
    storage = item.file.storage if item.file else None
    item.delete()
    if name and not Material.objects.filter(file=name).exists():
        storage.delete(name)


def file_visible_to(person, name):
    return visible(person).filter(file=name).exists()


def total(person):
    used = used_bytes(person)
    return {"used": used, "quota": QUOTA_BYTES, "used_mb": round(used / 1024 / 1024, 1)}
