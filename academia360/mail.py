"""The one way out for every mail Academia360 sends (spec 4.8; methodology
53 and 55).

`send` returns how many messages the backend accepted and never raises, so a
screen or an API answer can say "sent" only when the backend said so, and
"not sent" otherwise. Every path that gives a person access calls
`people.py`, and `people.py` calls here; there is no second door.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Q

from .models import Role

logger = logging.getLogger("academia360.mail")

SUBJECT_PREFIX = "אקדמיה 360° · "
SIGNATURE = "\n\n--\nאקדמיה 360° · אתר פיילוט שנבנה על ידי אבי סלמון, לא אתר רשמי של הממשלה, מל״ג/ות״ת או כל מוסד."
DEFAULT_BASE = "https://babook.co.il"


def base_url(request=None):
    """Where links in a mail point: the request's host when there is one."""
    if request is not None:
        return request.build_absolute_uri("/").rstrip("/")
    return getattr(settings, "ACADEMIA360_BASE_URL", "") or DEFAULT_BASE


def admin_emails():
    """Who hears about requests to join and redeemed invitations: every
    active admin of this app (a Role of kind admin, or a superuser), plus
    the address in ACADEMIA360_ADMIN_EMAIL if one is set."""
    User = get_user_model()
    admin_ids = set(Role.objects.filter(kind=Role.ADMIN, active=True).values_list("user_id", flat=True))
    people = User.objects.filter(is_active=True).filter(Q(pk__in=admin_ids) | Q(is_superuser=True)).exclude(email="")
    addresses = {u.email for u in people}
    extra = getattr(settings, "ACADEMIA360_ADMIN_EMAIL", "") or ""
    if extra:
        addresses.add(extra)
    return sorted(addresses)


def send(subject, body, to):
    """Send one plain-text mail. Returns the backend's own count (0 when it
    refused or when there was nobody to send to)."""
    if isinstance(to, str):
        to = [to]
    to = [t for t in (to or []) if t]
    if not to:
        return 0
    try:
        return int(send_mail(SUBJECT_PREFIX + subject, body + SIGNATURE,
                             getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@babook.co.il"), to) or 0)
    except Exception:  # the backend refused: the caller says "not sent"
        logger.exception("academia360 mail refused: %s", subject)
        return 0
