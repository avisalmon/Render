"""Error pages inside the app's walls, composed into mysite/errors.py by path."""

from django.shortcuts import render

PREFIX = "/design3d/"


def _page(request, status, text):
    return render(request, "design3d/error.html", {"status": status, "text": text}, status=status)


def page_not_found(request, exception=None):
    return _page(request, 404, "This page is not here.")


def server_error(request):
    return render(request, "design3d/error.html", {"status": 500, "text": "Something broke on our side. Try again in a moment."}, status=500)


def permission_denied(request, exception=None):
    return _page(request, 403, "This is not open to you.")
