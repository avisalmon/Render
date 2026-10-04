from django.apps import AppConfig


class ImprovConfig(AppConfig):
    """improv: Avi's piano improvisation practice app (docs/improv/spec.md).

    Its own app, own models, own URLs, own templates. It shares only the User
    table, and it is private: see access.py and middleware.py.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "improv"
    verbose_name = "improv"
