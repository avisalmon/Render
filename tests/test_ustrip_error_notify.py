"""ustrip mails Avi when it breaks (ustrip/middleware.py).

The point of the middleware is that a crash on the road reaches someone. These
drive the middleware directly with a fake request and a raised exception, so
they do not depend on wiring up a view that throws.
"""

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory, override_settings

from ustrip.middleware import UstripErrorNotifier

# A real locmem backend, so mail.outbox is the actual capture mechanism and we
# never reach through the guarded Resend backend from a test. Applied per test
# via the autouse fixture below (a module-level pytestmark can't hold an
# override_settings instance — pytest wants a real Mark there).
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


@pytest.fixture(autouse=True)
def _reset_state(settings):
    settings.EMAIL_BACKEND = LOCMEM
    # The throttle is a cache key, and outbox does not auto-clear here because
    # the project's default backend is not locmem — reset both per test.
    cache.clear()
    mail.outbox.clear()
    yield
    cache.clear()


def _mw():
    return UstripErrorNotifier(lambda request: None)


@override_settings(USTRIP_ERROR_NOTIFY="avi@example.com", DEFAULT_FROM_EMAIL="noreply@babook.co.il")
@pytest.mark.django_db
def test_an_error_under_ustrip_is_mailed(db):
    request = RequestFactory().get("/ustrip/itinerary/5/")
    request.user = AnonymousUser()

    _mw().process_exception(request, ValueError("something broke"))

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == ["avi@example.com"]
    assert "ValueError" in msg.subject and "/ustrip/itinerary/5/" in msg.subject
    assert "something broke" in msg.body


@override_settings(USTRIP_ERROR_NOTIFY="avi@example.com")
@pytest.mark.django_db
def test_an_error_outside_ustrip_is_ignored(db):
    """Middleware is project-wide; this notifier is not. A babook or מט״צים
    error is not ustrip's to report."""
    request = RequestFactory().get("/matazim/track/")
    request.user = AnonymousUser()

    _mw().process_exception(request, ValueError("not ustrip's problem"))

    assert mail.outbox == []


@override_settings(USTRIP_ERROR_NOTIFY="avi@example.com")
@pytest.mark.django_db
def test_a_crashloop_is_throttled_to_one(db):
    """The same error on every request must not send a message per request."""
    mw = _mw()
    for _ in range(20):
        request = RequestFactory().get("/ustrip/")
        request.user = AnonymousUser()
        mw.process_exception(request, ValueError("the same bug, again and again"))

    assert len(mail.outbox) == 1


@override_settings(USTRIP_ERROR_NOTIFY="avi@example.com")
@pytest.mark.django_db
def test_two_different_errors_both_get_through(db):
    """Throttling is per error signature, not a blanket mute — a second, real
    bug is not silenced because a first one happened."""
    mw = _mw()
    r1 = RequestFactory().get("/ustrip/")
    r1.user = AnonymousUser()
    mw.process_exception(r1, ValueError("bug one"))
    r2 = RequestFactory().get("/ustrip/")
    r2.user = AnonymousUser()
    mw.process_exception(r2, KeyError("bug two"))

    assert len(mail.outbox) == 2


@override_settings(USTRIP_ERROR_NOTIFY="")
@pytest.mark.django_db
def test_no_recipient_means_no_mail_not_a_crash(db):
    """Dev, and any environment where it is not configured: silent, not broken."""
    request = RequestFactory().get("/ustrip/")
    request.user = AnonymousUser()

    result = _mw().process_exception(request, ValueError("x"))

    assert result is None
    assert mail.outbox == []


@override_settings(USTRIP_ERROR_NOTIFY="", CONTACT_NOTIFY_EMAIL="someone@babook.co.il",
                    DEFAULT_FROM_EMAIL="noreply@babook.co.il")
@pytest.mark.django_db
def test_it_never_falls_back_to_the_sites_other_email_settings(db):
    """The bug this guards against: DEFAULT_FROM_EMAIL has a non-blank
    hardcoded default in this project's settings.py, so a fallback chain
    through it would mean this notifier is never actually off — it would
    fire in every environment, including a dev machine, straight to a
    sender address nobody reads. Only USTRIP_ERROR_NOTIFY counts."""
    request = RequestFactory().get("/ustrip/")
    request.user = AnonymousUser()

    _mw().process_exception(request, ValueError("x"))

    assert mail.outbox == []


@override_settings(USTRIP_ERROR_NOTIFY="avi@example.com")
@pytest.mark.django_db
def test_the_body_names_who_hit_it_but_not_the_request_body(db):
    user = User.objects.create_user("nirit", password="x")
    request = RequestFactory().post("/ustrip/api/journal-posts/", {"caption": "secret words"})
    request.user = user

    _mw().process_exception(request, RuntimeError("boom"))

    body = mail.outbox[0].body
    assert "nirit" in body
    assert "secret words" not in body  # the POST body is never in the email


@override_settings(USTRIP_ERROR_NOTIFY="avi@example.com")
@pytest.mark.django_db
def test_process_exception_returns_none_so_the_500_page_still_renders(db):
    """It observes; it must not swallow the error and rob the user of the real
    500 handling (ustrip/errors.py)."""
    request = RequestFactory().get("/ustrip/")
    request.user = AnonymousUser()

    assert _mw().process_exception(request, ValueError("x")) is None
