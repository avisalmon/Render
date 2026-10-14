"""Redeeming a role that was granted to an email address (spec Rule 4.3).

The admin's first real task is appointing a tech lead and judges, and
those are busy outsiders. `EventRole` can only point at a `User`, so
without this the admin's first action waits on three prior steps by
somebody who has never heard of this site.

Redeeming happens on sign-up and on sign-in, by email match, so the person
lands already holding the role rather than on a page wondering what they
are looking at. The invitation row is kept rather than deleted, because
"who invited whom" is worth having later.
"""

from django.db import transaction
from django.utils import timezone

from .models import EventRole, RoleInvitation


def pending_for_email(email):
    if not email:
        return RoleInvitation.objects.none()
    return RoleInvitation.objects.filter(email__iexact=email.strip(), accepted_at__isnull=True)


@transaction.atomic
def redeem_for(user):
    """Turn every pending invitation for this user's email into a role.

    Returns the roles created. Idempotent: an invitation already accepted
    is skipped, and `get_or_create` means a role the person somehow already
    holds is not duplicated.
    """
    created = []
    for invite in pending_for_email(getattr(user, "email", "")).select_for_update():
        role, was_new = EventRole.objects.get_or_create(
            hackathon=invite.hackathon,
            user=user,
            role=invite.role,
            defaults={"granted_by": invite.invited_by},
        )
        invite.accepted_at = timezone.now()
        invite.accepted_user = user
        invite.save(update_fields=["accepted_at", "accepted_user"])
        if was_new:
            created.append(role)
    return created
