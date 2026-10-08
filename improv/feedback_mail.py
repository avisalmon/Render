"""Every feedback note is emailed to the owner (SPR-I.9.4). The addresses are fixed on purpose."""

import logging

from django.conf import settings
from django.core.mail import EmailMessage

log = logging.getLogger(__name__)

OWNER_ADDRESSES = ["avi.salmon@gmail.com", "avi.salmon@intel.com"]


def _one_line(text, limit=120):
    return " ".join(str(text).split())[:limit]


def send_feedback_mail(note, user):
    """Send one note. A mail failure is logged and never loses the note, which is already saved."""
    try:
        sender = user.email or ""
        who = _one_line(user.get_full_name() or user.get_username())
        kind = note.get_kind_display()
        body = (
            f"{who} ({sender or 'no email on file'}) wrote about improv:\n\n"
            f"{note.message}\n\n"
            f"Kind: {kind}\n"
            f"Page: {_one_line(note.page, 200) or 'not given'}\n"
            f"Read all notes: /admin/improv/feedback/\n"
        )
        message = EmailMessage(
            subject=f"improv feedback: {kind}, from {who}",
            body=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None) or "noreply@babook.co.il",
            to=list(OWNER_ADDRESSES),
            reply_to=[sender] if sender else None,
        )
        message.send()
    except Exception:
        log.exception("improv feedback email failed for note %s", getattr(note, "pk", None))
