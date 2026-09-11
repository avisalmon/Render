"""SPR-M.8 — The leader's students, and what makes a mataz.

Two different kinds of thing are tested here and they fail in different ways.

The **reader** (F-M.8.1) is a performance rewrite with a correctness trap. A
roster is the inverse shape of every babook screen: babook asks one user about
many courses, a roster asks many users about one track. Rewriting it for the
cohort shape means the codebase briefly holds two definitions of "done", and
that divergence would never announce itself. It would quietly tell a leader that
a kid finished four lessons while the kid's own screen says three. So the reader
is pinned against babook's own answer rather than merely asserted to return
plausible numbers.

The **gate** (F-M.8.8, F-M.8.9) fails the other way: not by being wrong, but by
being polite. A hidden button is still a postable URL, so every refusal is
tested against the server rather than against the rendered page.

Traces: REQ-M.22, M.23, M.29, M.74, M.76, M.77, M.78.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm8

PASSWORD = "sprm8-pass-4417"


# --------------------------------------------------------------- fixtures


def _one_world():
    """REQ-M.88 — these suites describe a single institution.

    Leaders here belong to whichever program manager the test created, and the
    fixtures run in whatever order the test found readable. So a leader adopts
    the existing manager if there is one, and a manager adopts any leader made
    before it existed. Between them, order stops mattering.
    """
    from matazim.models import Leader, MemberProfile

    profile = MemberProfile.objects.filter(is_program_manager=True).first()
    owner = profile.user if profile else None
    if owner:
        Leader.objects.filter(program_manager__isnull=True).update(program_manager=owner)
    return owner


def make_user(email, name=""):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name or email})
    return user


def make_leader(email="noa@example.com", name="נעה מורה", school="עתיד רמלה"):
    from matazim.models import Leader, StudyClass

    leader = Leader.objects.create(user=make_user(email, name), program_manager=_one_world())
    StudyClass.objects.create(leader=leader, name="ט1", school_name=school)
    return leader


def make_student(leader=None, email="kid@example.com", name="יובל", passed=True):
    from matazim.models import MemberProfile, Student

    user = make_user(email, name)
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now() if passed else None,
            # REQ-M.84, added in SPR-M.10: joining a leader needs a parent's
            # consent. These tests are about rosters and certification, so the
            # fixture supplies it; the gate itself is tested in test_spr_m_10.
            "birth_year": 2012,
            "guardian_consent_at": timezone.now(),
        },
    )
    return Student.objects.create(user=user, leader=leader)


def make_course(slug, lessons=3, issues_certificate=True):
    from app.models import Course, Video

    course = Course.objects.create(
        slug=slug, title=slug, is_published=True, issues_certificate=issues_certificate
    )
    for n in range(lessons):
        Video.objects.create(course=course, title=f"{slug} {n}", lesson_order=n + 1)
    return course


def watch(user, course, count):
    """Mark the first `count` lessons of `course` watched, babook's own way."""
    from app.models import UserVideoProgress

    for video in course.videos.order_by("lesson_order")[:count]:
        UserVideoProgress.objects.update_or_create(
            user=user,
            video=video,
            defaults={
                "percent_watched": 100.0,
                "quiz_passed": True,
                "completed_at": timezone.now(),
            },
        )


def certify(user, course):
    from app.models import CourseCertificate

    return CourseCertificate.objects.get_or_create(user=user, course=course)[0]


def make_track():
    """The two courses that are actually the requirement (REQ-M.76)."""
    return make_course("scratch"), make_course("scratch-advanced")


def eligible_student(leader):
    scratch, advanced = make_track()
    student = make_student(leader=leader, passed=True)
    certify(student.user, scratch)
    certify(student.user, advanced)
    return student


# ------------------------------------------------- F-M.8.1: the cohort reader


def test_the_cohort_reader_agrees_with_babook_for_the_same_person(db):
    """T-F-M.8.1-1: REQ-M.74. The whole point of the file.

    Not "does it return numbers" but "does it return *babook's* numbers". If
    these two ever disagree, one of them is lying to a leader about a teenager.
    """
    from app.views import _catalog_progress
    from matazim.progress import cohort_progress

    course = make_course("scratch", lessons=4)
    student = make_student()
    watch(student.user, course, 3)

    theirs = _catalog_progress(student.user, [course.id])[course.id]
    ours = cohort_progress([student], [course.slug])[student.user_id][course.slug]

    assert ours["done"] == theirs["done"]
    assert ours["total"] == theirs["total"]
    assert ours["pct"] == theirs["pct"]


def test_the_two_readers_agree_across_a_whole_range_of_states(db):
    """T-F-M.8.1-2: REQ-M.74.

    One agreeing case can agree by accident. Nothing watched, part watched, all
    watched: the boundaries are where two implementations of one rule drift
    apart.
    """
    from app.views import _catalog_progress
    from matazim.progress import cohort_progress

    course = make_course("scratch", lessons=4)
    students = []
    for n in range(5):
        s = make_student(email=f"kid{n}@example.com", name=f"ילד {n}")
        watch(s.user, course, n)  # 0, 1, 2, 3, 4 of 4
        students.append(s)

    ours = cohort_progress(students, [course.slug])
    for s in students:
        theirs = _catalog_progress(s.user, [course.id])[course.id]
        mine = ours[s.user_id][course.slug]
        assert (mine["done"], mine["pct"]) == (theirs["done"], theirs["pct"]), s.user.email


def test_the_reader_does_not_grow_with_the_cohort(django_assert_num_queries, db):
    """T-F-M.8.1-3: REQ-M.74. The reason the file exists at all.

    Calling babook's per-user reader in a loop is correct and unusable: a query
    per teenager on every page load. Rather than pin an exact number, which
    would break on any unrelated refactor, this measures twelve students and
    then asserts twenty-four cost exactly the same.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from matazim.progress import cohort_progress

    course = make_course("scratch", lessons=3)
    small = [make_student(email=f"s{n}@example.com") for n in range(12)]
    big = small + [make_student(email=f"b{n}@example.com") for n in range(12)]
    for s in big:
        watch(s.user, course, 2)

    with CaptureQueriesContext(connection) as first:
        cohort_progress(small, [course.slug])
    with django_assert_num_queries(len(first)):
        cohort_progress(big, [course.slug])


def test_an_empty_cohort_is_not_an_error(db):
    """T-F-M.8.1-4: a leader's first day, before anyone has joined."""
    from matazim.progress import cohort_progress

    make_track()
    assert cohort_progress([], ["scratch"]) == {}


def test_a_student_who_has_done_nothing_still_appears(db):
    """T-F-M.8.1-5: REQ-M.23.

    Someone who has not started is exactly who a leader is looking for, so they
    must not go missing from the answer merely for having no rows.
    """
    from matazim.progress import cohort_progress

    make_course("scratch", lessons=3)
    student = make_student()

    row = cohort_progress([student], ["scratch"])[student.user_id]["scratch"]
    assert row["done"] == 0
    assert row["total"] == 3
    assert row["pct"] == 0


# ------------------------------------------- F-M.8.8: what makes a mataz


def test_all_three_conditions_make_a_mataz(db):
    """T-F-M.8.8-1: REQ-M.76. The happy path, stated once."""
    from matazim.certification import eligibility

    scratch, advanced = make_track()
    student = make_student(passed=True)
    certify(student.user, scratch)
    certify(student.user, advanced)

    state = eligibility(student)
    assert state.entrance_test_passed
    assert state.courses_certified
    assert state.is_eligible, "test passed and both certificates held"


def test_one_scratch_course_is_not_two(db):
    """T-F-M.8.8-2: REQ-M.76. The most likely near miss."""
    from matazim.certification import eligibility

    scratch, _advanced = make_track()
    student = make_student(passed=True)
    certify(student.user, scratch)

    state = eligibility(student)
    assert not state.is_eligible
    assert "scratch-advanced" in state.missing_courses


def test_finishing_the_lessons_is_not_the_same_as_being_certified(db):
    """T-F-M.8.8-3: REQ-M.76, and the subtlest way to get this wrong.

    Watching every lesson does not issue a certificate: babook issues one when
    the learner presses Finish, and a review-gated course needs a human first.
    Eligibility that counted lessons instead of certificates would let a leader
    certify someone babook has not.
    """
    from matazim.certification import eligibility

    scratch, advanced = make_track()
    student = make_student(passed=True)
    watch(student.user, scratch, 3)
    watch(student.user, advanced, 3)

    assert not eligibility(student).is_eligible


def test_the_entrance_test_is_required_even_with_both_certificates(db):
    """T-F-M.8.8-4: REQ-M.76. All three, not two of three."""
    from matazim.certification import eligibility

    scratch, advanced = make_track()
    student = make_student(passed=False)
    certify(student.user, scratch)
    certify(student.user, advanced)

    state = eligibility(student)
    assert not state.is_eligible
    assert not state.entrance_test_passed


def test_other_courses_do_not_substitute_for_the_two(db):
    """T-F-M.8.8-5: REQ-M.76.

    Avi: a student can do a lot of trainings before a leader decides. They still
    have to do these two.
    """
    from matazim.certification import eligibility

    make_track()
    student = make_student(passed=True)
    for slug in ("arduino", "python", "fusion360"):
        certify(student.user, make_course(slug))

    assert not eligibility(student).is_eligible


def test_eligibility_is_computed_not_stored(db):
    """T-F-M.8.8-6: REQ-M.76.

    A stored flag goes stale the moment a certificate is revoked. Losing one has
    to make someone ineligible again with nothing to run.
    """
    from app.models import CourseCertificate
    from matazim.certification import eligibility

    scratch, advanced = make_track()
    student = make_student(passed=True)
    certify(student.user, scratch)
    certify(student.user, advanced)
    assert eligibility(student).is_eligible

    CourseCertificate.objects.filter(user=student.user, course=advanced).delete()
    assert not eligibility(student).is_eligible


# ------------------------------ F-M.8.9: the leader certifies, the gate refuses


def test_a_leader_certifies_their_own_student(client, db):
    """T-F-M.8.9-1: REQ-M.78. The act the whole program exists to produce."""
    from matazim.models import Student

    leader = make_leader()
    student = eligible_student(leader)

    client.force_login(leader.user)
    client.post(reverse("matazim:certify", args=[student.pk]), {"action": "certify"})

    student.refresh_from_db()
    assert student.status == Student.CERTIFIED
    assert student.certified_by == leader.user, "who granted it is part of the record"
    assert student.certified_at is not None


def test_the_gate_refuses_on_the_server_not_only_in_the_template(client, db):
    """T-F-M.8.9-2: REQ-M.77. The one that matters.

    A hidden button is still a postable URL. If an `{% if %}` is the only thing
    stopping this, the rule is decoration.
    """
    from matazim.models import Student

    leader = make_leader()
    student = make_student(leader=leader, passed=True)  # no certificates at all

    client.force_login(leader.user)
    response = client.post(reverse("matazim:certify", args=[student.pk]), {"action": "certify"})

    student.refresh_from_db()
    assert student.status != Student.CERTIFIED
    assert response.status_code in (302, 403)


def test_a_leader_cannot_certify_another_leaders_student(client, db):
    """T-F-M.8.9-3: REQ-M.22, enforced on the most consequential write there is."""
    from matazim.models import Student

    mine = make_leader("mine@example.com")
    theirs = make_leader("theirs@example.com", name="מוביל אחר")
    student = eligible_student(theirs)

    client.force_login(mine.user)
    response = client.post(reverse("matazim:certify", args=[student.pk]), {"action": "certify"})

    student.refresh_from_db()
    assert student.status != Student.CERTIFIED
    assert response.status_code in (302, 403, 404)


def test_certification_is_never_automatic(db):
    """T-F-M.8.9-4: REQ-M.78.

    Meeting the prerequisites earns the right to be considered, never the status
    itself. Nothing may promote anyone on a certificate count.
    """
    from matazim.certification import eligibility
    from matazim.models import Student

    leader = make_leader()
    student = eligible_student(leader)

    assert eligibility(student).is_eligible
    student.refresh_from_db()
    assert student.status != Student.CERTIFIED, "eligible is not certified"


def test_certification_can_be_taken_back_by_the_same_hand(client, db):
    """T-F-M.8.9-5: REQ-M.78. Granted by hand means revocable by hand."""
    from matazim.models import Student

    leader = make_leader()
    student = eligible_student(leader)
    client.force_login(leader.user)
    client.post(reverse("matazim:certify", args=[student.pk]), {"action": "certify"})

    client.post(reverse("matazim:certify", args=[student.pk]), {"action": "revoke"})
    student.refresh_from_db()
    assert student.status != Student.CERTIFIED
    assert student.certified_at is None


def test_an_admin_can_certify_too(client, db):
    """T-F-M.8.9-6: REQ-M.22 precedence.

    An admin sees everyone, so an admin can act on everyone. A student whose
    leader is away is not stuck.
    """
    from matazim.models import MemberProfile, Student

    leader = make_leader()
    student = eligible_student(leader)

    boss = make_user("chief@example.com", "אבי")
    MemberProfile.objects.update_or_create(user=boss, defaults={"is_program_manager": True})
    _one_world()
    client.force_login(boss)
    client.post(reverse("matazim:certify", args=[student.pk]), {"action": "certify"})

    student.refresh_from_db()
    assert student.status == Student.CERTIFIED


# ------------------------------------------------- F-M.8.3: the roster


def test_the_roster_shows_only_this_leaders_students(client, db):
    """T-F-M.8.3-1: REQ-M.22. The access module, finally consumed by a screen."""
    mine = make_leader("mine@example.com")
    theirs = make_leader("theirs@example.com")
    make_student(leader=mine, email="ours@example.com", name="יובל שלנו")
    make_student(leader=theirs, email="not-ours@example.com", name="דני זר")

    client.force_login(mine.user)
    html = client.get(reverse("matazim:roster")).content.decode()

    assert "יובל שלנו" in html
    assert "דני זר" not in html


def test_the_roster_says_what_each_student_still_needs(client, db):
    """T-F-M.8.3-2: REQ-M.77.

    An ineligible student is an explained state, not a missing button. A leader
    who cannot see why has to guess, and will end up asking the teenager.
    """
    leader = make_leader()
    scratch, _advanced = make_track()
    student = make_student(leader=leader, passed=True)
    certify(student.user, scratch)

    client.force_login(leader.user)
    html = client.get(reverse("matazim:student", args=[student.pk])).content.decode()
    assert "scratch-advanced" in html or "סקראץ" in html


def test_the_roster_refuses_someone_who_is_not_a_leader(client, db):
    """T-F-M.8.3-3: REQ-M.22."""
    make_student(email="justakid@example.com")
    client.login(username="justakid@example.com", password=PASSWORD)

    response = client.get(reverse("matazim:roster"))
    assert response.status_code in (302, 403)


def test_a_leader_reaches_the_roster_from_their_own_page(client, db):
    """T-F-M.8.3-4: the SPR-M.7 lesson, applied before it is repeated.

    A screen you have to know the URL for is a screen nobody uses.
    """
    leader = make_leader()
    client.force_login(leader.user)

    html = client.get(reverse("matazim:leader_home")).content.decode()
    assert reverse("matazim:roster") in html


# ------------------------------------------------- F-M.8.4: classes


def test_a_leader_creates_a_class_and_puts_someone_in_it(client, db):
    """T-F-M.8.4-1: REQ-M.23."""
    from matazim.models import StudyClass

    leader = make_leader()
    student = make_student(leader=leader)
    client.force_login(leader.user)

    client.post(
        reverse("matazim:classes"),
        {"action": "add", "name": "ט2", "school_name": "עתיד רמלה"},
    )
    new = StudyClass.objects.get(leader=leader, name="ט2")

    client.post(
        reverse("matazim:student", args=[student.pk]),
        {"action": "set_classes", "classes": [new.pk]},
    )
    assert new.students.filter(pk=student.pk).exists()


def test_a_class_is_never_required(client, db):
    """T-F-M.8.4-2: Q14 defaulted.

    A leader with six students should never have to invent a filing system to
    see them. Someone in no class is listed like anyone else.
    """
    leader = make_leader()
    make_student(leader=leader, name="בלי כיתה")
    client.force_login(leader.user)

    html = client.get(reverse("matazim:roster")).content.decode()
    assert "בלי כיתה" in html


def test_a_leader_cannot_put_a_student_into_another_leaders_class(client, db):
    """T-F-M.8.4-3: REQ-M.22, on the write path again."""
    from matazim.models import StudyClass

    mine = make_leader("mine@example.com")
    theirs = make_leader("theirs@example.com")
    foreign = StudyClass.objects.create(leader=theirs, name="זרה", school_name="אחר")
    student = make_student(leader=mine)

    client.force_login(mine.user)
    client.post(
        reverse("matazim:student", args=[student.pk]),
        {"action": "set_classes", "classes": [foreign.pk]},
    )

    assert not foreign.students.filter(pk=student.pk).exists()


# ------------------------------------------------- REQ-M.29


def test_nothing_here_records_a_child(db):
    """T-F-M.8.5-1: REQ-M.29.

    The kids a mataz teaches are not users, not members, not rows. That is a
    standing property of the product, so it is checked against the models rather
    than against any one screen.
    """
    from django.apps import apps

    suspicious = {"child", "pupil", "mentee", "taught"}
    for model in apps.get_app_config("matazim").get_models():
        for field in model._meta.get_fields():
            name = field.name.lower()
            assert not any(
                word in name for word in suspicious
            ), f"{model.__name__}.{field.name} looks like a record about a child (REQ-M.29)"


# ------------------------------- the stage a student is actually at


def test_being_taken_on_by_a_leader_makes_you_a_learner(client, db):
    """T-F-M.8.3-5: REQ-M.23, found by looking at the roster rather than by a test.

    Every student sat at מתמיינים forever, because nothing in the app ever
    advanced `status` and מתמיינים is the default. A roster where four people in
    four different states all read the same word is a roster that answers
    nothing, and the word it chose was the wrong one: מתמיינים is the selection
    stage, and these are people a leader has already accepted.
    """
    from matazim.models import Student

    leader = make_leader()
    waiting = Student.objects.create(
        user=make_user("waiting@example.com", "יובל"), pending_leader=leader
    )
    assert waiting.status == Student.APPLIED, "asking is still מתמיינים"

    client.force_login(leader.user)
    client.post(reverse("matazim:leader_confirm", args=[waiting.pk]), {"action": "confirm"})

    waiting.refresh_from_db()
    assert waiting.status == Student.IN_TRAINING


def test_joining_by_invite_link_also_makes_you_a_learner(client, db):
    """T-F-M.8.3-6: the other way in, which must not leave people labelled differently."""
    from matazim.models import Student

    leader = make_leader()
    user = make_student(email="linked@example.com").user
    Student.objects.filter(user=user).delete()

    client.force_login(user)
    client.post(reverse("matazim:join", args=[leader.join_code]), {"action": "join"})

    assert Student.objects.get(user=user).status == Student.IN_TRAINING
