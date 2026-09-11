"""SPR-M.17 — The cohort, and the school report.

REQ-M.24, the last screen the spec names for the program manager and the one it
calls Litala's.

Two kinds of failure are possible here and they need different tests.

**Arithmetic that disagrees with the screens.** A funnel is a lot of counting,
and a count computed here rather than read from the same place as the roster is
a third opinion about the same teenagers. So the totals are compared against the
roster they came from, not merely asserted to be plausible.

**A number that crosses a world.** Aggregates are exactly where tenancy leaks
quietly: nobody notices that a total is four instead of three, and the leak has
no name attached to make it obvious. So every figure is checked with a second
institution present.

The export is aggregate on purpose, and one test exists to keep it that way.

Traces: REQ-M.24, REQ-M.88, §4.10.
"""

import csv
import io

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm17

PASSWORD = "sprm17-pass-9024"


def make_user(email, name=""):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name or email})
    return user


def make_manager(email="naomi@example.com", name="נעמי"):
    from matazim.models import MemberProfile

    user = make_user(email, name)
    MemberProfile.objects.update_or_create(user=user, defaults={"is_program_manager": True})
    return user


def make_leader(manager, email, name, school):
    from matazim.models import Leader, StudyClass

    leader = Leader.objects.create(
        user=make_user(email, name), program_manager=manager, approved_at=timezone.now()
    )
    klass = StudyClass.objects.create(leader=leader, name="ט1", school_name=school)
    return leader, klass


def make_student(leader, klass, email, name, status):
    from matazim.models import MemberProfile, Student

    user = make_user(email, name)
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now(),
            "birth_year": timezone.now().year - 14,
            "guardian_consent_at": timezone.now(),
        },
    )
    student = Student.objects.create(user=user, leader=leader, status=status)
    student.classes.add(klass)
    return student


def a_world(tag, manager=None):
    """One institution with two leaders in two schools and a spread of stages."""
    from matazim.models import Student

    manager = manager or make_manager(f"pm-{tag}@example.com", f"מנהלת {tag}")
    lead_a, class_a = make_leader(manager, f"la-{tag}@example.com", f"מוביל א {tag}", f"עתיד {tag}")
    lead_b, class_b = make_leader(manager, f"lb-{tag}@example.com", f"מוביל ב {tag}", f"אורט {tag}")

    make_student(lead_a, class_a, f"s1-{tag}@example.com", f"א1 {tag}", Student.CERTIFIED)
    make_student(lead_a, class_a, f"s2-{tag}@example.com", f"א2 {tag}", Student.IN_TRAINING)
    make_student(lead_a, class_a, f"s3-{tag}@example.com", f"א3 {tag}", Student.IN_TRAINING)
    make_student(lead_b, class_b, f"s4-{tag}@example.com", f"ב1 {tag}", Student.APPLIED)

    return {
        "manager": manager,
        "a": lead_a,
        "b": lead_b,
        "school_a": f"עתיד {tag}",
        "school_b": f"אורט {tag}",
    }


# ------------------------------------------------------------- the funnel


def test_the_funnel_counts_every_stage(client, db):
    """T-F-M.17.1-1: REQ-M.24. The shape of the programme, in numbers."""
    world = a_world("north")
    client.force_login(world["manager"])

    html = client.get(reverse("matazim:cohort")).content.decode()
    assert "לומדים" in html
    assert "מדריכים" in html
    assert "4" in html, "four students should be counted somewhere"


def test_the_funnel_total_agrees_with_the_roster(client, db):
    """T-F-M.17.1-2: REQ-M.24, and the failure this sprint can cause.

    A funnel is a lot of counting. A count computed here rather than read from
    the same place as the roster is a third opinion about the same teenagers,
    and nobody would notice it was wrong.
    """
    from matazim.access import visible_students

    world = a_world("north")
    client.force_login(world["manager"])

    response = client.get(reverse("matazim:cohort"))
    total = response.context["funnel_total"]
    assert total == visible_students(world["manager"]).count() == 4


def test_the_funnel_counts_only_this_world(client, db):
    """T-F-M.17.1-3: REQ-M.88.

    Aggregates are where tenancy leaks quietly: a total of eight instead of four
    has no name attached to make it obvious.
    """
    north = a_world("north")
    a_world("south")
    client.force_login(north["manager"])

    response = client.get(reverse("matazim:cohort"))
    assert response.context["funnel_total"] == 4, "another world's students were counted"


# ------------------------------------------------------------- by leader


def test_it_breaks_down_by_leader(client, db):
    """T-F-M.17.2-1: REQ-M.24. Who has how many, without opening each one."""
    world = a_world("north")
    client.force_login(world["manager"])

    rows = {r["leader"].pk: r for r in client.get(reverse("matazim:cohort")).context["by_leader"]}
    assert rows[world["a"].pk]["total"] == 3
    assert rows[world["b"].pk]["total"] == 1


def test_a_leader_with_nobody_still_appears(client, db):
    """T-F-M.17.2-2: REQ-M.24.

    A leader with no students is the one a program manager most needs to see,
    and a report built by grouping students would drop them entirely.
    """
    world = a_world("north")
    empty, _klass = make_leader(
        world["manager"], "idle@example.com", "מוביל בלי איש", "בית ספר ריק"
    )
    client.force_login(world["manager"])

    rows = {r["leader"].pk: r for r in client.get(reverse("matazim:cohort")).context["by_leader"]}
    assert empty.pk in rows, "a leader with no students fell out of the report"
    assert rows[empty.pk]["total"] == 0


# ------------------------------------------------------------- by school


def test_it_groups_by_school(client, db):
    """T-F-M.17.3-1: REQ-M.24. What Litala's brief actually asks for."""
    world = a_world("north")
    client.force_login(world["manager"])

    schools = {r["school"]: r for r in client.get(reverse("matazim:cohort")).context["by_school"]}
    assert schools[world["school_a"]]["total"] == 3
    assert schools[world["school_b"]]["total"] == 1


def test_a_student_in_no_class_is_still_counted_somewhere(client, db):
    """T-F-M.17.3-2: REQ-M.24, and Q14's consequence.

    A class is offered and never required, so grouping by school through classes
    drops anybody who is in none. They are real students and the total has to
    include them, or the school report quietly undercounts the programme.
    """
    from matazim.models import Student

    world = a_world("north")
    make_student(world["a"], None, "loose@example.com", "בלי כיתה", Student.IN_TRAINING)
    client.force_login(world["manager"])

    context = client.get(reverse("matazim:cohort")).context
    assert context["funnel_total"] == 5
    assert sum(r["total"] for r in context["by_school"]) == 5, "somebody fell between schools"


# ------------------------------------------------------------- the export


def test_the_export_is_a_file(client, db):
    """T-F-M.17.4-1: REQ-M.24."""
    world = a_world("north")
    client.force_login(world["manager"])

    response = client.get(reverse("matazim:cohort_export"))
    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]


def test_the_export_names_no_minor(client, db):
    """T-F-M.17.4-2: §4.10, and the judgement this sprint turns on.

    A spreadsheet of named teenagers is the version somebody asks for first and
    the one artefact that leaves the system entirely: it lands in a download
    folder, gets mailed onward, and outlives every access rule we wrote. A
    school-level report does not need it, so the export is aggregate.
    """
    world = a_world("north")
    client.force_login(world["manager"])

    body = client.get(reverse("matazim:cohort_export")).content.decode("utf-8-sig")
    for name in ("א1 north", "א2 north", "ב1 north"):
        assert name not in body, f"the export names a minor: {name}"
    for email in ("s1-north@example.com", "s2-north@example.com"):
        assert email not in body, "the export carries a minor's address"


def test_the_export_still_says_something_useful(client, db):
    """T-F-M.17.4-3: aggregate is not the same as empty.

    Refusing to name minors is only defensible if the report still does its job.
    """
    world = a_world("north")
    client.force_login(world["manager"])

    body = client.get(reverse("matazim:cohort_export")).content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(body)))
    flat = "\n".join(",".join(r) for r in rows)

    assert world["school_a"] in flat, "the school breakdown is missing"
    assert "מוביל א north" in flat, "leaders are staff, and naming them is the point"
    assert len(rows) > 4


def test_the_export_cannot_reach_another_world(client, db):
    """T-F-M.17.5-1: REQ-M.88. An export endpoint is a lovely thing to walk."""
    north = a_world("north")
    a_world("south")
    client.force_login(north["manager"])

    body = client.get(reverse("matazim:cohort_export")).content.decode("utf-8-sig")
    assert "עתיד south" not in body
    assert "מוביל א south" not in body


# ------------------------------------------------------------- who may look


def test_root_sees_across_worlds(client, db):
    """T-F-M.17.5-2: REQ-M.88, tested rather than assumed."""
    a_world("north")
    a_world("south")
    root = User.objects.create_superuser("root@example.com", "root@example.com", PASSWORD)
    client.force_login(root)

    assert client.get(reverse("matazim:cohort")).context["funnel_total"] == 8


def test_a_leader_cannot_open_the_cohort_report(client, db):
    """T-F-M.17.5-3: it is the programme's shape, not a leader's business."""
    world = a_world("north")
    client.force_login(world["a"].user)

    assert client.get(reverse("matazim:cohort")).status_code in (302, 403)
    assert client.get(reverse("matazim:cohort_export")).status_code in (302, 403)


def test_a_member_cannot_either(client, db):
    """T-F-M.17.5-4."""
    from matazim.models import Student

    world = a_world("north")
    student = Student.objects.filter(leader=world["a"]).first()
    client.force_login(student.user)

    assert client.get(reverse("matazim:cohort")).status_code in (302, 403)


def test_she_can_reach_it_without_knowing_the_url(client, db):
    """T-F-M.17.1-4: the lesson this product has learned four times now."""
    world = a_world("north")
    client.force_login(world["manager"])

    html = client.get(reverse("matazim:pm_leaders")).content.decode()
    assert reverse("matazim:cohort") in html


def test_the_report_does_not_grow_a_query_per_leader(django_assert_num_queries, client, db):
    """T-F-M.17.2-3: the same discipline as the roster.

    A report that costs a query per leader is a report that gets slower exactly
    as the programme succeeds.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    world = a_world("north")
    client.force_login(world["manager"])

    with CaptureQueriesContext(connection) as first:
        client.get(reverse("matazim:cohort"))

    for n in range(6):
        make_leader(world["manager"], f"more{n}@example.com", f"מוביל {n}", f"בית ספר {n}")

    with django_assert_num_queries(len(first)):
        client.get(reverse("matazim:cohort"))
