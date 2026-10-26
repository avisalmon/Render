"""Who may see what (spec Rule 3.1, 3.3, 3.4). One function per question,
used everywhere; nothing anywhere else decides access.

The rule that shapes this file: **everything belongs to a clinic, and a
superuser sees nothing clinical.** On every other app on this site the site
admin has a bypass; here the data is medical, so the bypass is refused on
purpose, and the one thing a superuser can do is create a clinic and invite
its first administrator.
"""

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import AccessLog, ClinicMember


def memberships(user):
    """Every active membership this person holds, with its clinic."""
    if not user.is_authenticated:
        return ClinicMember.objects.none()
    return ClinicMember.objects.filter(user=user, active=True).select_related("clinic")


def membership(user, clinic):
    """This person's role at this clinic, or None. A superuser gets None
    like anybody else (Rule 3.3)."""
    if not user.is_authenticated:
        return None
    return ClinicMember.objects.filter(user=user, clinic=clinic, active=True).first()


def require_member(user, clinic, role=None):
    """The one gate every clinical view goes through."""
    m = membership(user, clinic)
    if m is None or (role and m.role != role):
        raise PermissionDenied
    return m


def require_admin(user, clinic):
    """The administrator's screens: people, setup, the log, export, delete."""
    return require_member(user, clinic, role=ClinicMember.ADMIN)


def is_admin(user, clinic):
    m = membership(user, clinic)
    return bool(m and m.role == ClinicMember.ADMIN)


def patient_of(user):
    """The patient record this account is connected to, or None (Rule 3.4)."""
    if not user.is_authenticated:
        return None
    return getattr(user, "dn_patient", None)


def may_create_clinic(user):
    """Rule 3.3: the superuser's one clinical power."""
    return bool(user.is_authenticated and user.is_superuser)


def patients_for(user, clinic):
    """The patients this person may see: all of the clinic's for a member,
    exactly one for a patient account, none for anybody else."""
    m = membership(user, clinic)
    if m is not None:
        return clinic.patients.all()
    me = patient_of(user)
    if me is not None and me.clinic_id == clinic.pk:
        return clinic.patients.filter(pk=me.pk)
    return clinic.patients.none()


def patient_or_404(user, clinic, pk):
    """One patient of this clinic, through the same scope as the list, so
    another clinic's patient is "not here" rather than "not yours"."""
    return get_object_or_404(patients_for(user, clinic), pk=pk)


def log(clinic, user, action, patient=None, what=""):
    """Rule 4.5: every look is a row. Ids and screen names only (Rule 9.4)."""
    return AccessLog.objects.create(
        clinic=clinic, patient=patient, user=user if user.is_authenticated else None,
        action=action, what=what[:120],
    )
