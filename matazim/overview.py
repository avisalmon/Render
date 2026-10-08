"""What the programme looks like from above (SPR-M.53).

Avi, 2026-10-08, asking for נעמי and ליטל to see the programme the way he does.
His words are in the backlog under SPR-M.53 rather than here, because he used
the everyday Hebrew word for a course and `test_spr_m_41.py` reads every file in
this app to keep that word off the product (the brand term is הדרכות). In
English: on signing in they should plainly see every הדרכה there is, and every
מוביל with their progress and whether they sat the entrance test.

Both answers existed in the database and neither had a screen. The leaders list
printed a name, a school and a dot; the only screen that showed the whole
catalogue was root's, and it is a control panel rather than a report.

**Two readers, and they are readers.** Nothing here writes, and nothing here
decides who may look: every function takes the person asking and starts from
`access.visible_leaders` / `access.visible_students`, so tenancy is the same
property of the data it is everywhere else in this app. A program manager
reading this file sees her world; root sees all of it; the functions do not know
the difference.

**Fixed query count.** Both readers are built for a list page, so progress for
everybody is read in one pass through `progress.cohort_progress` rather than a
call per person. `test_the_overview_does_not_grow_with_the_programme` holds this
to it, because the version that does grow looks identical until there are forty
leaders and the page takes six seconds.
"""

from django.db.models import Count, Q

from .access import visible_leaders, visible_students
from .content import REQUIRED_COURSE_SLUGS


def _test_status(user_ids):
    """Where each person stands with the entrance test: True, False or None.

    **Three states, and the third is the one that matters.** A leader who never
    sat the test and a leader who sat it and did not pass look the same in a
    boolean, and they are nothing alike: the entrance test is for ninth-graders,
    so most leaders were simply never asked, and a red mark against them reports
    a failure that never happened.

    The question is therefore asked of `EntranceAttempt`, not of whether a
    `MemberProfile` row exists. The profile is created the moment somebody
    accepts the welcome notice, so every leader has one; the first version of
    this read the profile and printed טרם עבר/ה את המבחן against four teachers
    who had never been near it. Only an attempt means somebody actually tried.
    """
    from .models import EntranceAttempt, MemberProfile

    profiles = {
        profile.user_id: profile
        for profile in MemberProfile.objects.filter(user_id__in=user_ids)
    }
    tried = set(
        EntranceAttempt.objects.filter(member__user_id__in=user_ids)
        .values_list("member__user_id", flat=True)
    )
    out = {}
    for uid in user_ids:
        profile = profiles.get(uid)
        if profile and profile.has_passed_entrance_test():
            out[uid] = True
        elif uid in tried:
            out[uid] = False
        else:
            out[uid] = None
    return out


def _track_progress(user_ids):
    """Percent through the required track, per user id.

    The same reader the member's own screen uses (RULE-3), so a leader's row
    here and their own המסלול שלי can never disagree.
    """
    from .progress import JustAUser, cohort_progress

    if not user_ids:
        return {}
    per_user = cohort_progress([JustAUser(uid) for uid in user_ids], REQUIRED_COURSE_SLUGS)
    out = {}
    for uid in user_ids:
        courses = per_user.get(uid, {})
        done = sum(1 for slug in REQUIRED_COURSE_SLUGS
                   if courses.get(slug, {}).get("pct", 0) >= 100)
        pct = 0
        if courses:
            pct = round(
                sum(courses.get(slug, {}).get("pct", 0) for slug in REQUIRED_COURSE_SLUGS)
                / max(1, len(REQUIRED_COURSE_SLUGS))
            )
        out[uid] = {"pct": pct, "courses_done": done,
                    "courses_total": len(REQUIRED_COURSE_SLUGS)}
    return out


def _certificates_by_user(user_ids):
    """How many babook certificates each person holds, in one query.

    Counted rather than listed: the question this screen answers is "are they
    getting on with it", and a count answers it. The detail is one click away
    on the person's own page.
    """
    from app.models import CourseCertificate

    rows = (
        CourseCertificate.objects.filter(user_id__in=user_ids)
        .values("user_id")
        .annotate(n=Count("id"))
    )
    return {row["user_id"]: row["n"] for row in rows}


def leader_rows(user):
    """Every leader this person may see, with how they are getting on.

    Avi's second item, and the three facts he named are the three columns:
    who they are, how far through the training they are, and whether they sat
    the entrance test. The counts of their own מט״צים come along because a
    leader with no students and a leader with twelve are different situations
    and the list was showing them identically.

    `took_test` has three states rather than two, and `_test_status` explains
    why at length: never sat it is not the same as sat it and did not pass.
    """
    leaders = list(
        visible_leaders(user)
        .select_related("user", "user__profile", "institution")
        .prefetch_related("classes")
        .annotate(
            student_count=Count("students", distinct=True),
            certified_count=Count(
                "students", filter=Q(students__status="certified"), distinct=True
            ),
        )
        .order_by("user__profile__display_name", "pk")
    )
    user_ids = [row.user_id for row in leaders]
    took_test = _test_status(user_ids)
    progress = _track_progress(user_ids)
    certificates = _certificates_by_user(user_ids)

    out = []
    for leader in leaders:
        out.append({
            "leader": leader,
            "name": (getattr(getattr(leader.user, "profile", None), "display_name", "")
                     or leader.user.email or leader.user.username),
            "email": leader.user.email,
            # The model already knows how to answer this, and it is
            # prefetched above, so this costs nothing and cannot drift.
            "schools": leader.school_names,
            "is_active": leader.is_active,
            "is_candidate": leader.approved_at is None,
            # None means "never sat it", which is the ordinary case for an
            # adult and must not read as a failure. See `_test_status`.
            "took_test": took_test.get(leader.user_id),
            "progress": progress.get(leader.user_id, {"pct": 0, "courses_done": 0,
                                                      "courses_total": len(REQUIRED_COURSE_SLUGS)}),
            "certificates": certificates.get(leader.user_id, 0),
            "students": leader.student_count,
            "certified": leader.certified_count,
        })
    return out


def course_rows(user):
    """Every published הדרכה on babook, and what it is to this programme.

    Avi's first item. Deliberately the **whole** catalogue rather than the
    offered pool: he asked to see all the courses, and "which of these are open
    to our members" is one of the facts about each one rather than a filter
    applied before he gets to look.

    Three states a course can be in here, and they are different things:

    - **part of the track** — one of the two the certificate requires
      (REQ-M.76). Not withdrawable, by anybody.
    - **offered** — root has put it in the pool, so a leader may shelve it.
    - **withdrawn / not offered** — nobody in the programme can start it, while
      anybody half way through keeps their place (SPR-M.52's rule 2).

    The counts are of the people this reader may see, through
    `visible_students`, so a program manager's numbers are her programme's and
    root's are everybody's.
    """
    from app.models import Course, CourseCertificate, Enrollment

    from .models import OfferedCourse

    offered = {row.slug: row for row in OfferedCourse.objects.all()}
    students = visible_students(user)
    student_ids = list(students.values_list("user_id", flat=True))

    doing, done = {}, {}
    if student_ids:
        for row in (Enrollment.objects.filter(user_id__in=student_ids)
                    .values("course__slug")
                    .annotate(started=Count("id"),
                              finished=Count("id", filter=Q(completed_at__isnull=False)))):
            doing[row["course__slug"]] = row["started"]
            done[row["course__slug"]] = row["finished"]
        for row in (CourseCertificate.objects.filter(user_id__in=student_ids)
                    .values("course__slug").annotate(n=Count("id"))):
            # A certificate is the firmer fact where the two disagree.
            done[row["course__slug"]] = max(done.get(row["course__slug"], 0), row["n"])

    rows = []
    for course in Course.objects.filter(is_published=True).order_by("title"):
        row = offered.get(course.slug)
        required = course.slug in REQUIRED_COURSE_SLUGS
        rows.append({
            "course": course,
            "slug": course.slug,
            "title": course.title,
            "required": required,
            # The track's own two are open whatever the pool says (REQ-M.76).
            "offered": required or bool(row and row.is_active),
            "withdrawn": bool(row and not row.is_active) and not required,
            "note": getattr(row, "note", ""),
            "started": doing.get(course.slug, 0),
            "finished": done.get(course.slug, 0),
        })
    return rows


def programme_counts(user):
    """The handful of numbers worth putting at the top of a page.

    Read through the same scope functions as everything else, so a program
    manager is never shown another institution's totals — which is a bug this
    app has already had once, on the staff home, and fixed the same way.
    """
    from .models import Student

    leaders = visible_leaders(user)
    students = visible_students(user)
    return {
        "leaders": leaders.filter(is_active=True, approved_at__isnull=False).count(),
        "candidates": leaders.filter(approved_at__isnull=True).count(),
        "students": students.count(),
        "certified": students.filter(status=Student.CERTIFIED).count(),
        "unled": students.filter(leader__isnull=True).count(),
        "passed_test": students.filter(
            user__matazim_profile__entrance_test_passed_at__isnull=False
        ).count(),
        "leaders_total": leaders.filter(approved_at__isnull=False).count(),
    }
