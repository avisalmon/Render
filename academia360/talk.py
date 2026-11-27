"""The public talks back (spec 4.1 "Talk back", backlog B.5): a signed-in
visitor comments on an institution or a researcher, likes, and proposes a
correction on a fact; `/academia360/me/` shows their own proposals and
their status. Anonymous visitors read the comments and are invited to
sign in. Every write is a row in the ChangeLog, like any other.

Plain HTML forms, no JavaScript needed; the API routes do the same thing
for the agent and for anyone who prefers them.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import ChangeLog, CorrectionProposal, Institution, Like, PublicComment, Researcher

MAX_BODY = 2000
WRITES_PER_HOUR = 20

# The facts a visitor may propose a correction on, per target. Anything
# else goes under "other" with the field left empty.
FACTS = {
    "Institution": [("name_he", "השם"), ("city", "העיר"), ("founded", "שנת ההקמה"), ("website", "האתר"),
                    ("identity", "התיאור")],
    "Researcher": [("name_he", "השם"), ("title", "התואר"), ("areas", "תחומי המחקר"), ("unit", "היחידה")],
}


def _target(request):
    """The row a form points at: ?institution=<slug> or ?researcher=<slug>."""
    slug = request.POST.get("institution") or request.GET.get("institution")
    if slug:
        return get_object_or_404(Institution, slug=slug, active=True), "institution"
    slug = request.POST.get("researcher") or request.GET.get("researcher")
    if slug:
        return get_object_or_404(Researcher, slug=slug, verified=True), "researcher"
    return None, ""


def _back(request, target, kind):
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}) and nxt.startswith("/academia360/"):
        return redirect(nxt)
    if kind == "institution":
        return redirect(reverse("academia360:institution", args=[target.slug]) + "#talk")
    if kind == "researcher":
        return redirect(reverse("academia360:researcher", args=[target.slug]) + "#talk")
    return redirect("academia360:home")


def _sign_in(request):
    return redirect(f"{reverse('academia360:login')}?next={request.POST.get('next') or request.get_full_path()}")


def _plain(text):
    """Typed text, kept as text: tags stripped, length capped."""
    import nh3

    return nh3.clean(text or "", tags=set()).strip()[:MAX_BODY]


def _too_many(user):
    since = timezone.now() - timezone.timedelta(hours=1)
    n = (PublicComment.objects.filter(author=user, created_at__gte=since).count()
         + CorrectionProposal.objects.filter(proposer=user, created_at__gte=since).count())
    return n >= WRITES_PER_HOUR


def _log(user, instance, note="created"):
    ChangeLog.objects.create(model=instance._meta.label, row_id=str(instance.pk), by=user,
                             actor_kind=ChangeLog.PERSON, field="", old="", new=note)


def talk_context(request, target, kind):
    """What the page's talk-back section needs: comments, the like state,
    the facts one may correct, and the visitor's own open proposals."""
    link = {kind: target}
    comments = list(PublicComment.objects.filter(hidden=False, **link).select_related("author").order_by("created_at"))
    user = request.user if request.user.is_authenticated else None
    liked = bool(user and Like.objects.filter(user=user, **link).exists())
    model = target._meta.object_name
    mine = []
    if user:
        mine = list(CorrectionProposal.objects.filter(proposer=user, model=target._meta.label, row_id=str(target.pk))
                    .order_by("-created_at")[:5])
    return {
        "talk_kind": kind, "talk_target": target, "talk_comments": comments,
        "talk_like_count": Like.objects.filter(**link).count(), "talk_liked": liked,
        "talk_facts": [(f, label, getattr(target, f, "") or "") for f, label in FACTS.get(model, [])],
        "talk_mine": mine, "talk_next": request.get_full_path(),
    }


@require_POST
def comment(request):
    target, kind = _target(request)
    if target is None:
        return redirect("academia360:home")
    if not request.user.is_authenticated:
        return _sign_in(request)
    body = _plain(request.POST.get("body"))
    if len(body) < 2:
        messages.error(request, "התגובה ריקה.")
        return _back(request, target, kind)
    if _too_many(request.user):
        messages.error(request, "הרבה תגובות בשעה האחרונה; נסו שוב מאוחר יותר.")
        return _back(request, target, kind)
    row = PublicComment.objects.create(author=request.user, body=body, **{kind: target})
    _log(request.user, row)
    messages.success(request, "התגובה פורסמה.")
    return _back(request, target, kind)


@require_POST
def like(request):
    target, kind = _target(request)
    if target is None:
        return redirect("academia360:home")
    if not request.user.is_authenticated:
        return _sign_in(request)
    existing = Like.objects.filter(user=request.user, **{kind: target}).first()
    if existing is not None:
        _log(request.user, existing, "deleted")
        existing.delete()
    else:
        row = Like.objects.create(user=request.user, **{kind: target})
        _log(request.user, row)
    return _back(request, target, kind)


@require_POST
def correct(request):
    target, kind = _target(request)
    if target is None:
        return redirect("academia360:home")
    if not request.user.is_authenticated:
        return _sign_in(request)
    model = target._meta.object_name
    field = request.POST.get("field", "")
    allowed = {f for f, _l in FACTS.get(model, [])}
    if field not in allowed:
        field = ""
    proposed = _plain(request.POST.get("proposed_value"))
    reason = _plain(request.POST.get("reason"))
    if len(proposed) < 1:
        messages.error(request, "מה הערך הנכון? בלי זה אין מה לבדוק.")
        return _back(request, target, kind)
    if _too_many(request.user):
        messages.error(request, "הרבה הצעות בשעה האחרונה; נסו שוב מאוחר יותר.")
        return _back(request, target, kind)
    row = CorrectionProposal.objects.create(
        proposer=request.user, model=target._meta.label, row_id=str(target.pk), field=field,
        current_value=str(getattr(target, field, "") or "") if field else "", proposed_value=proposed, reason=reason)
    _log(request.user, row)
    from . import mail, notify
    from .models import Program
    notify.correction_proposed(row, Program.objects.order_by("pk").first(), actor=request.user, base=mail.base_url(request))  # E.1
    messages.success(request, "ההצעה נשלחה. היא מחכה לבדיקה; מצבה יופיע בעמוד 'שלי'.")
    return _back(request, target, kind)


def me(request):
    """One's own proposals and comments, with the proposals' status."""
    if not request.user.is_authenticated:
        return redirect(f"{reverse('academia360:login')}?next={request.get_full_path()}")
    proposals = list(CorrectionProposal.objects.filter(proposer=request.user).order_by("-created_at"))
    inst_ids = {int(p.row_id) for p in proposals if p.model == "academia360.Institution" and p.row_id.isdigit()}
    res_ids = {int(p.row_id) for p in proposals if p.model == "academia360.Researcher" and p.row_id.isdigit()}
    names = {("academia360.Institution", str(i.pk)): (i.name_he, reverse("academia360:institution", args=[i.slug]))
             for i in Institution.objects.filter(pk__in=inst_ids)}
    names.update({("academia360.Researcher", str(r.pk)): (r.name_he, reverse("academia360:researcher", args=[r.slug]))
                  for r in Researcher.objects.filter(pk__in=res_ids)})
    labels = {f: label for rows in FACTS.values() for f, label in rows}
    for p in proposals:
        p.about, p.url = names.get((p.model, p.row_id), ("", ""))
        p.field_label = labels.get(p.field, "אחר")
    comments = list(PublicComment.objects.filter(author=request.user).select_related("institution", "researcher")
                    .order_by("-created_at")[:50])
    from . import people
    from .models import RoleRequest

    return render(request, "academia360/me.html", {
        "section": "me", "proposals": proposals, "comments": comments,
        "likes": Like.objects.filter(user=request.user).count(),
        "roles_line": people.role_sentence(request.user),
        "requests": list(RoleRequest.objects.filter(user=request.user).select_related("institution").order_by("-created_at")),
    })

