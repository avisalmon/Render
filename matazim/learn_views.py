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
from django.urls import reverse
from django.views.decorators.http import require_POST

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
            # SPR-M.51 — the certificate REQ-M.76 requires, claimable here.
            certificate=_certificate_panel(request, course),
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

    # REQ-M.126 — the trainings are babook's, the experience is מט״צים's.
    #
    # Until now this page rendered a video and nothing else, while 18 of the 19
    # `scratch` lessons carry written notes and all 19 carry a summary. A מט״צ
    # was getting materially less of the same lesson than a babook learner,
    # inside the product that is supposed to be the better experience.
    #
    # Everything below is read from babook's own rows and written back through
    # babook's own endpoints (REQ-M.14, RULE-3). What belongs to מט״צים is the
    # page around it.
    from app.lesson_notes import render_lesson_notes
    from app.models import LessonQuiz, LessonReflection, UserVideoProgress

    quiz = LessonQuiz.objects.filter(video=lesson).first()
    progress = UserVideoProgress.objects.filter(user=request.user, video=lesson).first()
    reflection = LessonReflection.objects.filter(user=request.user, video=lesson).first()

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
            # The written lesson, which is most of it.
            notes_html=render_lesson_notes(lesson.notes_markdown),
            summary=(lesson.summary_he or "").strip(),
            # Rendered only when the lesson actually has one. The completion
            # rule gates on these, so a lesson that carries one and does not
            # show it is a member who cannot finish and is not told why.
            quiz=quiz,
            quiz_passed=bool(progress and progress.quiz_passed),
            reflection_prompt=(lesson.reflection_prompt or "").strip(),
            reflection=reflection,
            # Resolved here, so the template holds no babook url name (RULE-1).
            reflect_url=reverse("lesson_reflect", args=[lesson.pk]),
            # SPR-M.51 — handing in what they built, on the lesson they built
            # it in. Only for courses that ask for a project, which is both
            # Scratch courses; a lesson in a course that asks for none renders
            # nothing here rather than an empty panel.
            project=_project_panel(request, course, lesson),
        ),
    )


def _project_panel(request, course, lesson):
    """What the lesson's project panel shows, or None for courses without one.

    The count is of the whole course rather than this lesson, because that is
    what the gate counts: `project_min_count` is two projects anywhere in the
    course, not two on any one lesson.
    """
    from app.models import Course, LessonModelSubmission

    if not (course.requires_project and course.project_upload_type == Course.PROJECT_SCRATCH):
        return None

    mine = LessonModelSubmission.objects.filter(user=request.user, video=lesson).first()
    return {
        "here": mine,
        "made": LessonModelSubmission.objects.filter(
            user=request.user, video__course=course
        ).count(),
        "needed": course.project_min_count,
        # ?project=saved|badlink|notshared, set by the redirect after a post.
        "state": request.GET.get("project", ""),
    }


def _certificate_panel(request, course):
    """Whether the certificate is earned, already held, or what is missing.

    Asks `app/completion.py`, which is the same module babook's own finish
    button asks. Read-only here: this is a screen deciding what to draw, and
    the one gate with a side effect (submitting a manual review) belongs to the
    press, not to the render. So a course that wants review is reported as
    unavailable rather than silently opening a review every time somebody looks
    at the page.
    """
    from app.completion import why_not_certified
    from app.models import CourseCertificate

    held = CourseCertificate.objects.filter(user=request.user, course=course).first()
    if held:
        return {"held": held, "ready": False, "missing": None, "state": request.GET.get("cert", "")}
    if not course.issues_certificate or course.requires_review:
        return None

    not_yet = why_not_certified(request.user, course)
    return {
        "held": None,
        "ready": not_yet is None,
        "missing": not_yet.reason if not_yet else None,
        "state": request.GET.get("cert", ""),
    }


@require_POST
@login_required(login_url=LOGIN_URL)
def submit_project(request, slug, order):
    """SPR-M.51 — the thing a member built, handed in without leaving our walls.

    REQ-M.76 requires a `CourseCertificate` for both Scratch courses, and both
    are `requires_project` with `project_min_count = 2`. So a member had to
    submit two projects to be certified, and מט״צים rendered no way to submit
    one: the review on 2026-09-17 found that nobody could become a מט״צ מוסמך
    through this product at all.

    Avi, 2026-09-19: "whatever babook can do that is needed I want matazim to
    use or clone." So this parses and verifies with babook's own helpers rather
    than a second opinion about what a Scratch link is. `LessonModelSubmission`
    is the row babook's certificate gate counts, and writing a different row
    would be a submission that satisfies nobody.
    """
    from app.models import Enrollment, LessonModelSubmission, Video
    from app.views import parse_scratch_id, scratch_project_is_shared

    course = _track_course(slug)
    lesson = get_object_or_404(Video, course=course, lesson_order=order)

    def back(state):
        url = reverse("matazim:learn_lesson", kwargs={"slug": slug, "order": order})
        return redirect(f"{url}?project={state}#mzProject")

    pid = parse_scratch_id(request.POST.get("scratch_url", ""))
    if not pid:
        return back("badlink")

    existing = LessonModelSubmission.objects.filter(user=request.user, video=lesson).first()
    # Only a new or changed link is checked for sharing, which is babook's rule
    # too: re-saving the same project to fix its title must never be refused.
    if (not existing or existing.scratch_id != pid) and scratch_project_is_shared(pid) is False:
        return back("notshared")

    Enrollment.objects.get_or_create(user=request.user, course=course)
    row = existing or LessonModelSubmission(user=request.user, video=lesson)
    row.scratch_id = pid
    row.model_file = ""
    row.caption = (request.POST.get("caption", "") or "").strip()[:200]
    row.save()
    return back("saved")


@require_POST
@login_required(login_url=LOGIN_URL)
def finish_course(request, slug):
    """Ask babook whether this member has earned the certificate, and issue it.

    The gates live in `app/completion.py` and are the course's own rules; this
    asks and reports. No copy of them here, deliberately: a certificate two code
    paths disagree about is a certificate nobody can defend.
    """
    from app.completion import issue_certificate, why_not_certified

    course = _track_course(slug)
    not_yet = why_not_certified(request.user, course, request=request)
    url = reverse("matazim:learn_course", kwargs={"slug": slug})
    if not_yet:
        return redirect(f"{url}?cert={not_yet.reason}")

    issue_certificate(request.user, course)
    return redirect(f"{url}?cert=issued")
