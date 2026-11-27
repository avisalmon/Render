"""Error pages that stay inside /breakout/ (Rule 3). Composed into
mysite/errors.py by prefix like every other app's."""

from django.shortcuts import render

PREFIX = "/breakout/"


def _ours(request):
    return request.path.startswith(PREFIX)


def page_not_found(request, exception=None):
    if not _ours(request):
        from django.views import defaults

        return defaults.page_not_found(request, exception)
    return render(request, "breakout/error.html", {"code": 404, "title": "אין כאן כלום", "text": "העמוד שחיפשתם לא נמצא."}, status=404)


def server_error(request):
    if not _ours(request):
        from django.views import defaults

        return defaults.server_error(request)
    return render(request, "breakout/error.html", {"code": 500, "title": "משהו השתבש", "text": "נסו שוב בעוד רגע."}, status=500)


def permission_denied(request, exception=None):
    if not _ours(request):
        from django.views import defaults

        return defaults.permission_denied(request, exception)
    return render(request, "breakout/error.html", {"code": 403, "title": "זה לא שלכם", "text": "רק מי שכתב את האתגר יכול לערוך אותו."}, status=403)
