"""SPR-M.59 — the open door, and the entrance test beside the road.

Avi, 2026-10-12. Anyone who registers can learn the open basics with no
leader, no school and no test. "מטצ מוסמך" stays the one thing a leader's
code is for. And the entrance test is optional, chosen by the leader, a
parallel element and not a gate: nobody is shown it in front of their face.

What these tests hold is the two ways this can go wrong quietly: a page that
still sends a learner to the test first, and a door that opens for the wrong
person.

Traces: REQ-M.162 to REQ-M.166, REQ-M.177, REQ-M.178.
"""

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm59

PASSWORD = "sprm59-pass-4471"


def _user(email, name="x"):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _member(email="kid@example.com", passed=False):
    from matazim.models import MemberProfile

    user = _user(email, "יובל")
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "welcome_accepted_at": timezone.now(),
            "entrance_test_passed_at": timezone.now() if passed else None,
            "birth_year": 2012,
            "guardian_name": "רונית כהן",
            "guardian_email": "parent@example.com",
            "guardian_consent_at": timezone.now(),
        },
    )
    return user


def _leader(email="noa@example.com", requires=False):
    from matazim.models import Institution, Leader, StudyClass

    inst = Institution.objects.order_by("created_at").first() or Institution.objects.create(
        name="עתיד רמלה"
    )
    leader = Leader.objects.create(
        user=_user(email, "נעה"),
        institution=inst,
        approved_at=timezone.now(),
        requires_entrance_test=requires,
    )
    StudyClass.objects.create(leader=leader, name="ט1", school_name="עתיד")
    return leader


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()
    yield
    cache.clear()


# --- the front page: two doors, no test ----------------------------------


def _page(client, name):
    """The page body, without the member menu: REQ-M.177 keeps one quiet link
    to the test there, and what must stay clear of it is the page itself."""
    html = client.get(reverse(name)).content.decode()
    return html.split("<main", 1)[1]


# --- the open basics ------------------------------------------------------

OPEN = {
    "scratch", "scratch-advanced", "tinkercad", "fusion360",
    "micropython-thonny", "arduino-tinkercad", "arduino", "python",
}


def test_the_eight_open_basics_are_seeded_open(db):
    from matazim.access import open_slugs

    assert OPEN <= open_slugs()


def test_a_member_with_no_leader_sees_every_open_basic(db):
    from matazim.access import visible_course_slugs

    assert OPEN <= visible_course_slugs(_member())


def test_withdrawing_an_open_basic_takes_it_off_the_open_list(db):
    from matazim.access import open_slugs
    from matazim.models import OfferedCourse

    OfferedCourse.objects.filter(slug="python").update(is_active=False)
    assert "python" not in open_slugs()
    OfferedCourse.objects.filter(slug="python").update(is_active=True, open_to_all=False)
    assert "python" not in open_slugs()


def test_root_can_open_and_close_a_course_for_everyone(client, db):
    from app.models import Course
    from matazim.models import OfferedCourse

    Course.objects.create(slug="robotics", title="רובוטיקה", is_published=True)
    root = User.objects.create_superuser("root", "root@example.com", PASSWORD)
    client.force_login(root)
    url = reverse("matazim:staff_offered")

    client.post(url, {"slug": "robotics", "action": "open"})
    row = OfferedCourse.objects.get(slug="robotics")
    assert row.open_to_all and row.is_active

    client.post(url, {"slug": "robotics", "action": "close"})
    row.refresh_from_db()
    assert not row.open_to_all


def test_only_root_can_open_a_course_for_everyone(client, db):
    from app.models import Course
    from matazim.models import OfferedCourse

    Course.objects.create(slug="robotics", title="רובוטיקה", is_published=True)
    client.force_login(_member())
    response = client.post(
        reverse("matazim:staff_offered"), {"slug": "robotics", "action": "open"}
    )
    assert response.status_code == 403
    assert not OfferedCourse.objects.filter(slug="robotics", open_to_all=True).exists()


# --- the code box ---------------------------------------------------------

def test_the_code_box_is_public(client, db):
    assert client.get(reverse("matazim:code")).status_code == 200


def test_a_right_code_goes_to_the_leaders_page(client, db):
    leader = _leader()
    response = client.post(reverse("matazim:code"), {"code": leader.join_code})
    assert response.status_code == 302
    assert response["Location"] == reverse("matazim:join", args=[leader.join_code])


def test_a_pasted_link_works_like_the_code(client, db):
    leader = _leader()
    link = f"https://example.com/matazim/join/{leader.join_code}/"
    response = client.post(reverse("matazim:code"), {"code": f"  {link} "})
    assert response.status_code == 302
    assert response["Location"] == reverse("matazim:join", args=[leader.join_code])


def test_a_wrong_code_says_so_and_nothing_more(client, db):
    _leader()
    response = client.post(reverse("matazim:code"), {"code": "nope-nope"})
    assert response.status_code == 200
    assert "לא מוכר" in response.content.decode()


def test_a_retired_leaders_code_does_not_open(client, db):
    leader = _leader()
    leader.is_active = False
    leader.save()
    response = client.post(reverse("matazim:code"), {"code": leader.join_code})
    assert response.status_code == 200


def test_eight_wrong_guesses_rest_the_box(client, db):
    leader = _leader()
    for _ in range(8):
        client.post(reverse("matazim:code"), {"code": "wrong"})
    response = client.post(reverse("matazim:code"), {"code": leader.join_code})
    assert response.status_code == 200
    assert "הרבה פעמים" in response.content.decode()


# --- joining does not wait for the test -----------------------------------


# --- the certification waiver ---------------------------------------------

def _certified(user):
    from app.models import Course, CourseCertificate
    from matazim.content import REQUIRED_COURSE_SLUGS

    for slug in REQUIRED_COURSE_SLUGS:
        course, _ = Course.objects.get_or_create(
            slug=slug, defaults={"title": slug, "is_published": True}
        )
        CourseCertificate.objects.get_or_create(user=user, course=course)


def _student(leader, passed=False):
    from matazim.models import Student

    user = _member(passed=passed)
    _certified(user)
    return Student.objects.create(user=user, leader=leader)


def test_a_leader_who_does_not_ask_for_the_test_does_not_hold_the_student_back(db):
    from matazim.certification import eligibility

    state = eligibility(_student(_leader(requires=False)))
    assert state.is_eligible and not state.entrance_test_passed


def test_a_leader_who_asks_for_the_test_does(db):
    from matazim.certification import eligibility
    from matazim.models import MemberProfile

    student = _student(_leader(requires=True))
    assert not eligibility(student).is_eligible
    MemberProfile.objects.filter(user=student.user).update(
        entrance_test_passed_at=timezone.now()
    )
    assert eligibility(student).is_eligible


def test_a_new_leader_does_not_require_the_test_by_default(db):
    assert _leader().requires_entrance_test is False


# --- the leader's switch --------------------------------------------------

def test_a_leader_can_turn_the_test_on_and_off_and_nobody_is_removed(client, db):
    from matazim.models import Student

    leader = _leader()
    student = _student(leader)
    client.force_login(leader.user)
    url = reverse("matazim:leader_test_switch")

    client.post(url, {"required": "1"})
    leader.refresh_from_db()
    assert leader.requires_entrance_test

    client.post(url, {"required": "0"})
    leader.refresh_from_db()
    assert not leader.requires_entrance_test
    assert Student.objects.filter(pk=student.pk, leader=leader).exists()


def test_the_switch_is_post_only(client, db):
    leader = _leader()
    client.force_login(leader.user)
    assert client.get(reverse("matazim:leader_test_switch")).status_code == 405


def test_only_a_leader_has_the_switch(client, db):
    leader = _leader()
    client.force_login(_member("other@example.com"))
    response = client.post(reverse("matazim:leader_test_switch"), {"required": "1"})
    assert response.status_code == 403
    leader.refresh_from_db()
    assert not leader.requires_entrance_test


def test_a_leader_cannot_flip_another_leaders_switch(client, db):
    first = _leader("a@example.com")
    second = _leader("b@example.com")
    client.force_login(first.user)
    client.post(reverse("matazim:leader_test_switch"), {"required": "1"})
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.requires_entrance_test and not second.requires_entrance_test


# --- the screens that used to lead with the test --------------------------

def test_the_courses_page_shows_no_test_to_somebody_with_no_leader(client, db):
    client.force_login(_member())
    assert reverse("matazim:entrance_test") not in _page(client, "matazim:courses")


def test_the_courses_page_shows_the_test_when_the_leader_asks_for_it(client, db):
    from matazim.models import Student

    leader = _leader(requires=True)
    user = _member()
    Student.objects.create(user=user, leader=leader)
    client.force_login(user)
    assert reverse("matazim:entrance_test") in _page(client, "matazim:courses")


def test_the_test_page_itself_is_never_locked(client, db):
    client.force_login(_member())
    assert client.get(reverse("matazim:entrance_test")).status_code == 200


# --- a signed-in non-member reaches the open set and only the open set ----

def _published(slug):
    from app.models import Course, Video

    course = Course.objects.create(slug=slug, title=slug, is_published=True)
    Video.objects.create(course=course, title="שיעור 1", lesson_order=1, bunny_video_id=slug)
    return course


def test_the_same_account_is_refused_a_course_outside_the_open_set(client, db):
    _published("robotics")
    client.force_login(_member())
    response = client.get(reverse("matazim:learn_course", args=["robotics"]))
    assert response.status_code in (302, 403, 404)


def test_the_courses_page_calls_a_finished_course_a_completion_not_a_certification(client, db):
    client.force_login(_member())
    html = client.get(reverse("matazim:courses")).content.decode()
    assert "מטצ מוסמך" not in html.split("<main", 1)[1]


# --- the REST fields ------------------------------------------------------

def test_the_api_carries_the_new_fields():
    from matazim.serializers import LeaderSerializer, OfferedCourseSerializer

    assert "requires_entrance_test" in LeaderSerializer.Meta.fields
    assert "open_to_all" in OfferedCourseSerializer.Meta.fields
