"""SPR-M.30 — the bell.

REQ-M.33, built now rather than earlier on purpose. Before SPR-M.28 the only
events in this product were joining and being certified, and a bell for two
lifetime events is furniture. Now a leader writes feedback, returns work and
approves it, so there is something worth ringing about.

Two tests here matter more than the rest.

`test_nothing_is_discoverable_only_through_the_bell` holds REQ-M.128. Bells are
dismissed by accident constantly, and a product where that loses information is
broken. It is also exactly the rule that decays the first time somebody adds an
event in a hurry, which is why it is checked rather than trusted.

`test_a_notification_never_leaves_the_walls` holds RULE-1 from the one place the
template guard cannot see: a notification is not a template, so its `url` is
never inspected by anything else.

Traces: REQ-M.33, M.127, M.128, RULE-1.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm30

PASSWORD = "sprm30-pass-5514"


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _leader(email="noa@example.com", name="נעה מורה"):
    from matazim.models import Leader, MemberProfile

    manager = _user("naomi@example.com", "נעמי")
    MemberProfile.objects.update_or_create(user=manager, defaults={"is_program_manager": True})
    return Leader.objects.create(
        user=_user(email, name), program_manager=manager, approved_at=timezone.now()
    )


def _student(leader=None, email="kid@example.com"):
    from matazim.models import MemberProfile, Student

    user = _user(email, "יובל כהן")
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


def _hand_in(client, title="המבוך שלי"):
    return client.post(
        reverse("matazim:my_work"),
        {"title": title, "about": "בניתי משחק", "link": "https://scratch.mit.edu/projects/1"},
    )


# ------------------------------------------- the events


def test_feedback_rings_for_the_member(client, db):
    """T-F-M.30.4-1: REQ-M.33. The event the whole bell was waiting for."""
    from matazim.models import Notification, Submission

    student = _student()
    client.force_login(student.user)
    _hand_in(client)
    submission = Submission.objects.get()

    client.force_login(student.leader.user)
    client.post(
        reverse("matazim:review", args=[submission.pk]),
        {"action": "return", "body": "תחזקי את הבסיס ותגישי שוב"},
    )

    notice = Notification.objects.get(user=student.user, kind=Notification.WORK_RETURNED)
    assert "המבוך שלי" in notice.text
    assert notice.url == reverse("matazim:my_work"), "the pointer points nowhere useful"
    assert notice.is_unread


def test_work_arriving_rings_for_the_leader(client, db):
    """T-F-M.30.4-2: REQ-M.33, REQ-M.124."""
    from matazim.models import Notification

    student = _student()
    client.force_login(student.user)
    _hand_in(client, title="המנורה")

    notice = Notification.objects.get(
        user=student.leader.user, kind=Notification.WORK_WAITING
    )
    assert "המנורה" in notice.text


def test_being_accepted_rings(client, db):
    """T-F-M.30.4-3: REQ-M.33. Somebody has been waiting to hear this."""
    from matazim.models import Notification, Student

    leader = _leader()
    student = _student(leader=leader)
    student.leader = None
    student.pending_leader = leader
    student.status = Student.APPLIED
    student.save()

    client.force_login(leader.user)
    client.post(reverse("matazim:leader_confirm", args=[student.pk]), {"action": "confirm"})

    notice = Notification.objects.get(user=student.user, kind=Notification.JOINED)
    assert "נעה מורה" in notice.text


def test_certification_rings(client, db):
    """T-F-M.30.4-4: REQ-M.33. The best news this product has to give."""
    from app.models import Course, CourseCertificate, UserVideoProgress, Video
    from matazim.certification import certify
    from matazim.models import Notification

    student = _student()
    for slug, n in (("scratch", 2), ("scratch-advanced", 2)):
        course = Course.objects.create(slug=slug, title=slug, is_published=True)
        for i in range(n):
            video = Video.objects.create(course=course, title=f"{i}", lesson_order=i + 1)
            UserVideoProgress.objects.create(
                user=student.user, video=video, percent_watched=100.0,
                completed_at=timezone.now(),
            )
        CourseCertificate.objects.create(user=student.user, course=course)

    certify(student.leader.user, student)

    notice = Notification.objects.get(user=student.user, kind=Notification.CERTIFIED)
    assert notice.url == reverse("matazim:my_certificate")


def test_nobody_is_told_about_their_own_doing(client, db):
    """T-F-M.30.1-1: a leader who writes feedback does not need telling.

    The obvious implementation notifies whoever the row belongs to, which is
    right for the member and wrong for the leader answering their own queue.
    """
    from matazim.models import Notification, Submission

    student = _student()
    client.force_login(student.user)
    _hand_in(client)
    submission = Submission.objects.get()

    client.force_login(student.leader.user)
    client.post(
        reverse("matazim:review", args=[submission.pk]), {"action": "approve", "body": "יופי"}
    )

    assert not Notification.objects.filter(
        user=student.leader.user, kind=Notification.WORK_APPROVED
    ).exists(), "the leader was told about their own answer"


# ------------------------------------------- the rules


def test_a_notification_never_leaves_the_walls(db):
    """T-F-M.30.1-2: RULE-1, from where the template guard cannot see.

    A notification is not a template, so nothing else in this product would
    ever inspect its url.
    """
    from matazim.models import Notification
    from matazim.notify import notify

    student = _student()
    row = notify(student.user, Notification.FEEDBACK, "משהו", url="/courses/scratch/")

    assert row.url == "", "a notification would have navigated out of מט״צים"

    ok = notify(student.user, Notification.FEEDBACK, "משהו", url="/matazim/my-work/")
    assert ok.url == "/matazim/my-work/"


def test_nothing_is_discoverable_only_through_the_bell(client, db):
    """T-F-M.30.5-1: REQ-M.128, and the rule most likely to decay.

    Bells are dismissed by accident constantly. Every event that raises one
    also has to be visible on the screen it belongs to, so somebody who never
    opens the bell misses nothing.
    """
    from matazim.models import Submission

    student = _student()
    client.force_login(student.user)
    _hand_in(client)
    submission = Submission.objects.get()

    client.force_login(student.leader.user)
    # The leader's own screen carries the waiting work without any bell.
    assert "המבוך שלי" in client.get(reverse("matazim:leader_home")).content.decode()

    client.post(
        reverse("matazim:review", args=[submission.pk]),
        {"action": "return", "body": "תחזקי את הבסיס"},
    )

    # And the member's own screen carries the feedback without any bell.
    client.force_login(student.user)
    assert "תחזקי את הבסיס" in client.get(reverse("matazim:my_work")).content.decode()


def test_matazim_does_not_write_to_the_other_products_bell(db):
    """T-F-M.30.1-3: REQ-M.127.

    That table feeds the other product's bell in the other product's chrome, so
    an event of ours landing there puts this product inside theirs, which is the
    mirror of what RULE-1 forbids.
    """
    from app.models import Notification as TheirNotification
    from matazim.models import Notification
    from matazim.notify import notify

    student = _student()
    before = TheirNotification.objects.count()
    notify(student.user, Notification.FEEDBACK, "משהו", url="/matazim/my-work/")

    assert TheirNotification.objects.count() == before
    assert Notification.objects.filter(user=student.user).exists()


# ------------------------------------------- the screen


def test_the_bell_shows_a_count_and_the_list_clears_it(client, db):
    """T-F-M.30.2-1, T-F-M.30.3-1: REQ-M.33."""
    from matazim.models import Notification
    from matazim.notify import notify

    student = _student()
    notify(student.user, Notification.FEEDBACK, "משוב חדש", url="/matazim/my-work/")
    client.force_login(student.user)

    home = client.get(reverse("matazim:my_path"))
    assert home.context["unread_notices"] == 1
    assert reverse("matazim:notices") in home.content.decode()

    listing = client.get(reverse("matazim:notices"))
    assert "משוב חדש" in listing.content.decode()

    # Read once looked at, and the list still shows which were new on opening.
    assert client.get(reverse("matazim:my_path")).context["unread_notices"] == 0


def test_a_notice_takes_you_to_the_thing_itself(client, db):
    """T-F-M.30.3-2: a pointer you cannot follow is a worse kind of email."""
    from matazim.models import Notification
    from matazim.notify import notify

    student = _student()
    notify(student.user, Notification.FEEDBACK, "משוב", url=reverse("matazim:my_work"))
    client.force_login(student.user)

    html = client.get(reverse("matazim:notices")).content.decode()
    assert reverse("matazim:my_work") in html


def test_somebody_elses_bell_is_not_yours(client, db):
    """T-F-M.30.2-2: §4.4."""
    from matazim.models import Notification
    from matazim.notify import notify

    mine = _student()
    theirs = _student(leader=mine.leader, email="other@example.com")
    notify(theirs.user, Notification.FEEDBACK, "סוד של מישהו אחר", url="/matazim/my-work/")

    client.force_login(mine.user)
    assert "סוד של מישהו אחר" not in client.get(reverse("matazim:notices")).content.decode()
