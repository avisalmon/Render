from rest_framework.permissions import BasePermission

from ..access import profile_for


class HasBooksProfile(BasePermission):
    """Signed in and onboarded. Every Books endpoint starts here; querysets
    then scope to the caller, so nobody reaches another person's rows."""

    def has_permission(self, request, view):
        return profile_for(request.user) is not None
