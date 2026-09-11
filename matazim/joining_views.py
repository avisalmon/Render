"""How anyone becomes anyone.

Before this, nothing in the app could create a `Leader` or a `Student`: the
roles existed and Django admin was the only way in.

Four people walk four different paths through here, and Avi's brief was that the
UX is the feature. So the rule every view below follows is that **no state is a
dead end and nothing is silently dropped**. Someone who taps an invite before
they have an account, or before they have passed the entrance test, has not done
anything wrong: they are simply early, and the invite has to survive being
early. Losing it quietly is how a teenager ends up in the program attached to
nobody.

Asking is not the same as being accepted. `Student.leader` is who has them,
`Student.pending_leader` is who they asked. An invite link sets `leader`
outright, because the leader handed out the link and the choice is already
theirs (REQ-M.9). The open door sets `pending_leader` and waits (REQ-M.10).
"""

import io

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .access import is_admin, leader_of
from .models import Leader, Student
from .views import member_profile, shell

LOGIN_URL = "/matazim/login/"

# An invite lives here rather than in a column. A WhatsApp link survives being
# tapped again, which is the real recovery path, and a column would need a
# migration to hold something that usually lives for twenty minutes. What makes
# it safe is that the leader's name is shown at every step, so nobody has to
# trust that it is still there.
INVITE_KEY = "mz_invite_code"


def pending_invite(request):
    """The leader whose link brought them here, if that is still true."""
    code = request.session.get(INVITE_KEY)
    if not code:
        return None
    return Leader.objects.filter(join_code=code, is_active=True).first()


def student_of(user):
    if not getattr(user, "is_authenticated", False):
        return None
    return Student.objects.filter(user=user).order_by("-cohort_year").first()


def has_passed(user):
    profile = member_profile(user)
    return bool(profile and profile.has_passed_entrance_test())


# --- Journey A: someone arrives with a link ---------------------------------


def join(request, code):
    """REQ-M.9 — the landing page an invite opens.

    Reachable logged out on purpose: the link gets pasted into WhatsApp groups
    and meets people with no account. A bare login form would tell them nothing
    about where they had landed or who had asked them.
    """
    leader = Leader.objects.filter(join_code=code, is_active=True).first()
    if leader is None:
        # A mistyped or retired link says so, rather than showing an empty
        # invitation from nobody.
        raise Http404("unknown invite")

    # Remembered from this moment, so the invite survives whatever has to happen
    # before they are eligible (REQ-M.72).
    request.session[INVITE_KEY] = code

    already = student_of(request.user)
    passed = has_passed(request.user)

    if request.method == "POST" and request.POST.get("action") == "join":
        if not request.user.is_authenticated:
            return redirect(f"{LOGIN_URL}?next={request.path}")
        if not passed:
            return redirect("matazim:entrance_test")
        if already is None:
            already = Student.objects.create(
                user=request.user, leader=leader, status=Student.IN_TRAINING
            )
        else:
            already.leader = leader
            already.pending_leader = None
            # Being taken on by a leader is the moment someone stops being a
            # candidate and starts being a learner. Nothing advanced this
            # before, so every student sat at מתמיינים forever and the roster's
            # status column answered nothing.
            already.status = Student.IN_TRAINING
            already.save(update_fields=["leader", "pending_leader", "status", "updated_at"])
        request.session.pop(INVITE_KEY, None)
        return redirect("matazim:joined")

    return render(
        request,
        "matazim/join.html",
        shell(
            request,
            "join",
            leader=leader,
            schools=leader.classes.values_list("school_name", flat=True).distinct(),
            passed=passed,
            student=already,
        ),
    )


@login_required(login_url=LOGIN_URL)
def joined(request):
    """Where you land the moment you are in. A state, not a flash message."""
    return render(
        request,
        "matazim/joined.html",
        shell(request, "joined", student=student_of(request.user)),
    )


# --- Journey B: no link, so pick a leader -----------------------------------


@login_required(login_url=LOGIN_URL)
def apply(request):
    """REQ-M.16 and REQ-M.10 — the row that finally makes someone a student.

    Three questions and no more. The application is not what assesses anyone,
    the entrance test is, so every extra field here is only a teenager who does
    not finish the form.
    """
    if not has_passed(request.user):
        return redirect("matazim:entrance_test")

    existing = student_of(request.user)
    if existing and (existing.leader or existing.pending_leader):
        return redirect("matazim:profile")

    error = ""
    if request.method == "POST":
        leader = Leader.objects.filter(pk=request.POST.get("leader"), is_active=True).first()
        grade = (request.POST.get("grade") or "").strip()
        motivation = (request.POST.get("motivation") or "").strip()

        if leader is None:
            error = "בחרו מוביל מהרשימה."
        elif not grade or not motivation:
            error = "צריך למלא את הכיתה ואת מה שמושך אתכם לתוכנית."
        else:
            student = existing or Student(user=request.user)
            # Asking, not being accepted. The leader says yes (REQ-M.10).
            student.pending_leader = leader
            student.status = Student.APPLIED
            student.save()
            return redirect("matazim:joined")

    return render(
        request,
        "matazim/apply.html",
        shell(
            request,
            "apply",
            leaders=Leader.objects.filter(is_active=True).prefetch_related("classes"),
            error=error,
            posted=request.POST,
        ),
    )


# --- Journey D: the leader --------------------------------------------------


def leader_entrance(request):
    """REQ-M.66 — the same door, doing the right thing for the right person.

    An actual leader goes to their page. Everyone else gets told plainly that
    leader access is granted by the program team, instead of being handed the
    student registration form, which is what this door used to do.
    """
    if leader_of(request.user):
        return redirect("matazim:leader_home")
    return render(request, "matazim/leader_entrance.html", shell(request, "leader"))


@login_required(login_url=LOGIN_URL)
def leader_home(request):
    """REQ-M.73 — a leader has somewhere to stand.

    Their link to hand out, and the people waiting on them. The roster proper is
    a later sprint; without this the open door has no exit, because nobody can
    accept anyone.
    """
    leader = leader_of(request.user)
    if leader is None:
        raise PermissionDenied

    return render(
        request,
        "matazim/leader_home.html",
        shell(
            request,
            "leader",
            leader=leader,
            join_url=request.build_absolute_uri(f"/matazim/join/{leader.join_code}/"),
            waiting=Student.objects.filter(pending_leader=leader).select_related(
                "user", "user__profile"
            ),
            mine=Student.objects.filter(leader=leader).select_related("user", "user__profile"),
        ),
    )


@require_POST
@login_required(login_url=LOGIN_URL)
def leader_confirm(request, student_id):
    """Say yes, or say no. Scoped to people who actually asked *you*."""
    leader = leader_of(request.user)
    if leader is None:
        raise PermissionDenied

    # The scoping from SPR-M.6, enforced on a write this time: the queryset
    # cannot reach someone who asked a different leader.
    student = Student.objects.filter(pk=student_id, pending_leader=leader).first()
    if student is None:
        raise Http404("not waiting on you")

    if request.POST.get("action") == "confirm":
        student.leader = leader
        student.pending_leader = None
        # Same moment, the other way in. מתמיינים is the selection stage, and
        # this person has just been accepted out of it.
        student.status = Student.IN_TRAINING
        student.save(update_fields=["leader", "pending_leader", "status", "updated_at"])
    else:
        student.pending_leader = None
        student.save(update_fields=["pending_leader", "updated_at"])

    return redirect("matazim:leader_home")


@login_required(login_url=LOGIN_URL)
def leader_qr(request, leader_id):
    """The invite as an image, because it gets printed and stuck on a wall.

    REQ-M.79, spec §4.10 finding P1. This had no authentication and no
    authorization at all, and `leader_id` is a sequential integer, so the
    endpoint could be walked to harvest every leader's join code.

    That is worse than it sounds. A join code is not a convenience, it is a
    bearer credential: REQ-M.9 attaches whoever holds it to that leader **with
    no confirmation**, deliberately, because the leader handed the link out. An
    open endpoint here was therefore an unauthenticated write to somebody else's
    roster, not merely a leak.
    """
    import qrcode

    leader = get_object_or_404(Leader, pk=leader_id)

    mine = leader_of(request.user)
    if not is_admin(request.user) and (mine is None or mine.pk != leader.pk):
        raise PermissionDenied
    url = request.build_absolute_uri(f"/matazim/join/{leader.join_code}/")
    image = qrcode.make(url, box_size=8, border=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


# --- Journey C: the admin ---------------------------------------------------


@login_required(login_url=LOGIN_URL)
def staff_leaders(request):
    """REQ-M.25 — assigning a leader, the thing an admin exists to do."""
    if not is_admin(request.user):
        raise PermissionDenied

    error = ""
    notice = ""
    if request.method == "POST" and request.POST.get("action") == "add":
        email = (request.POST.get("email") or "").strip().lower()
        person = User.objects.filter(email__iexact=email).first()
        if person is None:
            # Never created here either, for the same reason as adminship: a
            # typo must not conjure an account with a role attached.
            error = f"לא נמצא חשבון עם האימייל {email}. אפשר למנות רק מי שכבר נרשם לאתר."
        else:
            leader, created = Leader.objects.get_or_create(
                user=person, defaults={"assigned_by": request.user}
            )
            if not created and not leader.is_active:
                leader.is_active = True
                leader.save(update_fields=["is_active"])
            notice = f"{email} מוגדר/ת כמוביל/ה."

    return render(
        request,
        "matazim/staff_leaders.html",
        shell(
            request,
            "staff",
            leaders=Leader.objects.all().select_related("user", "user__profile"),
            error=error,
            notice=notice,
        ),
    )


@login_required(login_url=LOGIN_URL)
def staff_leader(request, leader_id):
    """One leader: their link, their QR, and the two switches an admin has."""
    if not is_admin(request.user):
        raise PermissionDenied

    leader = get_object_or_404(Leader, pk=leader_id)
    notice = ""

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "rotate":
            from .models import new_join_code

            leader.join_code = new_join_code()
            leader.save(update_fields=["join_code"])
            notice = "הקישור הוחלף. הקישור הקודם כבר לא עובד."
        elif action == "deactivate":
            # REQ-M.67 — destroys nothing. They leave the join list and take no
            # new students; everyone they already have stays theirs.
            leader.is_active = False
            leader.save(update_fields=["is_active"])
            notice = "המוביל/ה הוצא/ה משימוש. המט״צים הקיימים נשארים משויכים."
        elif action == "activate":
            leader.is_active = True
            leader.save(update_fields=["is_active"])
            notice = "המוביל/ה חזר/ה לפעילות."

    return render(
        request,
        "matazim/staff_leader.html",
        shell(
            request,
            "staff",
            leader=leader,
            notice=notice,
            join_url=request.build_absolute_uri(f"/matazim/join/{leader.join_code}/"),
            students=Student.objects.filter(leader=leader).count(),
            waiting=Student.objects.filter(pending_leader=leader).count(),
        ),
    )
