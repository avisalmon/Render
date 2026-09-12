"""REQ-M.111 — the mail that closes the loop.

When a sprint ships work from a request, a summary goes to root and to whoever
asked: what was asked, in their words, what was built, and what was
deliberately left out.

**Why the mail and not just the screen.** She will not go and check a log to
see whether anything happened; nobody does. The screen is where she looks when
she wonders, and the mail is what tells her she did not need to wonder. Both, or
the loop only closes for people who remember to look.

**Same door as every other mail here**: `send_mail` through the guarded
backend, which holds the per-recipient daily cap and the send log. Never fatal:
a provider having a bad afternoon must not roll back a sprint's bookkeeping.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


def _site_url():
    """Where to send her to read the log.

    Every other mail in this product builds links with
    `request.build_absolute_uri`, which is right and is not available here:
    this is sent from a management command, at the end of a sprint, with no
    request in sight. So it is read from `ALLOWED_HOSTS`, which the deploy
    already sets, rather than written as a literal in this file that would
    quietly be wrong the day the domain changes.
    """
    for host in getattr(settings, "ALLOWED_HOSTS", []):
        host = host.strip().lstrip("*.")
        if host and host not in ("127.0.0.1", "localhost", "testserver"):
            scheme = "http" if host.endswith(".test") else "https"
            return f"{scheme}://{host}"
    return "http://localhost:8000"


def _display_name(user):
    from app.models import UserProfile

    if user is None:
        return ""
    name = UserProfile.objects.filter(user=user).values_list("display_name", flat=True).first()
    return (name or "").strip() or (user.email or user.username or "")


def _body(row, site_url):
    asked_by = _display_name(row.author)
    lines = [
        f"שלום,",
        "",
        f"בקשה שנרשמה במט״צים טופלה{f' בספרינט {row.sprint}' if row.sprint else ''}.",
        "",
        "מה התבקש",
        f"({asked_by}, {row.created_at:%d.%m.%Y}"
        + (f", מהמסך {row.from_screen}" if row.from_screen else "")
        + ")",
        "",
        # REQ-M.112 — verbatim. A paraphrase of a request is a request that has
        # already been answered.
        row.body.strip(),
        "",
        "מה נעשה",
        "",
        (row.outcome or "").strip() or "אין פירוט.",
        "",
        f"הבקשות והמצב שלהן: {site_url}/matazim/requests/",
        "",
        "צוות מט״צים",
    ]
    return "\n".join(lines)


def send_request_summary(row, *, site_url=None):
    """Mail the summary to root and to the requester. Returns the addresses used.

    Deliberately not called by approving (REQ-M.110): approving decides
    nothing about when work happens, so it has nothing to report. This is
    called when a request is actually closed.
    """
    from django.contrib.auth.models import User

    site_url = (site_url or _site_url()).rstrip("/")

    recipients = []
    for user in [row.author] + list(User.objects.filter(is_superuser=True)):
        address = (user.email or "").strip()
        if address and address not in recipients:
            recipients.append(address)

    if not recipients:
        return []

    subject = f"מט״צים: הבקשה שלך טופלה{f' · {row.sprint}' if row.sprint else ''}"
    try:
        send_mail(
            subject=subject,
            message=_body(row, site_url),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=True,
        )
    except Exception as exc:  # pragma: no cover - provider trouble, never fatal
        logger.warning("matazim: request summary for %s did not send: %s", row.pk, exc)
        return []

    row.summary_sent_at = timezone.now()
    row.save(update_fields=["summary_sent_at"])
    return recipients
