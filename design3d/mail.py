"""The one email design3d sends: you are in (REQ-D3.3). Sent once per
person, and "sent" only when the mail backend said so (methodology 53)."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

log = logging.getLogger(__name__)


def welcome(maker, request=None):
    if maker.welcomed_at or not maker.user.email:
        return False
    link = request.build_absolute_uri("/design3d/") if request else "https://babook.co.il/design3d/"
    body = (
        f"Hi {maker.display_name},\n\n"
        "You are in design3d: describe a part, send a sketch or a photo, and get a printable STL.\n"
        f"{link}\n\n"
        "Sign in with the same account you asked with.\n\n"
        "Avi Salmon"
    )
    try:
        sent = send_mail("You are in design3d", body, settings.DEFAULT_FROM_EMAIL, [maker.user.email])
    except Exception:
        log.exception("design3d: the welcome email to %s failed", maker.user.email)
        return False
    if not sent:
        return False
    maker.welcomed_at = timezone.now()
    maker.save(update_fields=["welcomed_at"])
    return True
