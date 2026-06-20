from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Course


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return ["home", "login", "register", "privacy", "terms"]

    def location(self, item):
        return reverse(item)


class CourseSitemap(Sitemap):
    priority = 0.9
    changefreq = "weekly"

    def items(self):
        return Course.objects.filter(is_published=True)

    def location(self, course):
        return f"/courses/{course.slug}/"
