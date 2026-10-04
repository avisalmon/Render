"""The gate: nobody but a player can tell improv exists (spec ch. 7).

Every request under /improv is stopped here, before routing, before CSRF,
before any view, unless the person is a player. A refusal is the site's own
404, rendered by the site's own handler, so a stranger sees the same page, the
same first-visit strip and the same cookies they would get for a path that was
never there. That is why the gate sits late in the stack (after authentication
and after the first-touch capture): everything the site does to any request has
already happened to this one.

Two things would still give the app away, and both are handled here:

- CommonMiddleware answers a 404 with a redirect when the path plus a slash
  resolves, so /improv would bounce to /improv/ for a stranger. A refused
  request is therefore pointed at an empty urlconf, where nothing resolves.
- A player who leaves off the slash is redirected by the gate itself, because
  the empty-urlconf trick is only for strangers.

Not an improv-branded 404, on purpose. A branded page would tell a stranger
what they had found, which is the opposite of the gate. This is the recorded
exception to the rule that each app owns its error pages.
"""

from django.http import Http404, HttpResponsePermanentRedirect
from django.urls import get_resolver

from .access import is_improv_path, is_player


class GateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_improv_path(request.path_info):
            if not is_player(request.user):
                request.urlconf = "improv.nothing_urls"
                return get_resolver().resolve_error_handler(404)(request, Http404())
            if not request.path_info.endswith("/"):
                return HttpResponsePermanentRedirect(request.get_full_path(force_append_slash=True))
        return self.get_response(request)
