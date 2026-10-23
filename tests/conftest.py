"""Test-wide guards for Books (tests/test_books_*.py only; other apps' tests
are untouched).

A developer machine may carry a real OPENAI_API_KEY in its environment.
Books' scan reading, tagging and web lookup would then make real, paid
calls from tests, and their background threads would outlive a live-server
test ("database table is locked"). Every Books test therefore starts with no
key and no background sweep; a test that needs a key sets a fake one and
replaces the client.
"""

import pytest


@pytest.fixture(autouse=True)
def _books_no_real_model_calls(request, settings):
    if not request.node.fspath.basename.startswith("test_books"):
        yield
        return
    settings.OPENAI_API_KEY = ""
    settings.BOOKS_ENRICH_SWEEP = False
    # Each feature's own tests run with every tier open; tests/test_books_11.py
    # closes them to test the tiers themselves.
    settings.BOOKS_PILOT_EVERYONE_ASKS = True
    settings.BOOKS_PILOT_GIFT = False  # the gift is tested where it is the subject (tests/test_books_give.py)
    settings.BOOKS_FRIENDS_FIRST_HOURS = 0  # friends-first is tested where it is the subject (test_books_give.py)
    yield
