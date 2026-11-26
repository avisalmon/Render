from django.apps import AppConfig


class Academia360Config(AppConfig):
    """The working system around אקדמיה 360, ות״ת's program for deep change in
    the bachelor's degree (docs/academia360/spec.md). Its own app: it shares
    only the site's User table, through its own Role rows (Rule 2)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "academia360"
    verbose_name = "אקדמיה 360"
