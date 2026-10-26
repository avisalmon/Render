"""How a person comes to exist in a clinic (spec Rule 3.2, 3.4).

Staff: an administrator invites an email address to a role; the invitation
is a token; whoever opens it while signed in gets the role, once. Patients:
the clinic makes a one-time link for a record; whoever opens it while
signed in becomes that record's account, once. Both are the only doors.
Every path that grants access goes through here, so a second door cannot
forget the mail or the log (mistake 53).
"""

from datetime import timedelta

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from . import access, mail
from .models import ClinicMember, Invitation, PatientLink

LINK_DAYS = 7


class Refused(Exception):
    """A reason a person can read, never a traceback."""


def invite(clinic, email, role, by, request):
    """Create the invitation and mail it. Returns (invitation, sent)."""
    email = (email or "").strip().lower()
    with transaction.atomic():
        invitation = Invitation.objects.create(clinic=clinic, email=email, role=role, invited_by=by)
    sent = resend(invitation, request)
    return invitation, sent


def resend(invitation, request):
    url = request.build_absolute_uri(reverse("dentist:accept_invitation", args=[invitation.token]))
    return mail.send_invitation(invitation, url)


def accept(invitation, user):
    """The role, once. A second visit to the link is a no-op that still
    lands the person in their clinic. Refused for a superuser: Rule 3.3
    says the site admin is a member of nothing."""
    if user.is_superuser:
        raise Refused("The site administrator cannot hold a role in a clinic.")
    with transaction.atomic():
        member, made = ClinicMember.objects.get_or_create(
            clinic=invitation.clinic, user=user,
            defaults={"role": invitation.role, "invited_by": invitation.invited_by},
        )
        if not made and not member.active:
            member.active = True
            member.save(update_fields=["active"])
        if invitation.accepted_at is None:
            invitation.accepted_at = timezone.now()
            invitation.accepted_by = user
            invitation.save(update_fields=["accepted_at", "accepted_by"])
    return member, made


def make_patient_link(patient, by, request):
    """A fresh link; any earlier unused link for this patient is retired so
    only one is live at a time."""
    PatientLink.objects.filter(patient=patient, used_at__isnull=True).update(used_at=timezone.now())
    link = PatientLink.objects.create(patient=patient, made_by=by, expires_at=timezone.now() + timedelta(days=LINK_DAYS))
    access.log(patient.clinic, by, "edited", patient=patient, what="patient link made")
    return link, request.build_absolute_uri(reverse("dentist:join", args=[link.token]))


def connect(link, user):
    """The account becomes the record's, once (Rule 3.4)."""
    mine = access.patient_of(user)
    if mine is not None and mine.pk == link.patient_id:
        return link.patient  # their own link, again: still theirs
    if not link.is_valid:
        raise Refused("This link has been used or has expired. Ask the clinic for a new one.")
    if mine is not None:
        raise Refused("This account is already connected to a patient record.")
    if access.memberships(user).exists() or user.is_superuser:
        raise Refused("This account belongs to a member of staff. Sign in with a personal account.")
    with transaction.atomic():
        patient = link.patient
        patient.user = user
        patient.save(update_fields=["user"])
        link.used_at = timezone.now()
        link.save(update_fields=["used_at"])
        access.log(patient.clinic, user, "edited", patient=patient, what="patient link used")
    return patient
