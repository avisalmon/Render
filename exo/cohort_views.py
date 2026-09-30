"""The workshop link, and Avi's page for making them (spec §4.2, EPIC K).

`join_by_link` is the second privileged thing in this app after
`approve_api.py`, and it follows the same discipline: the group it grants is
named here in code and never in the request, it grants ordinary membership and
nothing above it, the token comparison is constant-time, every refusal is
explicit, and every arrival is recorded.

It breaks the BKM's "never create the principal" on purpose, because a person
in a workshop has usually never used babook and an invite that cannot make an
account is not an invite. Spec K7 carries the reasoning and the blast-radius
sentence; the bounds are a short window, a kill switch and `max_joins`.
"""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.db import IntegrityError, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare, get_random_string
from django.views.decorators.http import require_POST

from .access import GROUP_NAME, admin_required, approve, membership_for
from .models import Cohort, CohortMember

User = get_user_model()


def _find_cohort(token):
    """The cohort for this token, compared in constant time.

    `==` on a secret leaks its length and prefix through timing. The lookup is
    indexed, so this walks the candidates only to compare them safely rather
    than to find them.
    """
    token = (token or "").strip()
    if not token:
        return None
    for cohort in Cohort.objects.filter(token__startswith=token[:4]):
        if constant_time_compare(cohort.token, token):
            return cohort
    return None


def join_by_link(request, token):
    """Open the workshop link.

    Signs the person in, creating their account if this is their first time,
    approves them into `exo_members`, records the arrival, and sends them
    straight to the builder. One click from a message to a working screen,
    which is the entire point.
    """
    cohort = _find_cohort(token)
    if cohort is None:
        # An unknown token is not told whether it was ever real.
        raise Http404

    refusal = cohort.refusal()
    if refusal:
        # A plain sentence, never an error page: somebody arriving a day late
        # has done nothing wrong and should be told what happened.
        return render(request, "exo/cohort_closed.html",
                      {"cohort": cohort, "reason": refusal}, status=410)

    if request.user.is_authenticated:
        user = request.user
    else:
        # A fresh account for somebody who has never been here. Username is
        # generated rather than asked for: a workshop should not open with a
        # form, and the person can be recognised later by the email they add.
        user = User.objects.create_user(
            username=f"exo-{get_random_string(10).lower()}",
            password=get_random_string(20),
        )
        auth_login(request, user,
                   backend="django.contrib.auth.backends.ModelBackend")

    membership = membership_for(user, create=True)
    fresh = not membership.user.groups.filter(name=GROUP_NAME).exists()
    approve(membership)
    if fresh:
        # Licensed by workshop windows, not open-ended. Only set when the link
        # is what let them in, so somebody Avi approved by hand never acquires
        # a window by attending a workshop later.
        membership.ai_needs_open_window = True
        membership.save(update_fields=["ai_needs_open_window"])

    try:
        with transaction.atomic():
            CohortMember.objects.get_or_create(cohort=cohort, user=user)
    except IntegrityError:  # pragma: no cover - the unique constraint racing
        pass

    return redirect("exo:concepts")


# ---------------------------------------------------------------------------
# Avi's cockpit
# ---------------------------------------------------------------------------


@admin_required
def cohorts(request):
    """Every workshop: its link, its window, who came, what came out."""
    rows = []
    now = timezone.now()
    for cohort in Cohort.objects.all().prefetch_related("members__user",
                                                        "concepts"):
        concepts = list(cohort.concepts.all())
        rows.append({
            "cohort": cohort,
            "open": cohort.is_open(now=now),
            "reason": cohort.refusal(now=now),
            "members": list(cohort.members.all()),
            "joined": cohort.members.count(),
            "concepts": len(concepts),
            "articles": sum(1 for c in concepts if getattr(c, "release", None)),
            "url": request.build_absolute_uri(cohort.join_url()),
        })
    return render(request, "exo/manage_cohorts.html",
                  {"rows": rows, "nav": "manage"})


@admin_required
@require_POST
def cohort_create(request):
    name = (request.POST.get("name") or "").strip()
    if not name:
        return redirect("exo:manage_cohorts")

    def positive(field, default):
        try:
            value = int(request.POST.get(field) or default)
        except (TypeError, ValueError):
            return default
        return value if value > 0 else default

    Cohort.objects.create(
        name=name[:120],
        window_hours=positive("window_hours", Cohort.WINDOW_HOURS),
        max_joins=positive("max_joins", 60),
        created_by=request.user,
    )
    return redirect("exo:manage_cohorts")


@admin_required
@require_POST
def cohort_close(request, pk):
    """Shut a room by hand, without waiting for its window."""
    cohort = get_object_or_404(Cohort, pk=pk)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        data = {}
    cohort.is_closed = bool(data.get("closed", True))
    cohort.save(update_fields=["is_closed"])
    return JsonResponse({"ok": True, "closed": cohort.is_closed,
                         "open": cohort.is_open()})
