"""SPR-M.18 — Every transition logged.

REQ-M.21. Five places set `Student.status` and only one of them recorded who had
done it: certification, because REQ-M.78 made that transition's author part of
the record. The other four were anonymous.

Every other table here answers "what is true now". This one answers "who
decided, and when". For a system holding data about minors that is not
bookkeeping: it is the difference between answering a parent's question and
having to say we do not know.

The guard at the bottom is the load-bearing test. A single door only stays
single while something checks, which is the same lesson as RULE-3.

Traces: REQ-M.21.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm18

PASSWORD = "sprm18-pass-4471"


def make_user(email, name=""):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name or email})
    return user


def make_manager(email="naomi@example.com"):
    from matazim.models import MemberProfile

    user = make_user(email, "נעמי")
    MemberProfile.objects.update_or_create(user=user, defaults={"is_program_manager": True})
    return user


def make_leader(manager=None, email="noa@example.com"):
    from matazim.models import Leader, StudyClass

    leader = Leader.objects.create(
        user=make_user(email, "נעה מורה"),
        program_manager=manager or make_manager(),
        approved_at=timezone.now(),
    )
    StudyClass.objects.create(leader=leader, name="ט1", school_name="עתיד רמלה")
    return leader


def make_member(email="kid@example.com", name="יובל"):
    from matazim.models import MemberProfile

    user = make_user(email, name)
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now(),
            "birth_year": timezone.now().year - 14,
            "guardian_consent_at": timezone.now(),
        },
    )
    return user


def make_track():
    from app.models import Course, Video

    made = []
    for slug in ("scratch", "scratch-advanced"):
        course = Course.objects.create(slug=slug, title=slug, is_published=True)
        for n in range(3):
            Video.objects.create(course=course, title=f"{slug} {n}", lesson_order=n + 1)
        made.append(course)
    return made


def certify_courses(user):
    from app.models import CourseCertificate

    for course in make_track():
        CourseCertificate.objects.get_or_create(user=user, course=course)


# ------------------------------------------------------------- the log itself


def test_a_transition_records_who_and_from_what(db):
    """T-F-M.18.1-1: REQ-M.21. What the table is for."""
    from matazim.history import set_status
    from matazim.models import Student

    leader = make_leader()
    boss = make_manager("chief@example.com")
    student = Student.objects.create(user=make_member(), leader=leader)

    entry = set_status(student, Student.CERTIFIED, by=boss, note="בדיקה")

    assert entry.from_status == Student.APPLIED
    assert entry.to_status == Student.CERTIFIED
    assert entry.changed_by == boss
    assert entry.note == "בדיקה"
    student.refresh_from_db()
    assert student.status == Student.CERTIFIED


def test_moving_to_the_stage_they_are_already_on_writes_nothing(db):
    """T-F-M.18.1-2: REQ-M.21.

    A history meant to be read by a person must not fill with lines saying
    nothing changed, which is what every re-run of a transition would add.
    """
    from matazim.history import set_status
    from matazim.models import StatusLog, Student

    student = Student.objects.create(user=make_member(), leader=make_leader())
    set_status(student, Student.IN_TRAINING)
    before = StatusLog.objects.count()

    set_status(student, Student.IN_TRAINING)
    assert StatusLog.objects.count() == before


def test_the_first_line_of_a_history_is_written_too(db):
    """T-F-M.18.1-3: REQ-M.21.

    A `Student` begins at מתמיינים by field default, so the first transition has
    no "before" and would never be logged. Their record would start at whatever
    happened second.
    """
    from matazim.history import record_arrival
    from matazim.models import Student

    student = Student.objects.create(user=make_member(), leader=make_leader())
    entry = record_arrival(student, note="הצטרפות")

    assert entry.from_status == ""
    assert entry.to_status == Student.APPLIED


# ---------------------------------------- the transitions that actually happen


def test_certifying_is_logged_with_its_author(client, db):
    """T-F-M.18.2-1: REQ-M.21 and REQ-M.78 agreeing."""
    from matazim.models import StatusLog, Student

    leader = make_leader()
    user = make_member()
    certify_courses(user)
    student = Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)

    client.force_login(leader.user)
    client.post(reverse("matazim:certify", args=[student.pk]), {"action": "certify"})

    entry = StatusLog.objects.filter(student=student, to_status=Student.CERTIFIED).first()
    assert entry is not None, "certification left no trace in the history"
    assert entry.changed_by == leader.user


def test_revoking_is_a_transition_like_any_other(client, db):
    """T-F-M.18.2-2: REQ-M.21, which says so explicitly.

    Taking something away is exactly when somebody later asks who did it.
    """
    from matazim.models import StatusLog, Student

    leader = make_leader()
    user = make_member()
    certify_courses(user)
    student = Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)

    client.force_login(leader.user)
    client.post(reverse("matazim:certify", args=[student.pk]), {"action": "certify"})
    client.post(reverse("matazim:certify", args=[student.pk]), {"action": "revoke"})

    trail = list(StatusLog.objects.filter(student=student).order_by("at"))
    assert [e.to_status for e in trail][-2:] == [Student.CERTIFIED, Student.IN_TRAINING]
    assert trail[-1].changed_by == leader.user


def test_a_leader_confirming_someone_is_logged(client, db):
    """T-F-M.18.2-3: REQ-M.21, on one of the four that used to be anonymous."""
    from matazim.models import StatusLog, Student

    leader = make_leader()
    student = Student.objects.create(user=make_member(), pending_leader=leader)

    client.force_login(leader.user)
    client.post(reverse("matazim:leader_confirm", args=[student.pk]), {"action": "confirm"})

    entry = StatusLog.objects.filter(student=student, to_status=Student.IN_TRAINING).first()
    assert entry is not None
    assert entry.changed_by == leader.user


def test_joining_by_link_is_logged(client, db):
    """T-F-M.18.2-4: REQ-M.21. The other way in leaves a record too."""
    from matazim.models import StatusLog, Student

    leader = make_leader()
    user = make_member()
    client.force_login(user)

    client.post(reverse("matazim:join", args=[leader.join_code]), {"action": "join"})

    student = Student.objects.get(user=user)
    assert StatusLog.objects.filter(student=student).exists(), "joining left no trace"


# ------------------------------------------------------------- append only


def test_nothing_in_the_product_edits_or_deletes_a_log_line():
    """T-F-M.18.3-1: REQ-M.21 says append-only, so this checks it is.

    A history somebody can quietly edit is not a history, it is a claim.
    """
    import re
    from pathlib import Path

    bad = re.compile(r"StatusLog\.objects\.[^\n]*\.(update|delete)\(")
    for src in Path("matazim").rglob("*.py"):
        assert not bad.search(src.read_text(encoding="utf-8")), f"{src.name} rewrites history"


def test_the_single_door_stays_single():
    """T-F-M.18.3-2: the load-bearing guard, and the same shape as RULE-3.

    `set_status` writes the field and the log together, which is the only
    arrangement where they cannot disagree. That holds exactly as long as
    nothing goes round it, so this fails if any module outside `history.py`
    assigns to `.status` again.

    **The rule is about a student's stage**, which is what REQ-M.21 governs and
    what `StatusLog` records. SPR-M.25 added `Request.status`, which is a
    feedback row's state: it has no history table, its record is `decided_by`
    and `decided_at`, and routing it through `set_status` would write a
    `StatusLog` row pointing at a student who does not exist.

    Rather than exempt those modules by name, which would let a real student
    transition hide inside them later, a line may opt out only by saying which
    model it is assigning and why, in a trailing comment. The guard still fires
    on every new `.status =` in this product; silencing it costs a sentence and
    leaves that sentence in the diff for somebody to argue with.
    """
    import re
    from pathlib import Path

    assigns = re.compile(r"(?<![\w.])\w+\.status\s*=(?!=)")
    allowed = re.compile(r"#\s*not-a-student-status:\s*\S+")
    offenders = []
    for src in Path("matazim").rglob("*.py"):
        if src.name == "history.py" or "migrations" in src.parts:
            continue
        for n, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
            if assigns.search(line) and not allowed.search(line):
                offenders.append(f"{src.name}:{n} {line.strip()[:60]}")
    assert not offenders, (
        "a transition goes round history.set_status:\n"
        + "\n".join(offenders)
        + "\n\nIf this is not a student's stage, say so on the line: "
        "`# not-a-student-status: <model>, <why>`"
    )


def test_the_history_is_on_the_student_page(client, db):
    """T-F-M.18.4-1: REQ-M.21.

    A log nobody can see answers nobody's question, and the person most likely
    to be asked one about a teenager is whoever is looking at their page.
    """
    from matazim.history import record_arrival, set_status
    from matazim.models import Student

    leader = make_leader()
    student = Student.objects.create(user=make_member(), leader=leader)
    record_arrival(student, by=leader.user, note="הצטרפות")
    set_status(student, Student.IN_TRAINING, by=leader.user, note="אישור מוביל/ה")

    client.force_login(leader.user)
    html = client.get(reverse("matazim:student", args=[student.pk])).content.decode()

    assert "היסטוריה" in html
    assert "אישור מוביל/ה" in html
    assert "נעה מורה" in html, "the history must name who made the change"


def test_the_history_reads_in_hebrew_not_in_database_keys(client, db):
    """T-F-M.18.4-2: found by rendering it.

    `StatusLog` began as two bare `CharField`s, so `get_to_status_display` did
    not exist and the template's fallback printed the raw key. A teacher opening
    a teenager's record saw "in_training ← certified". The fields now carry the
    same choices `Student.status` does, defined once so the two lists cannot
    drift.
    """
    from matazim.history import record_arrival, set_status
    from matazim.models import Student

    leader = make_leader()
    student = Student.objects.create(user=make_member(), leader=leader)
    record_arrival(student)
    set_status(student, Student.IN_TRAINING, by=leader.user, note="אישור מוביל/ה")

    client.force_login(leader.user)
    html = client.get(reverse("matazim:student", args=[student.pk])).content.decode()

    assert "לומדים" in html
    assert "מתמיינים" in html
    for key in ("in_training", "applied"):
        assert key not in html, f"a database key reached the page: {key}"
