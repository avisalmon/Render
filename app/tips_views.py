"""EPIC-6.4 - Tips (REQ-6.4.2). Short-form community posts with reactions.
Read surfaces are public (REQ-6.1.11); posting/reacting require login and go
through the same guidelines + rate-limit + moderation pipeline as the forum."""
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .community import (
    accept_guidelines,
    award_badge,
    award_points,
    guidelines_accepted,
    interact_required,
    moderation_ok,
    notify,
    rate_limit_ok,
)
from .models import Tip, TipReaction

TIP_MAX = 2000
TIP_REACTION_KINDS = {k for k, _ in TipReaction.KINDS}
TIPSTER_BADGE_AT = 10


def tips_list(request):
    """Public list of tips, newest first; a 'best this week' rail (REQ-6.4.2)."""
    from datetime import timedelta

    from django.db.models import Count
    from django.utils import timezone
    tips = Tip.objects.filter(is_hidden=False).select_related("author__profile")[:60]
    week_ago = timezone.now() - timedelta(days=7)
    best = (
        Tip.objects.filter(is_hidden=False, created_at__gte=week_ago)
        .annotate(n=Count("reactions")).filter(n__gt=0)
        .select_related("author__profile").order_by("-n")[:3]
    )
    return render(request, "app/community/tips_list.html", {
        "tips": tips, "best": best, "tip_kinds": TipReaction.KINDS,
    })


def tip_detail(request, tip_id):
    tip = get_object_or_404(Tip.objects.select_related("author__profile"), pk=tip_id)
    if tip.is_hidden:
        from django.http import Http404
        raise Http404
    return render(request, "app/community/tip_detail.html", {"tip": tip})


@interact_required
def tip_create(request):
    """REQ-6.4.2: post a tip (moderated, rate-limited). Badge at 10 tips."""
    if request.method != "POST":
        return redirect("tips_list")
    body = (request.POST.get("body") or "").strip()[:TIP_MAX]
    if not body:
        messages.error(request, "כתבו טיפ לפני השליחה.")
        return redirect("tips_list")
    if not guidelines_accepted(request.user) and not request.POST.get("accept_guidelines"):
        messages.error(request, "כדי לפרסם, סמנו שקראתם את כללי הקהילה")
        return redirect("tips_list")
    if request.POST.get("accept_guidelines"):
        accept_guidelines(request.user)
    if not rate_limit_ok(request.user):
        messages.error(request, "הגעת למגבלת הפרסומים לשעה. נסו שוב מאוחר יותר.")
        return redirect("tips_list")
    if not moderation_ok(body, user=request.user):
        messages.error(request, "הטיפ סומן על ידי מסנן התוכן. נסחו מחדש.")
        return redirect("tips_list")
    tags = [t.strip() for t in (request.POST.get("tags") or "").split(",") if t.strip()][:8]
    Tip.objects.create(
        author=request.user, body=body, tags=tags,
        link_url=(request.POST.get("link_url") or "").strip()[:500],
    )
    if request.user.tips.count() >= TIPSTER_BADGE_AT:
        award_badge(request.user, "tipster")
    from .community import ensure_public
    ensure_public(request.user)
    from .analytics import flash_event
    flash_event(request, "tip_posted")
    messages.success(request, "הטיפ פורסם! תודה ששיתפת 💡")
    return redirect(request.POST.get("next") or "community")


@interact_required
def tip_react(request, tip_id):
    """REQ-6.4.2: toggle an emoji reaction; awards the author +1 and notifies."""
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    tip = get_object_or_404(Tip, pk=tip_id)
    kind = request.POST.get("kind", "love")
    if kind not in TIP_REACTION_KINDS:
        return JsonResponse({"error": "bad kind"}, status=400)
    if tip.author == request.user:
        return JsonResponse({"error": "self"}, status=400)
    reaction, created = TipReaction.objects.get_or_create(
        tip=tip, user=request.user, kind=kind
    )
    if not created:
        reaction.delete()
    elif created:
        award_points(tip.author, "tip_reaction", ref=f"tip:{tip.pk}")
        notify(tip.author, verb="tip_reaction", actor=request.user,
               text=f"{request.user.profile.public_name} הגיב/ה לטיפ שלך",
               url=f"/community/tips/{tip.pk}/")
    count = tip.reactions.filter(kind=kind).count()
    return JsonResponse({"ok": True, "kind": kind, "count": count, "on": created})
