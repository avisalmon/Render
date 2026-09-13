"""DRF permission wrapping ustrip's one access rule (spec §3).

Same check everywhere in the app, page views and API alike: `is_family`.
"""

from rest_framework.permissions import BasePermission

from .access import is_family


class IsFamilyMember(BasePermission):
    message = "You must be a family member to do this."

    def has_permission(self, request, view):
        return is_family(request.user)
