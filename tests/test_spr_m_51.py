"""SPR-M.51 — the certification path closes.

The 2026-09-17 review found the hole this sprint fills, and it was the worst
kind: **a member who did everything מט״צים offered could not become a מט״צ
מוסמך.** REQ-M.76 requires a `CourseCertificate` for `scratch` and
`scratch-advanced`; both are `requires_project` with `project_min_count = 2`, so
each wants two handed-in projects, and the certificate is issued by a gate that
lived behind babook's own lesson screen. מט״צים rendered no way to hand anything
in and never called that gate. Everything downstream looked correct because the
certificates in the database had been seeded rather than earned.

Avi, 2026-09-19: "whatever babook can do that is needed I want matazim to use or
clone." Use. The gates moved to `app/completion.py` and both products ask it; the
submission goes through babook's own parser and sharing check and writes the row
babook's gate counts. A second opinion about who has earned a certificate is the
one duplication this codebase could least afford.

**The load-bearing test is `test_a_member_can_be_certified_without_leaving_
matazim`.** It walks the whole thing with nothing but מט״צים URLs: watch the
lessons, hand in two projects, press the button, hold the certificate. If that
test passes, the product's central promise is deliverable. It was not, six days
ago.

Traces: REQ-M.13, REQ-M.14, REQ-M.76, RULE-1, RULE-3.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

pytestmark = pytest.mark.sprm51

PASSWORD = "sprm51-pass-9930"


def _course(slug="scratch", lessons=4):
    """A Scratch course shaped like the real ones: project-gated, two required."""
    from app.models import Course, Video

    course = Course.objects.create(
        slug=slug, title="סקראץ׳ 1", is_published=True,
        requires_project=True, project_upload_type="scratch",
        project_min_count=2, cert_min_pct=80, issues_certificate=True,
    )
    for i in range(lessons):
        Video.objects.create(course=course, title=f"שיעור {i + 1}",
                             lesson_order=i + 1, bunny_video_id="abc123")
    return course


@pytest.fixture
def member(db):
    from app.models import UserProfile
    from matazim.models import Institution, Leader, MemberProfile, Student

    user = User.objects.create_user(
        username="kid@example.com", email="kid@example.com", password=PASSWORD
    )
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": "אלמה"})
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now(),
            "birth_year": timezone.now().year - 14,
            "guardian_consent_at": timezone.now(),
            "welcome_accepted_at": timezone.now(),
        },
    )
    inst = Institution.objects.create(name="רשת אחת")
    manager = User.objects.create_user(username="pm@example.com", email="pm@example.com",
                                       password=PASSWORD)
    inst.managers.add(manager)
    leader = Leader.objects.create(
        user=User.objects.create_user(username="l@example.com", email="l@example.com",
                                      password=PASSWORD),
        institution=inst, approved_at=timezone.now(),
    )
    Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)
    return user


def _watch_everything(user, course):
    """Mark every lesson watched, through the table babook's gate reads."""
    from app.models import UserVideoProgress

    for video in course.videos.all():
        UserVideoProgress.objects.update_or_create(
            user=user, video=video,
            defaults={"completed_at": timezone.now(), "percent_watched": 100.0},
        )


def _hand_in(client, course, order, pid, monkeypatch):
    """Submit a project the way the lesson screen does."""
    import app.views as bv

    monkeypatch.setattr(bv, "scratch_project_is_shared", lambda _pid: True)
    return client.post(
        f"/matazim/learn/{course.slug}/{order}/project/",
        {"scratch_url": f"https://scratch.mit.edu/projects/{pid}/", "caption": "המבוך שלי"},
    )


# ------------------------------------------------- the one that matters


def test_a_member_can_be_certified_without_leaving_matazim(client, member, monkeypatch):
    """The whole journey, using מט״צים URLs and nothing else.

    Six days ago this was impossible at any step after the lessons: there was
    no way to hand a project in, and nothing in this product ever asked whether
    the certificate had been earned.
    """
    from app.models import CourseCertificate, LessonModelSubmission

    course = _course()
    client.force_login(member)
    _watch_everything(member, course)

    # Not yet: the lessons are done and the projects are not.
    assert not CourseCertificate.objects.filter(user=member, course=course).exists()
    resp = client.post(f"/matazim/learn/{course.slug}/finish/")
    assert resp["Location"].endswith("?cert=project"), resp["Location"]
    assert not CourseCertificate.objects.filter(user=member, course=course).exists()

    # Hand in the two the course asks for, on two different lessons.
    _hand_in(client, course, 1, "111111111", monkeypatch)
    _hand_in(client, course, 2, "222222222", monkeypatch)
    assert LessonModelSubmission.objects.filter(user=member, video__course=course).count() == 2

    # And now the certificate is real, issued through babook's own writer.
    resp = client.post(f"/matazim/learn/{course.slug}/finish/")
    assert resp["Location"].endswith("?cert=issued"), resp["Location"]
    cert = CourseCertificate.objects.get(user=member, course=course)
    assert cert.certificate_id


def test_every_url_in_that_journey_stays_inside_matazim(client, member, monkeypatch):
    """RULE-1. The point of doing this here is that a member never leaves."""
    course = _course()
    client.force_login(member)
    _watch_everything(member, course)
    _hand_in(client, course, 1, "111111111", monkeypatch)
    _hand_in(client, course, 2, "222222222", monkeypatch)

    for url in (f"/matazim/learn/{course.slug}/1/project/",
                f"/matazim/learn/{course.slug}/finish/"):
        resp = client.post(url)
        assert resp.status_code in (302, 200)
        if resp.status_code == 302:
            assert resp["Location"].startswith("/matazim/"), f"{url} sent them to {resp['Location']}"


# ------------------------------------------------- the submission itself


def test_a_link_that_is_not_a_scratch_project_is_refused_in_words(client, member, monkeypatch):
    from app.models import LessonModelSubmission

    course = _course()
    client.force_login(member)
    resp = client.post(f"/matazim/learn/{course.slug}/1/project/",
                       {"scratch_url": "https://example.com/not-scratch"})
    assert resp["Location"].endswith("?project=badlink#mzProject")
    assert not LessonModelSubmission.objects.filter(user=member).exists()


def test_a_project_that_was_never_shared_is_refused(client, member, monkeypatch):
    """babook's own check, not a second opinion: an unshared project is a link
    to something nobody but its maker can open."""
    import app.views as bv
    from app.models import LessonModelSubmission

    course = _course()
    client.force_login(member)
    monkeypatch.setattr(bv, "scratch_project_is_shared", lambda _pid: False)
    resp = client.post(f"/matazim/learn/{course.slug}/1/project/",
                       {"scratch_url": "https://scratch.mit.edu/projects/123456/"})
    assert resp["Location"].endswith("?project=notshared#mzProject")
    assert not LessonModelSubmission.objects.filter(user=member).exists()


def test_resubmitting_the_same_project_updates_it_rather_than_adding_one(
    client, member, monkeypatch
):
    """Two projects means two projects, not one saved twice. The gate counts
    rows, so this is the difference between earning a certificate and appearing
    to."""
    from app.models import LessonModelSubmission

    course = _course()
    client.force_login(member)
    _hand_in(client, course, 1, "111111111", monkeypatch)
    _hand_in(client, course, 1, "111111111", monkeypatch)
    assert LessonModelSubmission.objects.filter(user=member, video__course=course).count() == 1


def test_a_member_cannot_hand_in_to_a_course_outside_the_track(client, member, monkeypatch):
    """`_track_course` refuses anything that is not the programme's own, and
    this route inherits that rather than restating it."""
    _course(slug="not-ours")
    client.force_login(member)
    resp = client.post("/matazim/learn/not-ours/1/project/",
                       {"scratch_url": "https://scratch.mit.edu/projects/1/"})
    assert resp.status_code == 404


# ------------------------------------------------- the gate is not re-implemented


def test_matazim_holds_no_second_copy_of_the_gate():
    """RULE-3, as a grep.

    The whole point of SPR-M.51 is that both products ask one module. A gate
    re-implemented here would drift from babook's within a sprint, and the
    thing it decides is whether a fourteen-year-old's certificate is real.
    """
    import pathlib
    import re

    # Reading `project_min_count` to *say* "you need two" is a screen doing its
    # job. Comparing against it is a second gate. The first version of this test
    # forbade both and failed on the sentence that tells a member what is left,
    # which is the opposite of the point.
    deciding = re.compile(
        r"(cert_min_pct|project_min_count|notebook_min_pass_count)\s*(<=?|>=?|==)"
        r"|(<=?|>=?|==)\s*\w*\.(cert_min_pct|project_min_count|notebook_min_pass_count)"
    )
    for name in ("learn_views.py", "certification.py"):
        src = (pathlib.Path("matazim") / name).read_text(encoding="utf-8")
        hit = deciding.search(src)
        assert not hit, (
            f"matazim/{name} decides with {hit.group(0)!r} instead of asking app.completion"
        )

    # And the positive half: something here actually does ask.
    views = (pathlib.Path("matazim") / "learn_views.py").read_text(encoding="utf-8")
    assert "why_not_certified" in views and "issue_certificate" in views


def test_certification_now_reaches_all_three_conditions(client, member, monkeypatch):
    """REQ-M.76 end to end: the entrance test, both certificates, and the
    leader's approval. The middle one is what this sprint made reachable."""
    from matazim.certification import eligibility
    from matazim.models import Student

    for slug in ("scratch", "scratch-advanced"):
        course = _course(slug=slug)
        client.force_login(member)
        _watch_everything(member, course)
        _hand_in(client, course, 1, f"1{slug[-1]}1111111", monkeypatch)
        _hand_in(client, course, 2, f"2{slug[-1]}2222222", monkeypatch)
        assert client.post(f"/matazim/learn/{slug}/finish/")["Location"].endswith("?cert=issued")

    state = eligibility(Student.objects.get(user=member))
    assert state.entrance_test_passed
    assert state.courses_certified, f"still missing {state.missing_courses}"
    assert state.is_eligible, "everything that does not need a person is done"
