"""SPR-M.39 — the review's first four.

Avi asked for a review of everything built so far and then said "start what you
think first." These are the four I put first, in the order I put them.

1. **Handover.** The tenancy root is a person, and the day she leaves her
   successor signs in to an empty programme. The real fix is an `Institution`
   row, which is Avi's to approve (`data_model.md` §6); this is the fix that
   needs no approval, a command that moves everything one manager owns to
   another.
2. **Mail.** Nothing reached a member outside the site: work returned, a
   certificate issued, an event tomorrow, all bell-only. A fourteen-year-old who
   does not open the site never learned their work came back.
3. **One word.** The public band said "שעות הדרכה" one screen away from a nav
   item ההדרכות meaning courses.
4. **One school.** `school_name` fed a public counter unnormalised, so a
   trailing space was a second school on the front page.

The test that carries the most weight is `test_a_mail_is_a_pointer_and_never_
the_feedback`. A minor's feedback is read inside the walls, behind a login, and
not in an inbox that may be shared with a whole family. The mail says something
happened and where to look, and nothing else.

Traces: REQ-M.142, REQ-M.5f, REQ-M.33, REQ-M.114, REQ-M.137, §4.4, §4.8, §4.11.
"""

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.utils import timezone

pytestmark = pytest.mark.sprm39

PASSWORD = "sprm39-pass-7715"


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _manager(email="naomi@example.com", name="נעמי"):
    from matazim.models import MemberProfile

    user = _user(email, name)
    _make_manager(user)
    return user


def _leader(email, name, manager):
    from matazim.models import Leader

    return Leader.objects.create(
        user=_user(email, name), institution=_inst(manager),
        approved_at=timezone.now(), approved_by=manager,
    )


def _student(email, leader, name="יובל כהן"):
    from matazim.models import MemberProfile, Student

    user = _user(email, name)
    MemberProfile.objects.update_or_create(
        user=user, defaults={"birth_year": timezone.now().year - 14}
    )
    return Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)


@pytest.fixture
def outbox(settings):
    """Mail through the guarded backend, caught in memory.

    Both settings, deliberately. Django's test runner swaps `EMAIL_BACKEND` for
    locmem at start-up, so a plain `send_mail` in a test never reaches the guard
    and the cap never runs. The first version of this fixture set only the inner
    backend, every mail test passed, and the cap test showed five mails under a
    cap of three: not because the guard was broken, but because nothing had gone
    through it. Putting the guard back outermost is what makes these tests say
    anything about production.
    """
    settings.EMAIL_BACKEND = "app.mail_guard.GuardedEmailBackend"
    settings.MAIL_GUARD_INNER_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    # The cap's counter is keyed by address and date in a process-local cache
    # that outlives a test, so a test that mailed kid@example.com earlier in the
    # run leaves the count where it stopped. The cap test then passed alone and
    # failed in the suite. Each mail test starts from a clean counter.
    from django.core.cache import cache

    cache.clear()
    mail.outbox.clear()
    return mail.outbox


# ------------------------------------------------------------ 1. handover


def _her_world(naomi):
    """Everything a program manager owns, one of each."""
    from matazim.models import Event, LeaderInvite, Post, Request

    noa = _leader("noa@example.com", "נעה", naomi)
    event = Event.objects.create(
        institution=_inst(naomi), title="תערוכה",
        starts_at=timezone.now() + timezone.timedelta(days=5), for_everyone=True,
    )
    invite = LeaderInvite.objects.create(
        institution=_inst(naomi), kind=LeaderInvite.PERSONAL, label="דנה",
        token="tok-handover-0123456789",
    )
    post = Post.objects.create(
        author=naomi, institution=_inst(naomi), kind=Post.ANNOUNCEMENT, body="שלום"
    )
    request = Request.objects.create(
        author=naomi, author_role="program_manager", body="בקשה שלי",
        kind=Request.IDEA, status=Request.NEW,
    )
    return noa, event, invite, post, request


def test_a_successor_inherits_the_whole_institution(db):
    """T-F-M.39.1-1: the day she leaves, her successor must not see an empty
    programme. Every table that points at her is checked, through the same
    `visible_*` functions the screens use.

    This test caught a real bug once the `Institution` row existed: every test
    database carries a second institution from migration 0032's backfill (the
    one seeded row, "רשת עתיד"), and the first version of `hand_over` called
    `grant_program_manager(new)` with no institution named, which joins
    whichever institution `Institution.default()` finds — the earliest
    created, not necessarily the one being handed over. The successor ended up
    managing both, and `institution_of()` picked the seeded one, which owns
    none of נעמי's rows. `visible_posts(successor)` came back empty. Fixed by
    telling `grant_program_manager` which institutions to join.
    """
    from matazim.access import visible_events, visible_invites, visible_leaders, visible_posts
    from matazim.handover import hand_over

    naomi = _manager()
    successor = _user("next@example.com", "רות")
    noa, event, invite, post, _request = _her_world(naomi)

    moved = hand_over(naomi, successor)

    assert moved == {"Leader": 1, "Event": 1, "LeaderInvite": 1, "Post": 1}
    assert list(visible_leaders(successor)) == [noa]
    assert list(visible_events(successor)) == [event]
    assert list(visible_invites(successor)) == [invite]
    assert list(visible_posts(successor)) == [post]

    for reader in (visible_leaders, visible_events, visible_invites, visible_posts):
        assert not reader(naomi).exists(), f"{reader.__name__} still shows the old manager rows"


def test_handover_moves_ownership_and_not_history(db):
    """T-F-M.39.1-2: a leader approved by נעמי stays approved by נעמי after
    she has gone. History is not reassigned when a person leaves."""
    from matazim.handover import hand_over

    naomi = _manager()
    successor = _user("next@example.com", "רות")
    noa, *_rest = _her_world(naomi)

    hand_over(naomi, successor)

    noa.refresh_from_db()
    assert successor in noa.institution.managers.all(), "the successor does not run the institution"
    assert noa.approved_by_id == naomi.id, "history was rewritten"


def test_her_requests_stay_hers(db):
    """T-F-M.39.1-3: §4.11 — the log is her voice, and a successor inherits the
    programme, not the things the previous manager asked for."""
    from matazim.handover import hand_over

    naomi = _manager()
    successor = _user("next@example.com", "רות")
    *_rest, request = _her_world(naomi)

    hand_over(naomi, successor)

    request.refresh_from_db()
    assert request.author_id == naomi.id


def test_the_successor_becomes_a_program_manager_the_same_way_the_screen_does(db):
    """T-F-M.39.1-4: REQ-M.137 — through `roles.grant_program_manager`, so a
    pending leader row on the successor is approved, not left waiting."""
    from matazim.access import is_program_manager, leader_of
    from matazim.handover import hand_over
    from matazim.models import Leader

    naomi = _manager()
    successor = _user("next@example.com", "רות")
    Leader.objects.create(user=successor, institution=_inst(naomi), approved_at=None)
    _her_world(naomi)

    hand_over(naomi, successor)

    assert is_program_manager(successor)
    assert leader_of(successor) is not None, "the successor was left waiting for approval"


def test_the_old_manager_stops_being_one(db):
    """T-F-M.39.1-5: under the `Institution` row a handover is add-and-remove.

    The first version of this test asserted the opposite, and was right for
    the first version of the model: rows belonged to a person, so removing her
    role was a separate decision. Rows belong to the institution now, and a
    manager who keeps the role keeps seeing everything, which is the opposite
    of a handover. Both facts change together, in one transaction.
    """
    from matazim.access import is_program_manager
    from matazim.handover import hand_over

    naomi = _manager()
    successor = _user("next@example.com", "רות")
    _her_world(naomi)

    hand_over(naomi, successor)

    assert not is_program_manager(naomi)
    assert is_program_manager(successor)


def test_handover_of_nobody_is_refused(db):
    """T-F-M.39.1-5b: handing over an institution somebody does not run is a
    grant with a misleading name, and the grant screen exists for that."""
    from matazim.handover import hand_over

    nobody = _user("nobody@example.com", "אף אחד")
    successor = _user("next@example.com", "רות")

    with pytest.raises(ValueError):
        hand_over(nobody, successor)


def test_handover_to_yourself_is_refused(db):
    """T-F-M.39.1-6."""
    from matazim.handover import hand_over

    naomi = _manager()
    _her_world(naomi)

    with pytest.raises(ValueError):
        hand_over(naomi, naomi)


def test_the_command_reports_before_it_moves(db):
    """T-F-M.39.1-7: report-only unless asked, like every other job here."""
    import io as _io

    from django.core.management import call_command

    from matazim.access import visible_leaders
    from matazim.handover import hand_over  # noqa: F401 - imported for the module

    naomi = _manager()
    successor = _user("next@example.com", "רות")
    noa, *_rest = _her_world(naomi)

    out = _io.StringIO()
    call_command("matazim_handover", naomi.email, successor.email, stdout=out)
    assert "report only" in out.getvalue()
    assert list(visible_leaders(naomi)) == [noa], "a dry run moved something"

    call_command("matazim_handover", naomi.email, successor.email, apply=True, stdout=out)
    assert list(visible_leaders(successor)) == [noa]


# ------------------------------------------------------------- 2. mail


def test_work_returned_reaches_the_inbox(db, outbox):
    """T-F-M.39.2-1: REQ-M.142. The largest UX gap the review found."""
    from matazim.models import Notification
    from matazim.notify import notify

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))

    notify(student.user, Notification.WORK_RETURNED, "הצגה: הוחזר לתיקון",
           url="/matazim/my-work/")

    assert len(outbox) == 1
    sent = outbox[0]
    assert sent.to == ["kid@example.com"]
    assert "הצגה: הוחזר לתיקון" in sent.body
    assert "/matazim/my-work/" in sent.body


def test_a_mail_is_a_pointer_and_never_the_feedback(db, outbox):
    """T-F-M.39.2-2: REQ-M.142, §4.10. The test that matters most here.

    A minor's feedback is read inside the walls, behind a login, not in an
    inbox that may be shared with a whole family. The mail says something
    happened and where to look, and nothing else.
    """
    from matazim.models import Feedback, Notification, Submission
    from matazim.notify import notify

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה מורה", naomi)
    student = _student("kid@example.com", noa)
    work = Submission.objects.create(
        student=student, leader=noa, title="הצגה", status=Submission.RETURNED
    )
    Feedback.objects.create(
        submission=work, author=noa.user, outcome=Submission.RETURNED,
        body="הבסיס צר מדי ונופל, תעבה אותו",
    )

    notify(student.user, Notification.WORK_RETURNED, "הצגה: הוחזר לתיקון",
           url="/matazim/my-work/", actor=noa.user)

    body = outbox[0].body
    assert "הבסיס צר מדי" not in body, "feedback text left the walls"
    assert "נעה מורה" not in body, "the leader was named in a mail"
    assert "יובל כהן" not in body, "the reader was named to their own inbox"


def test_the_kinds_that_do_not_mail(db, outbox):
    """T-F-M.39.2-3: a second mail for the same moment is how mail stops being
    opened. `FEEDBACK` accompanies a decision that already mails."""
    from matazim.models import Notification
    from matazim.notify import notify

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))

    notify(student.user, Notification.FEEDBACK, "עוד מילה", url="/matazim/my-work/")

    assert outbox == []


def test_no_address_means_no_mail_and_still_a_bell(db, outbox):
    """T-F-M.39.2-4: the bell is the record; the mail is a courtesy."""
    from matazim.models import MemberProfile, Notification, Student
    from matazim.notify import notify

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    user = User.objects.create_user(username="noaddress", email="", password=PASSWORD)
    MemberProfile.objects.create(user=user)
    Student.objects.create(user=user, leader=noa, status=Student.IN_TRAINING)

    row = notify(user, Notification.CERTIFIED, "הוסמכת", url="/matazim/my-certificate/")

    assert row is not None
    assert outbox == []


def test_a_broken_mail_backend_does_not_lose_the_bell(db, settings):
    """T-F-M.39.2-5: never raises. The bell is already written; a mail that
    fails must not undo it."""
    settings.MAIL_GUARD_INNER_BACKEND = "tests.no_such_backend.Backend"
    from matazim.models import Notification
    from matazim.notify import notify

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))

    row = notify(student.user, Notification.EVENT, "מחר: תערוכה", url="/matazim/calendar/")

    assert row is not None
    assert Notification.objects.filter(pk=row.pk).exists()


def test_the_daily_cap_still_applies_to_the_bell(db, outbox, settings):
    """T-F-M.39.2-6: the cap lives in the guarded backend and applies here
    without `notify` knowing about it. A member whose work is returned twenty
    times in a day gets twenty bells and the cap's worth of mail."""
    settings.MAIL_PER_RECIPIENT_DAILY_CAP = 3
    from matazim.models import Notification
    from matazim.notify import notify

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))

    for i in range(5):
        notify(student.user, Notification.WORK_RETURNED, f"עבודה {i}", url="/matazim/my-work/")

    assert Notification.objects.filter(user=student.user).count() == 5
    assert len(outbox) == 3, "the per-recipient cap did not hold"


# ------------------------------------------------------------ 3. one word


def test_the_band_does_not_call_the_practicum_a_course(db):
    """T-F-M.39.3-1: on this site הדרכה is a course. The band said "שעות הדרכה"
    about something else, one screen from the nav item ההדרכות."""
    from matazim.models import TeachingSession
    from matazim.public import counters

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    TeachingSession.objects.create(
        student=student, title="לולאות", happened_on=timezone.localdate(),
        minutes=120, learners=10,
    )

    labels = {row["label"] for row in counters()}
    assert "שעות פרקטיקום" in labels
    assert not any("הדרכה" in label for label in labels), "the band still says הדרכה"


# ------------------------------------------------------------ 4. one school


def test_a_school_name_is_normalised_at_the_one_door(db):
    """T-F-M.39.4-1: REQ-M.5f. A trailing space was a second school on the
    front page. Normalised in `save()`, so the view that stripped it and the
    API that did not are now the same door."""
    from matazim.models import StudyClass
    from matazim.public import counters

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    _student("kid@example.com", noa)

    a = StudyClass.objects.create(leader=noa, name="ט1", school_name="עתיד רמלה")
    b = StudyClass.objects.create(leader=noa, name=" ט2 ", school_name="  עתיד   רמלה ")

    assert b.school_name == "עתיד רמלה"
    assert b.name == "ט2"
    assert a.school_name == b.school_name

    figures = {row["label"]: row["figure"] for row in counters()}
    assert figures["בית ספר"] == 1, "one school with two spellings counted twice"


def test_the_api_goes_through_the_same_door(client, db):
    """T-F-M.39.4-2: the normalisation is on the model, not the form, so a
    class created through the API is spelled the same as one from the screen."""
    from matazim.models import StudyClass

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)

    client.force_login(noa.user)
    response = client.post(
        "/matazim/api/classes/",
        {"name": "ט3", "school_name": "עתיד רמלה  "},
        content_type="application/json",
    )

    assert response.status_code == 201, response.content
    assert StudyClass.objects.get(pk=response.json()["id"]).school_name == "עתיד רמלה"


# --- SPR-M.40: the role is Institution.managers, the FKs are `institution` ---

def _make_manager(user):
    """One institution per test manager, so two managers are two worlds."""
    from matazim.models import Institution

    Institution.objects.create(name=f"מוסד {user.pk}").managers.add(user)


def _inst(user):
    from matazim.access import institution_of

    return institution_of(user)


def _is_pm(user):
    from matazim.access import is_program_manager

    return is_program_manager(user)
