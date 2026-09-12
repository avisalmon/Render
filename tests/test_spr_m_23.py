"""SPR-M.23 — what the coherence pass found.

Three gaps, and the first is the reason the pass was worth doing. REQ-M.16 said
applying creates a `Student` row "plus an `Application`". There was no such
table. The form asked a fourteen-year-old for their grade, why they wanted to
join and what they had built; it required the first two, validated them, and
dropped all three, and the leader deciding about them saw a name and an email.

It was found by signing a fake person up through the real forms and then
searching every text column in the database for the sentence they had typed.
Nothing caught it in thirteen sprints because every screen rendered correctly
and every test passed: nobody had followed the data to the end.

Traces: REQ-M.16, REQ-M.8, REQ-M.98, REQ-M.85, RULE-1, §4.7.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm23

PASSWORD = "sprm23-pass-3318"


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
        user=_user(email, name),
        program_manager=manager,
        approved_at=timezone.now(),
    )


def _member(email="kid@example.com", name="יובל כהן"):
    from matazim.models import MemberProfile

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
    return user


# ------------------------------------------- F-M.23.1: the answers are kept


def test_what_they_wrote_is_stored(client, db):
    """T-F-M.23.1-1: REQ-M.16, and the defect this sprint exists for."""
    from matazim.models import Application

    leader = _leader("noa@example.com", "נעה מורה", _manager())
    user = _member()
    client.force_login(user)

    client.post(
        reverse("matazim:apply"),
        {
            "leader": str(leader.pk),
            "grade": "ט2",
            "motivation": "אני רוצה לבנות רובוטים ולעזור לילדים אחרים",
            "built": "מנורה עם ארדואינו",
        },
    )

    application = Application.objects.get(student__user=user)
    assert application.grade == "ט2"
    assert application.motivation == "אני רוצה לבנות רובוטים ולעזור לילדים אחרים"
    assert application.built_before == "מנורה עם ארדואינו"
    assert application.asked_id == leader.pk, "nothing says who it was written for"


def test_the_leader_deciding_can_read_it(client, db):
    """T-F-M.23.1-2: REQ-M.16.

    Storing it and not showing it would be the same defect one table along. The
    leader reads it on the screen where they say yes, not on one they would have
    to think to go and find.
    """
    leader = _leader("noa@example.com", "נעה מורה", _manager())
    user = _member()
    client.force_login(user)
    client.post(
        reverse("matazim:apply"),
        {
            "leader": str(leader.pk),
            "grade": "ט2",
            "motivation": "אני רוצה לבנות רובוטים",
            "built": "מנורה עם ארדואינו",
        },
    )

    client.force_login(leader.user)
    html = client.get(reverse("matazim:leader_home")).content.decode()

    assert "אני רוצה לבנות רובוטים" in html, "the leader is approving somebody blind"
    assert "מנורה עם ארדואינו" in html
    assert "ט2" in html


def test_asking_twice_keeps_both(client, db):
    """T-F-M.23.1-3: REQ-M.16, §4.7.

    A row per asking, not per person. Somebody turned down can apply again, and
    the second answer is not a correction of the first: whether this person has
    asked before is the thing a leader most wants to know.
    """
    from matazim.models import Application

    manager = _manager()
    first = _leader("noa@example.com", "נעה מורה", manager)
    second = _leader("dana@example.com", "דנה כהן", manager)
    user = _member()
    client.force_login(user)

    client.post(
        reverse("matazim:apply"),
        {"leader": str(first.pk), "grade": "ט1", "motivation": "פעם ראשונה", "built": ""},
    )

    # Declined, so they are free to ask somebody else.
    student = Application.objects.get().student
    client.force_login(first.user)
    client.post(reverse("matazim:leader_confirm", args=[student.pk]), {"action": "decline"})

    client.force_login(user)
    client.post(
        reverse("matazim:apply"),
        {"leader": str(second.pk), "grade": "ט1", "motivation": "פעם שנייה", "built": ""},
    )

    said = list(Application.objects.order_by("created_at").values_list("motivation", flat=True))
    assert said == ["פעם ראשונה", "פעם שנייה"], "an answer was overwritten"


def test_their_own_words_are_in_their_own_data(client, db):
    """T-F-M.23.1-4: REQ-M.85.

    Free text a child wrote about themselves is among the most personal things
    here. It cannot be visible to staff and absent from the answer we give that
    child when they ask what we hold.
    """
    leader = _leader("noa@example.com", "נעה מורה", _manager())
    user = _member()
    client.force_login(user)
    client.post(
        reverse("matazim:apply"),
        {"leader": str(leader.pk), "grade": "ט2", "motivation": "לבנות דברים", "built": ""},
    )

    program = client.get(reverse("matazim:my_data")).context["data"]["program"][0]
    assert program["applications"][0]["motivation"] == "לבנות דברים"
    assert program["applications"][0]["asked"] == "נעה מורה", "an email is not an answer"


# ------------------------------------------- F-M.23.2: return to intent


def test_signing_in_returns_to_where_they_were_going(client, db):
    """T-F-M.23.2-1: REQ-M.8.

    The view has honoured `next` for sprints and no template ever sent it, so
    the line could never fire.
    """
    user = _member()
    target = reverse("matazim:my_data")

    page = client.get(target)
    assert page.status_code == 302
    assert "next=" in page.url, "the gate does not say where they wanted to go"

    form = client.get(f"{reverse('matazim:login')}?next={target}").content.decode()
    assert f'value="{target}"' in form, "the form does not carry the destination"

    response = client.post(
        reverse("matazim:login"),
        {"email": user.email, "password": PASSWORD, "next": target},
    )
    assert response.status_code == 302
    assert response.url == target, f"landed on {response.url}, not where they were going"


@pytest.mark.parametrize(
    "hostile",
    [
        "https://evil.example/steal",
        "//evil.example/steal",
        "/courses/",  # inside babook: RULE-1 forbids it
        "/admin/",
        "\\\\evil.example",
        "/matazim/\\..\\admin/",
    ],
)
def test_it_refuses_to_be_an_open_redirect(client, db, hostile):
    """T-F-M.23.2-2: REQ-M.8, RULE-1.

    The destination comes from outside, so two different things are refused:
    bouncing somebody to an attacker's page with our domain in the referrer,
    and walking out of the walls into babook.
    """
    user = _member()
    response = client.post(
        reverse("matazim:login"),
        {"email": user.email, "password": PASSWORD, "next": hostile},
    )
    assert response.status_code == 302
    assert response.url == reverse("matazim:home"), f"followed {hostile!r} to {response.url}"


def test_registering_returns_there_too(client, db):
    """T-F-M.23.2-3: REQ-M.8. One link, new and existing users alike."""
    target = reverse("matazim:my_data")
    response = client.post(
        reverse("matazim:register"),
        {
            "name": "יובל כהן",
            "email": "new@example.com",
            "password": "a-long-enough-pass",
            "birth_year": str(timezone.now().year - 14),
            "guardian_name": "דנה כהן",
            "guardian_email": "parent@example.com",
            "guardian_consent": "on",
            "next": target,
        },
    )
    assert response.status_code == 302
    assert response.url == target


# ------------------------------------------- F-M.23.3: moving a student


def test_a_student_can_be_moved_and_it_is_logged(client, db):
    """T-F-M.23.3-1: REQ-M.98, §4.7.

    A teacher leaves, a child changes school, a pairing does not work. Doing it
    by hand in Django's admin writes the field with no log, which is the one
    thing §4.7 says must not happen.
    """
    from matazim.models import Student

    manager = _manager()
    here = _leader("noa@example.com", "נעה מורה", manager)
    there = _leader("dana@example.com", "דנה כהן", manager)
    student = Student.objects.create(user=_member(), leader=here, status=Student.IN_TRAINING)

    client.force_login(manager)
    client.post(
        reverse("matazim:staff_leader", args=[here.pk]),
        {"action": "move", "student": str(student.pk), "to": str(there.pk)},
    )

    student.refresh_from_db()
    assert student.leader_id == there.pk
    assert student.status == Student.IN_TRAINING, "moving is not progress or regress"

    entry = student.history.order_by("-at").first()
    assert entry.from_leader_id == here.pk
    assert entry.to_leader_id == there.pk
    assert entry.changed_by_id == manager.pk, "nobody is named as having done it"


def test_a_manager_cannot_move_somebody_into_another_world(client, db):
    """T-F-M.23.3-2: REQ-M.98, §4.4.

    Both ends are read through her own scope, so the move cannot reach across
    institutions in either direction.
    """
    from matazim.models import Student

    naomi = _manager("naomi@example.com")
    hers = _leader("noa@example.com", "נעה מורה", naomi)
    student = Student.objects.create(user=_member(), leader=hers, status=Student.IN_TRAINING)

    stranger = _leader("other-leader@example.com", "זרה", _manager("other-pm@example.com"))

    client.force_login(naomi)
    client.post(
        reverse("matazim:staff_leader", args=[hers.pk]),
        {"action": "move", "student": str(student.pk), "to": str(stranger.pk)},
    )

    student.refresh_from_db()
    assert student.leader_id == hers.pk, "a student was handed to another institution"
    assert not student.history.filter(to_leader=stranger).exists()


def test_moving_somebody_nowhere_writes_nothing(client, db):
    """T-F-M.23.3-3: a double-submitted form must not fill a history a person reads."""
    from matazim.history import record_leader_change
    from matazim.models import Student

    manager = _manager()
    here = _leader("noa@example.com", "נעה מורה", manager)
    student = Student.objects.create(user=_member(), leader=here, status=Student.IN_TRAINING)

    assert record_leader_change(student, here, by=manager) is None
    assert student.history.count() == 0
