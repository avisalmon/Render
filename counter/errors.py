"""Error pages that stay inside counter's walls (building_an_app.md Rule 3).
Composed into mysite/errors.py by path prefix, like memz's."""

from django.shortcuts import render

PREFIX = "/counter/"


def _ours(request):
    return request.path.startswith(PREFIX)


def page_not_found(request, exception=None):
    if not _ours(request):
        from django.views import defaults

        return defaults.page_not_found(request, exception)
    return render(request, "counter/404.html", status=404)


def server_error(request):
    if not _ours(request):
        from django.views import defaults

        return defaults.server_error(request)
    return render(request, "counter/500.html", status=500)


def permission_denied(request, exception=None):
    if not _ours(request):
        from django.views import defaults

        return defaults.permission_denied(request, exception)
    return render(request, "counter/403.html", status=403)
