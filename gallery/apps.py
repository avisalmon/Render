from django.apps import AppConfig


class GalleryConfig(AppConfig):
    """The public gallery of Avi's 10x engineer training (docs/gallery/spec.md).
    Its own app; it shares only the User table, through Person (Rule 2)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "gallery"
    verbose_name = "גלריה"
