from django.apps import AppConfig


class UstripConfig(AppConfig):
    """ustrip — Avi's family trip planner (docs/ustrip/spec.md).

    Its own app, same reasoning as matazim: own models, own migrations, own
    URLs, own templates, no babook branding either direction. The only thing
    it shares with the rest of the project is the User table.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "ustrip"
    verbose_name = "ustrip"
