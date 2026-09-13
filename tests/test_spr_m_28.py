"""SPR-M.28 — יוצרים: submissions, and the feedback that is the point of them.

Before this a leader could accept a student, read a roster and certify them.
That is administration. The spec has said which half matters since it was
written: *"the feedback is the interaction that matters here, not the approve
flag."*

So the load-bearing test here is `test_returning_work_without_words_is_refused`.
"Returned" on its own tells a fourteen-year-old they failed and not what to
change, which is the exact opposite of what this stage is for, and it is the
kind of rule that dies to one reasonable-looking convenience.

The second one to care about is the file. §4.10 P2 already found minors' uploads
sitting in public `/media/` under names like `יובל כהן מודל.stl`, and this
sprint adds a second place where a teenager uploads their work.

Traces: REQ-M.19, M.122, M.123, M.124, M.125, M.74, §4.4.
"""

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm28

PASSWORD = "sprm28-pass-9931"


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


def _leader(email="noa@example.com", name="נעה מורה", manager=None):
    from matazim.models import Leader

    return Leader.objects.create(
        user=_user(email, name),
        program_manager=manager or _manager(),
        approved_at=timezone.now(),
    )


def _student(email="kid@example.com", name="יובל כהן", leader=None):
    from matazim.models import MemberProfile, Student

    user = _user(email, name)
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now(),
            "birth_year": timezone.now().year - 14,
            "guardian_consent_at": timezone.now(),
            "welcome_accepted_at": timezone.now(),
        },
    )
    return Student.objects.create(
        user=user, leader=leader or _leader(), status=Student.IN_TRAINING
    )


def _hand_in(client, title="המבוך שלי", link="https://scratch.mit.edu/projects/1", **extra):
    payload = {"title": title, "about": "בניתי משחק", "link": link}
    payload.update(extra)
    return client.post(reverse("matazim:my_work"), payload)


# ------------------------------------------- F-M.28.2: handing work in


def test_a_member_hands_work_to_their_leader(client, db):
    """T-F-M.28.2-1: REQ-M.19."""
    from matazim.models import Submission

    student = _student()
    client.force_login(student.user)
    _hand_in(client)

    row = Submission.objects.get()
    assert row.student == student
    assert row.leader == student.leader, "nothing records who it was handed to"
    assert row.status == Submission.WAITING


def test_handing_work_in_moves_the_stage_and_logs_it(client, db):
    """T-F-M.28.2-2: REQ-M.74, §4.7.

    יוצרים is a stage of the programme, so reaching it is a transition like
    every other one, with a name and a time on it.
    """
    from matazim.models import Student

    student = _student()
    client.force_login(student.user)
    _hand_in(client)

    student.refresh_from_db()
    assert student.status == Student.PROJECT_SUBMITTED

    entry = student.history.order_by("-at").first()
    assert entry.to_status == Student.PROJECT_SUBMITTED
    assert entry.changed_by_id == student.user_id


def test_a_certified_mataz_is_not_sent_backwards(client, db):
    """T-F-M.28.2-3: handing in another project must not undo an honour.

    The obvious way to write the stage move is unconditionally, and it would
    take a certified מט״צ back to יוצרים for showing somebody a new project.
    """
    from matazim.models import Student

    student = _student()
    student.status = Student.CERTIFIED
    student.save(update_fields=["status"])

    client.force_login(student.user)
    _hand_in(client)

    student.refresh_from_db()
    assert student.status == Student.CERTIFIED


def test_work_needs_something_to_look_at(client, db):
    """T-F-M.28.2-4: a title and nothing else is not a submission."""
    from matazim.models import Submission

    student = _student()
    client.force_login(student.user)

    response = client.post(reverse("matazim:my_work"), {"title": "משהו", "about": "", "link": ""})
    assert response.status_code == 200
    assert not Submission.objects.exists()
    assert "קובץ או קישור" in response.content.decode()


# ------------------------------------------- F-M.28.3: the feedback


def test_returning_work_without_words_is_refused(client, db):
    """T-F-M.28.3-1: REQ-M.123, and the rule this sprint exists to protect.

    "Returned" on its own tells a fourteen-year-old they failed and not what to
    change. The refusal lives in the view, not in a placeholder on a textarea,
    because a template cannot refuse anything.
    """
    from matazim.models import Submission

    student = _student()
    client.force_login(student.user)
    _hand_in(client)
    submission = Submission.objects.get()

    client.force_login(student.leader.user)
    response = client.post(
        reverse("matazim:review", args=[submission.pk]), {"action": "return", "body": "   "}
    )

    assert response.status_code == 200
    submission.refresh_from_db()
    assert submission.status == Submission.WAITING, "work was sent back with no explanation"
    assert "מה לשנות" in response.content.decode()


def test_returning_work_with_words_reaches_the_member(client, db):
    """T-F-M.28.3-2: REQ-M.123.

    Written, stored, and readable by the person it is about. Feedback the
    member cannot see is a note to file.
    """
    from matazim.models import Submission

    student = _student()
    client.force_login(student.user)
    _hand_in(client)
    submission = Submission.objects.get()

    client.force_login(student.leader.user)
    client.post(
        reverse("matazim:review", args=[submission.pk]),
        {"action": "return", "body": "הרעיון טוב. הבסיס רעוע, תחזקי אותו ותגישי שוב."},
    )

    submission.refresh_from_db()
    assert submission.status == Submission.RETURNED

    client.force_login(student.user)
    html = client.get(reverse("matazim:my_work")).content.decode()
    assert "הבסיס רעוע, תחזקי אותו ותגישי שוב." in html
    assert "נעה מורה" in html, "the member cannot see who said it"


def test_approving_may_carry_words_and_need_not(client, db):
    """T-F-M.28.3-3: REQ-M.123. "Well done" is optional; "here is what to fix" is not."""
    from matazim.models import Submission

    student = _student()
    client.force_login(student.user)
    _hand_in(client)
    submission = Submission.objects.get()

    client.force_login(student.leader.user)
    client.post(reverse("matazim:review", args=[submission.pk]), {"action": "approve", "body": ""})

    submission.refresh_from_db()
    assert submission.status == Submission.APPROVED
    assert submission.decided_by == student.leader.user


def test_only_the_leader_it_was_handed_to_can_decide(client, db):
    """T-F-M.28.3-4: §4.4.

    Another leader may not answer work that was put in front of somebody else,
    even inside the same institution.
    """
    from matazim.models import Submission

    manager = _manager()
    mine = _leader("noa@example.com", "נעה מורה", manager)
    other = _leader("dana@example.com", "דנה כהן", manager)

    student = _student(leader=mine)
    client.force_login(student.user)
    _hand_in(client)
    submission = Submission.objects.get()

    client.force_login(other.user)
    assert client.get(reverse("matazim:review", args=[submission.pk])).status_code == 404
    response = client.post(
        reverse("matazim:review", args=[submission.pk]), {"action": "approve", "body": "יופי"}
    )
    assert response.status_code == 404

    submission.refresh_from_db()
    assert submission.status == Submission.WAITING


# ------------------------------------------- F-M.28.4: the queue


def test_work_waiting_shows_on_the_leaders_own_screen(client, db):
    """T-F-M.28.4-1: REQ-M.124.

    Somebody is waiting on a sentence from this person and nothing else in the
    product will tell them.
    """
    student = _student()
    client.force_login(student.user)
    _hand_in(client, title="המבוך שבניתי")

    client.force_login(student.leader.user)
    html = client.get(reverse("matazim:leader_home")).content.decode()

    assert "המבוך שבניתי" in html
    assert "עבודות שמחכות לך" in html


def test_answered_work_leaves_the_queue(client, db):
    """T-F-M.28.4-2: REQ-M.124. A queue that never empties is a list."""
    from matazim.models import Submission

    student = _student()
    client.force_login(student.user)
    _hand_in(client, title="המבוך שבניתי")
    submission = Submission.objects.get()

    client.force_login(student.leader.user)
    client.post(reverse("matazim:review", args=[submission.pk]), {"action": "approve", "body": ""})

    html = client.get(reverse("matazim:leader_home")).content.decode()
    assert "עבודות שמחכות לך" not in html


# ------------------------------------------- F-M.28.5: a second version


def test_a_returned_submission_can_be_answered_and_both_are_kept(client, db):
    """T-F-M.28.5-1: REQ-M.125.

    A resubmission that overwrote the first would destroy the thing the
    feedback was about, and a member reading "fix the base" wants the version
    that had the base.
    """
    from matazim.models import Submission

    student = _student()
    client.force_login(student.user)
    _hand_in(client, title="גרסה ראשונה")
    first = Submission.objects.get()

    client.force_login(student.leader.user)
    client.post(
        reverse("matazim:review", args=[first.pk]),
        {"action": "return", "body": "תחזקי את הבסיס"},
    )

    client.force_login(student.user)
    _hand_in(client, title="גרסה שנייה", answers=str(first.pk))

    rows = Submission.objects.order_by("created_at")
    assert [r.title for r in rows] == ["גרסה ראשונה", "גרסה שנייה"]
    assert rows[1].answers_id == first.pk
    first.refresh_from_db()
    assert first.status == Submission.RETURNED, "the first version was overwritten"


# ------------------------------------------- F-M.28.1: a minor's work


def test_the_file_is_not_in_public_media(client, db):
    """T-F-M.28.1-1: REQ-M.122, §4.10 P2.

    The finding that produced this rule: entrance uploads sat in `/media/`,
    served with no authentication, under names like `יובל כהן מודל.stl`. A
    second upload path must not reintroduce it.
    """
    from django.conf import settings

    from matazim.models import Submission

    student = _student()
    client.force_login(student.user)
    _hand_in(
        client,
        link="",
        work_file=SimpleUploadedFile("יובל כהן המבוך.sb3", b"scratch", "application/zip"),
    )

    row = Submission.objects.get()
    stored = str(row.work_file.name)

    assert "יובל" not in stored, "the child's name is in the path"
    assert "המבוך" not in stored, "the original filename was kept"
    assert str(settings.MEDIA_ROOT) not in str(row.work_file.path)
    assert str(settings.MATAZIM_PRIVATE_DIR) in str(row.work_file.path)


@pytest.mark.parametrize("who", ["owner", "leader", "manager", "root"])
def test_the_people_entitled_to_the_file_can_open_it(client, db, who):
    """T-F-M.28.1-2: REQ-M.122."""
    from matazim.models import Submission

    manager = _manager()
    leader = _leader("noa@example.com", "נעה מורה", manager)
    student = _student(leader=leader)

    client.force_login(student.user)
    _hand_in(client, link="", work_file=SimpleUploadedFile("work.sb3", b"scratch"))
    submission = Submission.objects.get()

    actor = {
        "owner": student.user,
        "leader": leader.user,
        "manager": manager,
        "root": User.objects.create_superuser("root@example.com", "root@example.com", PASSWORD),
    }[who]
    client.force_login(actor)

    assert client.get(reverse("matazim:work_file", args=[submission.pk])).status_code == 200


def test_a_stranger_is_told_nothing_at_all(client, db):
    """T-F-M.28.1-3: REQ-M.122.

    A 404 rather than a 403, because confirming submission 91 exists is itself
    something a stranger has no business learning.
    """
    from matazim.models import Submission

    student = _student()
    client.force_login(student.user)
    _hand_in(client, link="", work_file=SimpleUploadedFile("work.sb3", b"scratch"))
    submission = Submission.objects.get()

    other_manager = _manager("other@example.com")
    stranger = _student("nosy@example.com", "סקרן", leader=_leader("x@example.com", "זרה", other_manager))

    client.force_login(stranger.user)
    assert client.get(reverse("matazim:work_file", args=[submission.pk])).status_code == 404
    assert client.get(reverse("matazim:review", args=[submission.pk])).status_code == 404


def test_a_program_manager_sees_only_her_own_worlds_work(client, db):
    """T-F-M.28.1-4: §4.4, REQ-M.88."""
    from matazim.models import Submission

    naomi = _manager("naomi@example.com")
    hers = _leader("noa@example.com", "נעה מורה", naomi)
    student = _student(leader=hers)
    client.force_login(student.user)
    _hand_in(client)
    submission = Submission.objects.get()

    client.force_login(naomi)
    assert client.get(reverse("matazim:review", args=[submission.pk])).status_code == 200

    client.force_login(_manager("stranger@example.com"))
    assert client.get(reverse("matazim:review", args=[submission.pk])).status_code == 404
