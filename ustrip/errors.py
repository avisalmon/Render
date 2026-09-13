"""Error pages that stay inside the walls (spec §1: "no route back").

Same reasoning as matazim/errors.py (REQ-M.2): Django's error handlers are
project-wide, so an unhandled 404/500 anywhere under /ustrip/ would otherwise
render babook's page — its title, its drawer, its nav — breaking the
isolation spec §1 requires. These dispatch on the path: anything under
/ustrip/ gets our shell, everything else is untouched.

The family-group gate itself (access.py) never reaches these — it renders
its own access-denied page directly rather than raising. This file only
covers what Django itself raises: a bad URL under /ustrip/, or a server
error.
"""

from django.shortcuts import render

PREFIX = "/ustrip/"


def _ours(request):
    return request.path.startswith(PREFIX)


def page_not_found(request, exception=None):
    if not _ours(request):
        from django.views import defaults

        return defaults.page_not_found(request, exception)
    return render(request, "ustrip/404.html", status=404)


def server_error(request):
    if not _ours(request):
        from django.views import defaults

        return defaults.server_error(request)
    return render(request, "ustrip/500.html", status=500)
