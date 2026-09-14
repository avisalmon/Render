"""The one door a notification comes through.

REQ-M.33. Same shape as `history.set_status`: everything that raises one goes
through here, so the rules about what a notification may be live in one place
rather than at each of the half-dozen call sites.

Three rules, and each exists because of something this product has already got
wrong once somewhere else.

**It never navigates out of the walls.** A `url` is checked here rather than
trusted, because a notification is the one place nobody would think to look for
a RULE-1 breach: it is not a template, so the template guard cannot see it.

**It never raises for the person who caused it.** A leader who writes feedback
does not need telling that feedback was written. The obvious implementation
notifies whoever the row belongs to, which is right for the member and wrong
for the leader answering their own queue.

**It is never the only telling** (REQ-M.128). That rule cannot be enforced from
inside this function, so it is enforced by a test instead, and named here so
that whoever adds the next event knows it exists.
"""

import logging

from .models import Notification

logger = logging.getLogger(__name__)


def notify(user, kind, text, *, url="", actor=None):
    """Tell somebody something happened. Returns the row, or None.

    Never raises. A notification is a pointer to something that already
    happened and has already been recorded; failing to write one must not roll
    back the thing it was pointing at.
    """
    if user is None or not getattr(user, "is_authenticated", True):
        return None

    # REQ-M.128's other half: telling somebody about their own action is noise,
    # and noise is how a bell stops being read.
    if actor is not None and getattr(actor, "id", None) == getattr(user, "id", None):
        return None

    if url and not url.startswith("/matazim/"):
        # RULE-1, from the one place a template guard cannot see.
        logger.warning("matazim: refusing a notification that leaves the walls: %s", url)
        url = ""

    try:
        row = Notification.objects.create(
            user=user, kind=kind, text=text[:300], url=url[:300]
        )
    except Exception as exc:  # pragma: no cover - never worth losing the event for
        logger.warning("matazim: could not write a notification for %s: %s", user, exc)
        return None

    _mail(row)
    return row


# REQ-M.142 — the bell reaches outside the site for the things worth leaving
# the site for. Until 2026-09-14 nothing did: work returned, a certificate
# issued, an event tomorrow, all bell-only, and a fourteen-year-old who does not
# open the site never learns their work came back. The review named it the
# largest UX gap left.
#
# Not every kind. `FEEDBACK` accompanies a decision that already mails, and a
# second mail for the same moment is how mail stops being opened.
MAILED_KINDS = frozenset(
    {
        Notification.WORK_RETURNED,
        Notification.WORK_APPROVED,
        Notification.WORK_WAITING,
        Notification.CERTIFIED,
        Notification.JOINED,
        Notification.EVENT,
    }
)

SUBJECT = "מט״צים: יש לך משהו חדש"


def _mail(row):
    """One mail per notification, a pointer and never the content.

    The body carries the same short line the bell carries and a link to the
    site, and nothing else: no feedback text, no work, no names beyond the
    reader's own. A minor's feedback is read inside the walls, behind a login,
    not in an inbox that may be shared with a whole family.

    Never raises. The bell is already written; a mail that fails must not undo
    it. The per-recipient daily cap and the send log live in the guarded mail
    backend and apply here without this function knowing about them.
    """
    if row.kind not in MAILED_KINDS:
        return
    address = (getattr(row.user, "email", "") or "").strip()
    if not address:
        return

    from django.conf import settings
    from django.core.mail import send_mail

    from .request_mail import _site_url

    body = (
        f"{row.text}\n\n"
        f"{_site_url()}{row.url or '/matazim/'}\n\n"
        "המייל הזה נשלח כי משהו קרה בחשבון שלך במט״צים. "
        "כל הפרטים נמצאים באתר, אחרי כניסה."
    )
    try:
        send_mail(
            SUBJECT,
            body,
            getattr(settings, "DEFAULT_FROM_EMAIL", None),
            [address],
            fail_silently=True,
        )
    except Exception as exc:  # pragma: no cover - the bell must survive the mail
        logger.warning("matazim: notification mail to %s failed: %s", address, exc)


def unread_count(user):
    if not getattr(user, "is_authenticated", False):
        return 0
    return Notification.objects.filter(user=user, read_at__isnull=True).count()
