"""Error pages inside the gallery's walls, composed into mysite/errors.py by path."""

from django.shortcuts import render

PREFIX = "/gallery/"


def _page(request, status, key):
    return render(request, "gallery/error.html", {"status": status, "key": key}, status=status)


def page_not_found(request, exception=None):
    return _page(request, 404, "error.404")


def server_error(request):
    return _page(request, 500, "error.500")


def permission_denied(request, exception=None):
    return _page(request, 403, "error.403")
