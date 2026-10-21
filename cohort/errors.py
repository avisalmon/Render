"""Error pages inside the app's walls, composed into mysite/errors.py by path."""

from django.shortcuts import render

PREFIX = "/cohort/"


def _page(request, status, text):
    return render(request, "cohort/error.html", {"status": status, "text": text}, status=status)


def page_not_found(request, exception=None):
    return _page(request, 404, "הדף הזה לא נמצא, או שאין לך גישה אליו.")


def server_error(request):
    return render(request, "cohort/error.html", {"status": 500, "text": "משהו השתבש אצלנו. נסו שוב בעוד רגע."}, status=500)


def permission_denied(request, exception=None):
    return _page(request, 403, "אין לך גישה לדף הזה.")
