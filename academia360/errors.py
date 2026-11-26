"""Academia360's own error pages, composed into the project's single handlers
by mysite/errors.py (the isolated-app pattern)."""

from django.shortcuts import render

PREFIX = "/academia360/"

TEXT = {
    403: ("אין גישה", "העמוד הזה פתוח רק לאנשים עם תפקיד במערכת. אם זה אתם, היכנסו תחילה."),
    404: ("העמוד לא נמצא", "אולי הקישור השתנה. אפשר להתחיל מחדש מדף הבית."),
    500: ("משהו השתבש אצלנו", "לא אצלכם. נסו שוב בעוד רגע."),
}


def _page(request, status):
    title, text = TEXT[status]
    return render(request, "academia360/error.html", {"status": status, "title": title, "text": text},
                  status=status)


def page_not_found(request, exception=None):
    return _page(request, 404)


def server_error(request):
    return _page(request, 500)


def permission_denied(request, exception=None):
    return _page(request, 403)
