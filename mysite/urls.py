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
from django.urls import path, re_path, include
from django.http import JsonResponse
from django.views.static import serve
from django.contrib.sitemaps.views import sitemap
from app.sitemaps import StaticViewSitemap
from app.views import robots_txt, privacy, terms

sitemaps = {"static": StaticViewSitemap}


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
    path("", include("app.urls")),
]

# Serve media files in all environments — django.conf.urls.static.static()
# silently returns [] when DEBUG=False, so use re_path + serve directly.
# Acceptable for small sites; use object storage for high traffic.
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]
