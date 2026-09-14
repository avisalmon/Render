"""SPR-M.38 — the public front, held since SPR-M.1 and finally true.

REQ-M.5e, REQ-M.5f, REQ-M.30a. Litala's prototype had a band of invented numbers
and a showcase of invented projects; Avi cut both on sight and they have been
HELD ever since, correctly, because there was nothing real to put in them. There
is now.

This file is unusual in this suite: almost every test here is about something
**not** appearing. That is the shape of the requirement. This is the only code
in מט״צים whose output is readable by anybody on the internet, and it is about
fourteen-year-olds, so the interesting cases are all the ways a thing could
reach that page without having earned it.

The two that matter most:

`test_work_needs_both_yeses_and_either_can_be_taken_back` is the whole of
REQ-M.30a in one test. Two people agree, and either one changing their mind
removes it on the next request, with nothing to remember to run.

`test_the_public_page_never_names_a_child` is the rule that cannot be allowed to
erode. A title, a description and a school. Not the maker, not their class, not
their file.

Traces: REQ-M.5e, M.5f, M.30a, M.29, M.122, §4.10, §4.12.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm38

PASSWORD = "sprm38-pass-8140"


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


def _student(email, leader, name="יובל כהן", school="עתיד רמלה"):
    from matazim.models import MemberProfile, Student, StudyClass

    user = _user(email, name)
    MemberProfile.objects.update_or_create(
        user=user, defaults={"birth_year": timezone.now().year - 14}
    )
    student = Student.objects.create(
        user=user, leader=leader, status=Student.IN_TRAINING
    )
    if school:
        study_class = StudyClass.objects.create(
            leader=leader, name="ט1", school_name=school
        )
        student.classes.add(study_class)
    return student


def _work(student, leader, *, approved=True, offered=False, published=False, **extra):
    from matazim.models import Submission

    fields = {
        "student": student,
        "leader": leader,
        "title": "משחק המבוך",
        "about": "משחק בסקראץ׳ עם שלושה שלבים",
        "status": Submission.APPROVED if approved else Submission.WAITING,
    }
    fields.update(extra)
    row = Submission.objects.create(**fields)
    if offered:
        row.public_consent_at = timezone.now()
    if published:
        row.published_at = timezone.now()
    row.save()
    return row


def _home(client):
    return client.get(reverse("matazim:home")).content.decode()


# ----------------------------------------- REQ-M.5e: two yeses, either revocable


def test_work_needs_both_yeses_and_either_can_be_taken_back(client, db):
    """T-F-M.38.1-1: REQ-M.5e, REQ-M.30a. The whole requirement, in one test.

    Two people agree before a minor's work is public, and either one changing
    their mind removes it on the next request, with nothing to remember to run.
    """
    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    student = _student("kid@example.com", noa)
    work = _work(student, noa)

    assert "משחק המבוך" not in _home(client), "approved work published itself"

    # The maker offers.
    client.force_login(student.user)
    client.post(reverse("matazim:offer_publicly", args=[work.pk]))
    assert "משחק המבוך" not in _home(client), "one yes was enough"

    # The programme agrees.
    client.force_login(naomi)
    client.post(reverse("matazim:publish_work", args=[work.pk]))
    assert "משחק המבוך" in _home(client)

    # The programme changes its mind.
    client.post(reverse("matazim:publish_work", args=[work.pk]))
    assert "משחק המבוך" not in _home(client), "the programme could not take it back"

    # And so can the maker, from a published state.
    client.force_login(naomi)
    client.post(reverse("matazim:publish_work", args=[work.pk]))
    client.force_login(student.user)
    client.post(reverse("matazim:offer_publicly", args=[work.pk]))
    assert "משחק המבוך" not in _home(client), "the maker could not take it back"


def test_withdrawing_consent_clears_the_programmes_yes_too(client, db):
    """T-F-M.38.1-2: REQ-M.30a.

    Otherwise a member who withdraws and later changes their mind is
    republished the instant they re-offer, by a staff decision made about a
    different moment. That is not what the person taking it back thinks they
    did.
    """
    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    student = _student("kid@example.com", noa)
    work = _work(student, noa, offered=True, published=True)

    client.force_login(student.user)
    client.post(reverse("matazim:offer_publicly", args=[work.pk]))

    work.refresh_from_db()
    assert work.public_consent_at is None
    assert work.published_at is None, "a staff yes survived the consent it depended on"

    client.post(reverse("matazim:offer_publicly", args=[work.pk]))
    work.refresh_from_db()
    assert work.public_consent_at is not None
    assert work.published_at is None, "re-offering silently republished"


def test_the_programme_cannot_publish_what_nobody_offered(client, db):
    """T-F-M.38.1-3: REQ-M.30a, and the refusal is in the view.

    Publishing work whose maker never said yes is the exact thing this
    requirement exists to prevent. Refused where the POST lands, not on the
    screen, because the screen is not what receives it (REQ-M.77's lesson).
    """
    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    student = _student("kid@example.com", noa)
    work = _work(student, noa)

    client.force_login(naomi)
    client.post(reverse("matazim:publish_work", args=[work.pk]))

    work.refresh_from_db()
    assert work.published_at is None
    assert "משחק המבוך" not in _home(client)


def test_nobody_consents_on_a_members_behalf(client, db):
    """T-F-M.38.1-4: REQ-M.30a — the opt-in is the member's own.

    A leader pressing it for them is not an opt-in, however well meant, and
    neither is a program manager doing it.
    """
    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    student = _student("kid@example.com", noa)
    work = _work(student, noa)

    for user in (noa.user, naomi):
        client.force_login(user)
        assert client.post(
            reverse("matazim:offer_publicly", args=[work.pk])
        ).status_code == 404

    work.refresh_from_db()
    assert work.public_consent_at is None


def test_only_a_program_manager_gives_the_programmes_yes(client, db):
    """T-F-M.38.1-5: §4.4a.

    The one decision here whose audience is the whole internet rather than one
    school, so it sits with the person who answers for the programme.
    """
    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    student = _student("kid@example.com", noa)
    work = _work(student, noa, offered=True)

    client.force_login(noa.user)
    assert client.post(
        reverse("matazim:publish_work", args=[work.pk])
    ).status_code == 403

    work.refresh_from_db()
    assert work.published_at is None


def test_work_that_was_never_approved_is_never_offered(client, db):
    """T-F-M.38.1-6: the public page is not a place to be seen failing.

    Same rule the community feed follows (REQ-M.132).
    """
    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    student = _student("kid@example.com", noa)
    work = _work(student, noa, approved=False)

    client.force_login(student.user)
    client.post(reverse("matazim:offer_publicly", args=[work.pk]))

    work.refresh_from_db()
    assert work.public_consent_at is None


def test_sharing_to_the_community_is_not_consent_to_publish(client, db):
    """T-F-M.38.1-7: §4.12, and the worst misreading available here.

    A fourteen-year-old putting work in front of the people in their programme
    has not agreed to put it in front of the internet. The two consents are
    different fields because they are different decisions.
    """
    from matazim.models import Post

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    student = _student("kid@example.com", noa)
    work = _work(student, noa)

    Post.objects.create(
        author=student.user, program_manager=naomi, kind=Post.WORK,
        body="תראו מה עשיתי", submission=work,
    )

    work.refresh_from_db()
    assert work.public_consent_at is None
    assert "משחק המבוך" not in _home(client)


# ----------------------------------------- REQ-M.30a: what the page may say


def test_the_public_page_never_names_a_child(client, db):
    """T-F-M.38.2-1: REQ-M.30a, REQ-M.29, REQ-M.122.

    A title, a description and a school. Not the maker, not their class, not a
    link to their file. This is the rule that cannot be allowed to erode, so it
    is checked against a fully published piece of work rather than an empty
    page.
    """
    naomi = _manager()
    noa = _leader("noa@example.com", "נעה מורה", naomi)
    student = _student("kid@example.com", noa, name="יובל כהן")
    _work(student, noa, offered=True, published=True)

    html = _home(client)

    assert "משחק המבוך" in html
    assert "עתיד רמלה" in html, "a school is allowed and is the point"
    assert "יובל כהן" not in html, "a child was named on the public page"
    assert "נעה מורה" not in html, "a leader was named on the public page"
    assert "kid@example.com" not in html
    assert "/work/" not in html, "a link to a minor's work reached the public page"


def test_a_second_school_is_not_named_at_all(client, db):
    """T-F-M.38.2-2: REQ-M.30a.

    One school is context. A list of two starts to identify a person, because
    the set of teenagers who attend both is small. Blank is fine: an
    unattributed project is still a project.
    """
    from matazim.models import StudyClass

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    student = _student("kid@example.com", noa, school="עתיד רמלה")
    student.classes.add(
        StudyClass.objects.create(leader=noa, name="ט2", school_name="עתיד מודיעין")
    )
    _work(student, noa, offered=True, published=True)

    html = _home(client)

    assert "משחק המבוך" in html
    assert "עתיד רמלה" not in html
    assert "עתיד מודיעין" not in html


# ----------------------------------------- REQ-M.5f: counted, never typed


def test_an_empty_programme_shows_no_band_at_all(client, db):
    """T-F-M.38.3-1: REQ-M.5f.

    "0 בתי ספר" is a true sentence that makes a claim a counter is not for. The
    band is absent and the page reads as it did before, which is what it did
    for thirty-seven sprints.
    """
    from matazim.public import counters

    assert counters() == []
    assert "התוכנית במספרים" not in _home(client)


def test_the_figures_are_counted_from_real_rows(client, db):
    """T-F-M.38.3-2: REQ-M.5f.

    The prototype had a band of invented numbers and Avi cut it on sight. A
    figure on a public page is a claim about a real programme, and the only
    defensible way to make one is to count.
    """
    from matazim.models import TeachingSession
    from matazim.public import counters

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    one = _student("kid1@example.com", noa, school="עתיד רמלה")
    two = _student("kid2@example.com", noa, name="דנה לוי", school="עתיד רמלה")

    TeachingSession.objects.create(
        student=one, title="לולאות", happened_on=timezone.localdate(),
        minutes=90, learners=12,
    )
    TeachingSession.objects.create(
        student=two, title="רובוטיקה", happened_on=timezone.localdate(),
        minutes=30, learners=8,
    )

    figures = {row["label"]: row["figure"] for row in counters()}

    assert figures["מט״צים בתוכנית"] == 2
    assert figures["בית ספר"] == 1, "one school counted twice"
    assert figures["מוביל/ה"] == 1
    assert figures["שעות הדרכה"] == 2
    assert "מוסמכים" not in figures, "a zero was published"


def test_a_cancelled_session_is_not_an_hour_taught(client, db):
    """T-F-M.38.3-3: REQ-M.5f — the public figure and the member's own agree."""
    from matazim.models import TeachingSession
    from matazim.public import counters

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    student = _student("kid@example.com", noa)

    TeachingSession.objects.create(
        student=student, title="לולאות", happened_on=timezone.localdate(),
        minutes=60, learners=12,
    )
    TeachingSession.objects.create(
        student=student, title="שבוטל", happened_on=timezone.localdate(),
        minutes=600, learners=99, cancelled_at=timezone.now(),
    )

    figures = {row["label"]: row["figure"] for row in counters()}
    assert figures["שעת הדרכה"] == 1


def test_an_unapproved_leader_is_not_a_leader_in_the_figures(client, db):
    """T-F-M.38.3-4: REQ-M.93 — approval is an act by a person, here too.

    A pending leader row grants nothing anywhere else in this product and must
    not inflate a public number either.
    """
    from matazim.models import Leader
    from matazim.public import counters

    naomi = _manager()
    _leader("noa@example.com", "נעה", naomi)
    Leader.objects.create(
        user=_user("waiting@example.com", "איתי"),
        program_manager=naomi,
        approved_at=None,
    )

    figures = {row["label"]: row["figure"] for row in counters()}
    assert figures["מוביל/ה"] == 1


def test_a_private_event_is_not_a_public_figure(client, db):
    """T-F-M.38.3-5: REQ-M.129 — the same tick governs the count and the page."""
    from matazim.models import Event
    from matazim.public import counters

    naomi = _manager()
    _leader("noa@example.com", "נעה", naomi)
    Event.objects.create(
        program_manager=naomi, title="פנימי",
        starts_at=timezone.now() + timezone.timedelta(days=3),
    )

    figures = {row["label"]: row["figure"] for row in counters()}
    assert "יום שיא" not in figures, "an internal event was counted publicly"
    assert "ימי שיא" not in figures


def test_a_row_published_without_consent_still_never_shows(client, db):
    """T-F-M.38.1-8: the belt behind the brace, and the state no view creates.

    `offer_publicly` and `publish` both refuse to reach this state, so it can
    only arrive from a migration, the admin, or a future view somebody writes
    without reading this file. Written after noticing that removing the consent
    filter from `published_work` broke no test: every existing one went through
    the views, and the views were the only thing holding the rule.
    """
    from matazim.models import Submission

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    student = _student("kid@example.com", noa)
    work = _work(student, noa)

    Submission.objects.filter(pk=work.pk).update(
        published_at=timezone.now(), published_by=naomi
    )

    work.refresh_from_db()
    assert work.published_at is not None, "the fixture did not build the state"
    assert work.public_consent_at is None
    assert not work.is_public
    assert "משחק המבוך" not in _home(client), (
        "work reached the public page with no consent behind it"
    )


def test_one_of_something_reads_as_one(db):
    """T-F-M.38.3-6: Hebrew does not let a number sit in front of a plural noun.

    "1 בתי ספר" on a programme's own front page is a small thing that makes a
    site look unattended, and this is the page read by people deciding whether
    to trust it. Every count here starts at one.
    """
    from matazim.public import counters

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    _student("kid@example.com", noa, school="עתיד רמלה")

    labels = {row["label"] for row in counters()}

    assert "בית ספר" in labels
    assert "בתי ספר" not in labels
    assert "מט״צ בתוכנית" in labels
    assert "מט״צים בתוכנית" not in labels
