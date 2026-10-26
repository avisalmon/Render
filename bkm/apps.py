from django.apps import AppConfig


class BkmConfig(AppConfig):
    """The gateway to Avi's BKMs, at /bkm/ (docs/bkm/spec.md)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "bkm"
    verbose_name = "BKM gateway"
