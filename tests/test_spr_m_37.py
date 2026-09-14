"""SPR-M.37 — the leftovers, and one live contradiction hiding among them.

REQ-M.5b, REQ-M.11, REQ-M.12b. The last small things on the list, plus a defect
the review that produced this sprint found: ההדרכות told a signed-in member that
nothing past the entrance test was open, while המסלול שלי showed the same person
two required courses they were meant to be doing.

That one is worth naming because of how it survived. Each screen was internally
consistent and each had passing tests. It was only visible reading the two side
by side as one person, which is the kind of defect a screen-by-screen catalogue
cannot see. `test_the_two_screens_agree_about_the_track` is the guard, and it
asserts agreement rather than either screen's content, because the failure was
never in one of them.

Traces: REQ-M.5b, M.11, M.12b, M.59, M.76, M.101, RULE-3.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm37

PASSWORD = "sprm37-pass-2206"


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _member(email="kid@example.com", name="יובל כהן"):
    from matazim.models import MemberProfile

    user = _user(email, name)
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now(),
            "birth_year": timezone.now().year - 14,
            "welcome_accepted_at": timezone.now(),
        },
    )
    return user


def _track():
    """The required courses, as real rows, because the page reads titles."""
    from app.models import Course

    from matazim.content import REQUIRED_COURSE_SLUGS

    made = []
    for slug in REQUIRED_COURSE_SLUGS:
        course, _ = Course.objects.get_or_create(
            slug=slug, defaults={"title": f"הדרכה {slug}", "is_published": True}
        )
        made.append(course)
    return made


# ------------------------------------------- REQ-M.12b: the cards carry state


def test_a_visitor_gets_recruitment_and_not_somebody_elses_progress(client, db):
    """T-F-M.37.1-1: REQ-M.59, REQ-M.102.

    Two readers, two pages. Somebody deciding whether to join has no progress
    to show and should not be shown an empty track that reads as a locked door.
    """
    _track()
    html = client.get(reverse("matazim:courses")).content.decode()

    assert "מה לומדים בתוכנית" in html
    assert "המסלול הנדרש" not in html
    assert "0%" not in html


def test_a_member_sees_their_own_track_with_its_state(client, db):
    """T-F-M.37.1-2: REQ-M.12b.

    A progress figure, a status word, and an action that matches the state. A
    card saying "להתחיל" to somebody halfway through is the small kind of lie
    that makes a product feel like it is not paying attention.
    """
    _track()
    user = _member()

    client.force_login(user)
    html = client.get(reverse("matazim:courses")).content.decode()

    assert "המסלול הנדרש" in html
    assert "עוד לא התחלתם" in html
    assert "להתחיל" in html
    assert "0%" in html


def test_the_action_matches_where_they_actually_are(client, db):
    """T-F-M.37.1-3: REQ-M.12b, RULE-3.

    The state is read live from the shared progress tables. There is no second
    copy of "how far through am I" in this product and there must not be, which
    is why this test moves the shared rows rather than anything of ours.
    """
    from app.models import CourseCertificate

    from matazim.content import REQUIRED_COURSE_SLUGS

    courses = _track()
    user = _member()

    CourseCertificate.objects.create(user=user, course=courses[0])

    client.force_login(user)
    html = client.get(reverse("matazim:courses")).content.decode()

    assert "הושלם" in html
    assert "צפייה שוב" in html
    assert "100%" in html


def test_the_two_screens_agree_about_the_track(client, db):
    """T-F-M.37.1-4: the defect this sprint found, held as agreement.

    ההדרכות said nothing past the entrance test was open; המסלול שלי showed the
    same person two required courses. Each screen was internally consistent and
    each had passing tests, so only reading them side by side found it.

    This asserts the two agree rather than asserting either one's content,
    because the failure was never in one of them.
    """
    courses = _track()
    user = _member()
    client.force_login(user)

    on_courses = client.get(reverse("matazim:courses")).content.decode()
    on_path = client.get(reverse("matazim:my_path")).content.decode()

    for course in courses:
        named_on_courses = course.title in on_courses
        named_on_path = course.title in on_path
        assert named_on_courses == named_on_path, (
            f"the two screens disagree about {course.slug}: "
            f"ההדרכות={named_on_courses}, המסלול שלי={named_on_path}"
        )


def test_a_missing_course_says_so_rather_than_offering_a_dead_link(client, db):
    """T-F-M.37.1-5: REQ-M.104's lesson, applied here.

    The entrance task once hung off a course that might not be published, and a
    missing course turned the gate to the whole programme into a shrug. The
    track is named in our spec and its content lives in the shared engine, so
    the honest answer to a missing slug is that the teaching did not load.
    """
    from app.models import Course

    Course.objects.all().delete()
    user = _member()

    client.force_login(user)
    html = client.get(reverse("matazim:courses")).content.decode()

    assert "לא נטענה" in html
    assert "להתחיל" not in html.split("המסלול הנדרש")[1].split("מבחן הכניסה")[0]


# ------------------------------------------- REQ-M.11: what needs a role


def test_a_screen_about_you_needs_only_an_account(client, db):
    """T-F-M.37.2-1: REQ-M.11 as amended.

    The rule that actually holds: a screen showing somebody else's data requires
    a role; a screen showing only your own requires only an account. The
    original wording said anything past the public front needs a `Student` row,
    which the product contradicted three times over.
    """
    user = _member()
    client.force_login(user)

    from matazim.models import Student

    assert not Student.objects.filter(user=user).exists()

    for page in ("matazim:my_path", "matazim:profile", "matazim:my_data",
                 "matazim:my_work", "matazim:my_teaching", "matazim:courses"):
        assert client.get(reverse(page)).status_code == 200, page


def test_a_screen_about_somebody_else_needs_a_role(client, db):
    """T-F-M.37.2-2: REQ-M.11 as amended, the other half."""
    user = _member()
    client.force_login(user)

    for page in ("matazim:roster", "matazim:classes", "matazim:staff_home",
                 "matazim:cohort", "matazim:pm_leaders"):
        assert client.get(reverse(page)).status_code in (302, 403), page


# ------------------------------------------- REQ-M.5b: the menu is settled


def test_a_stage_that_has_not_opened_offers_no_door(client, db):
    """T-F-M.37.3-1: REQ-M.5b, closed by REQ-M.101, and one rule held both ways.

    REQ-M.5b named הגשות ותוצרים as a menu item. REQ-M.101 then cut the menu
    from nine items to six on the grounds that the menu is the role's menu, so
    what matters is reachability rather than membership of one bar.

    המסלול שלי argued the rule that decides it: a button leading to "this opens
    when you join somebody" is a button that teaches people not to press. So a
    member with no leader is offered neither יוצרים nor פרקטיקום, and one with
    a leader is offered both. This test was written the other way round first
    and the product was right: the פרקטיקום panel added in SPR-M.35 was the
    thing breaking the rule, not the work panel obeying it.
    """
    from matazim.models import Leader, Student

    user = _member()
    client.force_login(user)

    alone = client.get(reverse("matazim:my_path")).content.decode()
    for page in ("matazim:my_work", "matazim:my_teaching"):
        assert reverse(page) not in alone, (
            f"{page} was offered to somebody it is not open to yet"
        )

    pm = _user("pm@example.com", "נעמי")
    _make_manager(pm)
    leader = Leader.objects.create(
        user=_user("noa@example.com", "נעה"),
        institution=_inst(pm),
        approved_at=timezone.now(),
    )
    Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)

    joined = client.get(reverse("matazim:my_path")).content.decode()
    for page in ("matazim:my_work", "matazim:my_teaching"):
        assert reverse(page) in joined, f"{page} is not reachable once they have joined"


def test_nothing_still_claims_a_section_is_unbuilt(client, db):
    """T-F-M.37.3-2: the placeholder copy outlived two of its three sections.

    ימי שיא became real in SPR-M.31 and קהילת מט״צים in SPR-M.32, and the views
    that said "no Event model yet" and "no Post model yet" sat unreachable in
    `views.py` afterwards, asserting two things that had stopped being true.
    """
    from matazim import views

    assert not hasattr(views, "events"), "a dead placeholder view is still here"
    assert not hasattr(views, "community"), "a dead placeholder view is still here"

    for page in ("matazim:events", "matazim:community"):
        html = client.get(reverse(page)).content.decode()
        assert "בקרוב" not in html, f"{page} still says it is coming"


# --- SPR-M.40: the role is Institution.managers, the FKs are `institution` ---

def _make_manager(user):
    """One institution per test manager, so two managers are two worlds."""
    from matazim.models import Institution

    Institution.objects.create(name=f"מוסד {user.pk}").managers.add(user)


def _inst(user):
    from matazim.access import institution_of

    return institution_of(user)


def _is_pm(user):
    from matazim.access import is_program_manager

    return is_program_manager(user)
