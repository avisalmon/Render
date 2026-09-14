"""What a stranger may be told about this programme.

REQ-M.5e, REQ-M.5f, REQ-M.30a. Everything on the public front that is derived
from real rows rather than typed into a template lives here, in one file, for
one reason: this is the only code in מט״צים whose output is readable by anybody
on the internet, and it is about fourteen-year-olds.

Three rules, and they are the whole module.

**Every figure is counted, never typed.** REQ-M.5f exists because the prototype
had a stats band with invented numbers in it, and Avi cut it on sight. A number
on a public page is a claim about a real programme, and the only defensible way
to make one is to count.

**A zero is not shown, and neither is a band of zeros.** Not squeamishness:
"0 בתי ספר" is a true sentence that tells a visitor the programme has not
started, which is a different claim from the one a counter is for. What is shown
is what there is; when there is nothing, the band is absent and the page reads
as it did before.

**Nothing names a child, ever.** The gallery names a school and a title. Not the
maker, not their class, not their file. REQ-M.30a says the public gallery names
a school and never a student, and this is the only place that rule can be
broken, so it is the only place it is enforced.
"""

from django.db.models import Sum


def counters():
    """REQ-M.5f — the figures, counted fresh, with the empty ones dropped.

    Returns a list of `{"figure", "label"}` in the order they should read, or an
    empty list when the programme has nothing to show yet. A caller that gets an
    empty list renders no band at all rather than a row of zeros.

    Deliberately not cached. It runs on the home page a few times a day for a
    programme with tens of members, and a cached count that is wrong for an hour
    on a public page is a worse trade than five queries.
    """
    from .models import Event, Leader, Student, StudyClass, TeachingSession

    matazim = Student.objects.filter(
        status__in=[Student.IN_TRAINING, Student.PROJECT_SUBMITTED, Student.CERTIFIED]
    ).count()
    certified = Student.objects.filter(status=Student.CERTIFIED).count()
    leaders = Leader.objects.filter(is_active=True, approved_at__isnull=False).count()
    schools = (
        StudyClass.objects.exclude(school_name="")
        .values_list("school_name", flat=True)
        .distinct()
        .count()
    )
    # The number this programme is actually about: hours a teenager spent
    # teaching somebody younger. Nothing else here measures the thing the
    # charter says the programme produces.
    minutes = (
        TeachingSession.objects.filter(cancelled_at__isnull=True).aggregate(
            total=Sum("minutes")
        )["total"]
        or 0
    )
    events = Event.objects.filter(cancelled_at__isnull=True, is_public=True).count()

    # Singular and plural, because Hebrew does not let a number sit in front of
    # a plural noun and stay correct. A programme with one school reading
    # "1 בתי ספר" on its own front page is a small thing that makes a site look
    # unattended, and this is the one page read by people deciding whether to
    # trust it. Early counts here are all going to be 1.
    rows = [
        (matazim, "מט״צ בתוכנית", "מט״צים בתוכנית"),
        (schools, "בית ספר", "בתי ספר"),
        (leaders, "מוביל/ה", "מובילים ומובילות"),
        # פרקטיקום, not הדרכה. On this site הדרכה is a course (the standing
        # brand rule), and the nav item ההדרכות sat one screen away from a band
        # saying "שעות הדרכה" about something else entirely. The review of
        # 2026-09-14 caught it; the practicum screen had already been renamed
        # for the same collision and the band was missed.
        (round(minutes / 60), "שעת פרקטיקום", "שעות פרקטיקום"),
        (certified, "מוסמך/ת", "מוסמכים"),
        (events, "יום שיא", "ימי שיא"),
    ]
    return [
        {"figure": n, "label": one if n == 1 else many}
        for n, one, many in rows
        if n
    ]


def published_work(limit=6):
    """REQ-M.5e, REQ-M.30a — work the maker and the programme both agreed to show.

    Two yeses and an approval, all three read off the row rather than a flag
    somebody maintains, so withdrawing either consent takes the work off this
    page on the next request with nothing to remember to run.

    The shape returned is deliberately narrow: a title, a description, and a
    school. Not the maker, not their class, not a link to their file. The file
    is a minor's own work living outside `MEDIA_ROOT` behind a view that asks
    who is looking (REQ-M.122), and publishing a picture of a child's project is
    a further decision nobody has taken.
    """
    from .models import Submission

    rows = (
        Submission.objects.filter(
            status=Submission.APPROVED,
            public_consent_at__isnull=False,
            published_at__isnull=False,
        )
        .select_related("student")
        .prefetch_related("student__classes")
        .order_by("-published_at")[:limit]
    )

    out = []
    for row in rows:
        schools = sorted(
            {c.school_name for c in row.student.classes.all() if c.school_name}
        )
        out.append(
            {
                "title": row.title,
                "about": row.about,
                # One school, because a list of them starts to identify a
                # person. Blank when we do not know, and blank is fine: an
                # unattributed project is still a project.
                "school": schools[0] if len(schools) == 1 else "",
            }
        )
    return out
