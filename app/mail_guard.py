"""Outbound mail guard (2026-08-08).

Two problems, both learned the hard way after the Resend daily quota kept
running out.

1. We could not see what was sending. Nothing logged outbound mail, so the only
   evidence was Resend's own dashboard. Every message now leaves a line in the
   Render log with its subject and a masked recipient, which is enough to name
   the source without leaking addresses into the log.
2. The same address could be mailed over and over - /resend-verification/ used
   to send on a plain GET, so a refresh or a link prefetch was another email. A
   per-recipient daily cap stops a loop like that dead, and by construction it
   can never block a different, legitimate recipient.

This is a wrapper, not a backend: it counts, logs, and hands the survivors to
the real backend named in MAIL_GUARD_INNER_BACKEND.
"""
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.mail.backends.base import BaseEmailBackend
from django.utils import timezone
from django.utils.module_loading import import_string

logger = logging.getLogger("app.mail")

DEFAULT_PER_RECIPIENT_DAILY_CAP = 10


def _mask(address):
    """t***@example.com - enough to spot a loop, not enough to harvest."""
    local, sep, domain = (address or "").partition("@")
    if not sep:
        return "***"
    return f"{local[:1]}***@{domain}"


def _counter_key(address):
    digest = hashlib.sha256((address or "").strip().lower().encode()).hexdigest()[:16]
    return f"mailguard:{timezone.now():%Y%m%d}:{digest}"


def _cap():
    return int(getattr(settings, "MAIL_PER_RECIPIENT_DAILY_CAP",
                       DEFAULT_PER_RECIPIENT_DAILY_CAP))


def allow_recipient(address, subject=""):
    """Count one send to this address today; False once it is over the cap."""
    cap = _cap()
    if cap <= 0:  # 0 disables the guard entirely
        return True
    key = _counter_key(address)
    sent_today = cache.get(key, 0)
    if sent_today >= cap:
        logger.warning(
            "mail BLOCKED (%s already sent today, cap %s) to=%s subject=%r",
            sent_today, cap, _mask(address), subject,
        )
        return False
    cache.set(key, sent_today + 1, 86400)
    logger.info(
        "mail SEND to=%s subject=%r (%s/%s today)",
        _mask(address), subject, sent_today + 1, cap,
    )
    return True


class GuardedEmailBackend(BaseEmailBackend):
    """Logs and caps, then delegates to the configured real backend."""

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        inner = getattr(settings, "MAIL_GUARD_INNER_BACKEND",
                        "django.core.mail.backends.console.EmailBackend")
        self.inner = import_string(inner)(fail_silently=fail_silently, **kwargs)

    def open(self):
        return self.inner.open()

    def close(self):
        return self.inner.close()

    def send_messages(self, email_messages):
        allowed = []
        for message in email_messages or []:
            kept = [a for a in message.to if allow_recipient(a, message.subject)]
            if not kept:
                continue
            message.to = kept
            allowed.append(message)
        if not allowed:
            return 0
        return self.inner.send_messages(allowed)
