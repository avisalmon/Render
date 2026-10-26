"""dentist's pages (spec chapter 11). Sprint D.1: the front door, the
clinic's home per role, and the one thing a superuser may do.

Every view is tagged administrator, dentist or patient in its docstring,
because the tag decides its layout (Rule 11.1).
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify

from . import access
from .decorators import signed_in
from .models import Clinic, ClinicMember, Invitation


def _clinic(slug):
    return get_object_or_404(Clinic, slug=slug)


def home(request):
    """**Front door, every persona.** Signed out: what this is, and the way
    in. Signed in: the clinics this person belongs to, or their own record,
    or (a superuser with nothing) the one thing they may do."""
    if not request.user.is_authenticated:
        return render(request, "dentist/home.html", {"signed_out": True})

    mine = list(access.memberships(request.user))
    me = access.patient_of(request.user)
    if len(mine) == 1 and me is None:
        return redirect("dentist:clinic_home", slug=mine[0].clinic.slug)
    return render(request, "dentist/home.html", {
        "memberships": mine,
        "patient": me,
        "may_create": access.may_create_clinic(request.user),
    })


@signed_in
def clinic_new(request):
    """**Site admin.** Rule 3.3: the superuser's one power. Creates the
    clinic and invites its first administrator by email; the superuser is
    not made a member and sees nothing more."""
    if not access.may_create_clinic(request.user):
        raise PermissionDenied

    errors = {}
    data = {"name": "", "admin_email": ""}
    if request.method == "POST":
        data = {k: (request.POST.get(k) or "").strip() for k in data}
        if not data["name"]:
            errors["name"] = "Give the clinic a name."
        if "@" not in data["admin_email"]:
            errors["admin_email"] = "The first administrator's email address."
        slug = slugify(data["name"])[:70]
        if not errors and (not slug or Clinic.objects.filter(slug=slug).exists()):
            errors["name"] = "A clinic with this name already exists."
        if not errors:
            with transaction.atomic():
                clinic = Clinic.objects.create(
                    name=data["name"], slug=slug, created_by=request.user,
                    languages=["he", "en", "ru", "ar", "ti", "hi"],
                )
                Invitation.objects.create(
                    clinic=clinic, email=data["admin_email"].lower(),
                    role=ClinicMember.ADMIN, invited_by=request.user,
                )
            messages.success(
                request,
                f"{clinic.name} exists. Its first administrator has an invitation waiting "
                f"at {data['admin_email']}; you are not a member of it.",
            )
            return redirect("dentist:home")
    return render(request, "dentist/clinic_new.html", {"errors": errors, "data": data})


@signed_in
def clinic_home(request, slug):
    """**Administrator or dentist.** The clinic's home, answering "what now"
    for this person's role (Rule 11.5). D.1 shows the shape; the screens
    each row points at arrive in D.2 to D.6."""
    clinic = _clinic(slug)
    member = access.require_member(request.user, clinic)
    access.log(clinic, request.user, "viewed", what="clinic home")
    return render(request, "dentist/clinic_home.html", {
        "clinic": clinic,
        "member": member,
        "is_admin": member.role == ClinicMember.ADMIN,
        "counts": {
            "patients": clinic.patients.filter(status="active").count(),
            "members": clinic.members.filter(active=True).count(),
            "chairs": clinic.chairs.filter(active=True).count(),
            "pending": clinic.invitations.filter(accepted_at__isnull=True).count(),
        },
    })
