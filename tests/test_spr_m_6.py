"""SPR-M.6 — The roles, and nothing else.

Four models, one access module, and the tests that make everything after this
trivial. No screens on purpose: once scope is a property of the data, a roster
is a filtered queryset rather than permission logic.

The architecture rests on a single claim, that **a leader cannot reach another
leader's students because the query cannot get there**. Believing that is not
the same as knowing it, so most of this file builds two leaders with students
each and checks that neither queryset ever contains the other's.

Traces: REQ-M.22, M.65, M.67, M.68, spec §4.
"""

import pytest
from django.contrib.auth.models import User

pytestmark = pytest.mark.sprm6


def make_user(email):
    return User.objects.create_user(username=email, email=email, password="sprm6-pass")


def make_leader(email, active=True):
    from matazim.models import Leader

    return Leader.objects.create(user=make_user(email), is_active=active)


def make_student(email, leader=None, year=2026):
    from matazim.models import Student

    return Student.objects.create(user=make_user(email), leader=leader, cohort_year=year)


# ---------------------------------------------------------------- F-M.6.1


def test_the_four_models_exist_with_the_agreed_shape(db):
    """T-F-M.6.1-1: spec §4.2."""
    from matazim.models import MemberProfile, StudyClass

    leader = make_leader("lead@example.com")
    assert leader.is_active is True
    assert leader.join_code, "a leader needs a link to hand out"

    klass = StudyClass.objects.create(leader=leader, name="ט1", school_name="תיכון עתיד רמלה")
    assert klass.leader == leader

    student = make_student("kid@example.com", leader=leader)
    student.classes.add(klass)
    assert list(klass.students.all()) == [student]
    assert list(leader.students.all()) == [student]

    profile = MemberProfile.objects.create(user=make_user("nobody@example.com"))
    assert profile.is_admin is False, "adminship is granted, never a default"


def test_a_student_can_exist_before_any_leader_has_them(db):
    """T-F-M.6.1-2: REQ-M.65. `leader` is nullable on purpose.

    Someone registers, passes the entrance test, and is nobody's yet. From there
    it goes either way: they ask to join a leader, or a leader invites them.
    """
    student = make_student("orphan@example.com", leader=None)
    assert student.leader is None
    assert student.pk


def test_a_leader_can_run_classes_at_more_than_one_school(db):
    """T-F-M.6.1-3: Avi, 2026-09-10. School belongs to the class, not the leader."""
    from matazim.models import StudyClass

    leader = make_leader("roams@example.com")
    StudyClass.objects.create(leader=leader, name="ט1", school_name="עתיד רמלה")
    StudyClass.objects.create(leader=leader, name="ט2", school_name="עתיד לוד")

    schools = set(leader.classes.values_list("school_name", flat=True))
    assert schools == {"עתיד רמלה", "עתיד לוד"}


def test_one_person_one_row_per_cohort(db):
    """T-F-M.6.1-4: a person can be in two cohorts, not in one twice."""
    from django.db import IntegrityError

    from matazim.models import Student

    user = make_user("twice@example.com")
    Student.objects.create(user=user, cohort_year=2026)
    Student.objects.create(user=user, cohort_year=2027)

    with pytest.raises(IntegrityError):
        Student.objects.create(user=user, cohort_year=2026)


# ---------------------------------------------------------------- F-M.6.2


def test_a_leader_cannot_reach_another_leaders_students(db):
    """T-F-M.6.2-1: REQ-M.22, and the claim the whole architecture rests on.

    Not "the view remembered to check". The query cannot get there.
    """
    from matazim.access import visible_students

    noa = make_leader("noa@example.com")
    dan = make_leader("dan@example.com")
    hers = make_student("hers@example.com", leader=noa)
    his = make_student("his@example.com", leader=dan)

    assert set(visible_students(noa.user)) == {hers}
    assert set(visible_students(dan.user)) == {his}
    assert his not in visible_students(noa.user)
    assert hers not in visible_students(dan.user)


def test_a_student_sees_only_themselves(db):
    """T-F-M.6.2-2."""
    from matazim.access import visible_students

    leader = make_leader("lead2@example.com")
    me = make_student("me@example.com", leader=leader)
    make_student("peer@example.com", leader=leader)

    assert set(visible_students(me.user)) == {me}


def test_an_admin_sees_everyone_including_the_unclaimed(db):
    """T-F-M.6.2-3: REQ-M.65. Someone with no leader must not fall out of view."""
    from matazim.access import visible_students
    from matazim.models import MemberProfile

    boss = make_user("boss@example.com")
    MemberProfile.objects.create(user=boss, is_admin=True)

    leader = make_leader("lead3@example.com")
    claimed = make_student("claimed@example.com", leader=leader)
    unclaimed = make_student("unclaimed@example.com", leader=None)

    assert set(visible_students(boss)) == {claimed, unclaimed}


def test_a_superuser_sees_everyone(db):
    """T-F-M.6.2-4."""
    from matazim.access import visible_students

    root = make_user("root@example.com")
    root.is_superuser = True
    root.save(update_fields=["is_superuser"])
    student = make_student("someone@example.com")

    assert set(visible_students(root)) == {student}


def test_a_stranger_sees_nothing(db):
    """T-F-M.6.2-5: no role is not the same as a small role."""
    from matazim.access import visible_students

    make_student("member@example.com")
    assert not visible_students(make_user("stranger@example.com")).exists()


def test_role_precedence_is_admin_then_leader_then_student(db):
    """T-F-M.6.2-6: spec §4.2. One person can hold more than one.

    Written down rather than left to the accident of `if` ordering.
    """
    from matazim.access import role_of, visible_students
    from matazim.models import Leader, MemberProfile, Student

    user = make_user("all-three@example.com")
    Leader.objects.create(user=user)
    Student.objects.create(user=user, cohort_year=2026)
    MemberProfile.objects.create(user=user, is_admin=True)

    other = make_student("elsewhere@example.com", leader=make_leader("other@example.com"))

    assert role_of(user) == "admin"
    assert other in visible_students(user), "admin scope must win over leader scope"


def test_progress_crosses_the_boundary_in_one_join(db):
    """T-F-M.6.2-7: spec §4.5, proved now rather than discovered later.

    This query is why learning stays in babook's tables. Had we built our own
    progress model it would not exist, and we would be reconciling two sets of
    numbers forever.
    """
    from app.models import Course, Enrollment

    leader = make_leader("teach@example.com")
    mine = make_student("mine@example.com", leader=leader)
    theirs = make_student("theirs@example.com", leader=make_leader("elsewhere2@example.com"))

    course = Course.objects.create(slug="c1", title="הדרכה")
    Enrollment.objects.create(user=mine.user, course=course)
    Enrollment.objects.create(user=theirs.user, course=course)

    rows = Enrollment.objects.filter(user__matazim_student__leader=leader)
    assert [row.user for row in rows] == [mine.user]


# ---------------------------------------------------------------- F-M.6.3


def test_adminship_is_seeded_from_a_named_list(db):
    """T-F-M.6.3-1: REQ-M.68. Never self-served: the first admin could not use a screen."""
    from django.core.management import call_command

    from matazim.access import is_admin

    naomi = make_user("naomi@example.com")
    aviv = make_user("aviv@example.com")

    call_command("matazim_admins", grant=["naomi@example.com", "aviv@example.com"])
    assert is_admin(naomi) and is_admin(aviv)

    # Idempotent: it runs on every deploy.
    call_command("matazim_admins", grant=["naomi@example.com"])
    assert is_admin(naomi)


def test_adminship_can_be_taken_away(db):
    """T-F-M.6.3-2: granting without revoking is a one-way door."""
    from django.core.management import call_command

    from matazim.access import is_admin

    user = make_user("temp@example.com")
    call_command("matazim_admins", grant=["temp@example.com"])
    assert is_admin(user)

    call_command("matazim_admins", revoke=["temp@example.com"])
    user.refresh_from_db()
    assert not is_admin(user)


def test_an_unknown_email_is_reported_not_invented(db):
    """T-F-M.6.3-3: a typo must not silently create an account with admin rights."""
    from django.core.management import call_command

    call_command("matazim_admins", grant=["nobody-here@example.com"])
    assert not User.objects.filter(email="nobody-here@example.com").exists()


# ---------------------------------------------------------------- F-M.6.5


def test_deactivating_a_leader_destroys_nothing(db):
    """T-F-M.6.5-1: REQ-M.67. Same principle as retiring an entrance target."""
    from matazim.access import leader_of, visible_students

    leader = make_leader("leaving@example.com")
    student = make_student("kept@example.com", leader=leader)

    leader.is_active = False
    leader.save(update_fields=["is_active"])

    student.refresh_from_db()
    assert student.leader == leader, "the roster must survive"
    assert leader_of(leader.user) is None, "but they lose the leader view"
    assert not visible_students(leader.user).exists()


def test_an_inactive_leader_is_not_offered_to_join(db):
    """T-F-M.6.5-2: they stop taking new students."""
    from matazim.access import joinable_leaders

    active = make_leader("open@example.com")
    make_leader("closed@example.com", active=False)

    assert set(joinable_leaders()) == {active}


# ---------------------------------------------------------------- F-M.6.7


def test_adminship_can_be_granted_from_django_admin(db):
    """T-F-M.6.7-1: REQ-M.68's second path.

    Avi asked whether he could assign admins in production through the admin,
    and nothing of מט״צים was registered there at all. The command reading
    MATAZIM_ADMINS covers the deploy; this covers the day someone needs adding
    without one.
    """
    from django.contrib import admin

    from matazim.models import Leader, MemberProfile, Student, StudyClass

    for model in (MemberProfile, Leader, StudyClass, Student):
        assert model in admin.site._registry, f"{model.__name__} is not in Django admin"

    profile_admin = admin.site._registry[MemberProfile]
    assert (
        "is_admin" in profile_admin.list_editable
    ), "the whole point is flipping it from the list without a deploy"


def test_an_admin_can_find_the_students_nobody_has_taken(db):
    """T-F-M.6.7-2: REQ-M.65. A queue, not an error state."""
    from matazim.access import unclaimed_students

    leader = make_leader("has-some@example.com")
    make_student("taken@example.com", leader=leader)
    waiting = make_student("waiting@example.com", leader=None)

    assert set(unclaimed_students()) == {waiting}


# ---------------------------------------------------------------- F-M.6.8


def _client_as(client, email, admin=False, root=False):
    from matazim.models import MemberProfile

    user = make_user(email)
    if root:
        user.is_superuser = True
        user.save(update_fields=["is_superuser"])
    if admin:
        MemberProfile.objects.update_or_create(user=user, defaults={"is_admin": True})
    client.force_login(user)
    return user


def test_the_staff_area_has_one_door_and_it_is_admin_only(client, db):
    """T-F-M.6.8-1: REQ-M.69. The nav does not grow an item per tool."""
    from django.urls import reverse

    assert client.get(reverse("matazim:staff_home")).status_code in (302, 403)

    _client_as(client, "plain@example.com")
    assert client.get(reverse("matazim:staff_home")).status_code in (302, 403)

    client.logout()
    _client_as(client, "chief@example.com", admin=True)
    html = client.get(reverse("matazim:staff_home")).content.decode()
    assert reverse("matazim:staff_targets") in html
    assert reverse("matazim:staff_admins") in html


def test_only_admins_see_the_staff_door_in_the_nav(client, db):
    """T-F-M.6.8-2."""
    from django.urls import reverse

    _client_as(client, "member3@example.com")
    assert reverse("matazim:staff_home") not in client.get(reverse("matazim:home")).content.decode()

    client.logout()
    _client_as(client, "chief2@example.com", admin=True)
    assert reverse("matazim:staff_home") in client.get(reverse("matazim:home")).content.decode()


def test_an_admin_can_grant_adminship_by_email(client, db):
    """T-F-M.6.8-3: REQ-M.70."""
    from django.urls import reverse

    from matazim.access import is_admin

    _client_as(client, "chief3@example.com", admin=True)
    newcomer = make_user("newcomer@example.com")

    client.post(
        reverse("matazim:staff_admins"),
        {"action": "grant", "email": "newcomer@example.com"},
    )
    assert is_admin(newcomer)


def test_granting_never_creates_an_account(client, db):
    """T-F-M.6.8-4: a typo must not conjure the highest role in the system."""
    from django.urls import reverse

    _client_as(client, "chief4@example.com", admin=True)
    response = client.post(
        reverse("matazim:staff_admins"),
        {"action": "grant", "email": "typo@example.com"},
    )
    assert response.status_code == 200
    assert not User.objects.filter(email="typo@example.com").exists()


def test_an_admin_cannot_revoke_themselves(client, db):
    """T-F-M.6.8-5: the likeliest way to lose every admin is by accident."""
    from django.urls import reverse

    from matazim.access import is_admin

    me = _client_as(client, "careful@example.com", admin=True)
    client.post(
        reverse("matazim:staff_admins"),
        {"action": "revoke", "email": "careful@example.com"},
    )
    me.refresh_from_db()
    assert is_admin(me), "revoking yourself is how a program loses every admin"


def test_an_admin_can_revoke_someone_else(client, db):
    """T-F-M.6.8-6: granting without revoking is a one-way door."""
    from django.urls import reverse

    from matazim.access import is_admin
    from matazim.models import MemberProfile

    _client_as(client, "chief5@example.com", admin=True)
    other = make_user("other-admin@example.com")
    MemberProfile.objects.update_or_create(user=other, defaults={"is_admin": True})

    client.post(
        reverse("matazim:staff_admins"),
        {"action": "revoke", "email": "other-admin@example.com"},
    )
    other.refresh_from_db()
    assert not is_admin(other)


def test_a_site_owner_appears_on_the_list_of_who_has_power(client, db):
    """T-F-M.6.8-7: Avi, 2026-09-10, "I am the big chief admin of everything".

    A superuser holds every admin power whether or not the flag is set. Listing
    only the flag would let the site owner read this page and conclude they were
    not on it, which is the page lying about the thing it exists to show.
    """
    from django.urls import reverse

    root = _client_as(client, "salmon@example.com", root=True)
    html = client.get(reverse("matazim:staff_admins")).content.decode()

    assert "salmon@example.com" in html
    assert "מנהל/ת האתר" in html
    # And nobody offers to remove them, because nothing here could.
    body = html.split("salmon@example.com")[1][:400]
    assert "הסרת הרשאה" not in body
    assert root.is_superuser


# ---------------------------------------------------------------- F-M.6.9


def test_a_refusal_inside_the_walls_stays_inside_them(client, db):
    """T-F-M.6.9-1: REQ-M.2, found live in production.

    A 403 raised anywhere under /matazim/ rendered babook's page: its title, its
    drawer, its nav. The guard tests never saw it because they read templates
    under templates/matazim/ and pages we request successfully. An error page is
    neither, which is a reminder that a rule is only as good as the surface it
    is checked on.
    """
    from django.urls import reverse

    _client_as(client, "nosy@example.com")
    response = client.get(reverse("matazim:staff_admins"))

    assert response.status_code == 403
    html = response.content.decode()
    for leak in ("babook", "site-drawer", "nav-link px-2"):
        assert leak not in html, f"babook chrome leaked into a מט״צים error page: {leak}"
    assert "מט״צים" in html


def test_a_missing_page_inside_the_walls_stays_inside_them(client, db):
    """T-F-M.6.9-2: REQ-M.2, the 404 half."""
    response = client.get("/matazim/no-such-page/")
    assert response.status_code == 404
    html = response.content.decode()
    assert "babook" not in html
    assert "מט״צים" in html


def test_babooks_own_errors_are_left_alone(client, db):
    """T-F-M.6.9-3: RULE-4 in the other direction.

    We changed a project-wide setting, so the thing to prove is that we changed
    it only for ourselves.
    """
    response = client.get("/no-such-babook-page/")
    assert response.status_code == 404
    assert "מט״צים" not in response.content.decode()


def test_an_anonymous_visitor_meets_our_login_not_a_refusal(client, db):
    """T-F-M.6.9-4: a stranger has not done anything wrong yet."""
    from django.urls import reverse

    for name in ("matazim:staff_home", "matazim:staff_admins"):
        response = client.get(reverse(name))
        assert response.status_code == 302
        assert response.url.startswith(reverse("matazim:login"))


# ---------------------------------------------------------------- F-M.6.10


def _search(client, q):
    from django.urls import reverse

    return client.get(reverse("matazim:staff_user_search"), {"q": q}).json()["results"]


def test_the_picker_finds_someone_by_part_of_their_name(client, db):
    """T-F-M.6.10-1: REQ-M.71. Avi: typing נעמ should find נעמי.

    This is why a native datalist could not be used: browsers filter options by
    their value, so a Hebrew name would never match an option whose value is an
    email address.
    """
    from app.models import UserProfile

    naomi = make_user("n.levi@example.com")
    UserProfile.objects.update_or_create(user=naomi, defaults={"display_name": "נעמי לוי"})
    make_user("someone.else@example.com")

    _client_as(client, "chief6@example.com", admin=True)
    found = _search(client, "נעמ")

    assert [row["email"] for row in found] == ["n.levi@example.com"]
    assert found[0]["name"] == "נעמי לוי"


def test_the_picker_finds_someone_by_part_of_their_email(client, db):
    """T-F-M.6.10-2: a fragment of an address finds its owner."""
    make_user("dvora.cohen@example.com")
    make_user("nothing@example.com")

    _client_as(client, "chief7@example.com", admin=True)
    assert [row["email"] for row in _search(client, "dvora")] == ["dvora.cohen@example.com"]


def test_the_picker_says_who_is_already_an_admin(client, db):
    """T-F-M.6.10-3: offering someone as if they were not is a small lie."""
    from matazim.models import MemberProfile

    existing = make_user("already@example.com")
    MemberProfile.objects.update_or_create(user=existing, defaults={"is_admin": True})

    _client_as(client, "chief8@example.com", admin=True)
    found = _search(client, "already")
    assert found[0]["is_admin"] is True


def test_the_picker_cannot_be_used_to_walk_the_user_table(client, db):
    """T-F-M.6.10-4: it searches every account, and many belong to minors.

    Under two characters there is nothing to look for, and an empty box must not
    return the platform.
    """
    for i in range(5):
        make_user(f"person{i}@example.com")

    _client_as(client, "chief9@example.com", admin=True)
    assert _search(client, "") == []
    assert _search(client, "a") == []


def test_the_picker_is_admin_only(client, db):
    """T-F-M.6.10-5: a member must not be able to enumerate anyone."""
    from django.urls import reverse

    make_user("hidden@example.com")

    assert client.get(reverse("matazim:staff_user_search"), {"q": "hidden"}).status_code in (
        302,
        403,
    )

    _client_as(client, "plain2@example.com")
    assert client.get(reverse("matazim:staff_user_search"), {"q": "hidden"}).status_code in (
        302,
        403,
    )


def test_the_picker_returns_a_page_not_the_platform(client, db):
    """T-F-M.6.10-6: capped, so a broad query stays a list and not a dump."""
    for i in range(15):
        make_user(f"wide{i}@example.com")

    _client_as(client, "chief10@example.com", admin=True)
    assert len(_search(client, "wide")) == 10


def test_someone_with_no_name_is_not_listed_twice(client, db):
    """T-F-M.6.10-7: caught by looking at the page, not by a unit.

    Without a display name the row rendered the email beside itself:
    "x@y.com x@y.com".
    """
    from django.urls import reverse

    _client_as(client, "chief11@example.com", admin=True, root=True)
    html = client.get(reverse("matazim:staff_admins")).content.decode()
    rows = html.split("mz-training-title")
    mine = next(part for part in rows if "chief11@example.com" in part)
    assert mine.count("chief11@example.com") == 1


def test_the_page_says_which_kind_of_admin_each_person_is(client, db):
    """T-F-M.6.10-8: Avi asked whether Naomi ended up a site admin or a program one.

    The page could not answer that: a site owner got a tag and a granted admin
    got none, only a revoke link. A page about who has power should say what
    kind of power, since that is the question it exists for.
    """
    from django.urls import reverse

    from matazim.models import MemberProfile

    granted = make_user("naomi.real@example.com")
    MemberProfile.objects.update_or_create(user=granted, defaults={"is_admin": True})

    _client_as(client, "root2@example.com", root=True)
    html = client.get(reverse("matazim:staff_admins")).content.decode()

    assert "מנהל/ת האתר" in html
    assert "מנהל/ת התוכנית" in html

    row = html.split("naomi.real@example.com")[1][:600]
    assert "מנהל/ת התוכנית" in row
    assert "מנהל/ת האתר" not in row, "a granted admin must not read as a site owner"
