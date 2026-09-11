"""SPR-M.7 — How anyone becomes anyone.

Before this, nothing in the app could create a `Leader` or a `Student` at all:
the roles existed and Django admin was the only way in. And passing the entrance
test unlocked a door that sent you to a registration form you had already
filled in.

Avi's brief was that the UX is the feature, so these tests are written as the
four journeys rather than as a list of endpoints. What they mostly check is that
nobody ever reaches a dead end and that an invite is never silently dropped,
because that is how a teenager ends up in the program attached to nobody.

Traces: REQ-M.9, M.10, M.16, M.25, M.66, M.72, M.73.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm7

PASSWORD = "sprm7-pass-6612"


def make_user(email, name=""):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name or email})
    return user


def make_admin(client, email="chief@example.com"):
    from matazim.models import MemberProfile

    user = make_user(email, "אבי")
    MemberProfile.objects.update_or_create(user=user, defaults={"is_admin": True})
    client.force_login(user)
    return user


def make_leader(email="noa@example.com", name="נעה מורה", school="עתיד רמלה"):
    from matazim.models import Leader, StudyClass

    leader = Leader.objects.create(user=make_user(email, name))
    StudyClass.objects.create(leader=leader, name="ט1", school_name=school)
    return leader


def sign_in(client, email="kid@example.com", name="יובל", passed=True):
    from matazim.models import MemberProfile

    user = make_user(email, name)
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "welcome_accepted_at": timezone.now(),
            "entrance_test_passed_at": timezone.now() if passed else None,
        },
    )
    client.force_login(user)
    return user


# ------------------------------------------------- Journey C: the admin


def test_an_admin_can_make_someone_a_leader(client, db):
    """T-F-M.7.2-1: REQ-M.25. The thing an admin exists to do, and there was no screen."""
    from matazim.models import Leader

    make_admin(client)
    teacher = make_user("teacher@example.com", "רונית")

    client.post(
        reverse("matazim:staff_leaders"),
        {"action": "add", "email": "teacher@example.com"},
    )
    leader = Leader.objects.filter(user=teacher).first()
    assert leader is not None
    assert leader.is_active
    assert leader.join_code, "a leader is useless without a link to hand out"


def test_making_a_leader_is_admin_only(client, db):
    """T-F-M.7.2-2."""
    make_user("outsider@example.com")
    sign_in(client, "member@example.com")

    response = client.post(
        reverse("matazim:staff_leaders"),
        {"action": "add", "email": "outsider@example.com"},
    )
    assert response.status_code in (302, 403)


def test_an_admin_sees_a_leaders_link_and_can_rotate_it(client, db):
    """T-F-M.7.2-3: REQ-M.9. A code that cannot be rotated is a code you cannot recall."""
    make_admin(client)
    leader = make_leader()
    before = leader.join_code

    page = client.get(reverse("matazim:staff_leader", args=[leader.pk])).content.decode()
    assert before in page

    client.post(reverse("matazim:staff_leader", args=[leader.pk]), {"action": "rotate"})
    leader.refresh_from_db()
    assert leader.join_code != before


def test_the_qr_is_a_real_image(client, db):
    """T-F-M.7.3-1: printed on a page and stuck on a wall, so it has to be an image."""
    make_admin(client)
    leader = make_leader()

    response = client.get(reverse("matazim:leader_qr", args=[leader.pk]))
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"


# ------------------------------------------------- Journey A: the invite link


def test_the_invite_landing_works_logged_out_and_names_who_is_inviting(client, db):
    """T-F-M.7.3-2: REQ-M.9.

    The link gets pasted into WhatsApp groups, so it meets people with no
    account. A bare login form would tell them nothing about where they landed.
    """
    leader = make_leader(name="נעה מורה", school="עתיד רמלה")

    html = client.get(reverse("matazim:join", args=[leader.join_code])).content.decode()
    assert "נעה מורה" in html
    assert "עתיד רמלה" in html


def test_a_bad_code_does_not_pretend_to_be_an_invite(client, db):
    """T-F-M.7.3-3: a mistyped link should say so, not show an empty invitation."""
    response = client.get(reverse("matazim:join", args=["not-a-real-code"]))
    assert response.status_code == 404


def test_the_invite_survives_the_entrance_test(client, db):
    """T-F-M.7.7-1: REQ-M.72, and the thing most likely to lose a teenager.

    They tap the link before doing the test. If we forget who invited them, they
    come back later and join nobody.
    """
    leader = make_leader(name="נעה מורה")
    sign_in(client, passed=False)

    client.get(reverse("matazim:join", args=[leader.join_code]))

    # The invite is carried, and said out loud, everywhere they are sent next.
    for page in ("matazim:entrance_test", "matazim:home"):
        assert "נעה מורה" in client.get(reverse(page)).content.decode()


def test_joining_by_link_needs_no_confirmation(client, db):
    """T-F-M.7.3-4: REQ-M.9. The leader handed out the link; the choice is theirs."""
    from matazim.models import Student

    leader = make_leader()
    user = sign_in(client, passed=True)

    client.get(reverse("matazim:join", args=[leader.join_code]))
    client.post(reverse("matazim:join", args=[leader.join_code]), {"action": "join"})

    student = Student.objects.get(user=user)
    assert student.leader == leader
    assert student.pending_leader is None


def test_you_cannot_join_before_passing_the_test(client, db):
    """T-F-M.7.7-2: REQ-M.36 holds even with an invite in hand."""
    from matazim.models import Student

    leader = make_leader()
    sign_in(client, passed=False)

    client.post(reverse("matazim:join", args=[leader.join_code]), {"action": "join"})
    assert not Student.objects.exists()


# ------------------------------------------------- Journey B: the open door


def test_the_unlocked_door_leads_to_the_application(client, db):
    """T-F-M.7.4-1: it used to lead to the registration form they had just filled in."""
    sign_in(client, passed=True)
    html = client.get(reverse("matazim:home")).content.decode()
    assert reverse("matazim:apply") in html


def test_applying_creates_the_student_and_asks_a_leader(client, db):
    """T-F-M.7.4-2, T-F-M.7.5-1: REQ-M.16 and REQ-M.10.

    Three questions only. The application is not what assesses anyone, the
    entrance test is, so every extra field is a teenager who does not finish.
    """
    from matazim.models import Student

    leader = make_leader()
    user = sign_in(client, passed=True)

    client.post(
        reverse("matazim:apply"),
        {
            "grade": "ט1",
            "motivation": "אני רוצה לבנות דברים",
            "built_before": "משחק בסקראץ׳",
            "leader": leader.pk,
        },
    )

    student = Student.objects.get(user=user)
    assert student.status == Student.APPLIED
    assert student.pending_leader == leader
    assert student.leader is None, "asking is not being accepted"


def test_an_applicant_is_told_who_they_are_waiting_for(client, db):
    """T-F-M.7.5-2: REQ-M.5a. "Waiting" with no name attached is just silence."""
    leader = make_leader(name="נעה מורה")
    sign_in(client, passed=True)
    client.post(
        reverse("matazim:apply"),
        {"grade": "ט1", "motivation": "כי כן", "built_before": "כלום", "leader": leader.pk},
    )

    html = client.get(reverse("matazim:profile")).content.decode()
    assert "נעה מורה" in html
    assert "ממתין" in html or "אישור" in html


def test_you_cannot_apply_before_passing_the_test(client, db):
    """T-F-M.7.4-3."""
    from matazim.models import Student

    make_leader()
    sign_in(client, passed=False)
    response = client.get(reverse("matazim:apply"))
    assert response.status_code == 302
    assert not Student.objects.exists()


# ------------------------------------------------- Journey D: the leader


def test_a_leader_lands_on_their_own_page(client, db):
    """T-F-M.7.6-1: REQ-M.73."""
    leader = make_leader()
    client.force_login(leader.user)

    html = client.get(reverse("matazim:leader_home")).content.decode()
    assert leader.join_code in html


def test_a_leader_confirms_someone_who_asked(client, db):
    """T-F-M.7.6-2: REQ-M.10. Without this the open door has no exit."""
    from matazim.models import Student

    leader = make_leader()
    student = Student.objects.create(
        user=make_user("waiting@example.com", "יובל"), pending_leader=leader
    )

    client.force_login(leader.user)
    html = client.get(reverse("matazim:leader_home")).content.decode()
    assert "יובל" in html

    client.post(reverse("matazim:leader_confirm", args=[student.pk]), {"action": "confirm"})
    student.refresh_from_db()
    assert student.leader == leader
    assert student.pending_leader is None


def test_a_leader_cannot_confirm_someone_who_asked_another_leader(client, db):
    """T-F-M.7.6-3: the scoping from SPR-M.6, enforced on a write this time."""
    from matazim.models import Student

    mine = make_leader("mine@example.com")
    theirs = make_leader("theirs@example.com")
    student = Student.objects.create(user=make_user("notyours@example.com"), pending_leader=theirs)

    client.force_login(mine.user)
    response = client.post(
        reverse("matazim:leader_confirm", args=[student.pk]), {"action": "confirm"}
    )

    student.refresh_from_db()
    assert response.status_code in (302, 403, 404)
    assert student.leader is None


# ------------------------------------------------- Doors


def test_the_leader_door_does_not_offer_a_registration_form(client, db):
    """T-F-M.7.8-1: REQ-M.66. A door labelled for one role must not be the other."""
    html = client.get(reverse("matazim:leader_entrance")).content.decode()
    assert reverse("matazim:register") not in html
    assert "צוות התוכנית" in html or "מנהלי התוכנית" in html


def test_the_leader_door_sends_an_actual_leader_to_their_page(client, db):
    """T-F-M.7.8-2: the same door, doing the right thing for the right person."""
    leader = make_leader()
    client.force_login(leader.user)

    response = client.get(reverse("matazim:leader_entrance"))
    assert response.status_code == 302
    assert response.url == reverse("matazim:leader_home")


def test_a_leader_can_get_back_to_their_area_from_anywhere(client, db):
    """T-F-M.7.6-4: found by using it.

    The leader page was reachable only through the כניסת מובילים door on the
    home page, which is a strange way to ask someone to return to their own
    desk. Nobody who is not a leader sees the entry.
    """
    leader = make_leader()
    client.force_login(leader.user)
    assert reverse("matazim:leader_home") in client.get(reverse("matazim:home")).content.decode()

    client.logout()
    sign_in(client, "justakid@example.com")
    assert (
        reverse("matazim:leader_home") not in client.get(reverse("matazim:home")).content.decode()
    )


def test_an_admin_reaches_the_leaders_screen_from_the_staff_area(client, db):
    """T-F-M.7.2-4: a screen you have to know the URL for is a screen nobody uses."""
    make_admin(client)
    html = client.get(reverse("matazim:staff_home")).content.decode()
    assert reverse("matazim:staff_leaders") in html
