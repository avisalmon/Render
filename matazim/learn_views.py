"""The required track, rendered inside our own walls.

REQ-M.13 and REQ-M.14. This closes a dead end: המסלול שלי told a member
"להתחיל בסקראץ׳ 1" and gave them nowhere to click, because RULE-1 forbids
sending them to babook's player and nothing here rendered a lesson yet.

**Generalised from `entrance_views`, not copied.** That module already renders
one babook course in our chrome, for the entrance test, hardcoded to a single
slug. The shape was right and only the scope was wrong.

**Watching counts, and that is the half that was missing.** The SPR-M.3
renderer had an iframe and no heartbeat, so a member could have watched every
lesson inside our walls and stayed at 0/19 with their leader's roster agreeing,
because both read the same empty table. The page now posts to babook's own
`/api/video-progress/`, which is what REQ-M.14 means by "through the same code
path". That is not an outbound link: RULE-1 governs navigation, and a member
never leaves `/matazim/`.

**Deliberately narrow.** One line would let this render any course in the
catalogue, which would quietly turn מט״צים into a second front end for all of
babook, with no owner and no design. It renders the courses the programme
requires and 404s the rest.

Nothing here writes content. babook's courses are live and belong to their own
learners (REQ-M.47); we render them read-only and record progress the way their
own pages do.
"""

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from app.bunny import get_embed_url
from app.models import Course, Enrollment, Video

from .content import REQUIRED_COURSE_SLUGS
from .progress import cohort_progress
from .views import shell

LOGIN_URL = "/matazim/login/"


def _track_course(slug):
    """A course the programme requires, or nothing at all.

    The membership test is the point of the function. Reaching for
    `Course.objects.get(slug=...)` here is the one-line change that would make
    this a general reader, and it would not look like a mistake in review.
    """
    if slug not in REQUIRED_COURSE_SLUGS:
        raise Http404("not part of the מט״צים track")
    return get_object_or_404(Course, slug=slug)


class _Learner:
    """What `cohort_progress` needs, for somebody who may have no Student row.

    A member can be most of the way through the track before any leader takes
    them on (REQ-M.65), and their progress is theirs either way.
    """

    def __init__(self, user_id):
        self.user_id = user_id


def _progress_for(user, slug):
    return cohort_progress([_Learner(user.id)], [slug]).get(user.id, {}).get(slug, {})


@login_required(login_url=LOGIN_URL)
def learn_course(request, slug):
    """REQ-M.13 — one course, lesson by lesson, in our chrome.

    Somebody mid-course wants lesson seven, not a "start" button, so every
    lesson is listed with whether it is done.
    """
    course = _track_course(slug)

    watched = set(
        Video.objects.filter(course=course, user_progress__user=request.user).values_list(
            "id", flat=True
        )
    )
    lessons = [
        {"video": video, "done": video.pk in watched}
        for video in Video.objects.filter(course=course).order_by("lesson_order")
    ]

    return render(
        request,
        "matazim/learn_course.html",
        shell(
            request,
            "path",
            course=course,
            lessons=lessons,
            progress=_progress_for(request.user, slug),
            # The first lesson they have not finished: what "continue" means.
            resume=next((row["video"] for row in lessons if not row["done"]), None),
        ),
    )


@login_required(login_url=LOGIN_URL)
def learn_lesson(request, slug, order):
    """REQ-M.13, REQ-M.14 — the lesson itself, and the heartbeat that counts it."""
    course = _track_course(slug)
    lesson = Video.objects.filter(course=course, lesson_order=order).first()
    if lesson is None:
        return redirect("matazim:learn_course", slug=slug)

    # REQ-M.14, and RULE-3 as amended: enrolment is not the divergence the rule
    # guards against. You cannot watch a lesson without one, and babook's own
    # lesson view creates it with this same line in six places.
    Enrollment.objects.get_or_create(user=request.user, course=course)

    lessons = list(Video.objects.filter(course=course).order_by("lesson_order"))
    orders = [row.lesson_order for row in lessons]

    return render(
        request,
        "matazim/learn_lesson.html",
        shell(
            request,
            "path",
            course=course,
            lesson=lesson,
            lessons=lessons,
            embed_url=get_embed_url(lesson.bunny_video_id) if lesson.bunny_video_id else None,
            next_order=order + 1 if (order + 1) in orders else None,
            prev_order=order - 1 if (order - 1) in orders else None,
        ),
    )
