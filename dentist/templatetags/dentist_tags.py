"""The "try as" bar (spec Rule 3.7), shown on a demo clinic's pages to its
administrators, and on the patient's screen while a role is being tried.
"""

from django import template

from .. import access
from ..models import Clinic

register = template.Library()


@register.inclusion_tag("dentist/_try_as.html", takes_context=True)
def try_as_bar(context):
    request = context.get("request")
    empty = {"show": False}
    if request is None or not request.user.is_authenticated:
        return empty
    t = access.trying(request.user)
    slug = (request.resolver_match.kwargs.get("slug") if request.resolver_match else None) or (t or {}).get("clinic")
    if not slug:
        return empty
    clinic = Clinic.objects.filter(slug=slug, is_demo=True).first()
    if clinic is None or not access.may_try(request.user, clinic):
        return empty
    role = t["role"] if t and t.get("clinic") == slug else "admin"
    patient = access.patient_of(request.user) if role == "patient" else None
    return {
        "show": True, "clinic": clinic, "role": role, "patient": patient,
        "patients": clinic.patients.filter(is_demo=True).order_by("first_name")[:12],
        "request": request,
    }
