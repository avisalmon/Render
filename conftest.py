"""
Root conftest.py — pytest configuration and global fixtures.
Overrides STORAGES to use simple (non-manifest) static files storage during tests
so templates with {% static %} don't require collectstatic to have been run.
"""

import pytest


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

    # Measured 2026-09-14: the SPR-M.31 suite is thirteen straightforward
    # database tests and took 65 seconds. Almost all of it was PBKDF2. Every
    # test here builds a small world - a program manager, two leaders, two
    # students - and Django deliberately makes each `create_user` slow, which
    # is right in production and pure tax in a test that logs in as five
    # people. Nothing in this repository asserts anything about the algorithm,
    # only that the right password works, and MD5 answers that identically.
    #
    # This is the single biggest thing standing between us and a full
    # regression somebody will actually run.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


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
    avoidance - every caller here fails open when there is no model, because a
    model having a bad afternoon must never cost somebody their request, so the
    quiet run exercises the path that has to work anyway.

    **And when it is set, it is set for this product only** (`live_ai` below).
    The first version flipped one global and handed a live key to all 1638
    tests, including babook's content-safety suite, which calls the moderation
    and relevance endpoints on nearly every case. The full regression went from
    minutes to twenty seconds a test and would not have finished inside a
    working day. What Avi allowed was a real call for this product's
    assessment, not for everything that can reach an API.
    """
    from django.conf import settings

    _REAL_KEY["value"] = getattr(settings, "OPENAI_API_KEY", "") or ""
    settings.OPENAI_API_KEY = ""


# Held here because `pytest_collection_modifyitems` takes it away and `live_ai`
# hands it back for the few tests entitled to it.
_REAL_KEY = {"value": ""}


def _live_ai_allowed():
    import os

    return os.environ.get("MATAZIM_LIVE_AI", "").strip() in ("1", "true", "yes")


@pytest.fixture(autouse=True)
def live_ai(request):
    """A real model, for מט״צים's own sprint suites, when asked for.

    The rule is the module name: `tests/test_spr_m_*.py` is this product's own
    work and nothing else is. Deliberately narrow. A wider rule is how the
    previous version turned a twenty-minute gate into an overnight one.
    """
    from django.conf import settings

    module = getattr(request.node, "module", None)
    name = getattr(module, "__name__", "").rsplit(".", 1)[-1]
    if not (_live_ai_allowed() and name.startswith("test_spr_m_")):
        yield
        return

    settings.OPENAI_API_KEY = _REAL_KEY["value"]
    try:
        yield
    finally:
        settings.OPENAI_API_KEY = ""
