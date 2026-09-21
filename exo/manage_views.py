"""Avi's cockpit: who is waiting, what is on the wall, what it costs (§11).

Deliberately its own pages rather than Django admin. Approving someone is the
one routine act this app asks of its owner, and it happens on a phone, between
other things — the thing `building_an_app.md`'s "key, not the house" note was
written about. A list with two buttons beats `/admin/auth/user/` and a
checkbox.
"""

from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import ai
from .access import admin_required, approve, revoke
from .models import AiCall, Membership, PressRelease


@admin_required
def requests(request):
    """Everyone who asked, grouped by what has been decided."""
    return render(request, "exo/manage_requests.html", {
        "requested": Membership.objects.filter(
            status=Membership.Status.REQUESTED
        ).select_related("user"),
        "approved": Membership.objects.filter(
            status=Membership.Status.APPROVED
        ).select_related("user"),
        "denied": Membership.objects.filter(
            status=Membership.Status.DENIED
        ).select_related("user"),
        "nav": "manage",
    })


@admin_required
@require_POST
def decide(request, pk):
    """Approve, deny, or revoke one person. POST only: this changes access."""
    membership = get_object_or_404(Membership, pk=pk)
    action = request.POST.get("action")
    if action == "approve":
        approve(membership, by=request.user)
    elif action in ("deny", "revoke"):
        revoke(membership, by=request.user, denied=True)
    return redirect("exo:manage_requests")


@admin_required
def releases(request):
    """Everything anyone has published, with the one lever Avi needs: hide.

    Hiding rather than deleting is the point (spec §10.4): revoking a person's
    access does not destroy their work, and a release that should not be on the
    wall can leave the wall without anyone losing what they wrote.
    """
    return render(request, "exo/manage_releases.html", {
        "releases": PressRelease.objects.select_related(
            "concept", "concept__owner"
        ).annotate(likes=Count("like_rows")).order_by("-created_at"),
        "now": timezone.now(),
        "nav": "manage",
    })


@admin_required
@require_POST
def moderate(request, pk):
    release = get_object_or_404(PressRelease, pk=pk)
    release.hidden_by_admin = request.POST.get("action") == "hide"
    release.save(update_fields=["hidden_by_admin", "updated_at"])
    return redirect("exo:manage_releases")


@admin_required
def usage(request):
    """What the AI is costing, and who is spending it (spec §11, J3)."""
    since = timezone.now() - timezone.timedelta(days=30)
    calls = AiCall.objects.filter(created_at__gte=since)
    by_task = (calls.values("task")
               .annotate(n=Count("id"),
                         prompt=Sum("prompt_tokens"),
                         completion=Sum("completion_tokens"))
               .order_by("-n"))
    by_person = (calls.exclude(user=None).values("user__username")
                 .annotate(n=Count("id"),
                           prompt=Sum("prompt_tokens"),
                           completion=Sum("completion_tokens"))
                 .order_by("-n")[:25])
    day_ago = timezone.now() - timezone.timedelta(days=1)
    return render(request, "exo/manage_usage.html", {
        "by_task": by_task,
        "by_person": by_person,
        "today": calls.filter(created_at__gte=day_ago).count(),
        "failures": calls.filter(ok=False).count(),
        "total": calls.count(),
        # Read from the guard itself rather than recomputed here, so this page
        # can never reassure Avi with a number the guard disagrees with.
        "guard": ai.guard_status(),
        "limits": ai.limits(),
        "stub": ai.is_stub(),
        "nav": "manage",
    })
