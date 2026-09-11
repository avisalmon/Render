"""Reading babook's learning data in the shape a roster needs.

Every screen babook has asks the same question: *one user, many courses*. A
roster asks the inverse, *many users, one track*, and `app.views._catalog_progress`
cannot answer it without being called once per student. That is correct and
unusable: a query per teenager, on every page load, forever.

So this is a second reader, and the moment a second reader exists there are two
definitions of "done" in the codebase. That is exactly the divergence RULE-3
exists to prevent, and it is the quiet kind: nobody would see it, a leader would
simply be told a kid finished four lessons while the kid's own screen says
three, and the leader would believe the screen in front of them.

Two things hold it shut. The rule below is a deliberate mirror of babook's,
written to be read side by side with it rather than improved upon, and
`tests/test_spr_m_8.py` pins the two against each other across the whole range
from nothing-watched to all-watched. If they ever disagree, that test fails
before a leader ever sees it.

The rule, both here and there: a lesson counts as done once the learner has any
progress row for it, except that a lesson which *requires* a correct answer
needs `quiz_passed` too. A lesson requires one if it has a quiz marked
`requires_correct`, or if it carries a reflection prompt on a course that issues
certificates. Courses that issue no certificate do not gate on reflections,
because there is nothing to gate.

Nothing here writes. REQ-M.14 keeps writing honest by routing it through
babook's own code path; this file only ever looks.
"""

from app.models import Course, LessonQuiz, UserVideoProgress, Video


def cohort_progress(students, slugs):
    """Track progress for many students at once.

    `students` is any iterable of `Student` rows and `slugs` the courses that
    make up the track. Returns `{user_id: {slug: {pct, done, total}}}`, with an
    entry for every student given, including the ones who have started nothing:
    someone who has not begun is precisely who a leader is looking for, and a
    reader that silently omits them hides the only rows that need attention.

    A fixed number of queries regardless of cohort size. That is the entire
    reason this exists, and `test_the_reader_does_not_grow_with_the_cohort`
    holds it to it by measuring twelve students and then twenty-four.
    """
    user_ids = [s.user_id for s in students]
    if not user_ids or not slugs:
        return {}

    courses = {c.id: c for c in Course.objects.filter(slug__in=slugs)}
    if not courses:
        # A track naming courses that do not exist yet is a configuration
        # problem, not a crash. Every student reads as zero of zero.
        return {uid: {} for uid in user_ids}

    course_ids = list(courses)
    totals = _lesson_counts(course_ids)
    required = _required_video_ids(course_ids, courses)

    # One pass over the cohort's progress rows, bucketed by person and course.
    done = {}
    rows = UserVideoProgress.objects.filter(
        user_id__in=user_ids, video__course_id__in=course_ids
    ).values("user_id", "video_id", "video__course_id", "quiz_passed")
    for row in rows:
        if row["video_id"] in required and not row["quiz_passed"]:
            continue
        key = (row["user_id"], row["video__course_id"])
        done[key] = done.get(key, 0) + 1

    out = {}
    for uid in user_ids:
        per_course = {}
        for cid, course in courses.items():
            total = totals.get(cid, 0)
            # `min` because a lesson deleted after someone watched it would
            # otherwise put them above 100%. Same guard babook uses.
            finished = min(done.get((uid, cid), 0), total)
            per_course[course.slug] = {
                # The title travels with the numbers because every screen that
                # shows progress also has to name the course, and a slug is an
                # identifier, not something to put in front of a Hebrew reader.
                "title": course.title or course.slug,
                "done": finished,
                "total": total,
                "pct": int(finished / total * 100) if total else 0,
            }
        out[uid] = per_course
    return out


def _lesson_counts(course_ids):
    from django.db.models import Count

    return {
        r["course_id"]: r["n"]
        for r in Video.objects.filter(course_id__in=course_ids)
        .values("course_id")
        .annotate(n=Count("id"))
    }


def _required_video_ids(course_ids, courses):
    """Lessons that need a correct answer, not merely a visit.

    Mirrors babook's rule. Read this next to `app.views._catalog_progress` and
    they should say the same thing in the same order.
    """
    no_cert_ids = {cid for cid, c in courses.items() if not c.issues_certificate}
    quiz_gated = set(
        LessonQuiz.objects.filter(
            video__course_id__in=course_ids, requires_correct=True
        ).values_list("video_id", flat=True)
    )
    reflection_gated = set(
        Video.objects.filter(course_id__in=course_ids)
        .exclude(reflection_prompt="")
        .exclude(course_id__in=no_cert_ids)
        .values_list("id", flat=True)
    )
    return quiz_gated | reflection_gated


def track_summary(rows):
    """One number for a roster line, from a student's per-course rows.

    A roster column has room for a fraction, not for a course-by-course
    breakdown; the breakdown lives on the student's own page. Lessons are
    summed rather than percentages averaged, so a four-lesson course and a
    forty-lesson one do not count equally.
    """
    done = sum(r["done"] for r in rows.values())
    total = sum(r["total"] for r in rows.values())
    return {"done": done, "total": total, "pct": int(done / total * 100) if total else 0}
