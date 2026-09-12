"""SPR-M.19 — The member can actually learn.

REQ-M.13 and REQ-M.14, closing a dead end that shipped yesterday: המסלול שלי
told a member "להתחיל בסקראץ׳ 1" and gave them no way to start it.

Three things are being held at once here and they pull against each other,
which is why the tests are shaped the way they are.

**A member must be able to reach a lesson** (REQ-M.13), or the screen the spec
calls the product is a dead end.

**Without leaving the walls** (RULE-1), which is why it renders here rather than
linking to babook's player.

**And watching must count** (REQ-M.14), through babook's own path rather than a
second one of ours. The renderer built in SPR-M.3 recorded nothing at all, so
somebody could have watched nineteen lessons inside our chrome and stayed at
0/19 with their leader's roster agreeing. That is the test that matters most
here, because the failure is silent on every screen at once.

Traces: REQ-M.12, M.13, M.14, M.47, M.5a.
"""

import json

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm19

PASSWORD = "sprm19-pass-2260"


def make_user(email="kid@example.com", name="יובל"):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def make_track():
    from app.models import Course, Video

    made = {}
    for slug, title, n in (
        ("scratch", "סקראץ׳ למתחילים", 6),
        ("scratch-advanced", "סקראץ׳ מתקדם", 4),
    ):
        course = Course.objects.create(slug=slug, title=title, is_published=True)
        for i in range(n):
            Video.objects.create(
                course=course, title=f"שיעור {i + 1}", lesson_order=i + 1, bunny_video_id="abc123"
            )
        made[slug] = course
    return made


def make_member(email="kid@example.com", name="יובל", leader=None):
    from matazim.models import MemberProfile, Student

    user = make_user(email, name)
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now(),
            "birth_year": timezone.now().year - 14,
            "guardian_consent_at": timezone.now(),
            "welcome_accepted_at": timezone.now(),
        },
    )
    if leader is not None:
        Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)
    return user


def make_leader():
    from matazim.models import Leader, StudyClass

    leader = Leader.objects.create(
        user=make_user("noa@example.com", "נעה מורה"), approved_at=timezone.now()
    )
    StudyClass.objects.create(leader=leader, name="ט1", school_name="עתיד רמלה")
    return leader


# --------------------------------------------- F-M.19.3: the dead end closes


def test_the_next_step_actually_goes_somewhere(client, db):
    """T-F-M.19.3-1: REQ-M.5a, and the defect this sprint exists for.

    "What is your next task" is only half an answer if there is no way to do it.
    """
    make_track()
    user = make_member(leader=make_leader())
    client.force_login(user)

    html = client.get(reverse("matazim:my_path")).content.decode()
    assert (
        reverse("matazim:learn_course", args=["scratch"]) in html
    ), "the member is told what to do next and given no way to do it"


def test_the_track_links_lesson_by_lesson(client, db):
    """T-F-M.19.4-1: REQ-M.12. Somebody mid-course wants lesson seven, not one."""
    make_track()
    user = make_member(leader=make_leader())
    client.force_login(user)

    html = client.get(reverse("matazim:learn_course", args=["scratch"])).content.decode()
    assert reverse("matazim:learn_lesson", args=["scratch", 1]) in html
    assert reverse("matazim:learn_lesson", args=["scratch", 6]) in html


# --------------------------------------------- F-M.19.1: inside the walls


def test_a_lesson_renders_in_our_own_shell(client, db):
    """T-F-M.19.1-1: REQ-M.13, RULE-1.

    The point is not that a lesson is reachable, it is that reaching one does
    not take a member out of מט״צים.
    """
    make_track()
    user = make_member(leader=make_leader())
    client.force_login(user)

    html = client.get(reverse("matazim:learn_lesson", args=["scratch", 1])).content.decode()
    assert "mz-container" in html, "not our chrome"
    assert "babook" not in html.lower()


def test_no_link_on_these_screens_leaves_the_walls(client, db):
    """T-F-M.19.1-2: RULE-1, on the newest screens.

    Checked as navigation rather than by grepping for a word, the same
    distinction SPR-M.9 had to draw on the legal pages.
    """
    import re

    make_track()
    user = make_member(leader=make_leader())
    client.force_login(user)

    for name, args in (
        ("matazim:learn_course", ["scratch"]),
        ("matazim:learn_lesson", ["scratch", 1]),
    ):
        html = client.get(reverse(name, args=args)).content.decode()
        for href in re.findall(r'href=["\']([^"\']+)', html):
            if href.startswith(("mailto:", "#", "https://", "http://")):
                continue
            assert href.startswith(("/matazim/", "/static/")), f"{name} leaves the walls: {href}"


def test_the_lesson_names_itself_and_its_course(client, db):
    """T-F-M.19.1-3: REQ-M.13. A player with no title is a video, not a lesson."""
    make_track()
    user = make_member(leader=make_leader())
    client.force_login(user)

    html = client.get(reverse("matazim:learn_lesson", args=["scratch", 2])).content.decode()
    assert "שיעור 2" in html
    assert "סקראץ׳ למתחילים" in html


# --------------------------------------------- F-M.19.2: watching counts


def test_the_page_carries_what_it_needs_to_report_progress(client, db):
    """T-F-M.19.2-1: REQ-M.14, and the silent failure this sprint found.

    The renderer built in SPR-M.3 had an iframe and no heartbeat, so watching
    inside our chrome recorded nothing: a member could finish nineteen lessons
    and stay at 0/19, with their leader's roster agreeing because both read the
    same empty table.
    """
    from app.models import Video

    make_track()
    user = make_member(leader=make_leader())
    client.force_login(user)

    html = client.get(reverse("matazim:learn_lesson", args=["scratch", 1])).content.decode()
    video = Video.objects.get(course__slug="scratch", lesson_order=1)

    assert "/api/video-progress/" in html, "no way to report progress"
    assert str(video.pk) in html, "the page cannot say which lesson was watched"


def test_progress_written_here_is_the_same_progress_the_roster_reads(client, db):
    """T-F-M.19.2-2: REQ-M.14, REQ-M.74.

    The whole point of going through babook's endpoint rather than writing our
    own row. One fact, one table, and the member and their leader see the same
    number.
    """
    from app.models import Video
    from matazim.models import Student
    from matazim.progress import cohort_progress

    make_track()
    leader = make_leader()
    user = make_member(leader=leader)
    client.force_login(user)

    video = Video.objects.get(course__slug="scratch", lesson_order=1)
    response = client.post(
        "/api/video-progress/",
        data=json.dumps({"video_id": video.pk, "position": 300, "percent": 95.0}),
        content_type="application/json",
    )
    assert response.status_code == 200, response.content[:200]

    student = Student.objects.get(user=user)
    row = cohort_progress([student], ["scratch"])[user.id]["scratch"]
    assert row["done"] == 1, "watching inside our shell did not reach the shared reader"


def test_opening_a_lesson_enrolls_exactly_as_babook_does(client, db):
    """T-F-M.19.2-3: REQ-M.14, RULE-3 as amended.

    Enrolment is not the divergence the rule guards against: you cannot watch a
    lesson without one, and babook's own view creates it with this same line.
    """
    from app.models import Enrollment

    make_track()
    user = make_member(leader=make_leader())
    client.force_login(user)

    client.get(reverse("matazim:learn_lesson", args=["scratch", 1]))
    assert Enrollment.objects.filter(user=user, course__slug="scratch").exists()


# --------------------------------------------- F-M.19.5: the restraint


def test_it_renders_only_the_courses_the_programme_requires(client, db):
    """T-F-M.19.5-1: REQ-M.47.

    One line would let this render any course in babook, and that would quietly
    make מט״צים a second front end for the whole catalogue, with no owner and no
    design. It renders the track and refuses the rest.
    """
    from app.models import Course

    make_track()
    Course.objects.create(slug="arduino", title="ארדואינו", is_published=True)
    user = make_member(leader=make_leader())
    client.force_login(user)

    assert client.get(reverse("matazim:learn_course", args=["arduino"])).status_code == 404


def test_an_unknown_course_is_not_a_crash(client, db):
    """T-F-M.19.5-2: a mistyped URL says so."""
    make_track()
    user = make_member(leader=make_leader())
    client.force_login(user)

    assert client.get(reverse("matazim:learn_course", args=["nope"])).status_code == 404


def test_a_stranger_cannot_read_the_lessons(client, db):
    """T-F-M.19.5-3: REQ-M.11 as amended.

    Not a public page: these are babook's paid-for materials rendered in our
    chrome, and a member has an account by the time they are here.
    """
    make_track()
    assert client.get(reverse("matazim:learn_course", args=["scratch"])).status_code in (302, 403)


def test_a_member_with_no_leader_can_still_learn(client, db):
    """T-F-M.19.5-4: REQ-M.65.

    Having no leader is a normal state, and the courses are how somebody gets
    ready to be taken on. Gating learning behind a leader would invert the
    order the programme actually runs in.
    """
    make_track()
    user = make_member(leader=None)
    client.force_login(user)

    assert client.get(reverse("matazim:learn_course", args=["scratch"])).status_code == 200
