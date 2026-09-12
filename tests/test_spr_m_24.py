"""SPR-M.24 — every role's own journey, and need-to-know.

Avi, 2026-09-12: walk each role through every view it sees and check whether it
was intuitive to find, self-explanatory, complete for that role, well designed,
and whether the pages that role needs exist at all. Then, mid-review: "hide
everything this role does not need to see. Make everything on a need-to-know
basis."

The worst finding was the leader candidate. REQ-M.93 creates that state on
purpose and nothing in the product acknowledged it: כניסת מובילים told them to
sign in while they were signed in, and האזור האישי showed them, an adult
teacher, a parental-consent panel and an entrance-test status. An approved
leader with four students saw the same profile.

Traces: REQ-M.99, M.100, M.101, M.102, M.103, M.104, M.5b, M.63, §4.9.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm24

PASSWORD = "sprm24-pass-5520"


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _manager(email="naomi@example.com"):
    from matazim.models import MemberProfile

    user = _user(email, "נעמי")
    MemberProfile.objects.update_or_create(user=user, defaults={"is_program_manager": True})
    return user


def _leader(email="noa@example.com", name="נעה מורה", manager=None, approved=True):
    from matazim.models import Leader

    return Leader.objects.create(
        user=_user(email, name),
        program_manager=manager or _manager(),
        approved_at=timezone.now() if approved else None,
    )


def _member(email="kid@example.com", name="יובל כהן", passed=True):
    from matazim.models import MemberProfile

    user = _user(email, name)
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now() if passed else None,
            "birth_year": timezone.now().year - 14,
            "guardian_consent_at": timezone.now(),
            "welcome_accepted_at": timezone.now(),
        },
    )
    return user


# ------------------------------------- F-M.24.1: the candidate is told


def test_a_waiting_candidate_is_told_they_are_waiting(client, db):
    """T-F-M.24.1-1: REQ-M.99.

    The page told them "already appointed? sign in with the email you gave the
    team and this page will take you straight to your area" while they were
    signed in with that email, and then took them nowhere.
    """
    candidate = _leader("waiting@example.com", "מורה ממתינה", approved=False)
    client.force_login(candidate.user)

    html = client.get(reverse("matazim:leader_entrance")).content.decode()

    assert "ממתינה לאישור" in html, "nothing tells them the invitation was received"
    assert "נעמי" in html, "they are not told who they are waiting on"
    assert "התחברו עם אותו אימייל" not in html, "still telling a signed-in person to sign in"


def test_the_candidate_is_not_shown_a_pupils_profile(client, db):
    """T-F-M.24.1-2: REQ-M.100, REQ-M.102.

    An adult teacher was shown a parental-consent panel, told their leader was
    unassigned, that they had not joined the programme, and offered a button
    into the pupil journey.
    """
    candidate = _leader("waiting@example.com", "מורה ממתינה", approved=False)
    client.force_login(candidate.user)

    html = client.get(reverse("matazim:profile")).content.decode()

    assert "אישור הורה" not in html, "a consent panel for a child, shown to a teacher"
    assert "המעמד שלי בתוכנית" not in html, "a learner's standing, shown to a teacher"
    assert "ממתינה לאישור" in html, "nothing here says what they are waiting for"


def test_an_approved_leader_sees_their_own_standing(client, db):
    """T-F-M.24.1-3: REQ-M.100.

    נעה מורה, with students of her own, was told her leader was unassigned and
    that she had not sat the entrance test.
    """
    from matazim.models import Student

    leader = _leader()
    Student.objects.create(user=_member(), leader=leader, status=Student.IN_TRAINING)
    Student.objects.create(
        user=_member("two@example.com", "מאיה"), pending_leader=leader
    )
    client.force_login(leader.user)

    response = client.get(reverse("matazim:profile"))
    html = response.content.decode()

    assert "אישור הורה" not in html
    assert "המעמד שלי בתוכנית" not in html
    assert "האזור שלי כמוביל/ה" in html
    assert response.context["leader_students"] == 1
    assert response.context["leader_waiting"] == 1


def test_a_member_still_sees_everything_that_is_theirs(client, db):
    """T-F-M.24.1-4: REQ-M.100.

    The gating must not take a member's own screen away from them, which is the
    obvious way to break this while making the tests above pass.
    """
    from matazim.models import Student

    leader = _leader()
    user = _member()
    Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)
    client.force_login(user)

    html = client.get(reverse("matazim:profile")).content.decode()

    assert "המעמד שלי בתוכנית" in html
    assert "המסלול שלי" in html
    assert "האזור שלי כמוביל/ה" not in html


# ------------------------------------- F-M.24.3: the menu is the role's menu


def test_a_leader_is_not_offered_the_pupil_journey(client, db):
    """T-F-M.24.3-1: REQ-M.101, §4.9.

    A leader is not a מט״צ. Their menu carried המסלול שלי, which is a pupil's
    screen, and they could be halfway into the learning track before noticing
    that their own area was a different item.
    """
    leader = _leader()
    client.force_login(leader.user)

    html = client.get(reverse("matazim:leader_home")).content.decode()
    nav = html.split('<nav class="mz-nav"')[1].split("</nav>")[0]

    assert reverse("matazim:my_path") not in nav, "a pupil's screen in a teacher's menu"
    assert reverse("matazim:leader_home") in nav
    assert reverse("matazim:roster") in nav


def test_a_member_keeps_a_menu_of_their_own_work(client, db):
    """T-F-M.24.3-2: REQ-M.101, REQ-M.5b.

    Nine items of which two were theirs, the rest recruitment copy aimed at
    somebody who has not joined.
    """
    from matazim.models import Student

    Student.objects.create(user=_member(), leader=_leader(), status=Student.IN_TRAINING)
    client.force_login(User.objects.get(email="kid@example.com"))

    html = client.get(reverse("matazim:my_path")).content.decode()
    nav = html.split('<nav class="mz-nav"')[1].split("</nav>")[0]

    assert reverse("matazim:my_path") in nav
    assert reverse("matazim:about") in nav, "available, even if not offered first"
    assert reverse("matazim:schools") not in nav, "recruitment copy in a member's menu"


def test_the_entrance_test_stays_in_the_menu_once_passed(client, db):
    """T-F-M.24.3-3: REQ-M.63.

    Marked, never hidden. Hiding it also made the whole test chain unreachable
    for anyone who had passed, which the reachability audit caught on the first
    run after the menu was trimmed.
    """
    client.force_login(_member())
    html = client.get(reverse("matazim:my_path")).content.decode()
    nav = html.split('<nav class="mz-nav"')[1].split("</nav>")[0]

    assert reverse("matazim:entrance_test") in nav
    assert "mz-nav-done" in nav, "passed, and not marked as passed"


# ------------------------------------- F-M.24.5: the teachers' door


@pytest.mark.parametrize("path_name", ["home", "about", "schools", "login"])
def test_the_teachers_door_can_be_found(client, db, path_name):
    """T-F-M.24.5-1: REQ-M.103.

    Linked from no page in the product, so a teacher had to be sent a URL. The
    comment in base.html still described a home-page door, so it existed once.
    """
    html = client.get(reverse(f"matazim:{path_name}")).content.decode()
    assert reverse("matazim:leader_entrance") in html


# ------------------------------------- F-M.24.6: the task is not the teaching


def test_the_entrance_task_is_reachable_with_no_lessons_loaded(client, db):
    """T-F-M.24.6-1: REQ-M.104, REQ-M.36.

    The way to the task sat inside `{% if lessons %}`, and the lessons are
    babook's `tinkercad` course, which nothing in the deploy guarantees.
    Unpublish one course and the gate to the whole programme became
    unreachable, while saying "coming soon" so nobody would report it broken.
    """
    client.force_login(_member(passed=False))

    html = client.get(reverse("matazim:test_lessons")).content.decode()

    assert reverse("matazim:test_task") in html, "no way to the test without the teaching"
    assert "ייפתחו כאן בקרוב" not in html, "reads as coming soon when it is broken"


def test_the_task_still_comes_after_the_lessons_when_there_are_lessons(client, db):
    """T-F-M.24.6-2: REQ-M.104. Decoupling must not reorder the normal journey."""
    from app.models import Course, Video

    course = Course.objects.create(slug="tinkercad", title="טינקרקאד", is_published=True)
    for i in range(3):
        Video.objects.create(
            course=course, title=f"שיעור {i + 1}", lesson_order=i + 1, bunny_video_id="abc"
        )

    client.force_login(_member(passed=False))
    html = client.get(reverse("matazim:test_lessons")).content.decode()

    assert "ואז המשימה" in html
    assert html.index("שיעור 1") < html.index("ואז המשימה"), "the task jumped the lessons"
