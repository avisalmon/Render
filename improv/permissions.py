"""The gate, repeated inside the API.

GateMiddleware already stops outsiders before routing. This is the second lock:
if the middleware is ever removed or reordered the API still answers an outsider
with a plain 404, never a 401 or 403 that would say something is here.
"""

from django.http import Http404
from rest_framework.permissions import BasePermission

from .access import is_player


class IsPlayer(BasePermission):
    def has_permission(self, request, view):
        if not is_player(request.user):
            raise Http404
        return True
