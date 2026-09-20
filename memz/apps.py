from django.apps import AppConfig


class MemzConfig(AppConfig):
    """memz — one meme engine, two front doors (docs/memz/spec.md).

    Its own app, same reasoning as matazim and ustrip: own models, own
    migrations, own URLs, own templates, no babook chrome in either
    direction. The only thing it shares with the rest of the project is the
    User table (building_an_app.md Rule 2).
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "memz"
    verbose_name = "memz"

    def ready(self):
        from . import signals   # noqa: F401  (file cleanup on delete, Rule 6.8.1)
