"""The only place CrashTech sends email (spec chapter 12).

**One rule governs everything here: email is sent only for something that
happened while the person was not looking, and that they must act on or
would be upset to miss.** No digests, no engagement, no "here is what you
missed". That rule yields exactly six triggers, and this module holds them
all so the list cannot quietly grow.

Two constraints are built in rather than remembered:

- **Every message names which event it is about** (Rule 12.3). Somebody who
  competes three years running has three, and "your registration was
  accepted" is useless without saying to what.
- **Email is never the only channel** (Rule 12.2). Everything sent here is
  also on the person's role home. A mail that does not arrive must not
  cost anyone the event.

This is not a notification system. No model, no preferences, no inbox,
until it deliberately becomes one (Rule 12.4).
"""

from django.conf import settings
from django.core.mail import send_mail

#: The complete list. Adding a seventh is a spec change, not an edit.
TRIGGERS = (
    "role_invitation",
    "registration_decided",
    "kit_pickup",
    "event_live",
    "shortlisted",
    "results_published",
)


def _send(to, subject, body):
    """Never raises. A mail server having a bad afternoon must not take
    down the screen somebody was using, because the thing it carries is
    always also on their role home."""
    if not to:
        return False
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[to],
            fail_silently=True,
        )
        return True
    except Exception:  # noqa: BLE001 - see the docstring
        return False


def send_role_invitation(invitation, accept_url):
    """Trigger 1 of 6. The one that cannot be replaced by a screen, because
    the person has no account and therefore no screen to look at.

    This is the whole mechanism behind Rule 4.3: an admin appoints a tech
    lead or a judge by email, and the role is waiting when they arrive.
    """
    event = invitation.hackathon
    role = dict(invitation._meta.get_field("role").choices).get(invitation.role, invitation.role)
    body = (
        f"You have been invited to help run {event.name} as {role}.\n\n"
        f"Open this link to accept:\n{accept_url}\n\n"
        "If you do not already have a CrashTech account, the link will "
        "make one, and the role will be waiting.\n\n"
        "CrashTech"
    )
    return _send(invitation.email, f"{event.name}: you have been invited as {role}", body)
