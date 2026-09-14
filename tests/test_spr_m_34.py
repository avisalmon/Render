"""SPR-M.34 — the methodology retrofit: a REST API over every model.

REQ-M.139, REQ-M.140. `docs/building_an_app.md` Rules 4 and 6, applied to an app
that was built over thirty-three sprints before either existed. Avi, 2026-09-14:
"I need us to pause and stick to the principles there."

The single most important test in this file is
`test_no_endpoint_reaches_another_institution`. It builds two complete worlds
and, as a member of the first, asks every one of the eighteen endpoints for
everything, then checks that not one row from the second world came back. It is
written as a sweep rather than as eighteen hand-written cases on purpose: a
hand-written suite tests the endpoints somebody remembered, and the endpoint
that leaks will be the one they did not.

`test_every_model_has_an_endpoint` is the other half of that. A sweep only
covers what is registered, so something has to fail when a model is added and
its route is not.

The rest hold the refusals. Rule 6 asks for real CRUD rather than the verbs a
screen happens to need; it does not ask for a way around rules this product
already has. Each refusal below names the requirement it protects, because a
405 with no reason behind it is indistinguishable from an oversight.

Traces: REQ-M.139, M.140, §4.4, §4.7, M.21, M.53, M.78, M.80, M.87, M.112,
M.114, M.122, M.123, M.124, M.131.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

pytestmark = pytest.mark.sprm34

PASSWORD = "sprm34-pass-6624"
API = "/matazim/api/"


# --------------------------------------------------------------- two worlds


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def build_world(tag, *, secret):
    """One complete institution, with a row in every table that has one.

    `secret` is a string planted in every free-text field, so the leak test can
    ask one question of every response body: does the other world's word appear
    anywhere in it.
    """
    from matazim.history import record_arrival, set_status
    from matazim.models import (
        Application,
        EntranceAttempt,
        EntranceTarget,
        Event,
        Feedback,
        Leader,
        LeaderInvite,
        MatazCertificate,
        MemberProfile,
        Notification,
        Post,
        Request,
        RequestMessage,
        RetentionRun,
        Student,
        StudyClass,
        Submission,
    )

    manager = _user(f"pm-{tag}@example.com", f"מנהלת {secret}")
    MemberProfile.objects.update_or_create(
        user=manager, defaults={"is_program_manager": True}
    )

    leader = Leader.objects.create(
        user=_user(f"leader-{tag}@example.com", f"מוביל {secret}"),
        program_manager=manager,
        approved_at=timezone.now(),
        contact=secret,
    )
    study_class = StudyClass.objects.create(
        leader=leader, name=f"ט1 {secret}", school_name=f"בית ספר {secret}"
    )

    member_user = _user(f"kid-{tag}@example.com", f"תלמיד {secret}")
    member = MemberProfile.objects.update_or_create(
        user=member_user,
        defaults={
            "entrance_test_passed_at": timezone.now(),
            "birth_year": timezone.now().year - 14,
            "guardian_name": f"הורה {secret}",
            "guardian_email": f"parent-{tag}@example.com",
            "guardian_consent_at": timezone.now(),
            "welcome_accepted_at": timezone.now(),
        },
    )[0]
    student = Student.objects.create(
        user=member_user, leader=leader, status=Student.IN_TRAINING
    )
    student.classes.add(study_class)
    record_arrival(student)

    EntranceTarget.objects.create(
        target_id=f"t-{tag}", shape="cube", title=f"מטרה {secret}", brief=secret
    )
    EntranceAttempt.objects.create(
        member=member, target_id=f"t-{tag}", number=1, passed=True, issues=[secret]
    )

    LeaderInvite.objects.create(
        program_manager=manager, kind=LeaderInvite.PERSONAL, label=secret,
        token=f"tok-{tag}-0123456789",
    )
    Application.objects.create(
        student=student, asked=leader, grade="ט1", motivation=secret, built_before=secret
    )

    submission = Submission.objects.create(
        student=student, leader=leader, title=f"עבודה {secret}", about=secret,
        status=Submission.APPROVED,
    )
    Feedback.objects.create(
        submission=submission, author=leader.user, body=secret,
        outcome=Submission.APPROVED,
    )

    Notification.objects.create(
        user=member_user, kind=Notification.WORK_APPROVED, text=secret,
        url="/matazim/my-work/",
    )

    event = Event.objects.create(
        program_manager=manager, title=f"יום {secret}", about=secret,
        starts_at=timezone.now() + timezone.timedelta(days=5), place=secret,
        for_everyone=True,
    )
    event.leaders.add(leader)

    Post.objects.create(author=member_user, program_manager=manager, body=secret)

    req = Request.objects.create(
        author=manager, author_role="program_manager", body=secret,
        kind=Request.IDEA, status=Request.NEW,
    )
    RequestMessage.objects.create(request=req, who=RequestMessage.HER, body=secret)

    RetentionRun.objects.create(ran_by=manager, deleted_count=0, kind="failed_attempts")

    set_status(student, Student.PROJECT_SUBMITTED, by=leader.user, note=secret)
    set_status(student, Student.CERTIFIED, by=leader.user, note=secret)
    MatazCertificate.objects.create(
        student=student,
        name_on_certificate=f"תלמיד {secret}",
        awarded_by_name=f"מוביל {secret}",
        awarded_at=timezone.now(),
    )

    return {
        "manager": manager,
        "leader": leader,
        "class": study_class,
        "student": student,
        "member_user": member_user,
        "submission": submission,
        "event": event,
        "request": req,
    }


@pytest.fixture
def two_worlds(db):
    """Two institutions that share nothing but the `User` table."""
    return {
        "ours": build_world("a", secret="אלפא"),
        "theirs": build_world("b", secret="ביתא"),
    }


# The one table that is deliberately shared across institutions, and the only
# exception to the sweep below. The entrance-test bank is generated files: the
# same cube for everybody, seeded by a management command, with nothing
# per-institution about it. `test_the_bank_is_shared_on_purpose` asserts that
# rather than leaving it as a hole in the sweep, and names the cost.
SHARED_ACROSS_INSTITUTIONS = {"entrance-targets"}


def _routes():
    from matazim.api import ROUTES

    return [prefix for prefix, _viewset, _model in ROUTES]


# ------------------------------------------------------- the sweep that matters


@pytest.mark.parametrize("who", ["member_user", "leader", "manager"])
def test_no_endpoint_reaches_another_institution(client, two_worlds, who):
    """T-F-M.34.1-1: §4.4, asked of every endpoint at once.

    Written as a sweep rather than eighteen hand-written cases, because a
    hand-written suite covers the endpoints somebody remembered and the one
    that leaks will be the one they did not.

    Three readers, because the three roles reach the data by three different
    routes and a filter can be right for one and wrong for another.
    """
    person = two_worlds["ours"][who]
    if who == "leader":
        person = person.user
    client.force_login(person)

    leaked = []
    for prefix in _routes():
        response = client.get(f"{API}{prefix}/")
        assert response.status_code in (200, 403), f"{prefix} answered {response.status_code}"
        if response.status_code != 200 or prefix in SHARED_ACROSS_INSTITUTIONS:
            continue
        if "ביתא" in response.content.decode():
            leaked.append(prefix)

    assert not leaked, f"another institution's rows came back from: {leaked}"


def test_every_model_has_an_endpoint(db):
    """T-F-M.34.1-2: REQ-M.139, methodology Rule 6.

    The sweep above only covers what is registered, so something has to fail
    when a model is added and its route is not. This is that something.
    """
    from django.apps import apps

    from matazim.api import ROUTES

    wired = {model for _prefix, _viewset, model in ROUTES}
    declared = set(apps.get_app_config("matazim").get_models())

    missing = {m.__name__ for m in declared - wired}
    assert not missing, f"models with no REST endpoint: {sorted(missing)}"


def test_every_endpoint_refuses_a_stranger(client, two_worlds):
    """T-F-M.34.1-3: nothing in this app is readable by an anonymous client.

    The public surfaces of מט״צים are pages, each of which decides exactly what
    a stranger may see. None of them needs a queryset handed out.
    """
    open_to_all = []
    for prefix in _routes():
        response = client.get(f"{API}{prefix}/")
        if response.status_code == 200:
            open_to_all.append(prefix)

    assert not open_to_all, f"open to anonymous clients: {open_to_all}"


def test_a_member_cannot_read_the_staff_only_tables(client, two_worlds):
    """T-F-M.34.1-4: REQ-M.79, REQ-M.62, REQ-M.87.

    Three tables a teenager has no business in, and one of them is a list of
    live keys: an invite token attaches its holder to a leader with no
    confirmation.
    """
    client.force_login(two_worlds["ours"]["member_user"])

    for prefix in ("leader-invites", "entrance-targets", "retention-runs", "requests"):
        response = client.get(f"{API}{prefix}/")
        rows = response.json() if response.status_code == 200 else []
        rows = rows.get("results", rows) if isinstance(rows, dict) else rows
        assert response.status_code == 403 or not rows, f"{prefix} was readable by a member"


def test_no_endpoint_hands_out_a_key_or_a_file(client, two_worlds):
    """T-F-M.34.1-5: REQ-M.9, REQ-M.79, REQ-M.80, REQ-M.122.

    Four fields that must never appear in a response body: a leader's join code
    and an invite's token, because each attaches its holder to somebody with no
    confirmation, and the two file fields, because a minor's own work is handed
    out only by a view that asks who is looking.
    """
    client.force_login(two_worlds["ours"]["manager"])

    forbidden = ("join_code", "token", "model_file", "work_file")
    for prefix in _routes():
        response = client.get(f"{API}{prefix}/")
        if response.status_code != 200:
            continue
        body = response.content.decode()
        for field in forbidden:
            assert f'"{field}"' not in body, f"{prefix} returned {field}"


# ------------------------------------------------- the refusals, one at a time


def test_a_status_log_is_append_only(client, two_worlds):
    """T-F-M.34.2-1: §4.7, REQ-M.21.

    Every other record here answers "what is true now". This one answers "who
    decided, and when", and a history somebody can edit is the same as none.
    """
    from matazim.models import StatusLog

    client.force_login(two_worlds["ours"]["manager"])
    row = StatusLog.objects.filter(student=two_worlds["ours"]["student"]).first()

    assert client.post(f"{API}status-logs/", {}, content_type="application/json").status_code == 405
    assert client.patch(f"{API}status-logs/{row.pk}/", {"note": "x"},
                        content_type="application/json").status_code == 405
    assert client.delete(f"{API}status-logs/{row.pk}/").status_code == 405
    assert StatusLog.objects.filter(pk=row.pk).exists()


def test_a_students_status_cannot_be_written_as_a_field(client, two_worlds):
    """T-F-M.34.2-2: §4.7, and the reason the serializer field is read-only.

    A status that moves without writing its log is a teenager moved between
    stages with nobody recorded as having decided it. The guard test that
    watches for `something.status = ...` cannot see inside a ModelSerializer,
    so this is the test that can.
    """
    from matazim.models import Student

    student = two_worlds["ours"]["student"]
    client.force_login(two_worlds["ours"]["manager"])

    client.patch(
        f"{API}students/{student.pk}/",
        {"status": Student.REVOKED},
        content_type="application/json",
    )

    student.refresh_from_db()
    assert student.status != Student.REVOKED, "a status moved with no log behind it"


def test_the_status_action_writes_the_log(client, two_worlds):
    """T-F-M.34.2-3: §4.7 — the door that is open, and what it records."""
    from matazim.models import StatusLog, Student

    student = two_worlds["ours"]["student"]
    client.force_login(two_worlds["ours"]["manager"])

    response = client.post(
        f"{API}students/{student.pk}/set_status/",
        {"status": Student.ALUMNUS, "note": "סיים/ה"},
        content_type="application/json",
    )

    assert response.status_code == 200
    student.refresh_from_db()
    assert student.status == Student.ALUMNUS
    assert StatusLog.objects.filter(
        student=student, to_status=Student.ALUMNUS
    ).exists(), "the stage moved and nothing recorded who decided"


def test_feedback_is_never_edited_or_deleted(client, two_worlds):
    """T-F-M.34.2-4: REQ-M.123.

    Sharper than `StatusLog`, because this one is read by a fourteen-year-old.
    Words that can be changed afterwards are words they cannot rely on having
    read.
    """
    from matazim.models import Feedback

    row = Feedback.objects.filter(
        submission=two_worlds["ours"]["submission"]
    ).first()
    client.force_login(two_worlds["ours"]["leader"].user)

    assert client.patch(f"{API}feedback/{row.pk}/", {"body": "אחרת"},
                        content_type="application/json").status_code == 403
    assert client.delete(f"{API}feedback/{row.pk}/").status_code == 403

    row.refresh_from_db()
    assert row.body == "אלפא"


def test_an_entrance_attempt_is_never_rewritten(client, two_worlds):
    """T-F-M.34.2-5: REQ-M.53.

    A retry is a new row, because somebody who missed, read the feedback and
    came back has shown more of what this programme selects for than somebody
    who passed first time. Editing one rewrites that; deleting one erases it.
    """
    from matazim.models import EntranceAttempt

    row = EntranceAttempt.objects.filter(member__user=two_worlds["ours"]["member_user"]).first()
    client.force_login(two_worlds["ours"]["member_user"])

    assert client.patch(f"{API}entrance-attempts/{row.pk}/", {"passed": False},
                        content_type="application/json").status_code == 405
    assert client.delete(f"{API}entrance-attempts/{row.pk}/").status_code == 405

    row.refresh_from_db()
    assert row.passed is True


def test_a_notification_cannot_be_forged(client, two_worlds):
    """T-F-M.34.2-6: REQ-M.33.

    A notification says "something happened to you". A client that can write
    one can tell a teenager anything and point them anywhere, which is why they
    are written next to the thing that actually happened.
    """
    from matazim.models import Notification

    before = Notification.objects.count()
    client.force_login(two_worlds["ours"]["member_user"])

    response = client.post(
        f"{API}notifications/",
        {"kind": "certified", "text": "הוסמכת!", "url": "/matazim/"},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert Notification.objects.count() == before


def test_a_member_reads_only_their_own_bell(client, two_worlds):
    """T-F-M.34.2-7: REQ-M.33 — not even their leader reads it.

    A notification points at something the reader can already reach if they are
    entitled to it, so there is nothing here a staff member needs.
    """
    client.force_login(two_worlds["ours"]["leader"].user)
    payload = client.get(f"{API}notifications/").json()
    rows = payload.get("results", payload) if isinstance(payload, dict) else payload

    assert rows == [], "a leader read somebody else's notifications"


def test_only_root_grants_the_program_manager_role(client, two_worlds):
    """T-F-M.34.2-8: REQ-M.114.

    The role could once replicate itself: the screen handing out the highest
    role in the product was open to everybody who already held it. A writable
    serializer field would put that hole straight back, in a place no screen
    shows.
    """
    from matazim.models import MemberProfile

    profile = MemberProfile.objects.get(user=two_worlds["ours"]["member_user"])
    client.force_login(two_worlds["ours"]["manager"])

    client.patch(
        f"{API}member-profiles/{profile.pk}/",
        {"is_program_manager": True},
        content_type="application/json",
    )

    profile.refresh_from_db()
    assert profile.is_program_manager is False, "the role was granted through the API"


def test_passing_the_entrance_test_cannot_be_written(client, two_worlds):
    """T-F-M.34.2-9: REQ-M.36 — the gate to the whole programme."""
    from matazim.models import MemberProfile

    profile = MemberProfile.objects.get(user=two_worlds["ours"]["member_user"])
    profile.entrance_test_passed_at = None
    profile.save(update_fields=["entrance_test_passed_at"])

    client.force_login(two_worlds["ours"]["member_user"])
    client.patch(
        f"{API}member-profiles/{profile.pk}/",
        {"entrance_test_passed_at": timezone.now().isoformat()},
        content_type="application/json",
    )

    profile.refresh_from_db()
    assert profile.entrance_test_passed_at is None, "somebody walked through the gate"


def test_work_cannot_be_sent_back_without_words(client, two_worlds):
    """T-F-M.34.2-10: REQ-M.124.

    The rule this API had to be shaped around. "החזרה בלי מילים אומרת למי שכתב
    אותה שהוא נכשל, ולא מה לעשות." A writable `status` field would have been a
    way to say no with no words in it, so the field is read-only and this is
    the door.
    """
    from matazim.models import Submission

    submission = two_worlds["ours"]["submission"]
    client.force_login(two_worlds["ours"]["leader"].user)

    refused = client.post(
        f"{API}submissions/{submission.pk}/send-back/", {"body": "  "},
        content_type="application/json",
    )
    assert refused.status_code == 400
    submission.refresh_from_db()
    assert submission.status == Submission.APPROVED

    ok = client.post(
        f"{API}submissions/{submission.pk}/send-back/",
        {"body": "תשנה/י את הבסיס, הוא צר מדי"},
        content_type="application/json",
    )
    assert ok.status_code == 200
    submission.refresh_from_db()
    assert submission.status == Submission.RETURNED


def test_a_certificate_is_not_created_or_deleted_through_the_api(client, two_worlds):
    """T-F-M.34.2-11: REQ-M.20, REQ-M.78.

    `certification.certify` copies the name and the awarding name onto the row
    at the moment of issue, so a certificate created through a generic POST
    would be a document about a moment that never happened.
    """
    from matazim.models import MatazCertificate

    row = MatazCertificate.objects.filter(student=two_worlds["ours"]["student"]).first()
    client.force_login(two_worlds["ours"]["manager"])

    assert client.post(f"{API}certificates/", {}, content_type="application/json").status_code == 405
    assert client.delete(f"{API}certificates/{row.pk}/").status_code == 405
    assert MatazCertificate.objects.filter(pk=row.pk).exists()


def test_her_words_are_hers(client, two_worlds):
    """T-F-M.34.2-12: REQ-M.112, §4.11.

    A filed request is the thing Avi read. A later edit changes what he decided
    on, so the body is editable only by its author and only while it is a draft.
    """
    from matazim.models import Request

    row = two_worlds["ours"]["request"]
    other = two_worlds["theirs"]["manager"]

    client.force_login(other)
    assert client.patch(f"{API}requests/{row.pk}/", {"body": "משהו אחר"},
                        content_type="application/json").status_code == 404

    client.force_login(two_worlds["ours"]["manager"])
    assert client.patch(f"{API}requests/{row.pk}/", {"body": "משהו אחר"},
                        content_type="application/json").status_code == 403

    row.refresh_from_db()
    assert row.body == "אלפא"


def test_only_root_decides_a_request(client, two_worlds):
    """T-F-M.34.2-13: §4.11 — one human gate, and it is Avi's press."""
    from matazim.models import Request

    row = two_worlds["ours"]["request"]
    client.force_login(two_worlds["ours"]["manager"])

    assert client.post(f"{API}requests/{row.pk}/approve/").status_code == 403
    row.refresh_from_db()
    assert row.status == Request.NEW


def test_a_retention_run_is_a_record_not_a_row_to_write(client, two_worlds):
    """T-F-M.34.2-14: REQ-M.87.

    Deletion is the one action here where an unattended bug is irreversible, so
    it runs behind a person's review. A POST creating one of these would be a
    claim that a review happened.
    """
    from matazim.models import RetentionRun

    before = RetentionRun.objects.count()
    client.force_login(two_worlds["ours"]["manager"])

    assert client.post(f"{API}retention-runs/", {"deleted_count": 9, "kind": "x"},
                       content_type="application/json").status_code == 405
    assert RetentionRun.objects.count() == before


# --------------------------------------------------- the verbs that do work


def test_a_leader_is_created_into_the_creators_world_and_is_unapproved(client, two_worlds):
    """T-F-M.34.3-1: §4.4, REQ-M.93.

    Two things at once, because they are one decision: the institution is
    stamped from whoever created the row, and approval is an act by a person
    rather than a default. `leader_of()` refuses an unapproved row, so a leader
    created here grants nothing until somebody says yes through `approve`.
    """
    from matazim.access import leader_of
    from matazim.models import Leader

    newcomer = _user("fresh@example.com", "דנה חדשה")
    manager = two_worlds["ours"]["manager"]
    client.force_login(manager)

    response = client.post(
        f"{API}leaders/",
        {"user_id": newcomer.id, "contact": "0500000000"},
        content_type="application/json",
    )
    assert response.status_code == 201, response.content

    row = Leader.objects.get(pk=response.json()["id"])
    assert row.program_manager_id == manager.id, "a leader was created into no world"
    assert row.approved_at is None, "a leader was approved by being created"
    assert leader_of(newcomer) is None, "an unapproved row granted the role anyway"

    approved = client.post(f"{API}leaders/{row.pk}/approve/")
    assert approved.status_code == 200
    assert leader_of(newcomer) is not None


def test_a_leader_is_never_made_out_of_an_account_that_does_not_exist(client, two_worlds):
    """T-F-M.34.3-1b: the same lesson `staff_admins` learned from the other side.

    A typo must not conjure a record holding a role. Before this it was worse
    than wrong: the POST crashed on a NOT NULL constraint, which is a 500 rather
    than an answer.
    """
    from matazim.models import Leader

    before = Leader.objects.count()
    client.force_login(two_worlds["ours"]["manager"])

    response = client.post(
        f"{API}leaders/", {"user_id": 999999}, content_type="application/json"
    )

    assert response.status_code == 400, response.content
    assert Leader.objects.count() == before


def test_a_member_posts_edits_and_withdraws_their_own_work(client, two_worlds, settings):
    """T-F-M.34.3-2: Rule 6's actual point — real CRUD, not the screen's verbs.

    The screens never offered editing a submission. The API does, because the
    rule is that every row is an object a person can fix a mistake in without
    going to /admin/.
    """
    settings.CONTENT_RELEVANCE_ENABLED = False
    from matazim.models import Submission

    client.force_login(two_worlds["ours"]["member_user"])

    created = client.post(
        f"{API}submissions/",
        {"title": "המשחק שלי", "about": "סקראץ׳", "link": "https://scratch.mit.edu/x"},
        content_type="application/json",
    )
    assert created.status_code == 201, created.content
    row_id = created.json()["id"]

    edited = client.patch(
        f"{API}submissions/{row_id}/", {"title": "המשחק שלי, גרסה ב"},
        content_type="application/json",
    )
    assert edited.status_code == 200
    assert Submission.objects.get(pk=row_id).title == "המשחק שלי, גרסה ב"

    assert client.delete(f"{API}submissions/{row_id}/").status_code == 204
    assert not Submission.objects.filter(pk=row_id).exists()


def test_nobody_edits_or_deletes_somebody_elses_work(client, two_worlds):
    """T-F-M.34.3-3: the other half of the verb above."""
    from matazim.models import Submission

    submission = two_worlds["ours"]["submission"]
    client.force_login(two_worlds["ours"]["leader"].user)

    assert client.patch(f"{API}submissions/{submission.pk}/", {"title": "אחר"},
                        content_type="application/json").status_code == 403
    assert client.delete(f"{API}submissions/{submission.pk}/").status_code == 403
    assert Submission.objects.filter(pk=submission.pk).exists()


def test_an_event_is_cancelled_rather_than_deleted_through_the_api(client, two_worlds):
    """T-F-M.34.3-4: REQ-M.27 — the same manners the screen has."""
    event = two_worlds["ours"]["event"]
    client.force_login(two_worlds["ours"]["manager"])

    response = client.post(f"{API}events/{event.pk}/cancel/")
    assert response.status_code == 200

    event.refresh_from_db()
    assert event.is_cancelled


def test_a_member_cannot_write_an_event(client, two_worlds):
    """T-F-M.34.3-5: §4.4a — reading the diary is not writing it."""
    from matazim.models import Event

    before = Event.objects.count()
    client.force_login(two_worlds["ours"]["member_user"])

    response = client.post(
        f"{API}events/",
        {"title": "יום שהמצאתי", "starts_at": timezone.now().isoformat()},
        content_type="application/json",
    )
    assert response.status_code == 403
    assert Event.objects.count() == before


def test_the_bank_is_shared_on_purpose(client, two_worlds):
    """T-F-M.34.1-6: the sweep's one exception, asserted rather than skipped.

    The entrance-test bank is generated geometry: the same cube for everybody,
    seeded by a management command, with nothing per-institution about it. It is
    content, like babook's courses, not somebody's records.

    The cost is real and is recorded here rather than discovered later: a
    program manager retiring a target retires it for every institution. With one
    programme that is correct and convenient. The day there are two, this test
    is the thing that has to change, and it will be looked at because it says
    so out loud.
    """
    from matazim.models import EntranceTarget

    client.force_login(two_worlds["ours"]["manager"])
    payload = client.get(f"{API}entrance-targets/").json()
    rows = payload.get("results", payload) if isinstance(payload, dict) else payload

    assert len(rows) == EntranceTarget.objects.count() >= 2, (
        "the bank stopped being shared, which may be right, but the sweep and "
        "this test both have to be updated together"
    )
