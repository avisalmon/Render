from django.apps import AppConfig


class CounterConfig(AppConfig):
    """counter: a hit counter and tiny statistics service for Avi's own sites.

    Its own app, same reasoning as memz and ustrip: own models, migrations,
    URLs, templates, no babook chrome in either direction. The only thing it
    shares with the rest of the project is the User table
    (building_an_app.md Rule 2). See docs/counter/spec.md.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "counter"
    verbose_name = "counter"
