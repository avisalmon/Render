from django.apps import AppConfig


class CohortConfig(AppConfig):
    """The teachers' course home (docs/cohort/spec.md). Its own app; it shares
    only the User table, through Member (building_an_app.md Rule 2)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "cohort"
    verbose_name = "השתלמות"
