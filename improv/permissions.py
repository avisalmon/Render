"""The gate, repeated inside the API.

GateMiddleware already sends a visitor to the front door before routing. This is the second lock:
if the middleware is ever removed or reordered the API still refuses a visitor, with the
session-auth 403, and still lets any signed-in person through.
"""

from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import BasePermission

from .access import is_player


class IsPlayer(BasePermission):
    def has_permission(self, request, view):
        if not is_player(request.user):
            raise NotAuthenticated
        return True
