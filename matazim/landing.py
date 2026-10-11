"""What each persona sees first (SPR-M.58).

Avi, 2026-10-11, in three parts. A first-time student lands on one button and
"it's not intuitive what I need to do"; a program manager should "understand
in the first glance that the system recognized him" and see his leaders and
how to add one; a leader "needs to own students, invite students, track them,
report up" and should be shown that, not a shared shell. And the rule over
all three: "user experience has priority over the defined screens."

So three readers, one per persona, each answering the same two questions in
the persona's own terms: *what is my situation* and *what do I do now*. They
read through the same scope functions and the same progress readers as every
other screen (RULE-3, REQ-M.88), so a number here is the number the roster or
the report shows. Nothing here decides anything.

Everything is a dict a template can print. Links are route names resolved by
`{% url %}`, so a renamed route 500s rather than quietly pointing nowhere.
"""

from .content import REQUIRED_COURSE_SLUGS

NOW, DONE, LATER, OPEN = "now", "done", "later", "open"


# ---------------------------------------------------------------- student


def student_orientation(request):
    """The four steps into the programme, each with where *this* reader is.

    Shown on דף הבית to everybody, signed in or not. Avi's point was that
    "take the test" on its own is a door with no building behind it; this is
    the building. Four states:

    - ``now``   the thing to do next, one of them at most
    - ``done``  behind them
    - ``open``  available already, though not the next thing — the הדרכות
                are open to anyone with an account before the test (REQ-M.65),
                and Avi asked that this be said rather than discovered
    - ``later`` ahead of them, named so the road is visible

    Order is the programme's order (REQ-M.36: the test gates joining, not
    learning). A visitor sees step one as עכשיו; a certified מט״צ sees four
    ticks and a fifth step, teaching, which is what the rest of their year is.
    """
    from .views import _has_leader, _student_of, member_profile

    user = request.user
    signed_in = bool(getattr(user, "is_authenticated", False))
    passed = signed_in and member_profile(user).has_passed_entrance_test()
    student = _student_of(user) if signed_in else None
    joined = signed_in and _has_leader(user)
    certified = bool(student and student.status == "certified")

    steps = [
        {
            "key": "account",
            "title": "פותחים חשבון",
            "text": "חינם, דקה אחת, וכל מה שתלמדו נשמר עליו.",
            "state": DONE if signed_in else NOW,
            "where": None if signed_in else "matazim:register",
            "button": "פתיחת חשבון",
        },
        {
            "key": "test",
            "title": "מבחן הכניסה",
            "text": "הדרכת טינקרקאד קצרה ומשימה אחת. בודק התמדה, לא ידע מוקדם. אפשר לנסות שוב.",
            "state": DONE if passed else (NOW if signed_in else LATER),
            "where": None if passed else "matazim:entrance_test",
            "button": "למבחן",
        },
        {
            "key": "join",
            "title": "מצטרפים למוביל/ה",
            "text": "מורה מבית הספר שמלווה אתכם ומאשר/ת את ההסמכה בסוף.",
            "state": DONE if joined else (NOW if passed else LATER),
            "where": None if joined else ("matazim:apply" if passed else None),
            "button": "לבחירת מוביל/ה",
        },
        {
            "key": "learn",
            "title": "לומדים ומוסמכים",
            "text": "שתי הדרכות סקראץ׳, תוצר משלכם, ואישור המוביל/ה. אפשר להתחיל ללמוד עוד לפני המבחן.",
            "state": DONE if certified else (NOW if joined else (OPEN if signed_in else LATER)),
            "where": None if certified else "matazim:courses",
            "button": "להדרכות",
        },
    ]
    if certified:
        steps.append({
            "key": "teach",
            "title": "מדריכים",
            "text": "מעבירים מפגשים לתלמידים צעירים. כל מפגש נרשם.",
            "state": NOW,
            "where": "matazim:my_teaching",
            "button": "לפרקטיקום",
        })

    # Exactly one עכשיו. The list above can produce two (joined and the learn
    # step both say NOW for somebody mid-programme), and a page that says "now"
    # twice has said it zero times.
    seen = False
    for step in steps:
        if step["state"] == NOW:
            if seen:
                step["state"] = OPEN
            seen = True
    return steps


def hero_state(request):
    """Which single call to action the hero carries, for this reader.

    The hero used to offer להצטרף לתוכנית to anybody who had passed the
    test, including somebody who joined a leader weeks ago and was visiting
    דף הבית from the menu. A front door that asks a member to join is a
    front door that has not noticed who walked in.
    """
    from .views import _has_leader, _is_member, _student_of, member_profile

    user = request.user
    if not getattr(user, "is_authenticated", False):
        return {"kind": "test"}
    if not _is_member(user):
        # A leader or a program manager reading the public page: send them to
        # their own front door rather than to a pupil's.
        from .access import is_program_manager, leader_of

        if is_program_manager(user):
            return {"kind": "staff"}
        if leader_of(user):
            return {"kind": "leader"}
        return {"kind": "test"}
    if not member_profile(user).has_passed_entrance_test():
        return {"kind": "test", "learning_open": True}
    if not _has_leader(user):
        return {"kind": "join"}
    student = _student_of(user)
    return {"kind": "path", "certified": bool(student and student.status == "certified")}


# ----------------------------------------------------------------- leader


def leader_dashboard(leader):
    """What a leader sees first: their group, where each is, and the numbers
    the program manager sees about them.

    "Report up" in Avi's words. There is no form for it, because there was
    never anything to file: the program manager's screens read the same rows.
    So the honest version of reporting up is showing the leader the same
    figures their manager will see, on the page they open every day.
    """
    from .certification import eligibility_for_many
    from .models import Student
    from .progress import cohort_progress, track_summary

    mine = list(
        Student.objects.filter(leader=leader)
        .select_related("user", "user__profile")
        .order_by("user__profile__display_name", "pk")
    )
    progress = cohort_progress(mine, REQUIRED_COURSE_SLUGS)
    states = eligibility_for_many(mine)

    rows = []
    for student in mine:
        summary = track_summary(progress.get(student.user_id, {}))
        state = states.get(student.user_id)
        if student.status == "certified":
            status, word = "done", "מט״צ מוסמך"
        elif state and state.is_eligible:
            status, word = "fix", "מוכן להסמכה"
        elif summary["pct"]:
            status, word = "doing", f"{summary['pct']}% במסלול"
        else:
            status, word = "todo", "טרם התחיל/ה"
        rows.append({
            "student": student,
            "name": (getattr(getattr(student.user, "profile", None), "display_name", "")
                     or student.user.email),
            "pct": summary["pct"],
            "status": status,
            "word": word,
            "ready": bool(state and state.is_eligible and student.status != "certified"),
        })

    certified = sum(1 for r in rows if r["status"] == "done")
    ready = sum(1 for r in rows if r["ready"])
    return {
        "rows": rows,
        "students": len(rows),
        "certified": certified,
        "ready": ready,
        "learning": len(rows) - certified,
        "waiting": Student.objects.filter(pending_leader=leader).count(),
        # Rows that need a decision come first, and among the rest the ones
        # closest to the end: what a leader opens the page to find out.
        "attention": [r for r in rows if r["ready"]],
    }


# ---------------------------------------------------------- program manager


def pm_dashboard(user):
    """What a program manager sees first: their leaders, each at a glance.

    Avi: "who are the leaders that he owns, the main status of each one, like
    how many students, like pass rate, in a high level view, and a clear way
    to invite a new leader." The rows come from `overview.leader_rows`, the
    same reader the full report uses, trimmed to the four numbers that fit on
    one line. Pass rate is certified over students, and it is blank rather
    than 0% for a leader with nobody yet, because 0% is a claim about a
    person's work and "no students yet" is not.
    """
    from .access import institution_of
    from .overview import leader_rows, programme_counts

    rows = []
    candidates = []
    for row in leader_rows(user):
        if row["is_candidate"]:
            candidates.append(row)
            continue
        students = row["students"]
        certified = row["certified"]
        rows.append({
            **row,
            "rate": int(certified / students * 100) if students else None,
        })

    institution = institution_of(user)
    return {
        "rows": rows,
        "candidates": candidates,
        "counts": programme_counts(user),
        "institution": getattr(institution, "name", ""),
    }
