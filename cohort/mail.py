"""The one email the app sends: you are in (REQ-C.5). Sent once per person."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

log = logging.getLogger(__name__)


def welcome(member, request=None):
    if member.welcomed_at or not member.user.email:
        return False
    link = request.build_absolute_uri("/cohort/") if request else "https://babook.co.il/cohort/"
    body = (
        f"שלום {member.display_name},\n\n"
        "הבקשה שלך להצטרף לאתר ההשתלמות אושרה. האתר פתוח לך מעכשיו:\n"
        f"{link}\n\n"
        "נכנסים עם אותו חשבון שבו ביקשת להצטרף.\n\n"
        "אבי סלמון\n\n"
        "האתר זמני ונועד לתקשורת במהלך ההשתלמות בלבד. הוא אינו אתר רשמי של משרד החינוך, אינטל או כל גורם אחר."
    )
    try:
        send_mail("אושרת להיכנס לאתר ההשתלמות", body, settings.DEFAULT_FROM_EMAIL, [member.user.email])
    except Exception:
        log.exception("cohort: the welcome email to %s failed", member.user.email)
        return False
    member.welcomed_at = timezone.now()
    member.save(update_fields=["welcomed_at"])
    return True
