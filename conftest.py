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


def pytest_collection_modifyitems(session, config, items):
    """The mini gate never reaches OpenAI. The full regression may.

    Avi, 2026-09-13: "In full regression you can call real openai. But not
    regular mini regression."

    The reason the rule exists: the SPR-M.25 suite was making real
    chat-completion calls on every run, because `matazim.assess` reads
    `settings.OPENAI_API_KEY` and the developer machine has a real one. On the
    gate that runs after every change that is slow, it costs money each time,
    and it makes a green suite depend on somebody else's uptime. On the full
    regression, once a day and on purpose, a real call is exactly what you
    want: it is the only thing that proves the assessment still answers.

    So the key is blanked unless `MATAZIM_LIVE_AI=1` is set. Blanking is not
    avoidance — every caller here fails open when there is no model, because a
    model having a bad afternoon must never cost somebody their request, so the
    quiet run exercises the path that has to work anyway.
    """
    import os

    from django.conf import settings

    if os.environ.get("MATAZIM_LIVE_AI", "").strip() not in ("1", "true", "yes"):
        settings.OPENAI_API_KEY = ""
