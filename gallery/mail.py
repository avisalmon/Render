"""The one email the gallery sends: a person was blocked from uploading skills
after a second risky upload (REQ-G.72). To Avi, once per block.

"Sent" is what the mail backend said (methodology 53), not what we hoped:
`emailed_at` is set only when `send_mail` reports one message delivered.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

log = logging.getLogger(__name__)


def admin_address():
    return getattr(settings, "GALLERY_ADMIN_EMAIL", "") or ""


def blocked(person, strikes, chat_url):
    """Mail Avi about a block. `strikes` are the person's Strike rows, the
    newest first; the newest is marked emailed when the mail goes."""
    to = admin_address()
    newest = strikes[0]
    if newest.emailed_at or not to:
        return False
    lines = [
        f"{person.display_name} ({person.user.email}) was blocked from uploading skills to the gallery",
        f"after a second risky upload, {timezone.localtime(newest.created_at):%d.%m.%Y %H:%M}.",
        "",
        f"The chat: {chat_url}",
        "",
    ]
    for n, s in enumerate(reversed(strikes), start=1):
        lines += [f"Strike {n}, {timezone.localtime(s.created_at):%d.%m.%Y %H:%M}:", s.findings.strip()[:3000], ""]
    lines += ["To lift the block: /admin/gallery/person/ (clear 'skills blocked at')."]
    try:
        sent = send_mail(f"gallery: {person.display_name} blocked from uploading skills", "\n".join(lines),
                         settings.DEFAULT_FROM_EMAIL, [to])
    except Exception:
        log.exception("gallery: the block email about %s failed", person.pk)
        return False
    if sent != 1:
        return False
    newest.emailed_at = timezone.now()
    newest.save(update_fields=["emailed_at"])
    return True
