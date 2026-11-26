"""SPR-M.91, REQ-M.231 - a leader brings students straight into their class.

Naomi, 2026-11-19: "אני רוצה שלכל מוביל כיתה תהיה האפשרות לצרף תלמידים לכיתה שלו
גם ללא מבחן הכניסה. תוסיף בכל עמוד של מוביל את האפשרות לשלוח לתלמיד להצטרף פעם
ראשונה כתלמיד כיתה ט' ופעם שנייה כתלמיד כיתה י'. המוביל יוכל לשלוח קישור לתלמיד
שדרכו התלמיד יוכל להתחבר ישירות לכיתה שלו (ולסטטוס שלו במידה והוא כיתה ט' או י')".

Two links per leader, each its own secret (`Leader.direct_code`,
`Leader.graduate_code`):

- **כיתה ט.** The student joins this leader at once, with no entrance test. The
  waiver is written down as a waiver (`MemberProfile.entrance_waived_at`), never
  as a pass. A parent's consent is still owed before a minor's data is shown to
  the leader (REQ-M.84): the link changes who decides, not what a child is owed.
- **כיתה י.** The graduates' form (REQ-M.216) with the leader already chosen, and
  approved the moment it is sent, because the leader sent the link. The parent's
  signature is still asked.

Like the ordinary join link (REQ-M.9), the leader handing out the link is the
decision, so nobody waits on anybody's yes.
"""

from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from . import access
from .consent import needs_guardian_consent
from .models import Graduate, Leader, Student
from .views import member_profile, shell

LOGIN_URL = "/matazim/login/"

GRADE9, GRADE10 = "9", "10"
GRADUATE_KEY = "mz_graduate_link"


def class_url(request, leader):
    return request.build_absolute_uri(f"/matazim/class-link/{leader.direct_code}/")


def graduate_url(request, leader):
    return request.build_absolute_uri(f"/matazim/graduates/link/{leader.graduate_code}/")


def _live_leader(**code):
    leader = (
        Leader.objects.filter(is_active=True, approved_at__isnull=False, **code)
        .select_related("user", "user__profile").first()
    )
    if leader is None:
        raise Http404("unknown link")
    return leader


def _name(leader):
    from .certification import _display_name

    return _display_name(leader.user)


def _not_a_student(user):
    """A leader, a candidate or the programme team: the link is for students."""
    return bool(
        user.is_superuser or access.is_program_manager(user)
        or access.leader_of(user) or access.candidate_of(user)
    )


def waive_entrance(user, leader):
    """Let this person past the entrance test, on their leader's word (REQ-M.231)."""
    profile = member_profile(user)
    if profile.entrance_test_passed_at is None and profile.entrance_waived_at is None:
        profile.entrance_waived_at = timezone.now()
        profile.entrance_waived_by = leader.user
        profile.save(update_fields=["entrance_waived_at", "entrance_waived_by", "updated_at"])
    return profile


def class_link(request, code):
    """כיתה ט: join this leader's class now, without the entrance test."""
    from .joining_views import INVITE_KEY, _attach, student_of

    leader = _live_leader(direct_code=code)
    user = request.user
    student = student_of(user)
    blocked = ""
    if user.is_authenticated:
        if _not_a_student(user):
            blocked = "staff"
        elif Graduate.objects.filter(user=user).exists():
            blocked = "graduate"

    if request.method == "POST" and request.POST.get("action") == "join":
        if not user.is_authenticated:
            return redirect(f"{LOGIN_URL}?next={request.path}")
        if not blocked:
            waive_entrance(user, leader)
            if needs_guardian_consent(member_profile(user)):
                # The ordinary link carries them on after the parent's consent:
                # they are past the test now, so the next page is this leader.
                request.session[INVITE_KEY] = leader.join_code
                return redirect("matazim:profile")
            _attach(request, leader, "הצטרפות בקישור ישיר של המוביל/ה (כיתה ט), בלי מבחן כניסה")
            request.session.pop(INVITE_KEY, None)
            return redirect("matazim:joined")

    return render(
        request,
        "matazim/direct_link.html",
        shell(
            request, "join", grade=GRADE9, leader=leader, leader_name=_name(leader),
            schools=access.leader_schools(leader), blocked=blocked,
            already=bool(student and student.leader_id == leader.pk),
        ),
    )


def graduate_link(request, code):
    """כיתה י: the graduates' form, this leader already chosen, approved on sending."""
    leader = _live_leader(graduate_code=code)
    user = request.user
    request.session[GRADUATE_KEY] = code
    graduate = access.graduate_of(user) if user.is_authenticated else None
    blocked = ""
    if user.is_authenticated:
        if _not_a_student(user):
            blocked = "staff"
        elif graduate is None and Student.objects.filter(user=user).exists():
            blocked = "student"
        elif graduate is None:
            return redirect("matazim:graduates_join")
    return render(
        request,
        "matazim/direct_link.html",
        shell(
            request, "graduates", grade=GRADE10, leader=leader, leader_name=_name(leader),
            schools=access.leader_schools(leader), blocked=blocked, graduate=graduate,
        ),
    )


def invited_graduate_leader(request):
    """The leader whose grade 10 link this visitor is carrying, if still good."""
    code = request.session.get(GRADUATE_KEY)
    if not code:
        return None
    return Leader.objects.filter(
        graduate_code=code, is_active=True, approved_at__isnull=False
    ).select_related("user", "user__profile").first()
