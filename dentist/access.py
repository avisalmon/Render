"""Who may see what (spec Rule 3.1, 3.3, 3.4, 3.7). One function per
question, used everywhere; nothing anywhere else decides access.

The rule that shapes this file: **everything belongs to a clinic, and a
superuser sees nothing clinical.** On every other app on this site the site
admin has a bypass; here the data is medical, so the bypass is refused on
purpose, and the one thing a superuser can do is create a clinic and invite
its first administrator. The one exception is written in Rule 3.3: a
superuser may hold an explicit membership in a **demo clinic** (invented
data, `Clinic.is_demo`), which is how the people building the app see it.

**Trying a role (Rule 3.7).** In a demo clinic an administrator can see the
clinic as a dentist, or as one of its patients, to feel what they feel.
The choice lives in the session (`dn_try_as`, put on the user by
`dentist.middleware`), is honoured only by the functions here, only for a
demo clinic, and only while the person really is an active administrator
of it. Nothing is written to the database: in "dentist" the membership is
read with its role swapped; in "patient" there is no membership at all and
`patient_of` answers with the chosen demo patient, so every staff screen
refuses exactly as it would refuse a real patient.
"""

import copy

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import AccessLog, ClinicMember, Patient

TRY_KEY = "dn_try_as"
TRY_ROLES = ("admin", "dentist", "patient")


def trying(user):
    """The role being tried, as {"clinic": slug, "role": ..., "patient": id}
    or None. Set by the middleware from the session."""
    t = getattr(user, "dn_try", None)
    return t if isinstance(t, dict) and t.get("role") in TRY_ROLES else None


def _real_admin_of_demo(user, clinic):
    if not clinic.is_demo:
        return None
    return ClinicMember.objects.filter(user=user, clinic=clinic, active=True, role=ClinicMember.ADMIN).first()


def _try_for(user, clinic):
    """The try-as state if it applies to this clinic and this person may
    use it; else None."""
    t = trying(user)
    if not t or t.get("clinic") != clinic.slug:
        return None
    if _real_admin_of_demo(user, clinic) is None:
        return None
    return t


def memberships(user):
    """Every active membership this person holds, with its clinic."""
    if not user.is_authenticated:
        return ClinicMember.objects.none()
    rows = ClinicMember.objects.filter(user=user, active=True).select_related("clinic")
    t = trying(user)
    if t and t["role"] == "patient":
        rows = rows.exclude(clinic__slug=t.get("clinic"))  # as a patient you have no clinic
    return rows


def membership(user, clinic):
    """This person's role at this clinic, or None. A superuser gets None
    like anybody else (Rule 3.3) unless explicitly a member of a demo
    clinic. Honours a tried role (Rule 3.7)."""
    if not user.is_authenticated:
        return None
    t = _try_for(user, clinic)
    if t and t["role"] == "patient":
        return None
    member = ClinicMember.objects.filter(user=user, clinic=clinic, active=True).first()
    if t and t["role"] == "dentist" and member is not None:
        member = copy.copy(member)  # read with the tried role; never saved
        member.role = ClinicMember.DENTIST
    return member


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
    """The patient record this account is connected to, or None (Rule 3.4);
    or, trying "patient" in a demo clinic, the chosen demo patient."""
    if not user.is_authenticated:
        return None
    t = trying(user)
    if t and t["role"] == "patient":
        patient = Patient.objects.filter(pk=t.get("patient") or 0, clinic__slug=t.get("clinic"),
                                         clinic__is_demo=True, is_demo=True).select_related("clinic").first()
        if patient is not None and _real_admin_of_demo(user, patient.clinic) is not None:
            return patient
        return None
    return getattr(user, "dn_patient", None)


def may_create_clinic(user):
    """Rule 3.3: the superuser's one clinical power."""
    return bool(user.is_authenticated and user.is_superuser)


def may_try(user, clinic):
    """Rule 3.7: a real administrator of a demo clinic may try its roles."""
    return bool(user.is_authenticated and _real_admin_of_demo(user, clinic) is not None)


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
