"""A patient's record as a whole: find it, export it, delete it (Rule 4.6,
9.5). The clinic owns its data; these are the two ways it leaves."""

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Q
from django.forms.models import model_to_dict

from . import access


def find(patients, q):
    """Name, clinic number or phone, one box (Rule 4.6). Empty: the last
    few patients seen."""
    q = (q or "").strip()
    if not q:
        return patients.order_by("-updated_at")[:12]
    return patients.filter(
        Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(clinic_number__icontains=q)
        | Q(phone__icontains=q) | Q(whatsapp__icontains=q)
    ).order_by("first_name", "last_name")[:50]


def _rows(queryset, exclude=()):
    return [model_to_dict(row, exclude=list(exclude)) for row in queryset]


def export(patient, by):
    """Everything the clinic holds about one person, as JSON another system
    can read. Files are named, not embedded. Logged."""
    data = {
        "patient": model_to_dict(patient, exclude=["user"]),
        "history": _rows(patient.history.all()),
        "teeth": _rows(patient.teeth.all()),
        "plan": _rows(patient.plan.all()),
        "visits": [
            {**model_to_dict(v), "procedures": _rows(v.procedures.all())} for v in patient.visits.all()
        ],
        "appointments": _rows(patient.appointments.all()),
        "consents": _rows(patient.consents.all()),
        "attachments": [
            {**model_to_dict(a, exclude=["file"]), "file": a.file.name} for a in patient.attachments.all()
        ],
        "costs": _rows(patient.costs.all()),
        "access_log": [
            {"action": r.action, "what": r.what, "at": r.at, "user_id": r.user_id} for r in patient.access_log.all()
        ],
    }
    access.log(patient.clinic, by, "exported", patient=patient, what="patient export")
    return json.dumps(data, cls=DjangoJSONEncoder, ensure_ascii=False, indent=1)


def delete(patient, by):
    """Rows and files, gone (Rule 9.5). The log keeps a row that says a
    patient with this id was deleted, and nothing else about them."""
    clinic, pk = patient.clinic, patient.pk
    with transaction.atomic():
        for attachment in patient.attachments.all():
            try:
                attachment.file.delete(save=False)
            except Exception:  # noqa: BLE001 - a missing file must not stop the deletion
                pass
        patient.delete()
        access.log(clinic, by, "deleted", what=f"patient {pk}")
