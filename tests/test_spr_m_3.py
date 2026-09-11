"""SPR-M.3 — מבחן הכניסה.

The gate stops being a promise on a placeholder page. A stranger learns
Tinkercad on the shared course, builds the object we show them, uploads it, and
the student door opens.

Shape of it, agreed with Avi on 2026-09-10:

- The gate selects and onboards at once. Confirming the applicant has a computer
  is part of the point, not a side effect.
- We use babook's existing `tinkercad` lessons, read-only. Video and assignment
  only, no transcript. We never add our task to their course.
- Each member gets one target, kept. A retry draws a fresh one, which is what
  makes a downloaded model useless.
- Staff can retire targets that are too hard.

Traces: REQ-M.46 to M.55.
"""

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

pytestmark = pytest.mark.sprm3

PASSWORD = "sprm3-pass-4417"


def make_user(email="dana@example.com", name="דנה כהן", staff=False):
    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    if staff:
        # "Staff" became מט״צים adminship in SPR-M.6: is_staff was a stand-in while
        # this app had no roles of its own. Granting the real thing, not the
        # stand-in, so the test exercises the rule that actually ships.
        from matazim.models import MemberProfile

        MemberProfile.objects.update_or_create(user=user, defaults={"is_program_manager": True})
    from app.models import UserProfile

    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def sign_in(client, email="dana@example.com", staff=False):
    user = make_user(email, staff=staff)
    client.force_login(user)
    return user


def target_stl(target_id):
    """The reference model itself: a submission that should obviously pass."""
    from pathlib import Path

    from django.conf import settings

    path = Path(settings.BASE_DIR) / "static" / "matazim" / "targets" / f"{target_id}.stl"
    return path.read_bytes()


# ---------------------------------------------------------------- F-M.3.1


def test_register_lands_on_the_main_view(client, db):
    """T-F-M.3.1-1: REQ-M.46.

    Someone who just signed in wants to see the program, not a form about
    themselves. The personal area is one click away in the header.
    """
    resp = client.post(
        reverse("matazim:register"),
        {
            "name": "רותם",
            "email": "rotem@example.com",
            "password": PASSWORD,
            # REQ-M.84 — registration now asks how old they are, and a
            # ninth-grader needs a parent. These fields are required, so a
            # POST without them is refused rather than ignored.
            "birth_year": "2012",
            "guardian_name": "רונית כהן",
            "guardian_email": "parent@example.com",
            "guardian_consent": "on",
        },
    )
    assert resp.status_code == 302
    assert resp.url == reverse("matazim:home")


def test_google_return_lands_on_the_main_view(client, db):
    """T-F-M.3.1-2: every door ends in the same place."""
    sign_in(client, "viagoogle3@example.com")
    resp = client.get(reverse("matazim:auth_done"))
    assert resp.status_code == 302
    assert resp.url == reverse("matazim:home")


# ---------------------------------------------------------------- F-M.3.2


def test_the_bank_seeds_from_the_generated_files(db):
    """T-F-M.3.2-1: the files are the source of truth, the rows are the decisions."""
    from matazim.models import EntranceTarget
    from matazim.targets import sync_bank

    created = sync_bank()
    assert created >= 100
    assert EntranceTarget.objects.count() == created

    # Idempotent: running it again on a deploy must not duplicate or reset.
    again = sync_bank()
    assert again == 0
    assert EntranceTarget.objects.count() == created


def test_a_target_carries_its_shape_and_brief(db):
    """T-F-M.3.2-2."""
    from matazim.models import EntranceTarget
    from matazim.targets import sync_bank

    sync_bank()
    target = EntranceTarget.objects.get(target_id="t0000")
    assert target.shape == "plate_two_holes"
    assert "מ" in target.brief
    assert target.is_retired is False


# ---------------------------------------------------------------- F-M.3.3


def test_curation_is_staff_only(client, db):
    """T-F-M.3.3-1: deciding what a 14-year-old is asked to build is not public."""
    from matazim.targets import sync_bank

    sync_bank()

    assert client.get(reverse("matazim:staff_targets")).status_code in (302, 403)

    sign_in(client, "member@example.com")
    assert client.get(reverse("matazim:staff_targets")).status_code in (302, 403)

    client.logout()
    sign_in(client, "boss@example.com", staff=True)
    assert client.get(reverse("matazim:staff_targets")).status_code == 200


def test_curation_shows_every_target_with_drawing_and_model(client, db):
    """T-F-M.3.3-2: REQ-M.55. A drawing alone is not enough to judge difficulty."""
    from matazim.models import EntranceTarget
    from matazim.targets import sync_bank

    sync_bank()
    sign_in(client, "boss@example.com", staff=True)
    html = client.get(reverse("matazim:staff_targets")).content.decode()

    assert html.count("mz-target-card") == EntranceTarget.objects.count()
    assert "targets/t0000.svg" in html
    assert "targets/t0000.stl" in html


def test_retiring_takes_a_target_out_of_circulation(client, db):
    """T-F-M.3.3-3: reversible, and never destructive."""
    from matazim.models import EntranceTarget
    from matazim.targets import sync_bank

    sync_bank()
    sign_in(client, "boss@example.com", staff=True)

    client.post(reverse("matazim:staff_target_toggle", args=["t0000"]))
    assert EntranceTarget.objects.get(target_id="t0000").is_retired is True

    client.post(reverse("matazim:staff_target_toggle", args=["t0000"]))
    assert EntranceTarget.objects.get(target_id="t0000").is_retired is False


# ---------------------------------------------------------------- F-M.3.4


def test_the_lesson_list_is_the_shared_course_in_our_chrome(client, db):
    """T-F-M.3.4-1: REQ-M.47."""
    from app.models import Course, Video

    course = Course.objects.create(slug="tinkercad", title="טינקרקאד", is_published=True)
    Video.objects.create(course=course, title="שיעור ראשון", lesson_order=1)
    Video.objects.create(course=course, title="שיעור שני", lesson_order=2)

    sign_in(client)
    html = client.get(reverse("matazim:test_lessons")).content.decode()
    assert "שיעור ראשון" in html
    assert "שיעור שני" in html
    assert "babook" not in html


def test_we_never_modify_babooks_course(client, db):
    """T-F-M.3.4-2: their course is live, and its learners are not ours."""
    from app.models import Course, Video

    course = Course.objects.create(
        slug="tinkercad", title="טינקרקאד", is_published=True, project_upload_type="tinkercad"
    )
    Video.objects.create(course=course, title="שיעור ראשון", lesson_order=1)
    before = Video.objects.filter(course=course).count()

    sign_in(client)
    client.get(reverse("matazim:test_lessons"))
    client.get(reverse("matazim:test_task"))

    course.refresh_from_db()
    assert Video.objects.filter(course=course).count() == before
    assert course.project_upload_type == "tinkercad"


# ---------------------------------------------------------------- F-M.3.5


def test_a_lesson_shows_the_video_and_never_the_transcript(client, db):
    """T-F-M.3.5-1: REQ-M.48. A wall of text is a reason to stop."""
    from app.models import Course, Video

    course = Course.objects.create(slug="tinkercad", title="טינקרקאד", is_published=True)
    Video.objects.create(
        course=course,
        title="צורות בסיסיות",
        lesson_order=1,
        bunny_video_id="abc123",
        notes_markdown="תמלול ארוך מאוד שאסור להופיע כאן",
        summary_he="סיכום שגם הוא לא אמור להופיע",
    )

    sign_in(client)
    html = client.get(reverse("matazim:test_lesson", args=[1])).content.decode()
    assert "צורות בסיסיות" in html
    assert "abc123" in html
    assert "תמלול ארוך מאוד שאסור להופיע כאן" not in html
    assert "סיכום שגם הוא לא אמור להופיע" not in html


def test_watching_writes_progress_through_the_shared_tables(client, db):
    """T-F-M.3.5-2: REQ-M.49, one place, no backfill, no parallel table."""
    from app.models import Course, Enrollment, Video

    course = Course.objects.create(slug="tinkercad", title="טינקרקאד", is_published=True)
    Video.objects.create(course=course, title="שיעור", lesson_order=1, bunny_video_id="v1")

    user = sign_in(client)
    client.get(reverse("matazim:test_lesson", args=[1]))
    assert Enrollment.objects.filter(user=user, course=course).exists()


# ---------------------------------------------------------------- F-M.3.6


def test_reaching_the_task_assigns_one_target_and_keeps_it(client, db):
    """T-F-M.3.6-1: REQ-M.51. Shopping for an easier object is not possible."""
    from matazim.models import EntranceAttempt
    from matazim.targets import sync_bank

    sync_bank()
    user = sign_in(client)

    client.get(reverse("matazim:test_task"))
    first = EntranceAttempt.objects.get(member__user=user)

    client.get(reverse("matazim:test_task"))
    assert EntranceAttempt.objects.filter(member__user=user).count() == 1
    assert EntranceAttempt.objects.get(member__user=user).target_id == first.target_id


def test_the_task_shows_drawing_model_and_brief_and_has_no_video(client, db):
    """T-F-M.3.6-2: REQ-M.50. Formal drawing and 3D, as Avi asked."""
    from matazim.targets import sync_bank

    sync_bank()
    sign_in(client)
    html = client.get(reverse("matazim:test_task")).content.decode()

    assert "/static/matazim/targets/" in html
    assert ".svg" in html
    assert ".stl" in html
    # The brief says מ"מ, which autoescaping renders as מ&quot;מ, so match on a
    # phrase without a quote in it rather than on the escaping.
    assert "מידות חיצוניות" in html
    assert "iframe.mediadelivery" not in html


def test_a_retired_target_is_never_assigned(db):
    """T-F-M.3.6-3: retiring has to actually mean something."""
    from matazim.models import EntranceTarget
    from matazim.targets import pick_target, sync_bank

    sync_bank()
    EntranceTarget.objects.exclude(target_id="t0000").update(is_retired=True)
    assert pick_target().target_id == "t0000"

    EntranceTarget.objects.all().update(is_retired=True)
    assert pick_target() is None


# ---------------------------------------------------------------- F-M.3.7


def test_uploading_the_right_model_passes(client, db):
    """T-F-M.3.7-1: the reference model itself must clear its own bar."""
    from matazim.models import EntranceAttempt
    from matazim.targets import sync_bank

    sync_bank()
    user = sign_in(client)
    client.get(reverse("matazim:test_task"))
    attempt = EntranceAttempt.objects.get(member__user=user)

    client.post(
        reverse("matazim:test_task"),
        {"model_file": SimpleUploadedFile("mine.stl", target_stl(attempt.target_id))},
    )
    attempt.refresh_from_db()
    assert attempt.passed is True
    assert attempt.submitted_at is not None


def test_uploading_a_wrong_model_does_not_pass_and_says_why(client, db):
    """T-F-M.3.7-2: a different object from the bank is exactly the wrong size."""
    from matazim.models import EntranceAttempt
    from matazim.targets import sync_bank

    sync_bank()
    user = sign_in(client)
    client.get(reverse("matazim:test_task"))
    attempt = EntranceAttempt.objects.get(member__user=user)

    wrong = "t0005" if attempt.target_id != "t0005" else "t0000"
    client.post(
        reverse("matazim:test_task"),
        {"model_file": SimpleUploadedFile("mine.stl", target_stl(wrong))},
    )
    attempt.refresh_from_db()
    assert attempt.passed is False
    assert attempt.issues


def test_a_file_that_is_not_an_stl_is_refused_kindly(client, db):
    """T-F-M.3.7-3: a confused teenager gets a sentence, not a stack trace."""
    from matazim.targets import sync_bank

    sync_bank()
    sign_in(client)
    client.get(reverse("matazim:test_task"))

    resp = client.post(
        reverse("matazim:test_task"),
        {"model_file": SimpleUploadedFile("holiday.jpg", b"not a model at all")},
    )
    assert resp.status_code in (200, 302)


# ---------------------------------------------------------------- F-M.3.8


def test_a_miss_says_not_yet_and_never_rejected(client, db):
    """T-F-M.3.8-1: REQ-M.53. What a kid reads first decides whether they retry."""
    from matazim.models import EntranceAttempt
    from matazim.targets import sync_bank

    sync_bank()
    user = sign_in(client)
    client.get(reverse("matazim:test_task"))
    attempt = EntranceAttempt.objects.get(member__user=user)

    # A deliberately unmistakable miss rather than another target's model.
    # Substituting a different target used to be the way this was written, and
    # it made the test a coin flip: the bank is drawn from at random, and two
    # targets can be close enough that the substitute measures as a pass, at
    # which point the assertion below is checking a success message. A 1mm
    # tetrahedron cannot match anything in the bank.
    tiny = b"""solid tiny
facet normal 0 0 1
outer loop
vertex 0 0 0
vertex 1 0 0
vertex 0 1 0
endloop
endfacet
endsolid tiny
"""

    resp = client.post(
        reverse("matazim:test_task"),
        {"model_file": SimpleUploadedFile("mine.stl", tiny)},
        follow=True,
    )
    attempt.refresh_from_db()
    assert not attempt.passed, "the fixture was meant to be an obvious miss"

    html = resp.content.decode()
    assert "נדחה" not in html, "REQ-M.53: there is no machine rejection, only not yet"
    assert "עוד" in html or "כמעט" in html or "מתקרב" in html


def test_a_retry_draws_a_fresh_target_and_keeps_the_history(client, db):
    """T-F-M.3.8-2: REQ-M.51 and REQ-M.53 together.

    A new object each time is what makes a downloaded model useless, and the
    earlier attempt has to survive because the history is the commitment signal.
    """
    from matazim.models import EntranceAttempt
    from matazim.targets import sync_bank

    sync_bank()
    user = sign_in(client)
    client.get(reverse("matazim:test_task"))
    first = EntranceAttempt.objects.get(member__user=user)
    wrong = "t0005" if first.target_id != "t0005" else "t0000"
    client.post(
        reverse("matazim:test_task"),
        {"model_file": SimpleUploadedFile("mine.stl", target_stl(wrong))},
    )

    client.post(reverse("matazim:test_retry"))
    attempts = EntranceAttempt.objects.filter(member__user=user).order_by("number")
    assert attempts.count() == 2
    assert attempts[1].number == 2
    assert attempts[0].submitted_at is not None


# ---------------------------------------------------------------- F-M.3.9


def test_passing_opens_the_student_door(client, db):
    """T-F-M.3.9-1: REQ-M.54, and the flag SPR-M.2 shipped finally gets set."""
    from matazim.models import EntranceAttempt, MemberProfile
    from matazim.targets import sync_bank

    sync_bank()
    user = sign_in(client)
    client.get(reverse("matazim:test_task"))
    attempt = EntranceAttempt.objects.get(member__user=user)

    assert "mz-door-locked" in client.get(reverse("matazim:home")).content.decode()

    client.post(
        reverse("matazim:test_task"),
        {"model_file": SimpleUploadedFile("mine.stl", target_stl(attempt.target_id))},
    )

    assert MemberProfile.objects.get(user=user).entrance_test_passed_at is not None
    assert "mz-door-locked" not in client.get(reverse("matazim:home")).content.decode()
