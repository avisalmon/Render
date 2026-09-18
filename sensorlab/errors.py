"""Error pages that stay inside the walls (building_an_app.md Rule 3).

Django's error handlers are project-wide, so an unhandled 403/404/500 under
/sensorlab/ would otherwise render babook's page: its title, its nav, its
chrome. These dispatch on the path — anything under /sensorlab/ gets
SensorLab's shell, everything else is untouched — and are composed into
mysite/errors.py by prefix, so no app learns about another.

Same shape as memz/errors.py and matazim/errors.py, deliberately: this is a
solved problem on this site and there is no value in a third variation.
"""

from django.shortcuts import render

PREFIX = "/sensorlab/"


def _ours(request):
    return request.path.startswith(PREFIX)


def page_not_found(request, exception=None):
    if not _ours(request):
        from django.views import defaults

        return defaults.page_not_found(request, exception)
    return render(request, "sensorlab/404.html", status=404)


def server_error(request):
    if not _ours(request):
        from django.views import defaults

        return defaults.server_error(request)
    return render(request, "sensorlab/500.html", status=500)


def permission_denied(request, exception=None):
    if not _ours(request):
        from django.views import defaults

        return defaults.permission_denied(request, exception)
    return render(request, "sensorlab/403.html", status=403)
