"""SPR-M.44 — the leader's journey says what to do next, too.

SPR-M.43 did this for the member. This is the same walk for the adult, signed
in at each stage they actually pass through: a teacher waiting to be approved,
a leader with people waiting on them, and a leader on an ordinary day with
nothing pending, which is most days.

**The ordinary day was the one that was wrong.** A leader with a group and an
empty queue opened האזור שלי to a page whose first screen on a phone was the
join link and a QR code, with their own people below the fold, under a subtitle
promising "המט״צים שמחכים לאישור" when nobody was waiting. Recruiting is
occasional. Looking in on your group is why you opened the page.

**And a candidate was treated as a stranger.** A teacher whose row is not yet
approved (REQ-M.93) got the same 403 as anybody else, and that page says to
talk to "המוביל שלכם בבית הספר", which is the right sentence for a teenager and
advice to ask themselves for a teacher. ההרשאה שלי already existed and said
exactly what they wanted to know.

Traces: REQ-M.73, M.93, M.99, M.124.
"""

import pathlib

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm44

REPO = pathlib.Path(__file__).resolve().parent.parent
PASSWORD = "sprm44-pass-2288"


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _institution(name="רשת אחת"):
    from matazim.models import Institution

    inst = Institution.objects.create(name=name)
    inst.managers.add(_user(f"pm-{name}@example.com", "נעמי"))
    return inst


def _leader(email="mich@example.com", name="מיכל", approved=True, institution=None):
    from matazim.models import Leader

    return Leader.objects.create(
        user=_user(email, name),
        institution=institution or _institution(),
        approved_at=timezone.now() if approved else None,
    )


def _student(email, name, leader, pending=None):
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
        user=user, leader=leader, pending_leader=pending, status=Student.IN_TRAINING
    )


# ------------------------------------------- a candidate is not a trespasser


def test_a_waiting_teacher_is_taken_to_their_status_not_refused(client, db):
    """REQ-M.93, M.99. Their row exists and is unapproved, which is a real
    state rather than a failed break-in."""
    candidate = _leader(email="dana@example.com", name="דנה", approved=False)
    client.force_login(candidate.user)

    resp = client.get(reverse("matazim:leader_home"))
    assert resp.status_code == 302
    assert resp.url == reverse("matazim:leader_entrance")


def test_somebody_with_no_leader_row_is_still_refused(client, db):
    """The redirect is for a candidate, not a way in for anyone signed in."""
    client.force_login(_user("nobody@example.com", "אורח"))
    assert client.get(reverse("matazim:leader_home")).status_code == 403


# ------------------------------------------- the page says what is true today


def test_an_ordinary_day_names_the_group_not_a_queue_that_is_empty(client, db):
    """The subtitle claimed "המט״צים שמחכים לאישור" on every visit."""
    leader = _leader()
    _student("kid1@example.com", "אלמה", leader)
    client.force_login(leader.user)

    html = client.get(reverse("matazim:leader_home")).content.decode()
    assert "המט״צים שלכם, ואיפה הם בתוכנית" in html
    assert "שמחכים לאישור" not in html


def test_a_day_with_somebody_waiting_says_so(client, db):
    leader = _leader()
    other = _leader(email="other@example.com", name="יוסי", institution=leader.institution)
    _student("kid2@example.com", "נועה", other, pending=leader)
    client.force_login(leader.user)

    html = client.get(reverse("matazim:leader_home")).content.decode()
    assert "מה מחכה לכם עכשיו" in html


def test_a_leader_with_nobody_yet_is_pointed_at_the_link(client, db):
    """The one state where the join link really is the next thing."""
    leader = _leader()
    client.force_login(leader.user)

    html = client.get(reverse("matazim:leader_home")).content.decode()
    assert "הקישור שלכם, כדי שהמט״צים הראשונים יצטרפו" in html


# ------------------------------------------- the group comes before the tool


def test_the_group_is_put_before_the_join_link_once_there_is_a_group(client, db):
    """On a phone the link and its QR were the whole first screen.

    Asserted through the class that does it rather than by measuring pixels,
    so this test says what the template promises and the rule below says the
    stylesheet keeps that promise."""
    leader = _leader()
    _student("kid3@example.com", "שירה", leader)
    client.force_login(leader.user)

    assert "mz-two-up-flip" in client.get(reverse("matazim:leader_home")).content.decode()


def test_a_leader_with_nobody_keeps_the_link_first(client, db):
    leader = _leader()
    client.force_login(leader.user)
    assert "mz-two-up-flip" not in client.get(reverse("matazim:leader_home")).content.decode()


def test_the_stylesheet_actually_swaps_them():
    css = (REPO / "static" / "matazim" / "matazim.css").read_text(encoding="utf-8")
    assert ".mz-two-up-flip > :first-child" in css
    assert "order: 2" in css
