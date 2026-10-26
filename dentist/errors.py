"""Error pages that stay inside the clinic's walls (spec Rule 2.2).

Django's error handlers are project-wide, so without this every "forbidden"
and "not found" under /dentist/ would render babook's page, with babook's
header and Hebrew. CrashTech shipped exactly that for six sprints before a
screenshot caught it (postmortems PM-8), so for dentist it is here on day
one, composed into mysite/errors.py by prefix like every other app.
"""

from django.shortcuts import render

PREFIX = "/dentist/"


def _ours(request):
    return request.path.startswith(PREFIX)


def page_not_found(request, exception=None):
    if not _ours(request):
        from django.views import defaults

        return defaults.page_not_found(request, exception)
    return render(request, "dentist/404.html", status=404)


def server_error(request):
    if not _ours(request):
        from django.views import defaults

        return defaults.server_error(request)
    return render(request, "dentist/500.html", status=500)


def permission_denied(request, exception=None):
    if not _ours(request):
        from django.views import defaults

        return defaults.permission_denied(request, exception)
    return render(request, "dentist/403.html", status=403)
