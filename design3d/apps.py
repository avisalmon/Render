from django.apps import AppConfig


class Design3dConfig(AppConfig):
    """3D design through a chat, at /design3d/ (docs/design3d/spec.md)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "design3d"
    verbose_name = "design3d"
