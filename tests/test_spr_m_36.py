"""SPR-M.36 — the two decisions that were waiting, taken.

REQ-M.34's reminder half and REQ-M.113's retention half. Avi, 2026-09-14:
"continue with all of these", on a list that named both as open decisions.

**REQ-M.34: reminders may run unattended.** The rule they looked like they broke
is REQ-M.87, and reading it closely is the whole decision: "the machine
proposes, a person decides" was written about *deletion*, because deletion is
the one action here where a bug is irreversible. A reminder creates nothing a
person did not already decide and destroys nothing, and its worst failure is a
duplicate bell. So reminders run on a timer and purges still do not.

**REQ-M.113: two years after a request is closed.** Not from when it was filed,
because an unanswered question is not stale data. Two years because the log is
also the record of why this product is shaped the way it is.

The test that carries the most weight is `test_nobody_is_reminded_twice`. A
member told twice about one day stops reading the bell, and the bell is how they
hear about everything else, so a job that runs twice or a schedule that shifts
must not ring again.

Traces: REQ-M.34, M.87, M.113, M.86, M.33.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

pytestmark = pytest.mark.sprm36

PASSWORD = "sprm36-pass-5042"


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


def _leader(email, name, manager):
    from matazim.models import Leader

    return Leader.objects.create(
        user=_user(email, name), program_manager=manager, approved_at=timezone.now()
    )


def _student(email, leader, name="יובל כהן"):
    from matazim.models import MemberProfile, Student

    user = _user(email, name)
    MemberProfile.objects.update_or_create(
        user=user, defaults={"birth_year": timezone.now().year - 14}
    )
    return Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)


def _event(manager, hours=20, **extra):
    from matazim.models import Event

    fields = {
        "program_manager": manager,
        "title": "תערוכת סיום",
        "starts_at": timezone.now() + timezone.timedelta(hours=hours),
        "for_everyone": True,
    }
    fields.update(extra)
    return Event.objects.create(**fields)


def _bells(user):
    from matazim.models import Notification

    return Notification.objects.filter(user=user, kind=Notification.EVENT)


# --------------------------------------------------- REQ-M.34: the reminder


def test_the_people_it_is_for_are_told_it_is_tomorrow(db):
    """T-F-M.36.1-1: REQ-M.34."""
    from matazim.reminders import send_reminders

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    event = _event(naomi, place="אולם הספורט")

    events, told = send_reminders(apply=True)

    assert (events, told) == (1, 1)
    bell = _bells(student.user).last()
    assert "מחר" in bell.text
    assert "תערוכת סיום" in bell.text
    assert "אולם הספורט" in bell.text

    event.refresh_from_db()
    assert event.reminded_at is not None


def test_nobody_is_reminded_twice(db):
    """T-F-M.36.1-2: REQ-M.34, REQ-M.33.

    The rule the whole design turns on. A member told twice about one day stops
    reading the bell, and the bell is how they hear about everything else. The
    guard is a stamp on the row rather than a window calculation, so a job that
    runs twice or a deploy that shifts the schedule cannot ring again.
    """
    from matazim.reminders import send_reminders

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    _event(naomi)

    send_reminders(apply=True)
    send_reminders(apply=True)
    send_reminders(apply=True)

    assert _bells(student.user).count() == 1, "somebody was told the same thing twice"


def test_a_reminder_is_aimed_the_same_way_the_event_is(db):
    """T-F-M.36.1-3: REQ-M.27 — the audience rule holds on the reminder too.

    An event aimed at one leader's students must not become everybody's problem
    the day before it happens.
    """
    from matazim.reminders import send_reminders

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    dana = _leader("dana@example.com", "דנה", naomi)
    invited = _student("kid1@example.com", noa)
    not_invited = _student("kid2@example.com", dana, name="רות")

    event = _event(naomi, for_everyone=False)
    event.leaders.set([noa])

    send_reminders(apply=True)

    assert _bells(invited.user).exists()
    assert not _bells(not_invited.user).exists(), (
        "somebody was reminded about a day they are not invited to"
    )


def test_a_cancelled_day_reminds_nobody(db):
    """T-F-M.36.1-4: nobody should be told to turn up to something cancelled."""
    from matazim.reminders import send_reminders

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    _event(naomi, cancelled_at=timezone.now())

    send_reminders(apply=True)
    assert not _bells(student.user).exists()


def test_something_next_month_is_not_tomorrow(db):
    """T-F-M.36.1-5: REQ-M.34 — a reminder that arrives early is noise."""
    from matazim.reminders import send_reminders

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    _event(naomi, hours=24 * 30)

    events, _told = send_reminders(apply=True)
    assert events == 0
    assert not _bells(student.user).exists()


def test_the_job_can_be_rehearsed(db):
    """T-F-M.36.1-6: report-only unless asked, like every other job here.

    A job you cannot rehearse is a job people avoid running, and a reminder
    system nobody dares run is the same as not having one.
    """
    from matazim.reminders import send_reminders

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    event = _event(naomi)

    events, people = send_reminders()

    assert (events, people) == (1, 1)
    assert not _bells(student.user).exists(), "a dry run sent a real notification"
    event.refresh_from_db()
    assert event.reminded_at is None


def test_the_endpoint_is_shut_without_the_token(client, db):
    """T-F-M.36.1-7: an unset secret means closed, never open.

    A deploy that forgets the token must not leave a public endpoint that can
    write to every member's bell.
    """
    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    _event(naomi)

    assert client.post("/matazim/internal/remind/").status_code == 403
    assert client.get("/matazim/internal/remind/").status_code == 405
    assert not _bells(student.user).exists()


def test_the_endpoint_works_with_the_token(client, db, settings):
    """T-F-M.36.1-8: and it does actually run."""
    settings.BACKUP_TRIGGER_TOKEN = "a-real-secret-9931"

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    _event(naomi)

    response = client.post(
        "/matazim/internal/remind/", HTTP_X_MATAZIM_TOKEN="a-real-secret-9931"
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert _bells(student.user).count() == 1


def test_a_wrong_token_is_refused(client, db, settings):
    """T-F-M.36.1-9."""
    settings.BACKUP_TRIGGER_TOKEN = "a-real-secret-9931"

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    _event(naomi)

    assert client.post(
        "/matazim/internal/remind/", HTTP_X_MATAZIM_TOKEN="not-it"
    ).status_code == 403
    assert not _bells(student.user).exists()


# ------------------------------------------ REQ-M.113: how long a request lives


def test_a_closed_request_is_purged_after_its_period(db):
    """T-F-M.36.2-1: REQ-M.113, REQ-M.86.

    A stated period that nothing enforces is a sentence, not a policy.
    """
    from matazim.models import Request
    from matazim.retention import REQUEST_DAYS, approve_request_purge, due_requests

    naomi = _manager()
    old = Request.objects.create(
        author=naomi, author_role="program_manager", body="ישן",
        status=Request.DONE,
        decided_at=timezone.now() - timezone.timedelta(days=REQUEST_DAYS + 1),
    )
    recent = Request.objects.create(
        author=naomi, author_role="program_manager", body="טרי",
        status=Request.DONE, decided_at=timezone.now(),
    )

    assert set(due_requests().values_list("pk", flat=True)) == {old.pk}

    removed = approve_request_purge(naomi)

    assert removed == 1
    assert not Request.objects.filter(pk=old.pk).exists()
    assert Request.objects.filter(pk=recent.pk).exists()


def test_an_open_request_is_never_due_however_old(db):
    """T-F-M.36.2-2: REQ-M.113, and the reason the clock starts at closing.

    An unanswered question is not stale data. A request nobody has decided on,
    left for three years, is a reproach rather than something to tidy away.
    """
    from matazim.models import Request
    from matazim.retention import due_requests

    naomi = _manager()
    Request.objects.create(
        author=naomi, author_role="program_manager", body="עדיין פתוחה",
        status=Request.NEW,
        decided_at=None,
    )

    assert not due_requests().exists()


def test_the_purge_records_who_approved_it(db):
    """T-F-M.36.2-3: REQ-M.87 — a person in front of every deletion, with a name."""
    from matazim.models import Request, RetentionRun
    from matazim.retention import REQUEST_DAYS, approve_request_purge

    naomi = _manager()
    Request.objects.create(
        author=naomi, author_role="program_manager", body="ישן", status=Request.DECLINED,
        decided_at=timezone.now() - timezone.timedelta(days=REQUEST_DAYS + 5),
    )

    approve_request_purge(naomi)

    run = RetentionRun.objects.filter(kind="requests").first()
    assert run is not None
    assert run.ran_by_id == naomi.id
    assert run.deleted_count == 1


def test_the_conversation_goes_with_the_request(db):
    """T-F-M.36.2-4: REQ-M.113.

    A chat about a request that no longer exists is a record of nothing, about a
    person, kept for no reason.
    """
    from matazim.models import Request, RequestMessage
    from matazim.retention import REQUEST_DAYS, approve_request_purge

    naomi = _manager()
    row = Request.objects.create(
        author=naomi, author_role="program_manager", body="ישן", status=Request.DONE,
        decided_at=timezone.now() - timezone.timedelta(days=REQUEST_DAYS + 5),
    )
    RequestMessage.objects.create(request=row, who=RequestMessage.HER, body="ועוד משהו")

    approve_request_purge(naomi)

    assert not RequestMessage.objects.exists()


def test_the_screen_states_the_period_it_enforces(client, db):
    """T-F-M.36.2-5: REQ-M.86 — the number a person reads and the number the
    command applies are the same number, because there is only one of them."""
    from django.urls import reverse

    from matazim.retention import REQUEST_DAYS

    client.force_login(_manager())
    html = client.get(reverse("matazim:staff_retention")).content.decode()

    assert str(REQUEST_DAYS) in html
    assert "בקשה שעדיין פתוחה לא" in html
