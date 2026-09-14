"""Error pages that stay inside the walls (building_an_app.md Rule 3).

Same reasoning as matazim/errors.py and ustrip/errors.py: Django's error
handlers are project-wide, so an unhandled 403/404/500 under /memz/ would
otherwise render babook's page. These dispatch on the path: anything under
/memz/ gets memz's shell, everything else is untouched. Composed into
mysite/errors.py by prefix, so no app learns about another.
"""

from django.shortcuts import render

PREFIX = "/memz/"


def _ours(request):
    return request.path.startswith(PREFIX)


def page_not_found(request, exception=None):
    if not _ours(request):
        from django.views import defaults

        return defaults.page_not_found(request, exception)
    return render(request, "memz/404.html", status=404)


def server_error(request):
    if not _ours(request):
        from django.views import defaults

        return defaults.server_error(request)
    return render(request, "memz/500.html", status=500)


def permission_denied(request, exception=None):
    if not _ours(request):
        from django.views import defaults

        return defaults.permission_denied(request, exception)
    return render(request, "memz/403.html", status=403)
