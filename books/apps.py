from django.apps import AppConfig


class BooksConfig(AppConfig):
    """Books: sharing real books from shelf photos (docs/books/spec.md).

    The central app of the project. Its own app, same reasoning as memz and
    ustrip: own models, migrations, URLs, templates, no babook chrome in
    either direction. The only thing it shares is the User table, linked
    through Profile (building_an_app.md Rule 2).
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "books"
    verbose_name = "Books"

    def ready(self):
        # Job workers register themselves on import; import them here so a
        # job run from a command or the token endpoint finds its worker.
        from . import catalog, hub, shelf, signals  # noqa: F401
