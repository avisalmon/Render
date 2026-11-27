"""The admin's room (spec 4.5; backlog C.4, C.5), under /academia360/manage/
(Django's own /admin/ is something else). Admin only: committee members and
leaders get the plain "no access" page.

Every act posts to one view, `act`, which calls the one function in
`people.py` for it and reports what that function said, including whether
the mail left (methodology 53). The screens are drawn in the committee
room's restraint (spec 5.3): greys, dense rows, flat tables, no arcs.
"""

from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import mail, people
from .access import admin_only
from .models import (
    AgentRun,
    AiUsage,
    ChangeLog,
    CommitteeAttribute,
    CorrectionProposal,
    Institution,
    Invitation,
    LeaderOf,
    Like,
    Participation,
    PublicComment,
    Role,
    RoleRequest,
    Submission,
    SubmittedFile,
)

User = get_user_model()


def _people_rows():
    """Everyone with an active role, grouped the way the admin thinks:
    admins, committee members (with chair and reviewed institutions),
    leaders by institution."""
    roles = Role.objects.filter(active=True).select_related("user").order_by("user__first_name", "user__email")
    by_user = OrderedDict()
    for r in roles:
        by_user.setdefault(r.user, set()).add(r.kind)
    for su in User.objects.filter(is_superuser=True, is_active=True):
        by_user.setdefault(su, set()).add(Role.ADMIN)
    attrs = CommitteeAttribute.objects.select_related("institution").order_by("institution__name_he")
    chairs = {a.user_id for a in attrs if a.kind == CommitteeAttribute.CHAIR}
    reviews = {}
    for a in attrs:
        if a.kind == CommitteeAttribute.REVIEWER and a.institution_id:
            reviews.setdefault(a.user_id, []).append(a.institution)
    admins, committee = [], []
    for user, kinds in by_user.items():
        if Role.ADMIN in kinds:
            admins.append(user)
        if Role.COMMITTEE_MEMBER in kinds:
            committee.append({"user": user, "chair": user.pk in chairs, "reviews": reviews.get(user.pk, [])})
    leads = LeaderOf.objects.filter(active=True, user__a360_roles__kind=Role.LEADER, user__a360_roles__active=True) \
        .select_related("user", "institution").order_by("institution__name_he", "user__first_name").distinct()
    leaders = OrderedDict()
    for lead in leads:
        leaders.setdefault(lead.institution, []).append(lead)
    return admins, committee, leaders


@admin_only
def people_page(request):
    admins, committee, leaders = _people_rows()
    queue = list(RoleRequest.objects.filter(status="open").select_related("user", "institution").order_by("created_at"))
    decided = list(RoleRequest.objects.exclude(status="open").select_related("user", "institution", "decided_by")
                   .order_by("-decided_at")[:10])
    invitations = list(Invitation.objects.filter(accepted_at__isnull=True).select_related("institution").order_by("-created_at"))
    for inv in invitations:
        inv.state = people.invitation_state(inv)
    institutions = list(Institution.objects.filter(active=True).order_by("name_he"))
    return render(request, "academia360/manage/people.html", {
        "section": "manage", "admins": admins, "committee": committee, "leaders": leaders,
        "queue": queue, "decided": decided, "invitations": invitations, "institutions": institutions,
        "role_kinds": [(Role.COMMITTEE_MEMBER, "חבר/ת ועדה"), (Role.LEADER, "מוביל/ת תכנית במוסד"), (Role.ADMIN, "מנהל/ת המערכת")],
        "counts": {"people": len({u.pk for u in admins} | {c["user"].pk for c in committee}
                                 | {lead.user_id for rows in leaders.values() for lead in rows}),
                   "leaders": sum(len(v) for v in leaders.values())},
    })


def _back(request):
    nxt = request.POST.get("next", "")
    if nxt and nxt.startswith("/academia360/") and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt)
    return redirect("academia360:manage_people")


def _institution(request):
    pk = request.POST.get("institution") or ""
    return Institution.objects.filter(pk=pk).first() if pk.isdigit() else None


def _account(request):
    return people.find_account(request.POST.get("email") or request.POST.get("user") or "")


@admin_only
@require_POST
def act(request):
    """One POST for every act of the admin's room; `action` says which."""
    action = request.POST.get("action", "")
    base = mail.base_url(request)
    note = (request.POST.get("note") or "")[:300]
    done = None
    if action in ("approve", "decline"):
        row = RoleRequest.objects.filter(pk=request.POST.get("request") or 0).first()
        done = people.decide_request(request.user, row, action == "approve", note=note, base=base) if row else None
    elif action in ("grant", "revoke"):
        user = _account(request)
        kind = request.POST.get("kind", "")
        if user is None:
            messages.error(request, "אין חשבון עם הכתובת הזאת. אפשר להזמין במקום.")
            return _back(request)
        done = (people.grant_role(request.user, user, kind, institution=_institution(request),
                                  title=(request.POST.get("title") or "")[:160], base=base)
                if action == "grant" else people.revoke_role(request.user, user, kind, institution=_institution(request)))
    elif action in ("chair", "unchair", "reviewer", "unreviewer"):
        user = _account(request)
        if user is None:
            messages.error(request, "אין חשבון כזה.")
            return _back(request)
        kind = CommitteeAttribute.CHAIR if action.endswith("chair") else CommitteeAttribute.REVIEWER
        fn = people.set_attribute if action in ("chair", "reviewer") else people.clear_attribute
        done = fn(request.user, user, kind, institution=_institution(request))
    elif action == "invite":
        done = people.invite(request.user, request.POST.get("email", ""), request.POST.get("kind", ""),
                             institution=_institution(request), title=(request.POST.get("title") or "")[:160], base=base)
    elif action == "resend":
        row = Invitation.objects.filter(pk=request.POST.get("invitation") or 0, accepted_at__isnull=True).first()
        if row is not None:
            n = people.resend_invitation(row, base=base)
            done = people.Done(True, f"ההזמנה ל{row.email} נשלחה שוב." if n else f"ההזמנה ל{row.email} לא נשלחה.", mailed=n)
    elif action in ("hide", "unhide"):
        row = PublicComment.objects.filter(pk=request.POST.get("comment") or 0).first()
        if row is not None:
            before = people._snapshot(row)
            row.hidden = action == "hide"
            row.save(update_fields=["hidden"])
            people._log(request.user, row, before=before)
            done = people.Done(True, "התגובה הוסתרה." if row.hidden else "התגובה מוצגת שוב.")
    if done is None:
        messages.error(request, "לא ברור מה לעשות.")
        return _back(request)
    text = done.what
    if done.ok and done.mailed is not None and action in MAILING:
        text += f" {done.mail_word}."
    (messages.success if done.ok else messages.error)(request, text)
    return _back(request)


# The acts after which a mail is expected, so the screen says whether it left.
MAILING = {"approve", "decline", "grant", "revoke", "invite", "resend", "chair", "reviewer"}


@admin_only
def overview(request):
    """Spec 4.5 "Overview": people and roles, institutions and their leaders,
    the state of every participation, what is waiting on whom, what the
    public sent in, what the agent did lately, AI spend today. Sentences and
    rows, never tiles (spec 5.1)."""
    today = timezone.localdate()
    week_ago = timezone.now() - timedelta(days=7)
    roles = Role.objects.filter(active=True)
    admins = set(roles.filter(kind=Role.ADMIN).values_list("user_id", flat=True)) | \
        set(User.objects.filter(is_superuser=True, is_active=True).values_list("pk", flat=True))
    committee = set(roles.filter(kind=Role.COMMITTEE_MEMBER).values_list("user_id", flat=True))
    chairs = set(CommitteeAttribute.objects.filter(kind=CommitteeAttribute.CHAIR, user_id__in=committee).values_list("user_id", flat=True))
    leaders = set(roles.filter(kind=Role.LEADER).values_list("user_id", flat=True))
    led = set(LeaderOf.objects.filter(active=True, user_id__in=leaders).values_list("institution_id", flat=True))
    applied = list(Participation.objects.filter(applied=True).select_related("institution").order_by("institution__name_he"))
    without_leader = [p.institution for p in applied if p.institution_id not in led]
    by_status = OrderedDict((label, 0) for key, label in Participation.STATUS)
    for p in applied:
        by_status[dict(Participation.STATUS).get(p.status, p.status)] = by_status.get(dict(Participation.STATUS).get(p.status, p.status), 0) + 1
    unreviewed = Submission.objects.filter(status__in=("submitted", "under_review")) \
        .annotate(n=Count("reviews")).filter(n=0).select_related("participation__institution").order_by("created_at")
    open_requests = RoleRequest.objects.filter(status="open").select_related("user", "institution").order_by("created_at")
    open_corrections = list(CorrectionProposal.objects.filter(status="open").select_related("proposer").order_by("-created_at")[:8])
    inst_ids = {int(c.row_id) for c in open_corrections if c.model == "academia360.Institution" and c.row_id.isdigit()}
    names = {str(i.pk): i for i in Institution.objects.filter(pk__in=inst_ids)}
    for c in open_corrections:
        inst = names.get(c.row_id) if c.model == "academia360.Institution" else None
        c.about = inst.name_he if inst else c.model.split(".")[-1]
        c.url = reverse("academia360:institution", args=[inst.slug]) if inst else ""
    comments = list(PublicComment.objects.select_related("author", "institution", "researcher").order_by("-created_at")[:8])
    runs = list(AgentRun.objects.order_by("-started_at")[:6])
    spend = AiUsage.objects.filter(date=today).aggregate(c=Sum("cost_usd"), n=Sum("calls"))
    return render(request, "academia360/manage/overview.html", {
        "section": "manage",
        "n": {"people": len(admins | committee | leaders), "admins": len(admins), "committee": len(committee),
              "chairs": len(chairs), "leaders": len(leaders), "led": len(led),
              "institutions": Institution.objects.filter(active=True).count(), "applied": len(applied),
              "comments_week": PublicComment.objects.filter(created_at__gte=week_ago).count(),
              "likes_week": Like.objects.filter(created_at__gte=week_ago).count(),
              "changes_week": ChangeLog.objects.filter(created_at__gte=week_ago).count(),
              "open_requests": open_requests.count(), "open_corrections": CorrectionProposal.objects.filter(status="open").count(),
              "unreviewed": unreviewed.count(),
              "files_without_text": SubmittedFile.objects.filter(extracted_at__isnull=True).count(),
              "files": SubmittedFile.objects.count(),
              "invitations_open": Invitation.objects.filter(accepted_at__isnull=True).count()},
        "without_leader": without_leader, "by_status": [(k, v) for k, v in by_status.items() if v],
        "unreviewed": list(unreviewed[:8]), "open_requests": list(open_requests[:8]),
        "open_corrections": open_corrections, "comments": comments, "runs": runs,
        "spend_usd": spend["c"] or Decimal("0"), "spend_calls": spend["n"] or 0, "today": today,
    })
