"""Error pages that stay inside the walls.

REQ-M.2. Django's error handlers are project-wide, so a 403 raised anywhere,
including inside /matazim/, rendered babook's page: its title, its drawer, its
nav. That is a straight RULE-2 break and it was live in production.

The guard tests did not catch it because they read templates under
templates/matazim/ and pages we request successfully. An error page is neither,
which is a good reminder that a rule is only as good as the surface it is
checked on. The test added with this file walks the error path itself.

These handlers dispatch on the path: anything under /matazim/ gets our shell,
everything else gets babook's, unchanged.
"""

from django.shortcuts import render

PREFIX = "/matazim/"


def _ours(request):
    return request.path.startswith(PREFIX)


def _context(request):
    """The little the shell needs. Deliberately no database work.

    An error page that queries can fail while rendering the failure, which is
    the worst moment to discover a second bug.
    """
    return {"section": "", "welcome_pending": False, "test_passed": False}


def permission_denied(request, exception=None):
    if not _ours(request):
        from django.views import defaults

        return defaults.permission_denied(request, exception)
    return render(request, "matazim/403.html", _context(request), status=403)


def page_not_found(request, exception=None):
    if not _ours(request):
        from django.views import defaults

        return defaults.page_not_found(request, exception)
    return render(request, "matazim/404.html", _context(request), status=404)


def server_error(request):
    if not _ours(request):
        from django.views import defaults

        return defaults.server_error(request)
    return render(request, "matazim/500.html", _context(request), status=500)
