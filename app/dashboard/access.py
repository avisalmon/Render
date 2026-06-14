"""Superuser-only access for the admin dashboard (REQ-8.1.2).

Stricter than ``is_staff``: only ``is_superuser`` may reach any
``/admin-dashboard/*`` route. Anonymous users are routed to the ``/join/``
wall (consistent with the rest of the site); authenticated non-superusers get
a 403.
"""

from functools import wraps

from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

_FORBIDDEN_HE = "אזור מנהל בלבד"


def superuser_required(view_func):
    """Decorator for function views: allow only superusers (REQ-8.1.2)."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/join/?next={request.path}")
        if not request.user.is_superuser:
            return HttpResponseForbidden(_FORBIDDEN_HE)
        return view_func(request, *args, **kwargs)

    return _wrapped


class SuperuserRequiredMixin(UserPassesTestMixin):
    """Class-based-view counterpart of :func:`superuser_required`."""

    raise_exception = False

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect(f"/join/?next={self.request.path}")
        return HttpResponseForbidden(_FORBIDDEN_HE)
