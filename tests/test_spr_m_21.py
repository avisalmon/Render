"""SPR-M.21 — the review pass, and what rendering the screens turned up.

Item 1 of the review Avi asked for was to put the twenty-two uncovered screens
through the screen contract. Adding them was the easy half. The half that
mattered was checking the contract was looking at the screens it named, because
three guards in this project had already passed while measuring something else.

It was: `/matazim/apply/` rendered the profile, because the member the entry
signed in as already had a leader and `apply` redirects. That is correct product
behaviour and a broken test, and it is the reason `_assert_landed` now exists.

What rendering the rest found is what these tests hold.

Traces: REQ-M.85, REQ-M.88, §4.4 tenancy, §4.9 mataz vs leader.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm21

PASSWORD = "sprm21-pass-7741"


def _user(email, name=""):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name or email})
    return user


def _manager(email):
    from matazim.models import MemberProfile

    user = _user(email, "מנהלת")
    MemberProfile.objects.update_or_create(user=user, defaults={"is_program_manager": True})
    return user


def _leader(email, manager):
    from matazim.models import Leader

    return Leader.objects.create(
        user=_user(email, "נעה מורה"), program_manager=manager, approved_at=timezone.now()
    )


def _student(email, leader, status="in_training"):
    from matazim.models import MemberProfile, Student

    user = _user(email, "יובל כהן")
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now(),
            "birth_year": timezone.now().year - 14,
            "guardian_consent_at": timezone.now(),
        },
    )
    return Student.objects.create(user=user, leader=leader, status=status)


# ------------------------------------------- the staff home was not scoped


def test_a_manager_is_not_told_about_another_institution(client, db):
    """T-F-M.21.1-1: §4.4, REQ-M.88.

    ניהול counted `Student.objects.count()` and every active `Leader` in the
    installation, so the number נעמי read on her own dashboard included another
    programme's children. Nothing linked to them and nothing named them, which
    is exactly why it survived: a count is a disclosure that does not look like
    one.
    """
    naomi = _manager("naomi@example.com")
    mine = _leader("mine@example.com", naomi)
    _student("a@example.com", mine)

    other = _manager("other@example.com")
    theirs = _leader("theirs@example.com", other)
    _student("b@example.com", theirs)
    _student("c@example.com", theirs)

    client.force_login(naomi)
    counts = client.get(reverse("matazim:staff_home")).context["counts"]

    assert counts["students"] == 1, "another programme's children are in this number"
    assert counts["leaders"] == 1, "another manager's leaders are in this number"


def test_root_still_crosses_every_world(client, db):
    """T-F-M.21.1-2: §4.4. Scoping must not blind Avi, who owns all of it."""
    naomi = _manager("naomi@example.com")
    _student("a@example.com", _leader("mine@example.com", naomi))
    _student("b@example.com", _leader("theirs@example.com", _manager("other@example.com")))

    root = User.objects.create_superuser("root@example.com", "root@example.com", PASSWORD)
    client.force_login(root)
    counts = client.get(reverse("matazim:staff_home")).context["counts"]

    assert counts["students"] == 2
    assert counts["leaders"] == 2


def test_a_learner_is_not_called_a_mataz_until_certified(client, db):
    """T-F-M.21.1-3: §4.9.

    The dashboard labelled every student "מט״צים". That is the word for someone
    who finished, and handing it to four people when one has earned it makes the
    programme's own headline number wrong.
    """
    from matazim.models import Student

    naomi = _manager("naomi@example.com")
    leader = _leader("leader@example.com", naomi)
    _student("a@example.com", leader)
    _student("b@example.com", leader)
    _student("c@example.com", leader, status=Student.CERTIFIED)

    client.force_login(naomi)
    counts = client.get(reverse("matazim:staff_home")).context["counts"]

    assert counts["students"] == 3
    assert counts["certified"] == 1


# ------------------------------------------- what המידע שלי was telling people


def test_the_data_page_names_the_leader_rather_than_emailing_them(client, db):
    """T-F-M.21.2-1: REQ-M.85.

    It printed `leader@example.com`, on a screen a 14-year-old reads and in the
    file they download. Wrong, and a disclosure of a member of staff's address
    to a minor.
    """
    leader = _leader("leader@example.com", _manager("naomi@example.com"))
    student = _student("kid@example.com", leader)

    client.force_login(student.user)
    row = client.get(reverse("matazim:my_data")).context["data"]["program"][0]

    assert row["leader"] == "נעה מורה"
    assert "@" not in (row["leader"] or "")


def test_the_data_page_cannot_say_nought_courses_and_a_certificate(client, db):
    """T-F-M.21.2-2: REQ-M.85, RULE-3.

    It counted `Enrollment` rows only, so somebody who had watched half a course
    was told they had started none while the line beside it counted their
    certificate. A person asking what we hold is owed an answer that agrees with
    itself.
    """
    from app.models import Course, UserVideoProgress, Video

    leader = _leader("leader@example.com", _manager("naomi@example.com"))
    student = _student("kid@example.com", leader)

    course = Course.objects.create(slug="scratch", title="סקראץ׳", is_published=True)
    video = Video.objects.create(
        course=course, title="שיעור 1", lesson_order=1, bunny_video_id="abc"
    )
    UserVideoProgress.objects.create(
        user=student.user, video=video, percent_watched=100.0, completed_at=timezone.now()
    )

    client.force_login(student.user)
    learning = client.get(reverse("matazim:my_data")).context["data"]["learning"]

    assert [row["course"] for row in learning] == ["scratch"]


def test_the_data_page_agrees_with_the_rest_of_the_site_about_the_test(client, db):
    """T-F-M.21.2-3: REQ-M.85.

    The page read the attempt rows and said "עוד לא ניגשתם" to somebody whose
    profile says they passed, which is the two of them disagreeing in public.
    """
    leader = _leader("leader@example.com", _manager("naomi@example.com"))
    student = _student("kid@example.com", leader)

    client.force_login(student.user)
    response = client.get(reverse("matazim:my_data"))

    assert response.context["passed_at"] is not None
    assert "עוד לא ניגשתם" not in response.content.decode()
