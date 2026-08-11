"""Outbound mail containment (2026-08-08).

The Resend daily quota kept running out. These lock down the three things that
could mail on demand: the guard backend, /register/, and /resend-verification/.
"""
import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import Client
from django.urls import reverse


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


# --- the guard backend itself ---

def test_guard_caps_repeat_sends_to_one_address(settings):
    from app.mail_guard import allow_recipient
    settings.MAIL_PER_RECIPIENT_DAILY_CAP = 3
    assert [allow_recipient("loop@example.com", "s") for _ in range(5)] == [
        True, True, True, False, False,
    ]


def test_guard_never_blocks_a_different_recipient(settings):
    """The cap must not be able to starve real users - it is per address."""
    from app.mail_guard import allow_recipient
    settings.MAIL_PER_RECIPIENT_DAILY_CAP = 1
    assert allow_recipient("a@example.com", "s") is True
    assert allow_recipient("a@example.com", "s") is False
    assert allow_recipient("b@example.com", "s") is True  # unaffected


def test_guard_can_be_disabled(settings):
    from app.mail_guard import allow_recipient
    settings.MAIL_PER_RECIPIENT_DAILY_CAP = 0
    assert all(allow_recipient("x@example.com", "s") for _ in range(50))


def test_guard_masks_the_address_in_logs(caplog, settings):
    """Logs have to name the source without becoming a harvestable list."""
    from app.mail_guard import allow_recipient
    settings.MAIL_PER_RECIPIENT_DAILY_CAP = 5
    with caplog.at_level("INFO", logger="app.mail"):
        allow_recipient("yossi@example.com", "אימות האימייל שלך ב-babook")
    text = caplog.text
    assert "yossi@example.com" not in text
    assert "y***@example.com" in text
    assert "אימות האימייל" in text  # the subject is what identifies the source


def test_guard_backend_actually_delivers(settings):
    """The wiring itself: a broken wrapper would silently kill ALL site email,
    which is worse than the problem it fixes."""
    from django.core.mail import get_connection, send_mail
    settings.MAIL_GUARD_INNER_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.MAIL_PER_RECIPIENT_DAILY_CAP = 10
    conn = get_connection("app.mail_guard.GuardedEmailBackend")
    sent = send_mail("נושא", "גוף", "from@example.com", ["to@example.com"],
                     connection=conn)
    assert sent == 1
    assert mail.outbox[-1].subject == "נושא"
    assert mail.outbox[-1].to == ["to@example.com"]


def test_guard_backend_drops_only_the_capped_recipient(settings):
    """A message to two people, one over cap: the other still gets it."""
    from django.core.mail import EmailMessage, get_connection
    settings.MAIL_GUARD_INNER_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.MAIL_PER_RECIPIENT_DAILY_CAP = 1
    conn = get_connection("app.mail_guard.GuardedEmailBackend")
    EmailMessage("a", "b", "from@example.com", ["over@example.com"],
                 connection=conn).send()
    mail.outbox.clear()
    EmailMessage("a", "b", "from@example.com",
                 ["over@example.com", "fresh@example.com"],
                 connection=conn).send()
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["fresh@example.com"]


# --- /register/ ---

def _register(c, email, ip="203.0.113.9"):
    return c.post("/register/", {
        "name": "בודק", "email": email, "password": "StrongPass123!",
    }, HTTP_X_FORWARDED_FOR=ip)


@pytest.mark.django_db
def test_register_throttles_verification_mail_per_ip(settings):
    """A signup spray from one IP stops making us mail strangers."""
    settings.REGISTER_VERIFY_MAIL_PER_IP_HOUR = 3
    settings.REGISTER_VERIFY_MAIL_PER_IP_DAY = 100
    for i in range(3):
        _register(Client(), f"ok{i}@example.com")
    assert len(mail.outbox) == 3
    for i in range(4):
        _register(Client(), f"spray{i}@example.com")
    assert len(mail.outbox) == 3  # nothing further left the building


@pytest.mark.django_db
def test_register_still_creates_the_account_when_mail_is_throttled(settings):
    """Throttling the mail must not lock a real person out of signing up."""
    settings.REGISTER_VERIFY_MAIL_PER_IP_HOUR = 1
    _register(Client(), "first@example.com")
    resp = _register(Client(), "second@example.com")
    assert resp.status_code == 302
    assert User.objects.filter(email="second@example.com").exists()
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_a_second_ip_has_its_own_budget(settings):
    settings.REGISTER_VERIFY_MAIL_PER_IP_HOUR = 1
    _register(Client(), "a@example.com", ip="203.0.113.1")
    _register(Client(), "b@example.com", ip="203.0.113.1")
    assert len(mail.outbox) == 1
    _register(Client(), "c@example.com", ip="198.51.100.7")
    assert len(mail.outbox) == 2


# --- /resend-verification/ ---

def _unverified(username="unverified"):
    u = User.objects.create_user(username, email=f"{username}@example.com",
                                 password="pass12345")
    u.profile.email_verified = False
    u.profile.save(update_fields=["email_verified"])
    return u


@pytest.mark.django_db
def test_resend_verification_does_not_send_on_get():
    """It used to. A banner link on every page meant a click, a refresh or a
    browser prefetch was another email."""
    c = Client()
    c.force_login(_unverified())
    resp = c.get(reverse("resend_verification"))
    assert resp.status_code == 200
    assert mail.outbox == []


@pytest.mark.django_db
def test_resend_verification_sends_once_then_cools_down():
    c = Client()
    c.force_login(_unverified())
    assert c.post(reverse("resend_verification")).status_code == 200
    assert len(mail.outbox) == 1
    resp = c.post(reverse("resend_verification"))  # straight away again
    assert len(mail.outbox) == 1
    assert resp.context["throttled"] is True


@pytest.mark.django_db
def test_resend_verification_has_a_daily_ceiling():
    from app import views
    c = Client()
    c.force_login(_unverified())
    for _ in range(views.RESEND_VERIFY_PER_DAY + 3):
        cache.delete(f"resend_verify_wait_{User.objects.first().pk}")  # skip cooldown
        c.post(reverse("resend_verification"))
    assert len(mail.outbox) == views.RESEND_VERIFY_PER_DAY


@pytest.mark.django_db
def test_verified_user_is_never_mailed_again():
    u = _unverified("done")
    u.profile.email_verified = True
    u.profile.save(update_fields=["email_verified"])
    c = Client()
    c.force_login(u)
    c.post(reverse("resend_verification"))
    assert mail.outbox == []
