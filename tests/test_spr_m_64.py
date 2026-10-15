"""SPR-M.64 - the entrance product is approved by a person (REQ-M.182, REQ-M.183).

Atid: the TinkerCAD product goes to שקד and to Avi "לאישור", and שקד has to know
who submitted it, with a view over every school and every student. What these
tests protect: uploading a passing model does NOT open the door, only an approval
does; a return needs words; the team can overrule the script both ways; the
scope is the manager's own world plus the people with no leader yet; and a
member always sees where they stand.
"""

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from tests.test_spr_m_3 import target_stl

pytestmark = pytest.mark.sprm64

PASSWORD = "sprm64-pass-7710"


def _user(name):
    return User.objects.create_user(username=f"{name}@example.com", email=f"{name}@example.com",
                                    password=PASSWORD)


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, StudyClass
    from matazim.targets import sync_bank

    sync_bank()
    inst = Institution.objects.create(name="רשת עתיד")
    pm = _user("pm")
    inst.managers.add(pm)
    leader = Leader.objects.create(user=_user("leader"), institution=inst,
                                   approved_at=timezone.now())
    StudyClass.objects.create(leader=leader, name="ט1", school_name="עתיד רמלה")
    return {"inst": inst, "pm": pm, "leader": leader}


def _submit(client, user, good=True):
    """The member uploads. Returns the attempt."""
    from matazim.models import EntranceAttempt

    client.force_login(user)
    client.get("/matazim/test/task/")
    attempt = EntranceAttempt.objects.filter(member__user=user, submitted_at__isnull=True).first()
    data = target_stl(attempt.target_id) if good else b"solid empty\nendsolid empty\n"
    client.post("/matazim/test/task/", {"model_file": SimpleUploadedFile("m.stl", data)})
    attempt.refresh_from_db()
    return attempt


def _passed_at(user):
    from matazim.models import MemberProfile

    return MemberProfile.objects.get(user=user).entrance_test_passed_at


def test_a_passing_upload_does_not_open_the_door(client, world):
    from matazim.models import EntranceAttempt

    kid = _user("kid")
    attempt = _submit(client, kid)
    assert attempt.passed is True
    assert attempt.decision == EntranceAttempt.WAITING
    assert _passed_at(kid) is None


def test_approval_sets_the_flag_and_tells_the_member(client, world):
    from matazim.models import EntranceAttempt, Notification

    kid = _user("kid")
    attempt = _submit(client, kid)

    client.force_login(world["pm"])
    resp = client.post(f"/matazim/staff/entrance/{attempt.pk}/decide/", {"action": "approve"})
    assert resp.status_code == 302

    attempt.refresh_from_db()
    assert attempt.decision == EntranceAttempt.APPROVED
    assert attempt.decided_by_id == world["pm"].pk and attempt.decided_at
    assert _passed_at(kid) is not None
    assert Notification.objects.filter(user=kid, kind=Notification.ENTRANCE_APPROVED).exists()


def test_the_team_can_approve_what_the_script_failed(client, world):
    """The measurement is advice in both directions."""
    kid = _user("kid")
    attempt = _submit(client, kid, good=False)
    assert attempt.passed is False

    client.force_login(world["pm"])
    client.post(f"/matazim/staff/entrance/{attempt.pk}/decide/", {"action": "approve"})
    assert _passed_at(kid) is not None


def test_a_return_needs_words_and_leaves_the_door_shut(client, world):
    from matazim.models import EntranceAttempt, Notification

    kid = _user("kid")
    attempt = _submit(client, kid)
    client.force_login(world["pm"])

    resp = client.post(f"/matazim/staff/entrance/{attempt.pk}/decide/",
                       {"action": "return", "note": "   "})
    assert resp["Location"].endswith("?error=note")
    attempt.refresh_from_db()
    assert attempt.decision == EntranceAttempt.WAITING

    client.post(f"/matazim/staff/entrance/{attempt.pk}/decide/",
                {"action": "return", "note": "הבסיס צריך להיות רחב יותר"})
    attempt.refresh_from_db()
    assert attempt.decision == EntranceAttempt.RETURNED
    assert attempt.decision_note == "הבסיס צריך להיות רחב יותר"
    assert _passed_at(kid) is None
    assert Notification.objects.filter(user=kid, kind=Notification.ENTRANCE_RETURNED).exists()


def test_only_a_program_manager_decides(client, world):
    kid = _user("kid")
    attempt = _submit(client, kid)

    for who in (world["leader"].user, kid):
        client.force_login(who)
        assert client.post(f"/matazim/staff/entrance/{attempt.pk}/decide/",
                           {"action": "approve"}).status_code == 403
    assert _passed_at(kid) is None


def test_another_institutions_manager_cannot_decide_my_members_attempt(client, world):
    from matazim.models import Institution, Leader, Student

    kid = _user("kid")
    Student.objects.create(user=kid, leader=world["leader"], status="in_training")
    attempt = _submit(client, kid)

    other = Institution.objects.create(name="רשת אחרת")
    other_pm = _user("otherpm")
    other.managers.add(other_pm)
    client.force_login(other_pm)
    assert client.post(f"/matazim/staff/entrance/{attempt.pk}/decide/",
                       {"action": "approve"}).status_code == 404
    assert _passed_at(kid) is None


def test_a_member_with_no_leader_is_still_seen_by_the_manager(client, world):
    """The seam visible_students documents: nobody's yet is not nobody's business."""
    kid = _user("kid")
    attempt = _submit(client, kid)
    client.force_login(world["pm"])
    html = client.get("/matazim/staff/entrance/").content.decode()
    assert f"/matazim/staff/entrance/{attempt.pk}/decide/" in html


def test_the_screen_groups_by_school_and_filters(client, world):
    from matazim.models import Student

    a, b = _user("alef"), _user("bet")
    s = Student.objects.create(user=a, leader=world["leader"], status="in_training")
    s.classes.add(world["leader"].classes.first())
    _submit(client, a)
    attempt_b = _submit(client, b)

    client.force_login(world["pm"])
    html = client.get("/matazim/staff/entrance/").content.decode()
    assert "עתיד רמלה" in html and "לא צוין בית ספר" in html
    assert html.count('class="mz-entrance-row"') == 2

    client.post(f"/matazim/staff/entrance/{attempt_b.pk}/decide/", {"action": "approve"})
    html = client.get("/matazim/staff/entrance/?state=waiting").content.decode()
    assert html.count('class="mz-entrance-row"') == 1


def test_the_member_sees_where_they_stand_and_no_fresh_task_while_waiting(client, world):
    from matazim.models import EntranceAttempt

    kid = _user("kid")
    _submit(client, kid)
    before = EntranceAttempt.objects.filter(member__user=kid).count()

    html = client.get("/matazim/test/task/").content.decode()
    assert 'id="mzWaitingTeam"' in html
    assert EntranceAttempt.objects.filter(member__user=kid).count() == before  # nothing new drawn


def test_a_returned_member_sees_the_note_and_can_try_again(client, world):
    kid = _user("kid")
    attempt = _submit(client, kid)
    client.force_login(world["pm"])
    client.post(f"/matazim/staff/entrance/{attempt.pk}/decide/",
                {"action": "return", "note": "חסר חור במרכז"})

    client.force_login(kid)
    html = client.get("/matazim/test/task/").content.decode()
    start = html.index('id="mzReturned"')
    assert "חסר חור במרכז" in html[start:html.index("</section>", start)]
    assert 'name="model_file"' in html


def test_what_already_passed_before_this_rule_reads_as_approved(db):
    """The migration: everyone let in by the script stays let in, and nobody
    who was not let in is waved through."""
    import importlib

    from django.apps import apps

    from matazim.models import EntranceAttempt, MemberProfile

    mod = importlib.import_module("matazim.migrations.0041_entrance_decision")
    let_in, not_let_in = _user("in"), _user("out")
    for user, passed_at in ((let_in, timezone.now()), (not_let_in, None)):
        MemberProfile.objects.update_or_create(
            user=user, defaults={"entrance_test_passed_at": passed_at})
        EntranceAttempt.objects.create(
            member=MemberProfile.objects.get(user=user), target_id="t1", number=1,
            passed=True, submitted_at=timezone.now())

    mod.approve_what_already_passed(apps, None)

    assert EntranceAttempt.objects.get(member__user=let_in).decision == "approved"
    assert EntranceAttempt.objects.get(member__user=not_let_in).decision == "waiting"
