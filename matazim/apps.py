from django.apps import AppConfig


class MatazimConfig(AppConfig):
    """מט״צים — the young technology leaders program space.

    Its own app so that the separation in docs/matazim/spec.md is structural
    rather than a habit: own models, own migrations, own URLs, own templates.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "matazim"
    verbose_name = "מט״צים"
