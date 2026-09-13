"""Shared reorder ("prioritize") helper, used by the itinerary-item and
checklist-item viewsets' `move` action. Not itself a REST verb — DRF's
convention for an action that doesn't fit create/read/update/delete is a
custom `@action` on the viewset, which is what calls this.
"""


def move(item, siblings, direction):
    """Swap `order` with the previous/next sibling. `siblings` must already
    be ordered by `order`. No creator lock — any family member can reorder
    anything, same as edit/delete (spec §4.1 extended to every list)."""
    ordered = list(siblings)
    idx = ordered.index(item)
    swap_idx = idx - 1 if direction == "up" else idx + 1
    if not (0 <= swap_idx < len(ordered)):
        return False
    other = ordered[swap_idx]
    item.order, other.order = other.order, item.order
    item.save(update_fields=["order"])
    other.save(update_fields=["order"])
    return True
