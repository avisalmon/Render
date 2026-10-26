"""
URL configuration for mysite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import JsonResponse
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve  # noqa: F401  (kept for the admin's own use)

from .media_views import protected_serve

from app.sitemaps import CourseSitemap, StaticViewSitemap
from app.views import privacy, robots_txt, terms

sitemaps = {"static": StaticViewSitemap, "courses": CourseSitemap}


def healthz(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("healthz", healthz, name="healthz"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path("privacy/", privacy, name="privacy"),
    path("terms/", terms, name="terms"),
    # מט״צים is its own product (docs/matazim/spec.md). It is mounted before
    # app.urls so its prefix is unambiguously its own.
    path("matazim/", include("matazim.urls", namespace="matazim")),
    # ustrip is its own product too (docs/ustrip/spec.md) — same reasoning.
    path("ustrip/", include("ustrip.urls", namespace="ustrip")),
    # memz is its own product too (docs/memz/spec.md) — same reasoning.
    path("memz/", include("memz.urls", namespace="memz")),
    # SensorLab is its own product too (docs/sensorlab/spec.md) — same reasoning,
    # and mounted before app.urls so the prefix is unambiguously its own.
    path("sensorlab/", include("sensorlab.urls", namespace="sensorlab")),
    # exo is its own product too (docs/exo/spec.md) — same reasoning,
    # and mounted before app.urls so the prefix is unambiguously its own.
    path("exo/", include("exo.urls", namespace="exo")),
    # CrashTech is its own product too (docs/crashtech/spec.md), same
    # reasoning. Mounted before app.urls so it takes /crashtech/ from the
    # 2026 platform embedded in app/, which is reference only and holds
    # seeded demo data (spec Rule 13.2). Anything the new app has not
    # defined yet still falls through to the old routes below.
    path("crashtech/", include("crashtech.urls", namespace="crashtech")),
    # counter is its own capability (docs/counter/spec.md), same reasoning.
    path("counter/", include("counter.urls", namespace="counter")),
    # Books is the central app (docs/books/spec.md), its own product, same reasoning.
    path("books/", include("books.urls", namespace="books")),
    path("cohort/", include("cohort.urls", namespace="cohort")),
    # dentist is its own product (docs/dentist/spec.md): a volunteer dental
    # clinic, sealed both ways, same reasoning as the apps above.
    path("dentist/", include("dentist.urls", namespace="dentist")),
    # bkm is its own product (docs/bkm/spec.md): the gateway to Avi's BKMs.
    path("bkm/", include("bkm.urls", namespace="bkm")),
    path("blackjack/", include("blackjack.urls", namespace="blackjack")),
    # improv is private (docs/improv/spec.md ch. 7): its gate is in the middleware.
    path("improv/", include("improv.urls", namespace="improv")),
    # The domain opens Books (Avi, 2026-10-21); babook's main page is at /babook/ (url name "home").
    path("", RedirectView.as_view(url="/books/", permanent=False), name="root"),
    path("", include("app.urls")),
]

# Serve media files in all environments — django.conf.urls.static.static()
# silently returns [] when DEBUG=False, so use re_path + serve directly.
# Acceptable for small sites; use object storage for high traffic.
urlpatterns += [
    # Private folders are refused here and served by their app's checking view (mysite/media_views.py).
    re_path(r"^media/(?P<path>.*)$", protected_serve),
]

# REQ-M.2 / ustrip spec §1 — error pages stay inside the walls.
#
# Django's handlers are project-wide, so a 403 raised inside /matazim/ (or a
# 404 inside /ustrip/) used to render babook's page: its title, its drawer,
# its nav. mysite/errors.py composes both apps' own handlers by path prefix
# so babook's own errors are untouched everywhere else.
handler403 = "mysite.errors.permission_denied"
handler404 = "mysite.errors.page_not_found"
handler500 = "mysite.errors.server_error"
