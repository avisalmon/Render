"""המסלול שלי — the member's own screen.

REQ-M.12, and REQ-M.5a is its acceptance test, in Litala's words: *every member
sees immediately where they are, what they have completed, and what their next
task is.*

Until this, the teenager the whole programme exists for was the only role
without a screen of their own. Their leader could see their progress through
both Scratch courses; they could not.

**Everything here is read through the modules SPR-M.8 built**, never computed
locally. This screen and the leader's roster answer the same question from
opposite ends, and a member told they have finished four lessons while their
leader is told three is not a cosmetic bug: it is the product lying to one of
them, and neither would know. One source is the only defence that holds.

**What is deliberately absent.** REQ-M.12 as originally written promised cards
for the next submission due, the next יום שיא, and new feedback. None of those
have models (REQ-M.19, REQ-M.27), so they are not here. An empty card that will
never fill is worse than no card, because it teaches the reader that the screen
does not know things.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .certification import eligibility
from .content import FUNNEL, REQUIRED_COURSE_SLUGS
from .models import Student
from .progress import cohort_progress, track_summary
from .views import member_profile, shell

LOGIN_URL = "/matazim/login/"

# Which funnel stage a member is standing on, given their status. The funnel is
# the programme's five public stages (§4.7) and `Student.status` is the record;
# this is the one place they are joined, so the mapping cannot drift into two.
STAGE_FOR_STATUS = {
    Student.APPLIED: "apply",
    Student.IN_TRAINING: "learn",
    Student.PROJECT_SUBMITTED: "create",
    Student.CERTIFIED: "teach",
    Student.ALUMNUS: "impact",
}


def _current_stage(student, profile):
    """Where they are standing now.

    Somebody with no `Student` row has not joined anyone yet, which is a normal
    state (REQ-M.65) and is still a position on the path: they are at מתמיינים,
    either taking the entrance test or looking for a leader.
    """
    if student is None:
        return "apply"
    return STAGE_FOR_STATUS.get(student.status, "apply")


def _next_step(profile, student, state, per_course):
    """The one sentence a member actually acts on (REQ-M.5a).

    Ordered the way the programme is ordered, so the answer is always the
    earliest thing still open rather than a list of everything outstanding. A
    teenager given five things to do does none of them.
    """
    if not (profile and profile.has_passed_entrance_test()):
        return {
            "text": "לעבור את מבחן הכניסה",
            "where": "matazim:entrance_test",
            "why": "זה הצעד הראשון, והוא בודק התמדה ולא ידע מוקדם.",
        }

    if student is None or (student.leader is None and student.pending_leader is None):
        return {
            "text": "להצטרף למוביל/ה",
            "where": "matazim:apply",
            "why": "מוביל/ה מלווה אתכם בתוכנית ומאשר/ת את ההסמכה בסוף.",
        }

    if student.leader is None and student.pending_leader is not None:
        return {
            "text": "לחכות לאישור",
            "where": None,
            "why": f"ביקשתם להצטרף ל{_leader_name(student.pending_leader)}. "
            "ברגע שיאשרו, תוכלו להתחיל.",
        }

    # The earliest unfinished required course, named the way a reader would.
    for slug in REQUIRED_COURSE_SLUGS:
        if slug in state.missing_courses:
            row = per_course.get(slug) or {}
            title = row.get("title", slug)
            done, total = row.get("done", 0), row.get("total", 0)
            # "Continue" to somebody who has not started is the kind of small
            # wrongness that makes a screen feel like it is not looking at you.
            started = done > 0
            return {
                "text": f"{'להמשיך' if started else 'להתחיל'} ב{title}",
                # REQ-M.13 — somewhere to actually go. This was None, so the
                # card told a member what to do next and rendered no button:
                # the screen the spec calls the product was a dead end.
                "where": "matazim:learn_course",
                "where_args": [slug],
                "course": slug,
                "why": (
                    f"{done} מתוך {total} שיעורים. בסוף הקורס מקבלים תעודה."
                    if started
                    else f"{total} שיעורים, ובסוף מקבלים תעודה."
                ),
            }

    if student.status != Student.CERTIFIED:
        return {
            "text": "אתם מוכנים",
            "where": None,
            "why": "השלמתם את כל מה שתלוי בכם. ההחלטה עכשיו אצל המוביל/ה שלכם.",
        }

    return {
        "text": "אתם מט״צ מוסמך",
        "where": None,
        "why": "מכאן מדריכים אחרים. מזל טוב.",
    }


def _leader_name(leader):
    if leader is None:
        return ""
    profile = getattr(leader.user, "profile", None)
    return getattr(profile, "display_name", "") or leader.user.email


@login_required(login_url=LOGIN_URL)
def my_path(request):
    """REQ-M.12 — where I am, what I have done, what is next.

    Built from `request.user` and nothing in the URL, so there is no identifier
    here to tamper with and no way to ask about somebody else (REQ-M.22).
    """
    profile = member_profile(request.user)
    student = (
        Student.objects.filter(user=request.user)
        .select_related("leader__user", "leader__user__profile", "pending_leader__user")
        .order_by("-cohort_year")
        .first()
    )

    per_course = (
        cohort_progress([student], REQUIRED_COURSE_SLUGS).get(request.user.id, {})
        if student
        else {}
    )
    if not per_course:
        # No `Student` row yet, but their learning is still theirs and still
        # counts. The reader is keyed by user, so a lightweight stand-in is
        # enough to ask about somebody who has not joined anyone.
        per_course = cohort_progress([_LooseMember(request.user.id)], REQUIRED_COURSE_SLUGS).get(
            request.user.id, {}
        )

    state = eligibility(student) if student else _eligibility_without_a_student(request.user)

    current = _current_stage(student, profile)
    stages = [{**stage, "is_current": stage["key"] == current} for stage in FUNNEL]

    return render(
        request,
        "matazim/my_path.html",
        shell(
            request,
            "path",
            student=student,
            stages=stages,
            summary=track_summary(per_course),
            courses=[
                {
                    "slug": slug,
                    "progress": per_course.get(slug),
                    "certified": slug in state.certified_courses,
                }
                for slug in REQUIRED_COURSE_SLUGS
            ],
            eligibility=state,
            next_step=_next_step(profile, student, state, per_course),
            leader=student.leader if student else None,
            leader_name=_leader_name(student.leader) if student else "",
            pending_name=_leader_name(student.pending_leader) if student else "",
        ),
    )


class _LooseMember:
    """A stand-in for somebody who has no `Student` row yet.

    `cohort_progress` asks each row only for `user_id`, so this is enough, and
    it keeps the reader with one signature instead of two. Their learning exists
    whether or not they have joined a programme.
    """

    def __init__(self, user_id):
        self.user_id = user_id


def _eligibility_without_a_student(user):
    """The same three conditions for somebody who has not joined anyone.

    They can be most of the way to being certifiable before they have a leader,
    and the screen should say so rather than showing nothing until they join.
    """
    from app.models import CourseCertificate

    from .certification import Eligibility

    profile = member_profile(user)
    held = set(
        CourseCertificate.objects.filter(
            user=user, course__slug__in=REQUIRED_COURSE_SLUGS
        ).values_list("course__slug", flat=True)
    )
    return Eligibility(
        entrance_test_passed=bool(profile and profile.has_passed_entrance_test()),
        certified_courses=[s for s in REQUIRED_COURSE_SLUGS if s in held],
        missing_courses=[s for s in REQUIRED_COURSE_SLUGS if s not in held],
    )
