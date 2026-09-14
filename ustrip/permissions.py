"""DRF permissions wrapping ustrip's access rules (spec §3, §4.1).

Same check everywhere in the app, page views and API alike: `is_family`.
The one refinement is for things that are one person's own words or
gesture — a comment, a like: those can only be changed by the person who
made them (or a superuser). Everything else in the itinerary deliberately
has no creator lock.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .access import is_family


class IsFamilyMember(BasePermission):
    message = "You must be a family member to do this."

    def has_permission(self, request, view):
        return is_family(request.user)


class IsOwnerOrReadOnly(BasePermission):
    """Object-level: reading is open to the family; changing or deleting is
    for whoever made it. The viewset names the owner field (`author` for a
    comment, `user` for a like)."""

    message = "Only the person who wrote this can change it."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS or request.user.is_superuser:
            return True
        owner_field = getattr(view, "owner_field", "author")
        return getattr(obj, f"{owner_field}_id") == request.user.id
