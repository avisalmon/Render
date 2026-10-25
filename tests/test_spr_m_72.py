"""SPR-M.72 - A view from above of every school and every student's progress.

Lital, by mail, 2026-10-25 18:24: "אני רוצה לראות מבט על של כל בתי הספר כל
ההתקדמות של התלמידים, זה אפשרי?"

`/matazim/staff/schools/`: one panel per school with its leaders, the count at
each stage, who passed the screening test, the average through the track and
the list of its students. Program managers and root only, scoped like every
other report, and people who signed up but have not started are a number,
never names.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

URL = "/matazim/staff/schools/"


def _user(name, display=""):
    from app.models import UserProfile

    user = User.objects.create_user(username=f"{name}@example.com", email=f"{name}@example.com",
                                    password="sprm72-pass")
    if display:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.display_name = display
        profile.save()
    return user


@pytest.fixture
def world(db):
    from matazim.models import (Institution, Leader, MemberProfile, School, Student,
                                StudyClass)

    inst = Institution.objects.create(name="רשת עתיד")
    pm = _user("pm")
    inst.managers.add(pm)
    hanna = School.objects.get_or_create(name="עתיד חנה סנש")[0]
    sajur = School.objects.get_or_create(name="עתיד סאג'ור")[0]

    leader = Leader.objects.create(user=_user("liron", "לירון טל"), institution=inst,
                                   approved_at=timezone.now())
    klass = StudyClass.objects.create(leader=leader, name="ט1", school_name=hanna.name)

    passed = Student.objects.create(user=_user("kid1", "נועה"), leader=leader,
                                    status=Student.IN_TRAINING)
    passed.classes.add(klass)
    MemberProfile.objects.create(user=passed.user, school=hanna,
                                 entrance_test_passed_at=timezone.now())
    waiting = Student.objects.create(user=_user("kid2", "איתי"), leader=leader)
    MemberProfile.objects.create(user=waiting.user, school=hanna)

    # Signed up from Sajur, no Student row yet: counted, never named.
    MemberProfile.objects.create(user=_user("kid3", "שם-שלא-יוצג"), school=sajur)

    # Another institution's student must not appear.
    other = Institution.objects.create(name="רשת אחרת")
    stranger_leader = Leader.objects.create(user=_user("far"), institution=other,
                                            approved_at=timezone.now())
    far = Student.objects.create(user=_user("kid4", "רחוק-מאוד"), leader=stranger_leader)
    far_class = StudyClass.objects.create(leader=stranger_leader, name="x", school_name="בית ספר זר")
    far.classes.add(far_class)
    return {"pm": pm, "leader": leader, "passed": passed, "waiting": waiting}


def test_a_program_manager_sees_every_school_and_its_students(client, world):
    client.force_login(world["pm"])
    resp = client.get(URL)
    assert resp.status_code == 200
    page = resp.content.decode()
    assert "כל בתי הספר" in page
    for text in ("עתיד חנה סנש", "עתיד סאג", "לירון טל", "נועה", "איתי",
                 "עברו את מבחן המיון", "התקדמות ממוצעת במסלול"):
        assert text in page
    assert f"/matazim/leader/students/{world['passed'].pk}/" in page


def test_counts_per_school_are_right(world):
    from matazim.schools import school_rows, totals

    rows = {r["school"]: r for r in school_rows(world["pm"])}
    hanna = rows["עתיד חנה סנש"]
    assert hanna["total"] == 2
    assert hanna["passed_test"] == 1
    assert hanna["leaders"] == ["לירון טל"]
    stages = {s["label"]: s["count"] for s in hanna["stage_list"]}
    assert stages["לומדים"] == 1 and stages["מתמיינים"] == 1
    sajur = rows["עתיד סאג'ור"]
    assert sajur["total"] == 0 and sajur["not_started"] == 1
    assert totals(list(rows.values()))["not_started"] == 1


def test_signed_up_but_not_started_is_a_number_not_a_name(client, world):
    client.force_login(world["pm"])
    page = client.get(URL).content.decode()
    assert "שם-שלא-יוצג" not in page


def test_another_institution_does_not_leak(client, world):
    client.force_login(world["pm"])
    page = client.get(URL).content.decode()
    assert "רחוק-מאוד" not in page and "בית ספר זר" not in page


def test_root_sees_everyone(client, world):
    root = User.objects.create_superuser("root", "root@example.com", "x")
    client.force_login(root)
    page = client.get(URL).content.decode()
    assert "רחוק-מאוד" in page


@pytest.mark.parametrize("who", ["leader", "student", "anon"])
def test_nobody_else_gets_in(client, world, who):
    if who == "leader":
        client.force_login(world["leader"].user)
    elif who == "student":
        client.force_login(world["passed"].user)
    resp = client.get(URL)
    assert resp.status_code in (302, 403)


def test_reachable_from_the_cohort_page_and_the_staff_home(client, world):
    client.force_login(world["pm"])
    assert URL in client.get("/matazim/staff/cohort/").content.decode()
    assert URL in client.get("/matazim/staff/").content.decode()


def test_the_page_does_not_grow_a_query_per_student(client, world, django_assert_max_num_queries):
    from matazim.models import Student

    client.force_login(world["pm"])
    client.get(URL)
    for i in range(10):
        s = Student.objects.create(user=_user(f"more{i}", f"עוד{i}"), leader=world["leader"])
        s.classes.add(world["leader"].classes.first())
    with django_assert_max_num_queries(40):
        assert client.get(URL).status_code == 200
