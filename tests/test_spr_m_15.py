"""SPR-M.15 — Her leaders, and one of them in full.

The two screens the program manager actually lives in. The list answers "who
needs me today"; the detail answers "what is going on with this one".

The detail view deliberately does not build a second roster. SPR-M.8 already has
one, with search, paging, track progress and the three certification conditions,
and a duplicate is a thing that drifts until two screens disagree about the same
teenager. So this reads the same data through the program manager's scope.

Traces: REQ-M.94, M.95.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm15

PASSWORD = "sprm15-pass-1173"


def make_user(email, name=""):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name or email})
    return user


def _world():
    """A leader with students in three different states."""
    from django.utils import timezone

    from app.models import UserProfile
    from matazim.models import Leader, MemberProfile, Student, StudyClass

    boss = make_user("chief@example.com")
    MemberProfile.objects.create(user=boss, is_program_manager=True)

    teacher = make_user("noa@example.com")
    UserProfile.objects.update_or_create(user=teacher, defaults={"display_name": "נעה מורה"})
    # REQ-M.88 and REQ-M.93: owned by her, and actually approved. An unowned or
    # unapproved leader is invisible to a program manager, which is correct and
    # would make every assertion below fail for the wrong reason.
    leader = Leader.objects.create(user=teacher, program_manager=boss, approved_at=timezone.now())
    klass = StudyClass.objects.create(leader=leader, name="ט1", school_name="עתיד רמלה")

    for email, name, status in (
        ("a@example.com", "יובל כהן", Student.CERTIFIED),
        ("b@example.com", "מאיה לוי", Student.IN_TRAINING),
    ):
        user = make_user(email)
        UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
        MemberProfile.objects.create(user=user, entrance_test_passed_at=timezone.now())
        s = Student.objects.create(user=user, leader=leader, status=status)
        s.classes.add(klass)

    # Someone else's student, to prove the list is that leader's and not all of them.
    other = Leader.objects.create(
        user=make_user("other@example.com"), program_manager=boss, approved_at=timezone.now()
    )
    elsewhere = make_user("c@example.com")
    UserProfile.objects.update_or_create(user=elsewhere, defaults={"display_name": "דני זר"})
    Student.objects.create(user=elsewhere, leader=other)

    return boss, leader


def test_a_leaders_page_lists_that_leaders_students(client, db):
    """T-F-M.15.3-1: REQ-M.95.

    Avi, looking at the demo: opening a leader should show their students, not
    only a count. A number tells you there are three; it does not tell you which
    three, which is the only question worth opening the page for.
    """
    boss, leader = _world()
    client.force_login(boss)

    html = client.get(reverse("matazim:staff_leader", args=[leader.pk])).content.decode()
    assert "יובל כהן" in html
    assert "מאיה לוי" in html
    assert "דני זר" not in html, "another leader's student leaked onto this page"


def test_that_list_carries_progress_and_state(client, db):
    """T-F-M.15.3-2: REQ-M.95. A list of bare names answers no more than a count."""
    boss, leader = _world()
    client.force_login(boss)

    html = client.get(reverse("matazim:staff_leader", args=[leader.pk])).content.decode()
    assert "mz-bar-fill" in html, "no progress shown"
    assert "מט״צ מוסמך" in html, "certification state not shown"


def test_each_student_is_reachable_from_there(client, db):
    """T-F-M.15.3-3: REQ-M.95. The student page already exists; this is the door."""
    from matazim.models import Student

    boss, leader = _world()
    student = Student.objects.get(user__email="a@example.com")
    client.force_login(boss)

    html = client.get(reverse("matazim:staff_leader", args=[leader.pk])).content.decode()
    assert reverse("matazim:student", args=[student.pk]) in html


def test_the_list_shows_the_counts_that_answer_who_needs_me(client, db):
    """T-F-M.15.1-1: REQ-M.94.

    One line each, light enough to scan. A program manager opens this to find
    out where to look, so the line has to carry enough to decide without
    clicking, and little enough to read twenty of them.
    """
    boss, leader = _world()
    client.force_login(boss)

    html = client.get(reverse("matazim:pm_leaders")).content.decode()
    assert "נעה מורה" in html
    assert "עתיד רמלה" in html, "the school is how she recognises a leader"
    assert "2 מט״צים" in html, "the student count belongs on the line"


def test_a_leader_with_no_class_reads_as_a_state_not_a_blank(client, db):
    """T-F-M.15.1-2: REQ-M.94.

    A blank cell looks like a bug. A leader who has not opened a class yet is a
    normal thing on their first week, and the line should say so.
    """
    from matazim.models import Leader

    boss, _leader = _world()
    Leader.objects.create(
        user=make_user("new@example.com", "מוביל חדש"),
        program_manager=boss,
        approved_at=timezone.now(),
    )
    client.force_login(boss)

    html = client.get(reverse("matazim:pm_leaders")).content.decode()
    assert "עוד לא פתח/ה כיתה" in html


def test_the_detail_page_does_not_duplicate_the_roster_template(db):
    """T-F-M.15.3-4: REQ-M.95, checked structurally.

    A second roster is the thing this sprint is trying not to build. Two
    templates rendering the same rows drift until they disagree about the same
    teenager, and nobody notices because both look fine on their own.
    """
    from pathlib import Path

    detail = Path("templates/matazim/staff_leader.html").read_text(encoding="utf-8")
    assert "mz-roster-row" in detail, "the detail page should reuse the roster row"
    # And the progress it shows comes from the shared reader, not a hand count.
    views = Path("matazim/joining_views.py").read_text(encoding="utf-8")
    assert "cohort_progress" in views, "progress must come from matazim.progress"


def test_a_school_is_named_once_however_many_classes(client, db):
    """T-F-M.15.1-3: REQ-M.94, found by looking at the demo.

    A leader with two classes in the same school rendered
    "עתיד רמלה · עתיד רמלה", because the line was built by looping classes
    rather than schools. On a list meant to be scanned, a repeated word is read
    as two different things.
    """
    from matazim.models import StudyClass

    boss, leader = _world()
    StudyClass.objects.create(leader=leader, name="ט3", school_name="עתיד רמלה")
    client.force_login(boss)

    html = client.get(reverse("matazim:pm_leaders")).content.decode()

    # Scoped to the leader's own row. A page-wide count catches the placeholder
    # text in the invite form ("למשל: רונית מעתיד רמלה"), which is a test
    # agreeing with itself rather than reading the line a person would read.
    import re

    row = re.search(r'class="mz-roster-row".*?</li>', html, re.S).group(0)
    assert row.count("עתיד רמלה") == 1, "the school is named more than once on the line"
