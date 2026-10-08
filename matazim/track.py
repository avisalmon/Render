"""המסלול שלי as Litala drew it (SPR-M.56, screen 3 of her brief).

Her sentence, which REQ-M.5a already quotes as the acceptance test: *every
member sees immediately where they are, what they have completed, and what
their next task is*. Her screen answers it with three things, top to bottom:
a row of status cards, a horizontal path of named milestones each carrying a
status word and a date, and three panels (the course they are in now with its
lessons, their submissions, what is coming up).

Everything here is read from the tables that already exist and nothing is
invented to fill a slot. Her drawing has fourteen milestones with dates on all
of them because it is a drawing; a real member on day one has one. So a
milestone appears only when the programme actually has that step, and a date
appears only when something happened. The number of nodes is the number of
true things.

**Status is always a word plus a colour, never a colour alone** (her design
system, and §4.10 for the screen reader). Four states, matching her legend
minus the one we have no data for: `done`, `doing`, `fix`, `todo`.

Nothing here decides anything. `certification.eligibility` is still the only
place that says whether somebody is ready, and this reads its answer.
"""

from django.utils import timezone

from .content import REQUIRED_COURSE_SLUGS

DONE, DOING, FIX, TODO = "done", "doing", "fix", "todo"

STATUS_WORD = {
    DONE: "הושלם",
    DOING: "בתהליך",
    FIX: "דורש תיקון",
    TODO: "טרם התחיל",
}

#: The legend under the path, in the order her drawing has it.
LEGEND = [(DONE, STATUS_WORD[DONE]), (DOING, STATUS_WORD[DOING]),
          (FIX, STATUS_WORD[FIX]), (TODO, STATUS_WORD[TODO])]


def _node(key, title, status, when=None, *, pct=None, where=None, where_args=None):
    return {
        "key": key,
        "title": title,
        "status": status,
        "word": STATUS_WORD[status],
        "when": when,
        "pct": pct,
        "where": where,
        "where_args": where_args or [],
        "is_current": False,
    }


def milestones(user, profile, student, state, per_course):
    """The path, as a list of nodes in programme order.

    One node per real step. The required הדרכות each contribute two, the
    learning and the certificate, because REQ-M.76 counts the certificate and
    a member half way through a course has done something a plain "course"
    node could not show.
    """
    from app.models import CourseCertificate

    from .models import EntranceAttempt, Submission, TeachingSession

    nodes = []

    # 1. The entrance test.
    passed_at = getattr(profile, "entrance_test_passed_at", None) if profile else None
    if passed_at:
        nodes.append(_node("test", "מבחן הכניסה", DONE, passed_at))
    else:
        tried = bool(profile) and EntranceAttempt.objects.filter(member=profile).exists()
        nodes.append(_node("test", "מבחן הכניסה", FIX if tried else TODO,
                           where="matazim:entrance_test"))

    # 2. Joining a leader. Pending is a real state and reads as one.
    if student is not None and student.leader_id:
        nodes.append(_node("join", "הצטרפות למוביל/ה", DONE, student.joined_at))
    elif student is not None and student.pending_leader_id:
        nodes.append(_node("join", "הצטרפות למוביל/ה", DOING))
    else:
        nodes.append(_node("join", "הצטרפות למוביל/ה", TODO, where="matazim:apply"))

    # 3. Each required הדרכה, then its certificate.
    issued = {
        c.course.slug: c.issued_at
        for c in CourseCertificate.objects.filter(
            user=user, course__slug__in=REQUIRED_COURSE_SLUGS
        ).select_related("course")
    }
    for slug in REQUIRED_COURSE_SLUGS:
        row = per_course.get(slug) or {}
        title = row.get("title") or slug
        pct = int(row.get("pct") or 0)
        if slug in state.certified_courses or pct >= 100:
            nodes.append(_node(f"course-{slug}", title, DONE, issued.get(slug), pct=100,
                               where="matazim:learn_course", where_args=[slug]))
        elif pct:
            nodes.append(_node(f"course-{slug}", title, DOING, pct=pct,
                               where="matazim:learn_course", where_args=[slug]))
        else:
            nodes.append(_node(f"course-{slug}", title, TODO,
                               where="matazim:learn_course", where_args=[slug]))
        if slug in state.certified_courses:
            nodes.append(_node(f"cert-{slug}", f"תעודה: {title}", DONE, issued.get(slug)))
        else:
            nodes.append(_node(f"cert-{slug}", f"תעודה: {title}", TODO))

    # 4. The first piece of work handed to a leader. Only once there is a
    #    leader to hand it to; before that the node would point at a wall.
    if student is not None and student.leader_id:
        rows = Submission.objects.filter(student=student).order_by("created_at")
        approved = rows.filter(status=Submission.APPROVED).first()
        waiting = rows.filter(status=Submission.WAITING).first()
        other = rows.exclude(status__in=[Submission.APPROVED, Submission.WAITING]).first()
        if approved:
            nodes.append(_node("work", "תוצר ראשון", DONE, approved.decided_at or approved.created_at,
                               where="matazim:my_work"))
        elif waiting:
            nodes.append(_node("work", "תוצר ראשון", DOING, waiting.created_at,
                               where="matazim:my_work"))
        elif other:
            nodes.append(_node("work", "תוצר ראשון", FIX, other.decided_at or other.created_at,
                               where="matazim:my_work"))
        else:
            nodes.append(_node("work", "תוצר ראשון", TODO, where="matazim:my_work"))

    # 5. Certification: the leader's yes.
    if student is not None and student.status == "certified":
        nodes.append(_node("certified", "מט״צ מוסמך", DONE, student.certified_at,
                           where="matazim:my_certificate"))
    elif state.is_eligible:
        nodes.append(_node("certified", "מט״צ מוסמך", DOING))
    else:
        nodes.append(_node("certified", "מט״צ מוסמך", TODO))

    # 6. The thing the whole programme is for: teaching somebody younger.
    if student is not None and student.status == "certified":
        first = (TeachingSession.objects.filter(student=student, cancelled_at__isnull=True)
                 .order_by("happened_on").first())
        if first:
            nodes.append(_node("teach", "מפגש הדרכה ראשון", DONE, first.happened_on,
                               where="matazim:my_teaching"))
        else:
            nodes.append(_node("teach", "מפגש הדרכה ראשון", TODO, where="matazim:my_teaching"))

    # The current node is the first one not finished. Her drawing badges it
    # המשימה הנוכחית, and so does ours.
    for node in nodes:
        if node["status"] != DONE:
            node["is_current"] = True
            break
    return nodes


def status_cards(*, summary, next_step, student, work_waiting, work_answered,
                 next_events, unread):
    """The row across the top of her screen, built only from what is true.

    Her drawing shows five cards every time because it is a drawing. A card
    that says "no submission", "no event" and "no feedback" three times across
    is a row that teaches people to stop reading it, so a card is present when
    there is something behind it. Progress and the next task are always
    something.
    """
    cards = []

    pct = int(summary.get("pct") or 0)
    if pct >= 100:
        mood = "סיימתם את כל ההדרכות. כל הכבוד!"
    elif pct >= 60:
        mood = "אתם בדרך הנכונה, המשיכו כך"
    elif pct > 0:
        mood = "התחלתם. כל שיעור נספר"
    else:
        mood = "הכל עוד לפניכם, וזה בסדר"
    cards.append({
        "key": "progress", "tone": "purple", "title": "התקדמות כללית",
        "figure": f"{pct}%", "pct": pct, "text": mood,
    })

    cards.append({
        "key": "next", "tone": "blue", "title": "המשימה הבאה",
        "text": next_step["text"], "sub": next_step.get("why", ""),
        "where": next_step.get("where"), "where_args": next_step.get("where_args") or [],
        "button": "קדימה",
    })

    if student is not None and student.leader_id:
        if work_waiting:
            cards.append({"key": "work", "tone": "teal", "title": "הגשה",
                          "text": "תוצר ממתין למוביל/ה", "where": "matazim:my_work",
                          "button": "לעבודות שלי"})
        elif not work_answered:
            cards.append({"key": "work", "tone": "teal", "title": "הגשה",
                          "text": "אפשר להגיש תוצר למוביל/ה", "where": "matazim:my_work",
                          "button": "להגשת תוצר"})

    if next_events:
        event = next_events[0]
        cards.append({"key": "event", "tone": "amber", "title": "יום שיא קרוב",
                      "text": event.title, "sub": timezone.localtime(event.starts_at).strftime("%d.%m.%Y"),
                      "where": "matazim:calendar", "button": "פרטים נוספים"})

    if work_answered or unread:
        cards.append({"key": "feedback", "tone": "purple", "title": "משוב חדש",
                      "text": "המוביל/ה כתב/ה לכם משוב" if work_answered else "יש לכם הודעה חדשה",
                      "where": "matazim:my_work" if work_answered else "matazim:notices",
                      "button": "לצפייה במשוב" if work_answered else "לצפייה"})

    return cards


def current_course(user, per_course):
    """The הדרכה they are in now, with its lessons as a checklist.

    The earliest required course that is not finished, or the last one when
    everything is. Lessons come with a done mark and the first unfinished one
    is the current one, which is what "continue" means on the button.
    """
    from app.models import Course, Video

    chosen = None
    for slug in REQUIRED_COURSE_SLUGS:
        row = per_course.get(slug) or {}
        if int(row.get("pct") or 0) < 100:
            chosen = slug
            break
    if chosen is None and REQUIRED_COURSE_SLUGS:
        chosen = REQUIRED_COURSE_SLUGS[-1]
    if chosen is None:
        return None

    course = Course.objects.filter(slug=chosen).first()
    if course is None:
        return None

    watched = set(
        Video.objects.filter(course=course, user_progress__user=user).values_list("id", flat=True)
    )
    lessons = [
        {"order": v.lesson_order, "title": v.title, "done": v.pk in watched, "is_current": False}
        for v in Video.objects.filter(course=course).order_by("lesson_order")
    ]
    resume = next((row for row in lessons if not row["done"]), None)
    if resume:
        resume["is_current"] = True

    # Her panel shows five. A nineteen-lesson course as a list of nineteen is
    # the course page, not a glance; keep a window around the current one.
    window = lessons
    if len(lessons) > 6:
        at = lessons.index(resume) if resume else len(lessons) - 1
        start = max(0, min(at - 2, len(lessons) - 6))
        window = lessons[start:start + 6]

    row = per_course.get(chosen) or {}
    return {
        "slug": chosen,
        "title": row.get("title") or course.title,
        "pct": int(row.get("pct") or 0),
        "done": int(row.get("done") or 0),
        "total": int(row.get("total") or 0),
        "lessons": window,
        "hidden": len(lessons) - len(window),
        "resume_order": resume["order"] if resume else None,
    }


def recent_work(student, limit=3):
    """The last few submissions, each with the word its status has."""
    if student is None or not student.leader_id:
        return []
    from .models import Submission

    out = []
    for row in Submission.objects.filter(student=student).order_by("-created_at")[:limit]:
        if row.status == Submission.APPROVED:
            status, word = DONE, "אושר"
        elif row.status == Submission.WAITING:
            status, word = DOING, "ממתין למוביל/ה"
        else:
            status, word = FIX, row.get_status_display()
        out.append({"title": row.title, "status": status, "word": word,
                    "when": row.decided_at or row.created_at})
    return out
