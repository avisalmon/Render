"""
SPR-2.1.3 - Newsletter Capture: MVP
TDD tests for F-2.1.28 through F-2.1.32.
Run: pytest -m spr213 -v
"""

import pytest
from django.apps import apps
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, override_settings
from django.utils import timezone

pytestmark = [pytest.mark.spr213, pytest.mark.django_db]


def _content(response):
    return response.content.decode("utf-8", errors="ignore")


def _subscriber_model():
    return apps.get_model("app", "NewsletterSubscriber")


def _valid_payload(**overrides):
    payload = {
        "email": "Dana@Example.COM ",
        "language": "he",
        "source_page": "/corporate/",
        "utm_source": "linkedin",
        "utm_medium": "social",
        "utm_campaign": "launch",
        "utm_content": "footer",
    }
    payload.update(overrides)
    return payload


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_newsletter_signup_creates_lowercase_subscriber_and_sends_confirmation(client):
    """T-F-2.1.28/29-1: signup stores subscriber data and sends double opt-in email."""
    cache.clear()
    NewsletterSubscriber = _subscriber_model()
    response = client.post(
        "/newsletter/signup/",
        _valid_payload(),
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        REMOTE_ADDR="203.0.113.30",
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    subscriber = NewsletterSubscriber.objects.get(email="dana@example.com")
    assert subscriber.language == "he"
    assert subscriber.source_page == "/corporate/"
    assert subscriber.utm_source == "linkedin"
    assert subscriber.confirmed_at is None
    assert len(mail.outbox) == 1
    assert "/newsletter/confirm/" in mail.outbox[0].body


def test_newsletter_component_renders_once_on_corporate_page(client):
    """T-F-2.1.29/30-1: reusable newsletter CTA renders once with consent copy."""
    html = _content(client.get("/corporate/?utm_source=linkedin&utm_campaign=launch"))
    assert html.count("newsletter-signup-form") == 1
    assert "טיפ AI שבועי" in html
    assert 'name="email"' in html
    assert 'name="source_page" value="/corporate/"' in html
    assert "אפשר להסיר הרשמה בכל רגע" in html
    assert "newsletter_signup" in html


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_newsletter_confirmation_token_sets_confirmed_at(client):
    """T-F-2.1.29-2: confirmation link marks the subscriber as confirmed."""
    cache.clear()
    NewsletterSubscriber = _subscriber_model()
    response = client.post(
        "/newsletter/signup/",
        _valid_payload(email="confirm@example.com"),
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        REMOTE_ADDR="203.0.113.31",
    )
    assert response.status_code == 200
    token_path = mail.outbox[0].body.split("/newsletter/confirm/", 1)[1].split()[0]

    confirm = client.get(f"/newsletter/confirm/{token_path}")
    assert confirm.status_code == 200
    subscriber = NewsletterSubscriber.objects.get(email="confirm@example.com")
    assert subscriber.confirmed_at is not None
    assert "ההרשמה אושרה" in _content(confirm)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_newsletter_honeypot_rate_limit_and_duplicate_handling(client):
    """T-F-2.1.31-1: signup blocks bots, rate limits, and handles duplicates safely."""
    cache.clear()
    NewsletterSubscriber = _subscriber_model()
    bot = client.post(
        "/newsletter/signup/",
        _valid_payload(email="bot@example.com", website="https://spam.example"),
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        REMOTE_ADDR="203.0.113.32",
    )
    assert bot.status_code == 200
    assert NewsletterSubscriber.objects.count() == 0

    first = client.post(
        "/newsletter/signup/",
        _valid_payload(email="dupe@example.com"),
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        REMOTE_ADDR="203.0.113.33",
    )
    second = client.post(
        "/newsletter/signup/",
        _valid_payload(email="DUPE@example.com"),
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        REMOTE_ADDR="203.0.113.33",
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert NewsletterSubscriber.objects.filter(email="dupe@example.com").count() == 1

    for index in range(3):
        response = client.post(
            "/newsletter/signup/",
            _valid_payload(email=f"rate{index}@example.com"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            REMOTE_ADDR="203.0.113.34",
        )
        assert response.status_code == 200
    blocked = client.post(
        "/newsletter/signup/",
        _valid_payload(email="rate4@example.com"),
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        REMOTE_ADDR="203.0.113.34",
    )
    assert blocked.status_code == 429


def test_newsletter_validation_and_csrf(client):
    """T-F-2.1.28/31-2: invalid email is rejected and CSRF is enforced."""
    invalid = client.post(
        "/newsletter/signup/",
        _valid_payload(email="not-an-email"),
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        REMOTE_ADDR="203.0.113.35",
    )
    assert invalid.status_code == 400
    assert "email" in invalid.json()["errors"]

    csrf_client = Client(enforce_csrf_checks=True)
    missing_csrf = csrf_client.post(
        "/newsletter/signup/",
        _valid_payload(email="csrf@example.com"),
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert missing_csrf.status_code == 403


def test_newsletter_signup_tracking_uses_non_pii_props(client):
    """T-F-2.1.32-1: signup captures UTM fields and Plausible event has no email prop."""
    html = _content(client.get("/corporate/?utm_source=linkedin&utm_medium=social&utm_campaign=launch"))
    for field in ["utm_source", "utm_medium", "utm_campaign", "utm_content"]:
        assert f'name="{field}"' in html
    assert "newsletter_signup" in html
    assert "source_page" in html
    assert "language" in html
    assert "email:" not in html


def test_purge_unconfirmed_newsletter_subscribers_command():
    """T-F-2.1.29-3: unconfirmed subscribers older than 14 days can be purged."""
    NewsletterSubscriber = _subscriber_model()
    old_subscriber = NewsletterSubscriber.objects.create(email="old@example.com", source_page="/corporate/")
    fresh_subscriber = NewsletterSubscriber.objects.create(email="fresh@example.com", source_page="/corporate/")
    confirmed_subscriber = NewsletterSubscriber.objects.create(
        email="confirmed@example.com",
        source_page="/corporate/",
        confirmed_at=timezone.now(),
    )
    NewsletterSubscriber.objects.filter(pk=old_subscriber.pk).update(
        created_at=timezone.now() - timezone.timedelta(days=15)
    )

    call_command("purge_unconfirmed_newsletter", verbosity=0)

    assert not NewsletterSubscriber.objects.filter(pk=old_subscriber.pk).exists()
    assert NewsletterSubscriber.objects.filter(pk=fresh_subscriber.pk).exists()
    assert NewsletterSubscriber.objects.filter(pk=confirmed_subscriber.pk).exists()
