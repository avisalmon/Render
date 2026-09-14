"""SPR-M.31 — ימי שיא, and what is coming.

REQ-M.27, M.129, M.130. The third placeholder page becomes real.

Two tests here carry more weight than the rest.

`test_an_event_is_aimed_not_broadcast` holds the rule that makes an event
useful: a day for one school's ninth-graders appearing on every member's screen
as though they were invited is worse than not telling them, because it is an
invitation that turns out not to be one.

`test_the_public_page_shows_only_what_was_ticked` holds a privacy rule that is
easy to get backwards. A public page about a programme for fourteen-year-olds is
a public statement of when and where children gather, so the programme's diary
is private unless somebody deliberately says otherwise.

Traces: REQ-M.27, M.129, M.130, M.33, §4.4, §4.10.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm31

PASSWORD = "sprm31-pass-7182"


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _manager(email="naomi@example.com", name="נעמי"):
    from matazim.models import MemberProfile

    user = _user(email, name)
    MemberProfile.objects.update_or_create(user=user, defaults={"is_program_manager": True})
    return user


def _leader(email, name, manager):
    from matazim.models import Leader

    return Leader.objects.create(
        user=_user(email, name), program_manager=manager, approved_at=timezone.now()
    )


def _student(email, leader):
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
    return Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)


def _soon(days=7):
    return timezone.now() + timezone.timedelta(days=days)


def _make(manager, title="תערוכת סיום", **extra):
    from matazim.models import Event

    fields = {"program_manager": manager, "title": title, "starts_at": _soon()}
    fields.update(extra)
    return Event.objects.create(**fields)


# ------------------------------------------- who an event is for


def test_an_event_is_aimed_not_broadcast(client, db):
    """T-F-M.31.1-1: REQ-M.27.

    A day for one school's ninth-graders showing on every member's screen as
    though they were invited is worse than not telling them.
    """
    from matazim.access import visible_events

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה מורה", naomi)
    dana = _leader("dana@example.com", "דנה כהן", naomi)

    hers = _student("kid1@example.com", noa)
    theirs = _student("kid2@example.com", dana)

    only_noa = _make(naomi, "יום של נעה", for_everyone=False)
    only_noa.leaders.set([noa])
    everyone = _make(naomi, "יום של כולם", for_everyone=True)

    seen_by_hers = set(visible_events(hers.user).values_list("title", flat=True))
    seen_by_theirs = set(visible_events(theirs.user).values_list("title", flat=True))

    assert seen_by_hers == {"יום של נעה", "יום של כולם"}
    assert seen_by_theirs == {"יום של כולם"}, "somebody was shown a day they are not invited to"


def test_another_institutions_diary_is_not_yours(client, db):
    """T-F-M.31.1-2: §4.4.

    Not merely hidden: never in the queryset.
    """
    from matazim.access import visible_events

    naomi = _manager("naomi@example.com")
    other = _manager("other@example.com", "מנהלת אחרת")

    mine = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    _make(naomi, "היום שלנו")
    _make(other, "היום שלהם")

    titles = set(visible_events(mine.user).values_list("title", flat=True))
    assert titles == {"היום שלנו"}


def test_a_member_with_no_leader_belongs_to_no_diary(client, db):
    """T-F-M.31.1-3: REQ-M.65, §4.4.

    Having no leader is a normal state, and it means no institution's calendar
    is theirs yet. Not an error, and not everybody's events either.
    """
    from matazim.access import visible_events
    from matazim.models import MemberProfile

    naomi = _manager()
    _make(naomi, "יום של כולם")

    loose = _user("loose@example.com", "איתי")
    MemberProfile.objects.update_or_create(
        user=loose, defaults={"birth_year": timezone.now().year - 14}
    )
    assert not visible_events(loose).exists()


# ------------------------------------------- the public page


def test_the_public_page_shows_only_what_was_ticked(client, db):
    """T-F-M.31.3-1: REQ-M.129, §4.10.

    A public page about a programme for fourteen-year-olds is a public
    statement of when and where children gather. Private unless somebody said
    otherwise.
    """
    naomi = _manager()
    _make(naomi, "יום פנימי")
    _make(naomi, "יום פומבי", is_public=True)

    html = client.get(reverse("matazim:events")).content.decode()

    assert "יום פומבי" in html
    assert "יום פנימי" not in html, "the programme's own diary was published"


def test_the_public_page_names_nobody(client, db):
    """T-F-M.31.3-2: REQ-M.30a, §4.10."""
    naomi = _manager()
    noa = _leader("noa@example.com", "נעה מורה", naomi)
    _student("kid@example.com", noa)
    event = _make(naomi, "יום פומבי", is_public=True, place="אולם הספורט, עתיד רמלה")
    event.leaders.set([noa])

    html = client.get(reverse("matazim:events")).content.decode()

    assert "יום פומבי" in html
    assert "אולם הספורט" in html, "a place is fine and useful"
    assert "יובל כהן" not in html, "a member was named on a public page"
    assert "נעה מורה" not in html, "a leader was named on a public page"


def test_a_cancelled_day_leaves_the_public_page(client, db):
    """T-F-M.31.3-3: nobody should travel to something that is not happening."""
    naomi = _manager()
    _make(naomi, "יום פומבי", is_public=True, cancelled_at=timezone.now())

    assert "יום פומבי" not in client.get(reverse("matazim:events")).content.decode()


# ------------------------------------------- what is close


def test_what_is_close_is_on_the_screen_they_already_open(client, db):
    """T-F-M.31.4-1: REQ-M.130.

    A calendar somebody has to remember to visit tells nobody anything.
    """
    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    _make(naomi, "תערוכת סיום")

    client.force_login(student.user)
    html = client.get(reverse("matazim:my_path")).content.decode()

    assert "תערוכת סיום" in html
    assert reverse("matazim:calendar") in html


def test_the_calendar_separates_ahead_from_behind(client, db):
    """T-F-M.31.4-2: REQ-M.130. A programme is partly what you can look back on."""
    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    _make(naomi, "מה שיהיה", starts_at=_soon(10))
    _make(naomi, "מה שהיה", starts_at=_soon(-10))

    client.force_login(student.user)
    response = client.get(reverse("matazim:calendar"))

    assert [e.title for e in response.context["upcoming"]] == ["מה שיהיה"]
    assert [e.title for e in response.context["past"]] == ["מה שהיה"]


# ------------------------------------------- נעמי writes one


def test_she_writes_a_day_and_the_right_people_are_told(client, db):
    """T-F-M.31.5-1: REQ-M.27, REQ-M.33.

    Announcing it is the event. Told to the people it is for, and nobody else.
    """
    from matazim.models import Event, Notification

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה מורה", naomi)
    dana = _leader("dana@example.com", "דנה כהן", naomi)
    invited = _student("kid1@example.com", noa)
    not_invited = _student("kid2@example.com", dana)

    client.force_login(naomi)
    client.post(
        reverse("matazim:staff_events"),
        {
            "title": "תערוכת סיום",
            "starts_at": _soon().strftime("%Y-%m-%dT%H:%M"),
            "place": "אולם הספורט",
            "leaders": [str(noa.pk)],
        },
    )

    event = Event.objects.get()
    assert event.for_everyone is False
    assert list(event.leaders.all()) == [noa]

    assert Notification.objects.filter(
        user=invited.user, kind=Notification.EVENT
    ).exists()
    assert not Notification.objects.filter(
        user=not_invited.user, kind=Notification.EVENT
    ).exists(), "somebody was told about a day they are not invited to"


def test_an_event_for_nobody_is_refused(client, db):
    """T-F-M.31.5-2: a row no screen can show is not a record, it is litter."""
    from matazim.models import Event

    client.force_login(_manager())
    response = client.post(
        reverse("matazim:staff_events"),
        {"title": "יום", "starts_at": _soon().strftime("%Y-%m-%dT%H:%M")},
    )

    assert response.status_code == 200
    assert not Event.objects.exists()
    assert "בחרו למי" in response.content.decode()


def test_cancelling_tells_the_people_who_were_told(client, db):
    """T-F-M.31.5-3: REQ-M.27.

    Taken down rather than deleted. Somebody arranged their week around it, and
    a row that vanishes leaves them holding a date nobody will explain.
    """
    from matazim.models import Event, Notification

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    event = _make(naomi, "תערוכת סיום")

    client.force_login(naomi)
    client.post(reverse("matazim:cancel_event", args=[event.pk]))

    event.refresh_from_db()
    assert event.is_cancelled, "the row was destroyed instead of marked"

    told = Notification.objects.filter(user=student.user, kind=Notification.EVENT).last()
    assert "בוטל" in told.text


def test_only_a_program_manager_writes_days(client, db):
    """T-F-M.31.5-4: §4.4a."""
    naomi = _manager()
    leader = _leader("noa@example.com", "נעה", naomi)
    student = _student("kid@example.com", leader)

    for user in (leader.user, student.user):
        client.force_login(user)
        assert client.get(reverse("matazim:staff_events")).status_code == 403


def test_she_cannot_cancel_another_institutions_day(client, db):
    """T-F-M.31.5-5: §4.4, on a write."""
    naomi = _manager("naomi@example.com")
    other = _manager("other@example.com", "אחרת")
    theirs = _make(other, "היום שלהם")

    client.force_login(naomi)
    assert client.post(reverse("matazim:cancel_event", args=[theirs.pk])).status_code == 404

    theirs.refresh_from_db()
    assert not theirs.is_cancelled
