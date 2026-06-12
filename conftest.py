"""
Root conftest.py — pytest configuration and global fixtures.
Overrides STORAGES to use simple (non-manifest) static files storage during tests
so templates with {% static %} don't require collectstatic to have been run.
"""


# Use simple static files storage in all tests so templates with {% static %}
# work without requiring a pre-built staticfiles manifest.
def pytest_configure(config):
    from django.conf import settings
    if hasattr(settings, "STORAGES"):
        settings.STORAGES = {
            **settings.STORAGES,
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }
