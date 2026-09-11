"""SPR-M.13 — The worlds do not touch.

Several institutions will adopt this platform, each with its own program
manager, its own leaders and its own students, and they must be separate
products that happen to share a database, a course engine and a login screen.

Most of this file is one idea tested many ways: **two complete worlds, and
nothing crosses**. That repetition is the point. A tenancy bug is not a crash,
it is a screen quietly showing one institution's teenagers to another's staff,
and it would look completely normal to whoever was reading it. The only defence
is to enumerate every door and try each one from the wrong side.

Root is the exception, and is tested as one rather than left implied.

Traces: REQ-M.88, and it supersedes the "admins see everyone" half of REQ-M.22.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm13

PASSWORD = "sprm13-pass-8842"


def make_user(email, name=""):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name or email})
    return user


def make_world(tag, *, students=2):
    """One institution, entire: a program manager, a leader, a class, students.

    Returned as a dict rather than a tuple because the tests below read better
    when they can say `north["student"]` than `north[3]`.
    """
    from matazim.models import Leader, MemberProfile, Student, StudyClass

    manager = make_user(f"pm-{tag}@example.com", f"מנהלת {tag}")
    MemberProfile.objects.update_or_create(user=manager, defaults={"is_program_manager": True})

    leader = Leader.objects.create(
        user=make_user(f"leader-{tag}@example.com", f"מוביל {tag}"),
        program_manager=manager,
    )
    klass = StudyClass.objects.create(leader=leader, name="ט1", school_name=f"בית ספר {tag}")

    made = []
    for i in range(students):
        user = make_user(f"kid{i}-{tag}@example.com", f"תלמיד {i} {tag}")
        MemberProfile.objects.update_or_create(
            user=user,
            defaults={
                "entrance_test_passed_at": timezone.now(),
                "birth_year": timezone.now().year - 14,
                "guardian_consent_at": timezone.now(),
            },
        )
        student = Student.objects.create(user=user, leader=leader)
        student.classes.add(klass)
        made.append(student)

    return {
        "manager": manager,
        "leader": leader,
        "class": klass,
        "students": made,
        "student": made[0],
    }


# ------------------------------------------------------ the querysets themselves


def test_a_program_manager_sees_only_their_own_leaders(db):
    """T-F-M.13.2-1: REQ-M.88. The floor the whole epic stands on."""
    from matazim.access import visible_leaders

    north, south = make_world("north"), make_world("south")

    mine = set(visible_leaders(north["manager"]))
    assert north["leader"] in mine
    assert south["leader"] not in mine


def test_a_program_manager_sees_only_their_own_leaders_students(db):
    """T-F-M.13.2-2: REQ-M.88.

    The one that actually matters. Leaders are staff; students are named minors,
    and showing one institution's to another is the failure this is all for.
    """
    from matazim.access import visible_students

    north, south = make_world("north"), make_world("south")

    mine = set(visible_students(north["manager"]))
    assert set(north["students"]) <= mine
    assert not (set(south["students"]) & mine)


def test_root_crosses_every_world(db):
    """T-F-M.13.2-3: REQ-M.88. Deliberate, and tested rather than assumed."""
    from matazim.access import visible_leaders, visible_students

    north, south = make_world("north"), make_world("south")
    root = User.objects.create_superuser("root@example.com", "root@example.com", PASSWORD)

    assert {north["leader"], south["leader"]} <= set(visible_leaders(root))
    assert set(north["students"] + south["students"]) <= set(visible_students(root))


def test_a_leader_is_unaffected_by_tenancy(db):
    """T-F-M.13.2-4: REQ-M.22 still holds underneath REQ-M.88.

    Adding a floor above must not change the floor below.
    """
    from matazim.access import visible_students

    north, south = make_world("north"), make_world("south")

    mine = set(visible_students(north["leader"].user))
    assert set(north["students"]) == mine
    assert not (set(south["students"]) & mine)


def test_an_orphaned_leader_belongs_to_nobody_but_root(db):
    """T-F-M.13.1-1: REQ-M.88.

    A null owner means orphaned, not shared. That is the safe direction to fail
    in: invisible is recoverable by reassigning, visible-to-everyone is not
    recoverable at all once somebody has read the screen.
    """
    from matazim.access import visible_leaders
    from matazim.models import Leader

    north = make_world("north")
    orphan = Leader.objects.create(user=make_user("orphan@example.com"))
    root = User.objects.create_superuser("root@example.com", "root@example.com", PASSWORD)

    assert orphan not in set(visible_leaders(north["manager"]))
    assert orphan in set(visible_leaders(root))


# ------------------------------------------------------ every door, from outside


def test_no_screen_lets_a_program_manager_reach_the_other_world(client, db):
    """T-F-M.13.4-1: REQ-M.88, and the point of this sprint.

    Enumerated rather than sampled. A tenancy hole is invisible by nature: the
    page renders perfectly, it simply contains somebody else's children. So
    every screen that takes an id is tried from the wrong side, and any of them
    answering 200 is a leak.
    """
    north, south = make_world("north"), make_world("south")
    client.force_login(north["manager"])

    doors = [
        ("matazim:staff_leader", [south["leader"].pk]),
        ("matazim:leader_qr", [south["leader"].pk]),
        ("matazim:student", [south["student"].pk]),
    ]
    leaked = []
    for name, args in doors:
        response = client.get(reverse(name, args=args))
        if response.status_code == 200:
            leaked.append(f"{name} answered 200 for another world")
    assert not leaked, "\n".join(leaked)


def test_no_write_crosses_either(client, db):
    """T-F-M.13.4-2: REQ-M.88.

    Reads are the obvious hole. A write that crosses is worse, because it
    changes another institution's data and leaves no trace on any screen the
    victim looks at.
    """
    from matazim.models import Leader, Student

    north, south = make_world("north"), make_world("south")
    client.force_login(north["manager"])

    before_code = south["leader"].join_code
    client.post(reverse("matazim:staff_leader", args=[south["leader"].pk]), {"action": "rotate"})
    south["leader"].refresh_from_db()
    assert south["leader"].join_code == before_code, "rotated another world's join code"

    client.post(reverse("matazim:certify", args=[south["student"].pk]), {"action": "certify"})
    south["student"].refresh_from_db()
    assert south["student"].status != Student.CERTIFIED, "certified another world's student"

    assert Leader.objects.filter(pk=south["leader"].pk, is_active=True).exists()


def test_the_leader_list_shows_only_this_world(client, db):
    """T-F-M.13.3-1: REQ-M.88, on the screen she opens most."""
    north, south = make_world("north"), make_world("south")
    client.force_login(north["manager"])

    html = client.get(reverse("matazim:staff_leaders")).content.decode()
    # The list renders display names, not addresses, so assert on what a reader
    # would actually see rather than on what the row happens to contain.
    assert "מוביל north" in html
    assert "מוביל south" not in html, "another world's leader on the list"


def test_the_roster_shows_only_this_world(client, db):
    """T-F-M.13.3-2: REQ-M.88.

    The roster is `visible_students` rendered, so this is really a test that the
    screen asks the access module rather than building its own queryset.
    """
    north, south = make_world("north"), make_world("south")
    client.force_login(north["manager"])

    html = client.get(reverse("matazim:roster")).content.decode()
    assert "תלמיד 0 north" in html
    assert "תלמיד 0 south" not in html


def test_search_cannot_be_used_to_reach_across(client, db):
    """T-F-M.13.4-3: REQ-M.88.

    A filter applied on top of a scoped queryset stays scoped, but only if the
    scoping came first. Searching for a name that exists only in the other world
    must find nothing, not find it.
    """
    north, south = make_world("north"), make_world("south")
    client.force_login(north["manager"])

    html = client.get(reverse("matazim:roster"), {"q": "south"}).content.decode()
    assert "תלמיד 0 south" not in html


def test_a_program_manager_cannot_file_a_student_into_another_worlds_class(client, db):
    """T-F-M.13.4-4: REQ-M.88, on the one write that takes an id from a form."""
    north, south = make_world("north"), make_world("south")
    client.force_login(north["manager"])

    client.post(
        reverse("matazim:student", args=[north["student"].pk]),
        {"action": "set_classes", "classes": [south["class"].pk]},
    )
    assert not south["class"].students.filter(pk=north["student"].pk).exists()
