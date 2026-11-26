"""Django admin is a fallback for Avi only; the app's own screens and API are
the way content is edited (methodology: "content is edited in the app")."""

from django.apps import apps
from django.contrib import admin

for model in apps.get_app_config("academia360").get_models():
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:  # pragma: no cover
        pass
