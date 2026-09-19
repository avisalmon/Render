"""SPR-M.52 — the shelf: הדרכות a leader opens for their own מט״צים.

Avi, 2026-09-19:

> "We want everybody that is in מט״צים, any student, to see the availability of
> trainings that are available in babook, but not all of them. I want to be able
> as a leader to decide what training I want to expose for my students to see
> that are available for them to take. And then they take it inside מט״צים, but
> with the system of babook. Now, it's not about certification."

That last sentence is the design. REQ-M.76 does not move: a מט״צ מוסמך is the
entrance test, both Scratch courses, and the leader's approval. This is
opportunity, and the screens are built so that a card here can never be mistaken
for a card up there.

Possible at all only since SPR-M.51, which closed the pipe: a course taken here
now really works, with babook's hand-ins, gates and certificates behind it.

**The load-bearing test is `test_a_course_nobody_offered_stays_shut`.** This
sprint turns a guard that allowed exactly two slugs into one that consults a
rule, and seventeen published courses sit on the other side of it. The failure
mode is not a broken screen, it is a quiet widening: everything looks right and
every member can reach everything.

Traces: REQ-M.65, REQ-M.76, REQ-M.114, RULE-1, RULE-3.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

pytestmark = pytest.mark.sprm52

PASSWORD = "sprm52-pass-6621"


def _course(slug, title="הדרכה"):
    from app.models import Course, Video

    course = Course.objects.create(slug=slug, title=title, is_published=True)
    Video.objects.create(course=course, title="שיעור 1", lesson_order=1,
                         bunny_video_id="abc123")
    return course


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, MemberProfile, Student

    for slug in ("scratch", "scratch-advanced"):
        _course(slug, "סקראץ׳")
    _course("arduino", "ארדואינו")
    _course("django", "Django")
    _course("fpga", "FPGA")

    root = User.objects.create_superuser("root@example.com", "root@example.com", PASSWORD)
    inst = Institution.objects.create(name="רשת אחת")
    inst.managers.add(_user("pm@example.com", "נעמי"))

    leaders = {}
    for key, email in (("mine", "l1@example.com"), ("other", "l2@example.com")):
        leaders[key] = Leader.objects.create(
            user=_user(email, "מוביל"), institution=inst, approved_at=timezone.now()
        )

    members = {}
    for key, email, leader in (("mine", "kid1@example.com", leaders["mine"]),
                               ("theirs", "kid2@example.com", leaders["other"]),
                               ("loose", "kid3@example.com", None)):
        user = _user(email, "מט״צ")
        MemberProfile.objects.update_or_create(
            user=user,
            defaults={"entrance_test_passed_at": timezone.now(),
                      "birth_year": timezone.now().year - 14,
                      "guardian_consent_at": timezone.now(),
                      "welcome_accepted_at": timezone.now()},
        )
        members[key] = Student.objects.create(
            user=user, leader=leader, status=Student.IN_TRAINING
        )
    return {"root": root, "leaders": leaders, "members": members}


def _offer(slug, by):
    from matazim.models import OfferedCourse

    return OfferedCourse.objects.create(slug=slug, added_by=by)


def _shelve(leader, slug):
    from matazim.models import LeaderCourse

    return LeaderCourse.objects.create(leader=leader, slug=slug)


# ------------------------------------------------- the one that matters


def test_a_course_nobody_offered_stays_shut(client, world):
    """Seventeen published courses sit behind this guard. Widening it is the
    failure nobody would see: every screen renders, every member reaches
    everything."""
    from matazim.access import visible_course_slugs

    member = world["members"]["mine"]
    assert "django" not in visible_course_slugs(member.user)

    client.force_login(member.user)
    assert client.get("/matazim/learn/django/").status_code == 404
    assert client.get("/matazim/learn/django/1/").status_code == 404


def test_one_leaders_shelf_is_not_anothers(client, world):
    """The same shape as every other rule here: a leader decides for their own
    members and nobody else's."""
    from matazim.access import visible_course_slugs

    _offer("arduino", world["root"])
    _shelve(world["leaders"]["mine"], "arduino")

    assert "arduino" in visible_course_slugs(world["members"]["mine"].user)
    assert "arduino" not in visible_course_slugs(world["members"]["theirs"].user)

    client.force_login(world["members"]["theirs"].user)
    assert client.get("/matazim/learn/arduino/").status_code == 404


def test_a_leader_cannot_shelve_what_root_never_offered(client, world):
    """The outer layer is a gate, not a suggestion. Posting a slug straight at
    the screen is how somebody would find out."""
    from matazim.models import LeaderCourse

    client.force_login(world["leaders"]["mine"].user.__class__.objects.get(
        pk=world["leaders"]["mine"].user_id))
    resp = client.post("/matazim/leader/courses/", {"slug": "fpga"})
    assert resp.status_code in (302, 200)
    assert not LeaderCourse.objects.filter(slug="fpga").exists()


# ------------------------------------------------- what stays open


def test_the_programmes_own_two_are_never_withdrawable(world):
    """REQ-M.76's courses are what a מט״צ is made of. No pool and no shelf can
    take them away, including from a member with no leader at all."""
    from matazim.access import visible_course_slugs

    for key in ("mine", "theirs", "loose"):
        slugs = visible_course_slugs(world["members"][key].user)
        assert {"scratch", "scratch-advanced"} <= slugs


def test_a_member_keeps_a_course_they_already_started(world):
    """Taking away something somebody is half-way through is not curation.

    The course is retired from the pool *and* absent from their shelf, and it
    stays theirs because they have an enrolment.
    """
    from app.models import Course, Enrollment
    from matazim.access import visible_course_slugs
    from matazim.models import OfferedCourse

    member = world["members"]["loose"]
    Enrollment.objects.create(user=member.user, course=Course.objects.get(slug="django"))
    OfferedCourse.objects.create(slug="django", is_active=False)

    assert "django" in visible_course_slugs(member.user)


def test_retiring_a_course_closes_it_to_members_who_had_not_started(world):
    """The second layer, which the perturbation run showed nothing covered.

    A leader's shelf is filtered against the live pool every time it is read,
    not only when a course is chosen. So withdrawing one closes it to the
    members who had not begun it, while `test_a_member_keeps_a_course_they_
    already_started` holds the other half: whoever had begun it keeps it.
    """
    from matazim.access import visible_course_slugs
    from matazim.models import OfferedCourse

    row = _offer("arduino", world["root"])
    _shelve(world["leaders"]["mine"], "arduino")
    member = world["members"]["mine"]
    assert "arduino" in visible_course_slugs(member.user)

    row.is_active = False
    row.save()
    assert "arduino" not in visible_course_slugs(member.user)
    assert OfferedCourse.objects.filter(slug="arduino").exists(), "withdrawal is a flag"


def test_retiring_a_course_does_not_delete_anybodys_progress(world):
    """Withdrawal is a flag. Progress and certificates live in babook's tables
    and never belonged to the `OfferedCourse` row."""
    from app.models import Course, CourseCertificate, Enrollment

    member = world["members"]["mine"]
    course = Course.objects.get(slug="arduino")
    Enrollment.objects.create(user=member.user, course=course)
    CourseCertificate.objects.create(user=member.user, course=course)

    row = _offer("arduino", world["root"])
    row.is_active = False
    row.save()

    assert Enrollment.objects.filter(user=member.user, course=course).exists()
    assert CourseCertificate.objects.filter(user=member.user, course=course).exists()


# ------------------------------------------------- who may decide


def test_only_root_sets_the_pool(client, world):
    """REQ-M.114's shape: the widest decisions are root's. A program manager
    runs a programme; this says what the programme *is*."""
    from matazim.models import OfferedCourse

    manager = User.objects.get(username="pm@example.com")
    client.force_login(manager)
    assert client.get("/matazim/staff/offered/").status_code == 403
    client.post("/matazim/staff/offered/", {"slug": "arduino"})
    assert not OfferedCourse.objects.filter(slug="arduino").exists()

    client.force_login(world["root"])
    assert client.get("/matazim/staff/offered/").status_code == 200
    client.post("/matazim/staff/offered/", {"slug": "arduino"})
    assert OfferedCourse.objects.filter(slug="arduino", is_active=True).exists()


def test_a_member_cannot_reach_either_control_screen(client, world):
    client.force_login(world["members"]["mine"].user)
    assert client.get("/matazim/staff/offered/").status_code == 403
    assert client.get("/matazim/leader/courses/").status_code == 403


# ------------------------------------------------- it is not a requirement


def test_the_shelf_changes_nothing_about_certification(client, world):
    """Avi: "it's not about certification." Asserted rather than trusted,
    because the whole feature would be tempting to wire into eligibility."""
    from matazim.certification import eligibility

    member = world["members"]["mine"]
    before = eligibility(member)

    _offer("arduino", world["root"])
    _shelve(world["leaders"]["mine"], "arduino")

    after = eligibility(member)
    assert after.missing_courses == before.missing_courses
    assert sorted(after.missing_courses) == ["scratch", "scratch-advanced"]


# ------------------------------------------------- the same rules, over REST


def test_the_api_refuses_a_leader_who_would_widen_the_pool(client, world):
    """Methodology Rule 6 gave these two models endpoints, and SPR-M.50's
    finding says what to check first: a screen that refuses and an endpoint
    that accepts is a locked door beside an open window.

    The pool is root's. A leader reads it, because it is the list their shelf
    screen is built from, and may not add to it.
    """
    from matazim.models import OfferedCourse

    client.force_login(world["leaders"]["mine"].user)
    assert client.get("/matazim/api/offered-courses/").status_code == 200

    resp = client.post("/matazim/api/offered-courses/", {"slug": "fpga"},
                       content_type="application/json")
    assert resp.status_code == 403, resp.content[:200]
    assert not OfferedCourse.objects.filter(slug="fpga").exists()


def test_the_api_files_a_shelf_row_under_whoever_posted_it(client, world):
    """`leader` comes from the session. A client that could name its own would
    stock somebody else's shelf, which is REQ-M.88 undone in a place no screen
    shows."""
    from matazim.models import LeaderCourse

    _offer("arduino", world["root"])
    client.force_login(world["leaders"]["mine"].user)
    resp = client.post(
        "/matazim/api/leader-courses/",
        {"slug": "arduino", "leader": world["leaders"]["other"].pk},
        content_type="application/json",
    )
    assert resp.status_code in (200, 201), resp.content[:300]
    row = LeaderCourse.objects.get(slug="arduino")
    assert row.leader_id == world["leaders"]["mine"].pk, "filed under the leader it named"


def test_the_api_refuses_a_slug_root_never_offered(client, world):
    """The same gate as the screen, asked of the same function. This is the
    one that a queryset cannot enforce: scope decides what comes back, and
    this is about what goes in."""
    from matazim.models import LeaderCourse

    client.force_login(world["leaders"]["mine"].user)
    resp = client.post("/matazim/api/leader-courses/", {"slug": "fpga"},
                       content_type="application/json")
    assert resp.status_code == 400, resp.content[:200]
    assert not LeaderCourse.objects.filter(slug="fpga").exists()


def test_one_leader_cannot_read_or_clear_anothers_shelf(client, world):
    """REQ-M.88 through the endpoint, both verbs."""
    from matazim.models import LeaderCourse

    _offer("arduino", world["root"])
    theirs = _shelve(world["leaders"]["other"], "arduino")

    client.force_login(world["leaders"]["mine"].user)
    assert client.get("/matazim/api/leader-courses/").json() == []
    assert client.delete(f"/matazim/api/leader-courses/{theirs.pk}/").status_code in (403, 404)
    assert LeaderCourse.objects.filter(pk=theirs.pk).exists()


def test_the_pool_is_one_programme_wide_decision(client, world):
    """The one place this sprint crosses §4.4, named rather than discovered.

    Two leaders in two institutions read the same pool, because the pool is
    what the *programme* offers and root sets it once. Their shelves are not
    shared, which is the line: what may be offered is programme-wide, what is
    offered to a given teenager is their own leader's call.

    `test_spr_m_34.py`'s tenancy sweep passes on this endpoint today only
    because an `OfferedCourse` row holds a slug and nothing else. Left at that,
    the exemption would be an accident of which fields exist rather than a
    decision, so it is asserted here from both sides.
    """
    from matazim.models import Institution, Leader

    _offer("arduino", world["root"])
    elsewhere = Institution.objects.create(name="רשת ביתא")
    far = Leader.objects.create(
        user=_user("l9@example.com", "מוביל רחוק"), institution=elsewhere,
        approved_at=timezone.now(),
    )

    client.force_login(far.user)
    pool = client.get("/matazim/api/offered-courses/").json()
    assert [row["slug"] for row in pool] == ["arduino"], "the pool is programme-wide"

    _shelve(world["leaders"]["mine"], "arduino")
    assert client.get("/matazim/api/leader-courses/").json() == [], "a shelf is not"


def test_a_member_reads_neither_table_through_the_api(client, world):
    """The pool is everything a leader *could* open. A member reading it would
    be shown exactly the הדרכות their own leader chose not to put in front of
    them, which is the feature running backwards."""
    _offer("arduino", world["root"])
    _shelve(world["leaders"]["mine"], "arduino")

    client.force_login(world["members"]["mine"].user)
    for prefix in ("offered-courses", "leader-courses"):
        resp = client.get(f"/matazim/api/{prefix}/")
        assert resp.status_code in (200, 403)
        if resp.status_code == 200:
            assert resp.json() == [], f"{prefix} handed a member rows"


def test_no_screen_offers_a_leader_a_way_to_make_one_required():
    """The absence is the design, so it is pinned. REQ-M.76 is uniform across
    the programme and a control here would promise otherwise."""
    import pathlib
    import re

    # What a leader reads, not the note to whoever edits this next: the first
    # version of this test failed on the template comment that explains why
    # there is no such control, which is the one place the word belongs.
    shelf = pathlib.Path("templates/matazim/leader_shelf.html").read_text(encoding="utf-8")
    visible = re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "", shelf, flags=re.S)
    for word in ("חובה", "required", "נדרש להסמכה"):
        assert word not in visible, f"the shelf screen offers {word!r}"

    from matazim.models import LeaderCourse

    assert not any(f.name == "required" for f in LeaderCourse._meta.get_fields())
