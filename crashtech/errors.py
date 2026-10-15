"""Error pages that stay inside the walls (building_an_app.md Rule 3).

Django's error handlers are project-wide, so an unhandled 403/404/500
under /crashtech/ renders babook's page: its title, its nav, its Hebrew
chrome. That is exactly what Rule 2.2.1 forbids, and it had been true of
every permission refusal in this app since C.1 without a single test
noticing, because the tests asserted on the status code and never on what
the page actually said. A screenshot of a 403 caught it.

Same shape as sensorlab/errors.py, memz/errors.py and matazim/errors.py,
deliberately: this is a solved problem on this site and there is no value
in a fourth variation.

One note on the prefix. The 2026 platform still lives under /crashtech/
too (Rule 13.1), so until C.8 retires it, its refusals get these pages
rather than babook's. That is an improvement rather than a regression:
neither page says anything specific to either app.
"""

from django.shortcuts import render

PREFIX = "/crashtech/"


def _ours(request):
    return request.path.startswith(PREFIX)


def page_not_found(request, exception=None):
    if not _ours(request):
        from django.views import defaults

        return defaults.page_not_found(request, exception)
    return render(request, "crashtech/404.html", status=404)


def server_error(request):
    if not _ours(request):
        from django.views import defaults

        return defaults.server_error(request)
    return render(request, "crashtech/500.html", status=500)


def permission_denied(request, exception=None):
    if not _ours(request):
        from django.views import defaults

        return defaults.permission_denied(request, exception)
    return render(request, "crashtech/403.html", status=403)
