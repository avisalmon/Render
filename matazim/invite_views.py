"""How a leader gets made. Three doors, one act.

REQ-M.90 to M.93. Avi described these on 2026-09-11, and the shape they share is
the important part: **all three end at a person pressing approve.** Nothing here
makes a leader automatically, because a leader can see named minors' progress
and that is not a role to hand out on the strength of holding a URL.

**Door one, they already have an account.** The program manager searches, clicks,
approves. They get an email saying so.

**Door two, they do not.** A personal invite: one token, a link, a QR, and an
optional email. She names who it is for and may be wrong, because the label is a
label and the real name arrives when they register. Single use: it may be
forwarded, which is tolerated, but the first registration spends it.

**Door three, a whole staff room.** An open invite, reusable, nobody named.
Precisely because anyone holding it could use it, it confers nothing. Whoever
registers through it becomes a candidate and waits.

Everything here is scoped by `visible_leaders` and by the invite's own
`program_manager`, so an invitation lands its holder in the right world
(REQ-M.88).
"""

import io

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import is_program_manager, visible_leaders
from .models import Leader, LeaderInvite
from .views import shell

LOGIN_URL = "/matazim/login/"

# Where a carried invitation lives between tapping the link and having an account.
INVITE_KEY = "mz_leader_invite"


def _manager_or_403(request):
    if not is_program_manager(request.user):
        raise PermissionDenied
    return request.user


def _invite_url(request, invite):
    return request.build_absolute_uri(f"/matazim/leaders/join/{invite.token}/")


# --- Door one: they already have an account ---------------------------------


def approve_leader(user, manager, *, invite=None):
    """Make someone a leader, or approve the candidate they already are.

    One function for both doors on purpose (REQ-M.93). Approving a candidate who
    signed up through an open invite and approving someone found by search are
    the same decision, so they must not be two code paths that can drift into
    meaning different things.
    """
    leader, _ = Leader.objects.get_or_create(
        user=user, defaults={"program_manager": manager, "assigned_by": manager}
    )
    if leader.program_manager_id is None:
        leader.program_manager = manager
    leader.approved_at = leader.approved_at or timezone.now()
    leader.approved_by = leader.approved_by or manager
    leader.is_active = True
    leader.save(update_fields=["program_manager", "approved_at", "approved_by", "is_active"])
    if invite is not None and invite.kind == LeaderInvite.PERSONAL:
        invite.used_at = invite.used_at or timezone.now()
        invite.used_by = invite.used_by or user
        invite.save(update_fields=["used_at", "used_by"])
    return leader


def tell_them(request, leader):
    """REQ-M.90 — a role granted in silence is a role nobody knows they have.

    Failure here is swallowed on purpose. The person *is* a leader the moment
    the row is written, and an email provider having a bad minute must not undo
    that or leave the program manager staring at a traceback. The screen says
    whether the message went.
    """
    to = (leader.user.email or "").strip()
    if not to:
        return False

    manager = leader.approved_by or leader.program_manager
    manager_name = ""
    if manager:
        manager_name = getattr(getattr(manager, "profile", None), "display_name", "")
        manager_name = manager_name or manager.email

    where = request.build_absolute_uri("/matazim/leader/")
    body = (
        f"שלום,\n\n"
        f"קיבלת הרשאת מוביל/ה בתוכנית מט״צים"
        f"{f', על ידי {manager_name}' if manager_name else ''}.\n\n"
        f"האזור שלך נמצא כאן:\n{where}\n\n"
        f"שם תמצא/י את קישור ההצטרפות שלך לתלמידים, את הכיתות שלך, "
        f"ואת רשימת המט״צים שלך ככל שיצטרפו.\n\n"
        f"בהצלחה,\nצוות מט״צים\n"
    )
    try:
        send_mail(
            subject="קיבלת הרשאת מוביל/ה במט״צים",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
            fail_silently=True,
        )
        return True
    except Exception:  # pragma: no cover - provider trouble, never fatal
        return False


# --- The program manager's screen -------------------------------------------


@login_required(login_url=LOGIN_URL)
def leaders(request):
    """REQ-M.89, M.94 — her leaders, her candidates, and the three doors."""
    manager = _manager_or_403(request)

    error = notice = ""
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "approve":
            # Door one, and also the button on a candidate. Same act (REQ-M.93).
            email = (request.POST.get("email") or "").strip().lower()
            person = User.objects.filter(email__iexact=email).first()
            if person is None:
                error = f"לא נמצא חשבון עם האימייל {email}."
            else:
                existing = Leader.objects.filter(user=person).first()
                if existing and existing.program_manager_id not in (None, manager.pk):
                    # REQ-M.88 — somebody else's leader is not hers to approve.
                    error = "החשבון הזה כבר משויך לתוכנית אחרת."
                else:
                    leader = approve_leader(person, manager)
                    sent = tell_them(request, leader)
                    notice = f"{email} מוגדר/ת כמוביל/ה." + (
                        " נשלח אליו/ה מייל." if sent else " לא הצלחנו לשלוח מייל."
                    )

        elif action in ("invite_personal", "invite_open"):
            kind = LeaderInvite.PERSONAL if action == "invite_personal" else LeaderInvite.OPEN
            label = (request.POST.get("label") or "").strip()
            if kind == LeaderInvite.PERSONAL and not label:
                # The label is not validated against anything, but it has to
                # exist: an unnamed personal invite is indistinguishable from an
                # open one on the screen, which is how the wrong link gets sent.
                error = "צריך לכתוב עבור מי ההזמנה. אפשר לטעות בשם, זה רק תווית."
            else:
                invite = LeaderInvite.objects.create(
                    program_manager=manager,
                    kind=kind,
                    label=label,
                    email=(request.POST.get("email") or "").strip(),
                )
                notice = "ההזמנה נוצרה."
                if invite.email:
                    notice += " " + (
                        "נשלחה במייל."
                        if _send_invite(request, invite)
                        else "לא הצלחנו לשלוח מייל, אפשר להעתיק את הקישור."
                    )

        elif action == "revoke_invite":
            invite = get_object_or_404(
                LeaderInvite, pk=request.POST.get("invite"), program_manager=manager
            )
            invite.revoked_at = timezone.now()
            invite.save(update_fields=["revoked_at"])
            notice = "ההזמנה בוטלה."

    mine = visible_leaders(request.user).select_related("user", "user__profile")
    return render(
        request,
        "matazim/pm_leaders.html",
        shell(
            request,
            "staff",
            leaders=mine.filter(approved_at__isnull=False),
            candidates=mine.filter(approved_at__isnull=True),
            invites=LeaderInvite.objects.filter(
                program_manager=manager, revoked_at__isnull=True
            ).filter(Q(kind=LeaderInvite.OPEN) | Q(used_at__isnull=True)),
            error=error,
            notice=notice,
        ),
    )


def _send_invite(request, invite):
    body = (
        f"שלום,\n\n"
        f"הוזמנת להצטרף לתוכנית מט״צים כמוביל/ה.\n\n"
        f"הקישור להרשמה:\n{_invite_url(request, invite)}\n\n"
        f"אחרי ההרשמה, מנהל/ת התוכנית תאשר אותך ותקבל/י גישה לאזור המובילים.\n\n"
        f"צוות מט״צים\n"
    )
    try:
        send_mail(
            subject="הזמנה להיות מוביל/ה במט״צים",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invite.email],
            fail_silently=True,
        )
        invite.sent_at = timezone.now()
        invite.save(update_fields=["sent_at"])
        return True
    except Exception:  # pragma: no cover
        return False


@login_required(login_url=LOGIN_URL)
def invite_qr(request, invite_id):
    """The invite as an image, for printing or showing on a phone."""
    import qrcode

    _manager_or_403(request)
    invite = get_object_or_404(LeaderInvite, pk=invite_id, program_manager=request.user)
    image = qrcode.make(_invite_url(request, invite), box_size=8, border=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


@require_POST
@login_required(login_url=LOGIN_URL)
def reject_candidate(request, leader_id):
    """Say no. Removes the candidacy, never the account.

    Same principle as REQ-M.67: this product does not destroy people, it changes
    what they can reach. They keep their babook account and everything on it.
    """
    _manager_or_403(request)
    candidate = get_object_or_404(
        visible_leaders(request.user), pk=leader_id, approved_at__isnull=True
    )
    candidate.delete()
    return redirect("matazim:pm_leaders")


# --- Doors two and three: arriving through a link ---------------------------


def invite_landing(request, token):
    """Where an invitation link lands, logged in or not (REQ-M.91, M.92).

    Reachable logged out for the same reason the student invite is: the link
    arrives by WhatsApp or on a printed sheet and meets people with no account,
    and a bare login form would tell them nothing about where they were.
    """
    invite = (
        LeaderInvite.objects.filter(token=token)
        .select_related("program_manager", "program_manager__profile")
        .first()
    )

    if invite is None or invite.revoked_at is not None:
        return render(
            request, "matazim/invite_dead.html", shell(request, "leader", reason="unknown")
        )
    if invite.is_spent:
        # A personal invite that has been used says so plainly, rather than
        # offering a form that would fail. Forwarding is tolerated; a second use
        # is not.
        return render(request, "matazim/invite_dead.html", shell(request, "leader", reason="spent"))

    if request.user.is_authenticated:
        existing = Leader.objects.filter(user=request.user).first()
        if existing and existing.is_approved:
            return redirect("matazim:leader_home")
        if not existing:
            # A candidate, not a leader. Nothing is granted by holding a link
            # (REQ-M.93).
            Leader.objects.create(
                user=request.user,
                program_manager=invite.program_manager,
                is_active=True,
            )
            if invite.kind == LeaderInvite.PERSONAL:
                invite.used_at = timezone.now()
                invite.used_by = request.user
                invite.save(update_fields=["used_at", "used_by"])
        return render(
            request, "matazim/invite_waiting.html", shell(request, "leader", leader_invite=invite)
        )

    # Not signed in: keep the token so registering or signing in comes back here.
    request.session[INVITE_KEY] = token
    return render(
        request, "matazim/invite_landing.html", shell(request, "leader", leader_invite=invite)
    )


def pending_leader_invite(request):
    """The invitation a visitor is carrying, if it is still good.

    Read after sign-in and after registration, so that arriving through a link
    survives the account they had to make on the way (the same lesson as
    REQ-M.72, which is about students).
    """
    token = request.session.get(INVITE_KEY)
    if not token:
        return None
    invite = LeaderInvite.objects.filter(token=token, revoked_at__isnull=True).first()
    if invite is None or invite.is_spent:
        return None
    return invite


def claim_leader_invite(request, user):
    """Turn a carried invitation into a candidacy, once they have an account."""
    invite = pending_leader_invite(request)
    if invite is None:
        return None
    if Leader.objects.filter(user=user).exists():
        return None

    Leader.objects.create(user=user, program_manager=invite.program_manager, is_active=True)
    if invite.kind == LeaderInvite.PERSONAL:
        invite.used_at = timezone.now()
        invite.used_by = user
        invite.save(update_fields=["used_at", "used_by"])
    request.session.pop(INVITE_KEY, None)
    return invite
