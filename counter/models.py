"""counter's data (docs/counter/data_model.md).

Five models. Statistics are not stored, they are computed from Event by
counter/stats.py. Nothing here touches another app's models; the only shared
thing is the Django User, and only to say who owns a site.
"""

import secrets

from django.conf import settings
from django.db import models


def new_site_key():
    """The public identifier that goes in a site's snippet. Not a secret."""
    return secrets.token_hex(5)


class Site(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="counter_sites")
    name = models.CharField(max_length=120)
    key = models.CharField(max_length=32, unique=True, default=new_site_key, editable=False)
    base_url = models.CharField(max_length=300, blank=True)
    repo = models.CharField(max_length=200, blank=True, help_text='"owner/name" on GitHub')
    local_path = models.CharField(max_length=300, blank=True, help_text="Checkout on Avi's PC")
    is_active = models.BooleanField(default=True)
    snippet_installed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Page(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="pages")
    path = models.CharField(max_length=300)
    title = models.CharField(max_length=200, blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["path"]
        constraints = [models.UniqueConstraint(fields=["site", "path"], name="counter_page_unique_path")]

    def __str__(self):
        return f"{self.site.name}{self.path}"


class Promo(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="counter_promos")
    title = models.CharField(max_length=120)
    text = models.CharField(max_length=300, blank=True)
    url = models.CharField(max_length=500)
    image_url = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class PromoPlacement(models.Model):
    promo = models.ForeignKey(Promo, on_delete=models.CASCADE, related_name="placements")
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="placements")
    path_prefix = models.CharField(max_length=300, blank=True, help_text="Blank means the whole site")
    weight = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["site", "path_prefix"]

    def __str__(self):
        return f"{self.promo} on {self.site}{self.path_prefix}"


class Event(models.Model):
    VIEW, CLICK, CUSTOM, PROMO_SHOWN, PROMO_CLICK = "view", "click", "custom", "promo_shown", "promo_click"
    KINDS = [
        (VIEW, "view"),
        (CLICK, "click"),
        (CUSTOM, "custom"),
        (PROMO_SHOWN, "promo shown"),
        (PROMO_CLICK, "promo click"),
    ]

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="events")
    page = models.ForeignKey(Page, on_delete=models.CASCADE, null=True, blank=True, related_name="events")
    kind = models.CharField(max_length=16, choices=KINDS, default=VIEW)
    name = models.CharField(max_length=80, blank=True)
    visitor_id = models.CharField(max_length=64, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    referrer = models.CharField(max_length=300, blank=True)
    user_agent = models.CharField(max_length=200, blank=True)
    promo = models.ForeignKey(Promo, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["site", "kind", "created_at"], name="counter_event_site_kind_ts")]

    def __str__(self):
        return f"{self.kind} {self.site_id} {self.created_at:%Y-%m-%d %H:%M}"
