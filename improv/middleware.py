"""The gate: every page of the app is for a signed-in person (spec ch. 7).

Anyone who signs in or signs up may play. A visitor who is not signed in meets the app's own front
door at /improv/, which has the log in and sign up, and is sent back to the page they asked for once
they are in. The API is left to its permission class, which answers a visitor with a plain 403 so a
script gets an answer it can read rather than a page of HTML.

This sits after authentication so it can see who is asking.
"""

from urllib.parse import quote

from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect

from .access import API_PREFIX, HOME, PUBLIC_PATHS, is_improv_path, is_player


class GateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if is_improv_path(path):
            if not path.endswith("/"):
                return HttpResponsePermanentRedirect(request.get_full_path(force_append_slash=True))
            if not is_player(request.user) and path not in PUBLIC_PATHS and not path.startswith(API_PREFIX):
                return HttpResponseRedirect(f"{HOME}?next={quote(request.get_full_path(), safe='/')}")
        return self.get_response(request)
