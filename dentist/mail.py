"""The only place dentist sends email.

Two messages exist: an invitation to a role (Rule 3.2) and nothing else
yet. Reminders to patients go by SMS or WhatsApp (Rule 7.5), not email, and
arrive in D.7.

"Sent" here is what the mail backend answered, never what the code hoped
(building_an_app.md, mistake 53: מט״צים told the program manager "sent" for
mails that never left). `send_mail` returns the number delivered to the
backend; a refusal is 0, an exception is 0, and the screen says so.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _send(to, subject, body):
    """The backend's own count, 0 on any failure. Never raises: a mail
    server having a bad afternoon must not take down the screen."""
    if not to:
        return 0
    try:
        return int(send_mail(subject=subject, message=body,
                             from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                             recipient_list=[to]))
    except Exception as exc:  # noqa: BLE001 - the screen reports "not sent"
        logger.warning("dentist mail not sent: %s", exc.__class__.__name__)
        return 0


def send_invitation(invitation, accept_url):
    """A role is waiting at this link. The mail names the clinic and the
    role and nothing else: no patient, no number, nothing clinical."""
    role = dict(invitation._meta.get_field("role").choices).get(invitation.role, invitation.role)
    body = (
        f"You have been invited to {invitation.clinic.name} as {role.lower()}.\n\n"
        f"Open this link to accept:\n{accept_url}\n\n"
        "If you do not have an account yet, the link lets you sign in with "
        "Google and the role will be waiting.\n\n"
        "This is a pilot system, not an official one."
    )
    return _send(invitation.email, f"{invitation.clinic.name}: you are invited as {role.lower()}", body) > 0
