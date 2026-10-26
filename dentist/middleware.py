"""Puts the tried role (spec Rule 3.7) on the user for `access.py`.

One line of state, read from the session on every request under
/dentist/ and attached to the user object, so the access functions, which
take a user and not a request, can honour it; the same user object reaches
the DRF views, so the API honours it too. Nothing else reads it.
"""

from .access import TRY_KEY


class TryAsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/dentist/") and hasattr(request, "session") and request.user.is_authenticated:
            request.user.dn_try = request.session.get(TRY_KEY)
        return self.get_response(request)
