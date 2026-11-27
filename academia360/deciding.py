"""The chair's decision (spec 2.6.3, 4.4 "Decide", backlog E.3): one row per
submission, recorded by a chair or the admin and re-recorded in place. It
sends nothing and changes nothing the institution can see: the letter does
that when it is sent (spec 2.6.5; backlog E decisions).
"""

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import access, mail, notify
from .access import chair_only
from .api import _snapshot as snapshot
from .api import log_change
from .models import Decision, Submission

OUTCOMES = [k for k, _ in Decision.OUTCOMES]


def amount_from(raw):
    """"5,000,000", "5000000", "5000000.50" and blank; anything else is None."""
    text = (raw or "").replace(",", "").replace("₪", "").replace(" ", "").strip()
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value >= 0 else None


def record(request, submission, outcome, amount=None, conditions=""):
    """Write the decision, log it field by field, tell the admin. Returns
    (decision, created)."""
    row, created = Decision.objects.get_or_create(submission=submission, defaults={
        "outcome": outcome, "approved_amount_nis": amount, "conditions": conditions,
        "decided_by": request.user, "decided_at": timezone.now()})
    if created:
        log_change(request, row)
    else:
        before = snapshot(row)
        row.outcome, row.approved_amount_nis, row.conditions = outcome, amount, conditions
        row.decided_by, row.decided_at = request.user, timezone.now()
        row.save()
        log_change(request, row, before=before)
    notify.decision_recorded(row, actor=request.user, base=mail.base_url(request))
    return row, created


@chair_only
@require_http_methods(["GET", "POST"])
def decide(request, pk):
    sub = get_object_or_404(Submission.objects.select_related("participation__institution", "participation__program"), pk=pk)
    inst = sub.participation.institution
    row = Decision.objects.filter(submission=sub).select_related("decided_by").first()
    if request.method == "POST":
        outcome = request.POST.get("outcome", "")
        amount_raw = request.POST.get("approved_amount_nis", "")
        amount = amount_from(amount_raw)
        if outcome not in OUTCOMES:
            messages.error(request, "מה ההחלטה? צריך לבחור אחת.")
        elif amount_raw.strip() and amount is None:
            messages.error(request, "הסכום לא נקרא כמספר.")
        else:
            row, created = record(request, sub, outcome, amount, (request.POST.get("conditions") or "").strip())
            messages.success(request, "ההחלטה נרשמה." if created else "ההחלטה עודכנה.")
            return redirect(reverse("academia360:committee_file", args=[inst.slug]) + f"#decision-{sub.pk}")
    return render(request, "academia360/committee/decide.html", {
        "section": "committee", "sub": sub, "inst": inst, "decision": row, "outcomes": Decision.OUTCOMES,
        "amount": format(row.approved_amount_nis.normalize(), "f") if row and row.approved_amount_nis is not None else "",
        "letter": getattr(sub, "letter", None) if hasattr(sub, "letter") else None,
        "is_admin": access.is_admin(request.user),
    })
