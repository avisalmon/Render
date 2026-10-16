from rest_framework.permissions import BasePermission

from ..access import can_use


class IsCounterOwner(BasePermission):
    """The owner side: Avi only (access.can_use). Everything is also
    owner-scoped in the querysets, so loosening this alone shares nothing."""

    def has_permission(self, request, view):
        return can_use(request.user)
