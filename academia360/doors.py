"""The doors in (spec 4.5 "People, and requests to join"; backlog C.1 and
C.3): a signed-in person asks for a role, and an invited person opens the
link they were mailed. Both end in `people.py`, the one place access is
given.

The invitation page is the app's own front door for someone with no account
(methodology "a lighter front door is fine"): Google, a password sign-in, or
a new password account made only from an open invitation, for the invited
address alone. There is no open signup anywhere else in the app.
"""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from . import mail, people
from .models import Institution, Invitation, Role, RoleRequest

KINDS = [(Role.LEADER, "מוביל/ת התכנית במוסד שלי"), (Role.COMMITTEE_MEMBER, "חבר/ת הוועדה")]


def _plain(text, cap):
    import nh3

    return nh3.clean(text or "", tags=set()).strip()[:cap]


def _sign_in_first(request):
    return redirect(f"{reverse('academia360:login')}?next={request.get_full_path()}")


@require_http_methods(["GET", "POST"])
def join(request):
    """Ask to be a program leader (institution, title) or a committee member."""
    if not request.user.is_authenticated:
        return _sign_in_first(request)
    institutions = list(Institution.objects.filter(active=True).order_by("name_he"))
    form = {"kind": request.POST.get("kind") or request.GET.get("kind") or "",
            "institution": request.POST.get("institution") or request.GET.get("institution") or "",
            "title": request.POST.get("title", ""), "message": request.POST.get("message", "")}
    if request.method == "POST":
        institution = next((i for i in institutions if i.slug == form["institution"]), None)
        done = people.ask_to_join(request.user, form["kind"], institution=institution,
                                  title=_plain(form["title"], 160), message=_plain(form["message"], 2000),
                                  base=mail.base_url(request))
        if done.ok:
            note = "" if done.mailed else " (ההודעה במייל למנהל לא יצאה; הבקשה בכל זאת בתור.)"
            messages.success(request, done.what + note)
            return redirect("academia360:me")
        messages.error(request, done.what)
    mine = list(RoleRequest.objects.filter(user=request.user).order_by("-created_at"))
    return render(request, "academia360/join.html", {
        "section": "me", "kinds": KINDS, "institutions": institutions, "form": form, "mine": mine,
        "roles_line": people.role_sentence(request.user),
    })


@require_http_methods(["GET", "POST"])
def invite(request, token):
    """The link an invited person was mailed. Signed in: the role is theirs
    (ownership first, then validity). Not signed in: the three ways in."""
    row = get_object_or_404(Invitation.objects.select_related("institution", "sent_by"), token=token)
    state = people.invitation_state(row)
    word = people.ROLE_WORDS.get(row.role_kind, row.role_kind)
    if row.institution_id and row.role_kind == Role.LEADER:
        word += f" ב{row.institution.short_name_he or row.institution.name_he}"
    context = {"section": "", "row": row, "state": state, "word": word, "errors": [],
               "here": request.get_full_path(),
               "google_url": "/accounts/google/login/?process=login&next=" + request.path,
               "login_url": f"{reverse('academia360:login')}?next={request.path}"}

    if request.user.is_authenticated:
        done = people.redeem(request.user, row, base=mail.base_url(request))
        if done.ok:
            messages.success(request, done.what + ".")
            return redirect("academia360:me")
        context["refusal"] = done.what
        return render(request, "academia360/invite.html", context, status=done.status if done.status >= 400 else 200)

    if state != "open":
        context["refusal"] = ("ההזמנה הזאת כבר נוצלה." if state == "accepted"
                              else f"ההזמנה פגה (היא תקפה {people.INVITATION_DAYS} ימים). בקשו הזמנה חדשה.")
        return render(request, "academia360/invite.html", context, status=410)

    if request.method == "POST" and request.POST.get("action") == "make":
        pw1, pw2 = request.POST.get("password", ""), request.POST.get("password2", "")
        if pw1 != pw2:
            context["errors"].append("שתי הסיסמאות שונות.")
        else:
            try:
                validate_password(pw1)
            except ValidationError as exc:
                context["errors"].extend(exc.messages)
        if not context["errors"]:
            user = people.make_account_for(row, pw1)
            if user is None:
                context["errors"].append(f"לכתובת {row.email} כבר יש חשבון באתר; היכנסו איתו.")
            else:
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                done = people.redeem(user, row, base=mail.base_url(request))
                messages.success(request, done.what + "." if done.ok else done.what)
                return redirect("academia360:me")
        return render(request, "academia360/invite.html", context, status=400)
    return render(request, "academia360/invite.html", context)
