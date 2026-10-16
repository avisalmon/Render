"""counter's pages: the dashboard (Avi only), one site's detail, the snippet."""

from pathlib import Path

from django.conf import settings
from django.contrib.auth import views as auth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie

from . import stats
from .access import can_use, sites_for
from .api.public import CORS

SNIPPET = Path(__file__).with_name("snippet.js")


class LoginView(auth.LoginView):
    template_name = "counter/login.html"
    redirect_authenticated_user = True
    next_page = reverse_lazy("counter:dashboard")


class LogoutView(auth.LogoutView):
    next_page = reverse_lazy("counter:login")


def _gate(request):
    """None when allowed, else the response to send instead."""
    if not request.user.is_authenticated:
        return redirect(f"{reverse_lazy('counter:login')}?next={request.path}")
    if not can_use(request.user):
        return render(request, "counter/403.html", status=403)
    return None


@ensure_csrf_cookie
def dashboard(request):
    denied = _gate(request)
    if denied:
        return denied
    rows = [{"site": s, "totals": stats.totals(s), "clicks": stats.summary(s, days=1)["clicks"]}
            for s in sites_for(request.user)]
    return render(request, "counter/dashboard.html", {"rows": rows})


@ensure_csrf_cookie
def site_detail(request, pk):
    denied = _gate(request)
    if denied:
        return denied
    site = get_object_or_404(sites_for(request.user), pk=pk)
    summary = stats.summary(site, days=30)
    peak = max((d["views"] for d in summary["by_day"]), default=0) or 1
    for d in summary["by_day"]:
        d["pct"] = round(100 * d["views"] / peak)
    origin = settings.COUNTER_PUBLIC_ORIGIN.rstrip("/")
    snippet = f'<script defer src="{origin}/counter/c.js" data-site="{site.key}"></script>'
    return render(request, "counter/site.html", {"site": site, "summary": summary, "snippet": snippet})


@cache_control(max_age=3600, public=True)
def snippet_js(request):
    response = HttpResponse(SNIPPET.read_text(encoding="utf-8"), content_type="application/javascript; charset=utf-8")
    for k, v in CORS.items():
        response[k] = v
    return response
