"""Open classes, the screens (SPR-M.60, REQ-M.167 to REQ-M.176).

Avi, 2026-10-12: "כל משתמש יכול לפתוח כיתה ולהכניס משתמשים אחרים", and the
sentence that matters more, "הפעולה האקטיבית של ההצטרפות לכיתה תהיה על ידי
משתמש". So an owner invites and the joiner acts. Nothing below inserts a row for
anybody but `request.user`, and `open_class.join_class` is the only function
that inserts one at all.

An owner is a מורה on screen and nothing in the database. They certify nobody,
see no email and no birth year, and reach no roster: the open tables hold no key
to `Leader`, `Student` or `MatazCertificate` (REQ-M.172).

Every lookup goes through `access.visible_open_classes` and a class that is not
yours is a 404, not a 403, so the response does not tell a stranger that a
guessed id exists.
"""

import io

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import open_class as oc
from .access import open_class_for_code, visible_open_classes, visible_open_members
from .consent import consent_blocker, needs_guardian_consent
from .gate import entrance_gated
from .models import Request
from .views import member_profile, shell

LOGIN_URL = "/matazim/login/"

TERMS = [
    "אני לא מוביל/ה מוסמך/ת, ואני לא יכול/ה להסמיך אף אחד למט״צ.",
    "אני אראה רק את ההתקדמות של מי שהצטרף בעצמו, ורק בהדרכות הפתוחות.",
    "אני לא אראה כתובות מייל, שנות לידה, הגשות או משובים.",
    "אני אשתף את הקוד רק עם מי שאני רוצה שיצטרף, ואוכל להסיר חברים בכל רגע.",
]


def _own_class(request, pk):
    """A class I own, or a 404. The owner's controls never reach anybody else."""
    return get_object_or_404(
        visible_open_classes(request.user), pk=pk, owner=request.user, archived_at__isnull=True
    )


# --- Opening a class ------------------------------------------------------------


@login_required(login_url=LOGIN_URL)
@entrance_gated
def open_new(request):
    """REQ-M.167 — one field, the terms ticked, and a class exists.

    No approval, no role row, no test. A minor may own one. The only things in
    the way are the terms, which are a sentence of what an owner is and is not,
    and the cap (REQ-M.174).
    """
    error = ""
    name = ""
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            error = "צריך שם לכיתה."
        elif not request.POST.get("terms"):
            error = "כדי לפתוח כיתה צריך לאשר את הנאמר למעלה."
        elif not oc.can_open_another(request.user):
            error = f"אפשר להחזיק עד {oc.MAX_LIVE_CLASSES} כיתות פתוחות בו זמנית. אפשר לסיים אחת כדי לפתוח חדשה."
        else:
            row = oc.create_class(request.user, name)
            return redirect("matazim:open_class", pk=row.pk)
    return render(
        request,
        "matazim/open_new.html",
        shell(request, "classes", terms=TERMS, error=error, name=name),
    )


# --- The class page -------------------------------------------------------------


@login_required(login_url=LOGIN_URL)
@entrance_gated
def open_class_page(request, pk):
    """One page, two readers: the owner and a member (REQ-M.175).

    The owner sees the code, the link, the QR and the members with the lens. A
    member sees the class, who runs it, exactly what that person can see about
    them, and a way out. Members do not see each other (Q18).
    """
    cls = get_object_or_404(visible_open_classes(request.user), pk=pk)
    is_owner = cls.owner_id == request.user.id
    is_member = visible_open_members(request.user).filter(
        open_class=cls, user=request.user
    ).exists()
    notice = ""

    if request.method == "POST" and is_owner and not cls.is_archived:
        action = request.POST.get("action")
        if action == "remove":
            member_id = request.POST.get("member") or ""
            row = cls.members.filter(pk=member_id, ended_at__isnull=True).first() if member_id.isdigit() else None
            if row is not None:
                oc.end_membership(row, by=request.user)
            return redirect("matazim:open_class", pk=cls.pk)
        if action in ("close", "reopen"):
            cls.is_open = action == "reopen"
            cls.save(update_fields=["is_open"])
            return redirect("matazim:open_class", pk=cls.pk)
        if action == "replace_code":
            oc.replace_code(cls)
            return redirect("matazim:open_class", pk=cls.pk)
        if action == "archive":
            oc.archive(cls)
            return redirect("matazim:my_classes")

    ctx = {"cls": cls, "is_owner": is_owner, "is_member": is_member, "notice": notice}
    if is_owner or request.user.is_superuser:
        ctx["rows"] = oc.lens_rows(cls)
        ctx["count"] = len(ctx["rows"])
        ctx["max_members"] = oc.MAX_MEMBERS
    if is_owner:
        ctx["join_url"] = request.build_absolute_uri(f"/matazim/class/{cls.code}/")
    ctx["owner_name"] = oc.display_name(cls.owner)
    ctx["lens"] = oc.LENS
    ctx["never"] = oc.NEVER
    return render(request, "matazim/open_class.html", shell(request, "classes", **ctx))


@login_required(login_url=LOGIN_URL)
@entrance_gated
def open_class_qr(request, pk):
    """The invite as an image, for the owner and nobody else.

    Finding P1 of §4.10 was this exact endpoint on the leader side: sequential
    ids, no login, a bearer credential handed to anyone who counted. So it
    starts from the owner's own classes, and root gets no image either: the code
    is the owner's to hand out.
    """
    import qrcode

    cls = get_object_or_404(
        visible_open_classes(request.user).filter(owner=request.user),
        pk=pk,
        archived_at__isnull=True,
    )
    url = request.build_absolute_uri(f"/matazim/class/{cls.code}/")
    image = qrcode.make(url, box_size=8, border=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


@login_required(login_url=LOGIN_URL)
@require_POST
@entrance_gated
def open_leave(request, pk):
    """REQ-M.170 — a member leaves at any time and the owner stops seeing them.

    Nothing the learner did is touched: it was never copied here.
    """
    row = get_object_or_404(
        visible_open_members(request.user), open_class_id=pk, user=request.user
    )
    oc.end_membership(row, by=request.user)
    return redirect("matazim:my_classes")


@login_required(login_url=LOGIN_URL)
@require_POST
@entrance_gated
def open_report(request, pk):
    """REQ-M.174 — anyone in or looking at a class can report it.

    The lamp is the program managers' tool, so a report is written as a `Request`
    row, which is what the lamp writes, and it reaches root through the queue
    root already reads. It carries the class and the words and never the code.
    """
    cls = get_object_or_404(visible_open_classes(request.user), pk=pk)
    _file_report(request, cls)
    return redirect("matazim:open_class", pk=cls.pk)


def _file_report(request, cls):
    reason = (request.POST.get("reason") or "").strip()[:500]
    Request.objects.create(
        author=request.user,
        author_role="כיתה פתוחה",
        kind=Request.PROBLEM,
        status=Request.NEW,
        body=f"דיווח על כיתה פתוחה מספר {cls.pk}, \"{cls.name}\". {reason}".strip(),
        from_screen=request.path[:300],
    )


# --- Joining --------------------------------------------------------------------


@entrance_gated
def open_join(request, code):
    """REQ-M.168, REQ-M.170 — the page a class link or QR opens.

    Public on purpose, like a leader's: the link is pasted into a chat and meets
    people with no account. It names the owner and the class, lists exactly what
    the owner will see (the lens) before there is any button, and the button is
    the joiner's own act. A closed, archived or unknown code is one and the same
    404, which does not say which.
    """
    cls = open_class_for_code(code)
    if cls is None:
        raise Http404("unknown class")

    user = request.user
    signed_in = user.is_authenticated
    is_owner = signed_in and cls.owner_id == user.id
    already = signed_in and visible_open_members(user).filter(open_class=cls, user=user).exists()
    error = ""

    if request.method == "POST" and signed_in and not is_owner:
        if request.POST.get("action") == "report":
            _file_report(request, cls)
            return redirect("matazim:open_join", code=code)
        if request.POST.get("action") == "join":
            # REQ-M.84, behind its flag: the moment another person starts to see
            # your progress is the moment consent is owed.
            if needs_guardian_consent(member_profile(user)):
                return redirect("matazim:profile")
            try:
                _row, created = oc.join_class(cls, user)
            except oc.ClassFull:
                error = "הכיתה מלאה כרגע. אפשר לבקש מהמורה מקום."
            except oc.ClassClosed:
                raise Http404("unknown class")
            else:
                if created:
                    oc.announce_join(cls, user)
                return redirect("matazim:open_class", pk=cls.pk)

    return render(
        request,
        "matazim/open_join.html",
        shell(
            request,
            "classes",
            cls=cls,
            owner_name=oc.display_name(cls.owner),
            lens=oc.LENS,
            never=oc.NEVER,
            is_owner=is_owner,
            already=already,
            error=error,
            consent_blocker=consent_blocker(member_profile(user)) if signed_in else None,
        ),
    )


# --- The guide ------------------------------------------------------------------


def open_guide(request):
    """REQ-M.176 — a short page for the person who opens a class."""
    return render(
        request,
        "matazim/guide_open_class.html",
        shell(request, "classes", terms=TERMS, lens=oc.LENS, never=oc.NEVER, cap=oc.MAX_LIVE_CLASSES, members=oc.MAX_MEMBERS),
    )
