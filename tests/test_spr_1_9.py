"""
SPR-1.9 — Email Service (Resend)
TDD tests written BEFORE implementation. All should fail (RED) until features are implemented.
"""
import pytest
from django.conf import settings
from django.core import mail
from django.test import Client, TestCase, override_settings


pytestmark = pytest.mark.spr19


# --- F-1.9.1: django-resend backend wired in settings ---


class TestEmailBackendSettings(TestCase):
    """T-F-1.9.1-1 through T-F-1.9.1-4"""

    def test_email_backend_setting_exists(self):
        """T-F-1.9.1-1: EMAIL_BACKEND setting exists and is non-empty."""
        backend = getattr(settings, "EMAIL_BACKEND", "")
        assert backend, "EMAIL_BACKEND must be set"

    @override_settings(RESEND_API_KEY="")
    def test_dev_uses_console_backend(self):
        """T-F-1.9.1-2: When RESEND_API_KEY empty, backend is NOT the Resend backend."""
        resend_key = getattr(settings, "RESEND_API_KEY", "")
        if not resend_key:
            assert "resend" not in settings.EMAIL_BACKEND.lower()

    def test_resend_backend_class_importable(self):
        """T-F-1.9.1-3: anymail resend backend is importable."""
        from anymail.backends.resend import EmailBackend  # noqa: F401

    def test_send_mail_does_not_raise(self):
        """T-F-1.9.1-4: send_mail() succeeds with test backend."""
        mail.send_mail(
            subject="Test",
            message="Hello",
            from_email="test@babook.co.il",
            recipient_list=["user@example.com"],
        )
        assert len(mail.outbox) == 1


# --- F-1.9.2: RESEND_API_KEY + DEFAULT_FROM_EMAIL env vars ---


class TestResendEnvVars(TestCase):
    """T-F-1.9.2-1 through T-F-1.9.2-2"""

    def test_resend_api_key_setting_exists(self):
        """T-F-1.9.2-1: RESEND_API_KEY setting reads from env."""
        assert hasattr(settings, "RESEND_API_KEY"), "RESEND_API_KEY must exist in settings"
        assert isinstance(settings.RESEND_API_KEY, str)

    def test_default_from_email_exists(self):
        """T-F-1.9.2-2: DEFAULT_FROM_EMAIL setting is non-empty."""
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "")
        assert from_email, "DEFAULT_FROM_EMAIL must be set"
        assert "@" in from_email, "DEFAULT_FROM_EMAIL must be a valid email"


# --- F-1.9.3: Forgot-password / reset-password flow ---


class TestPasswordResetFlow(TestCase):
    """T-F-1.9.3-1 through T-F-1.9.3-4"""

    def setUp(self):
        from django.contrib.auth.models import User

        self.user = User.objects.create_user(
            username="resetuser",
            email="reset@example.com",
            password="testpass123",
        )
        self.client = Client()

    def test_password_reset_url_resolves(self):
        """T-F-1.9.3-1: /accounts/password/reset/ returns 200."""
        response = self.client.get("/accounts/password/reset/")
        assert response.status_code == 200

    def test_password_reset_post_sends_email(self):
        """T-F-1.9.3-2: POST with valid email sends reset email."""
        response = self.client.post(
            "/accounts/password/reset/",
            {"email": "reset@example.com"},
        )
        # allauth redirects on success
        assert response.status_code in (200, 302)
        assert len(mail.outbox) >= 1, "Password reset email should be sent"

    def test_password_reset_done_url_resolves(self):
        """T-F-1.9.3-3: Password reset done page loads."""
        response = self.client.get("/accounts/password/reset/done/")
        assert response.status_code == 200

    def test_login_page_has_forgot_password_link(self):
        """T-F-1.9.3-4: Login template contains link to password reset."""
        response = self.client.get("/login/")
        content = response.content.decode()
        assert "password/reset" in content or "forgot" in content.lower(), (
            "Login page must have a forgot-password link"
        )


# --- F-1.9.4: Email verification on signup (optional) ---


class TestEmailVerificationSetting(TestCase):
    """T-F-1.9.4-1"""

    def test_email_verification_setting_exists(self):
        """T-F-1.9.4-1: ACCOUNT_EMAIL_VERIFICATION is one of none/optional/mandatory."""
        val = getattr(settings, "ACCOUNT_EMAIL_VERIFICATION", None)
        assert val in ("none", "optional", "mandatory"), (
            f"ACCOUNT_EMAIL_VERIFICATION must be none/optional/mandatory, got {val!r}"
        )


# --- F-1.9.5: Admin can test-send from Django shell ---


class TestSendMailImportable(TestCase):
    """T-F-1.9.5-1"""

    def test_send_mail_importable_and_callable(self):
        """T-F-1.9.5-1: send_mail function is importable and callable."""
        from django.core.mail import send_mail

        assert callable(send_mail)
