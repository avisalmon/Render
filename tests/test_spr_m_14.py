"""SPR-M.14 — How a leader gets made.

Three doors, and the thing they have in common is the point: **all three end at
a person pressing approve.** Nothing makes a leader automatically, because a
leader can see named minors' progress, and that is not a role to hand out on the
strength of holding a URL.

The sharpest test in here is `test_a_candidate_has_nothing`. A candidate is a
`Leader` row that exists and grants nothing, which means `access.leader_of` has
to refuse to return it. Miss that one filter and somebody who followed a link
pinned to a staff-room noticeboard has a roster, an invite code of their own,
and a view of named minors, before anyone said yes. That is the same class of
mistake as the unauthenticated QR endpoint in SPR-M.9, arriving by a different
road.

Traces: REQ-M.89, M.90, M.91, M.92, M.93.
"""

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm14

PASSWORD = "sprm14-pass-6690"


def make_user(email, name=""):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name or email})
    return user


def make_manager(email="naomi@example.com", name="נעמי"):
    from matazim.models import MemberProfile

    user = make_user(email, name)
    MemberProfile.objects.update_or_create(user=user, defaults={"is_program_manager": True})
    return user


def make_invite(manager, kind="personal", label="רונית מעתיד רמלה", email=""):
    from matazim.models import LeaderInvite

    return LeaderInvite.objects.create(program_manager=manager, kind=kind, label=label, email=email)


# ------------------------------------------ door one: they already have an account


def test_a_manager_approves_someone_who_already_has_an_account(client, db):
    """T-F-M.14.2-1: REQ-M.90. The simplest door, and the one she uses most."""
    from matazim.models import Leader

    manager = make_manager()
    teacher = make_user("ronit@example.com", "רונית")
    client.force_login(manager)

    client.post(reverse("matazim:pm_leaders"), {"action": "approve", "email": teacher.email})

    leader = Leader.objects.get(user=teacher)
    assert leader.is_approved
    assert leader.program_manager == manager
    assert leader.approved_by == manager


def test_approving_tells_them(client, db):
    """T-F-M.14.3-1: REQ-M.90.

    A role granted in silence is a role nobody knows they have, and this one
    comes with a screen they would never think to look for.
    """
    manager = make_manager()
    teacher = make_user("ronit@example.com", "רונית")
    client.force_login(manager)
    mail.outbox.clear()

    client.post(reverse("matazim:pm_leaders"), {"action": "approve", "email": teacher.email})

    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert teacher.email in sent.to
    assert "מוביל" in sent.subject
    assert "/matazim/leader/" in sent.body, "the mail must say where to go"


def test_an_unknown_email_is_refused_and_creates_nobody(client, db):
    """T-F-M.14.2-2: a typo must not conjure a person holding a role."""
    from matazim.models import Leader

    manager = make_manager()
    client.force_login(manager)

    client.post(reverse("matazim:pm_leaders"), {"action": "approve", "email": "nope@example.com"})
    assert not Leader.objects.exists()
    assert not User.objects.filter(email="nope@example.com").exists()


def test_a_manager_cannot_approve_another_worlds_leader(client, db):
    """T-F-M.14.2-3: REQ-M.88, on the approval path."""
    from matazim.models import Leader

    mine = make_manager("a@example.com")
    theirs = make_manager("b@example.com")
    teacher = make_user("ronit@example.com")
    Leader.objects.create(user=teacher, program_manager=theirs, approved_at=timezone.now())

    client.force_login(mine)
    client.post(reverse("matazim:pm_leaders"), {"action": "approve", "email": teacher.email})

    assert Leader.objects.get(user=teacher).program_manager == theirs


# --------------------------------------------- door two: a personal invitation


def test_a_personal_invite_names_who_it_is_for(client, db):
    """T-F-M.14.4-1: REQ-M.91. The label is a label, but it has to exist."""
    from matazim.models import LeaderInvite

    manager = make_manager()
    client.force_login(manager)

    client.post(
        reverse("matazim:pm_leaders"),
        {"action": "invite_personal", "label": "רונית מעתיד רמלה"},
    )
    invite = LeaderInvite.objects.get()
    assert invite.kind == LeaderInvite.PERSONAL
    assert invite.label == "רונית מעתיד רמלה"
    assert invite.program_manager == manager


def test_a_personal_invite_without_a_name_is_refused(client, db):
    """T-F-M.14.4-2: REQ-M.91.

    Not validation for its own sake. An unnamed personal invite looks exactly
    like an open one on the screen, which is how the wrong link gets sent to a
    staff room.
    """
    from matazim.models import LeaderInvite

    manager = make_manager()
    client.force_login(manager)

    client.post(reverse("matazim:pm_leaders"), {"action": "invite_personal", "label": "  "})
    assert not LeaderInvite.objects.exists()


def test_the_landing_page_works_logged_out(client, db):
    """T-F-M.14.4-3: REQ-M.91. It arrives by WhatsApp and meets strangers."""
    invite = make_invite(make_manager())

    html = client.get(reverse("matazim:invite_landing", args=[invite.token])).content.decode()
    assert "רונית מעתיד רמלה" in html
    assert reverse("matazim:register") in html


def test_a_personal_invite_is_spent_by_the_first_person(client, db):
    """T-F-M.14.4-4: REQ-M.91, the property Avi was specific about.

    Forwarding is tolerated. A second use is not.
    """
    from matazim.models import Leader

    invite = make_invite(make_manager())
    first = make_user("first@example.com")
    client.force_login(first)
    client.get(reverse("matazim:invite_landing", args=[invite.token]))

    invite.refresh_from_db()
    assert invite.used_by == first
    assert invite.is_spent

    client.logout()
    second = make_user("second@example.com")
    client.force_login(second)
    response = client.get(reverse("matazim:invite_landing", args=[invite.token]))

    assert not Leader.objects.filter(user=second).exists(), "a spent invite let a second person in"
    assert "כבר לא בתוקף" in response.content.decode()


def test_a_revoked_invite_is_dead(client, db):
    """T-F-M.14.4-5: REQ-M.91. She can take one back."""
    invite = make_invite(make_manager())
    invite.revoked_at = timezone.now()
    invite.save()

    html = client.get(reverse("matazim:invite_landing", args=[invite.token])).content.decode()
    assert "כבר לא בתוקף" in html


def test_an_unknown_token_does_not_pretend_to_be_an_invitation(client, db):
    """T-F-M.14.4-6: a mistyped link says so."""
    html = client.get(reverse("matazim:invite_landing", args=["not-a-token"])).content.decode()
    assert "כבר לא בתוקף" in html


# ------------------------------------------------- door three: the open invite


def test_an_open_invite_is_reusable(client, db):
    """T-F-M.14.5-1: REQ-M.92. A staff room is more than one person."""
    from matazim.models import Leader, LeaderInvite

    invite = make_invite(make_manager(), kind=LeaderInvite.OPEN, label="חדר מורים")

    for email in ("a@example.com", "b@example.com"):
        user = make_user(email)
        client.force_login(user)
        client.get(reverse("matazim:invite_landing", args=[invite.token]))
        client.logout()

    assert Leader.objects.count() == 2
    invite.refresh_from_db()
    assert not invite.is_spent, "an open invite must not be spent"


def test_an_open_invite_confers_nothing(client, db):
    """T-F-M.14.5-2: REQ-M.92.

    The whole reason it can be reusable. Anyone could be holding it, so holding
    it cannot be what makes you staff.
    """
    from matazim.models import Leader, LeaderInvite

    invite = make_invite(make_manager(), kind=LeaderInvite.OPEN, label="חדר מורים")
    user = make_user("teacher@example.com")
    client.force_login(user)
    client.get(reverse("matazim:invite_landing", args=[invite.token]))

    leader = Leader.objects.get(user=user)
    assert not leader.is_approved


# ----------------------------------------- the trap: a candidate has nothing


def test_a_candidate_has_nothing(client, db):
    """T-F-M.14.6-1: REQ-M.93, and the sharpest test in this sprint.

    A candidate is a `Leader` row that grants nothing at all. If `leader_of`
    returned it, somebody who followed a link off a noticeboard would have a
    roster, an invite code of their own, and a view of named minors, before any
    person said yes.
    """
    from matazim.access import leader_of
    from matazim.models import Leader, LeaderInvite

    invite = make_invite(make_manager(), kind=LeaderInvite.OPEN, label="חדר מורים")
    user = make_user("hopeful@example.com")
    client.force_login(user)
    client.get(reverse("matazim:invite_landing", args=[invite.token]))

    assert Leader.objects.filter(user=user).exists(), "the candidacy should exist"
    assert leader_of(user) is None, "a candidate must not resolve as a leader"

    for name in ("matazim:leader_home", "matazim:roster", "matazim:classes"):
        assert client.get(reverse(name)).status_code in (302, 403), f"{name} let a candidate in"


def test_a_candidate_cannot_be_certified_into_existence(client, db):
    """T-F-M.14.6-2: REQ-M.93. No side door either."""
    from matazim.models import Leader, LeaderInvite

    invite = make_invite(make_manager(), kind=LeaderInvite.OPEN)
    user = make_user("hopeful@example.com")
    client.force_login(user)
    client.get(reverse("matazim:invite_landing", args=[invite.token]))

    leader = Leader.objects.get(user=user)
    assert client.get(reverse("matazim:leader_qr", args=[leader.pk])).status_code in (
        302,
        403,
        404,
    )


def test_approving_a_candidate_is_the_same_act_as_approving_a_stranger(client, db):
    """T-F-M.14.6-3: REQ-M.93.

    One code path on purpose. Two would drift into meaning different things, and
    the difference would be invisible until somebody had the wrong access.
    """
    from matazim.access import leader_of
    from matazim.models import Leader, LeaderInvite

    manager = make_manager()
    invite = make_invite(manager, kind=LeaderInvite.OPEN)
    hopeful = make_user("hopeful@example.com")
    client.force_login(hopeful)
    client.get(reverse("matazim:invite_landing", args=[invite.token]))
    client.logout()

    client.force_login(manager)
    client.post(reverse("matazim:pm_leaders"), {"action": "approve", "email": hopeful.email})

    leader = Leader.objects.get(user=hopeful)
    assert leader.is_approved
    assert leader.approved_by == manager
    assert leader_of(hopeful) == leader


def test_rejecting_a_candidate_removes_the_candidacy_not_the_person(client, db):
    """T-F-M.14.6-4: REQ-M.67's principle, applied to candidates.

    This product does not destroy people. It changes what they can reach.
    """
    from matazim.models import Leader, LeaderInvite

    manager = make_manager()
    invite = make_invite(manager, kind=LeaderInvite.OPEN)
    hopeful = make_user("hopeful@example.com")
    client.force_login(hopeful)
    client.get(reverse("matazim:invite_landing", args=[invite.token]))
    leader = Leader.objects.get(user=hopeful)
    client.logout()

    client.force_login(manager)
    client.post(reverse("matazim:reject_candidate", args=[leader.pk]))

    assert not Leader.objects.filter(user=hopeful).exists()
    assert User.objects.filter(pk=hopeful.pk).exists(), "the account was destroyed"


def test_candidates_appear_on_her_screen(client, db):
    """T-F-M.14.6-5: REQ-M.94.

    On the same page as her leaders, not a screen of their own. A separate
    screen for "people waiting on you" is a screen nobody remembers to visit.
    """
    from matazim.models import LeaderInvite

    manager = make_manager()
    invite = make_invite(manager, kind=LeaderInvite.OPEN)
    hopeful = make_user("hopeful@example.com", "מיכל חדשה")
    client.force_login(hopeful)
    client.get(reverse("matazim:invite_landing", args=[invite.token]))
    client.logout()

    client.force_login(manager)
    html = client.get(reverse("matazim:pm_leaders")).content.decode()
    assert "מיכל חדשה" in html


# -------------------------------------------------- the invitation survives


def test_an_invitation_survives_making_an_account(client, db):
    """T-F-M.14.4-7: REQ-M.91, and the same lesson as REQ-M.72.

    They tap the link, discover they need an account, and make one. If the
    invitation does not survive that, they land on the home page as an ordinary
    visitor with no idea what became of the link they were sent.
    """
    from matazim.models import Leader

    invite = make_invite(make_manager())
    client.get(reverse("matazim:invite_landing", args=[invite.token]))

    year = timezone.now().year
    client.post(
        reverse("matazim:register"),
        {
            "name": "רונית אמיתית",
            "email": "real@example.com",
            "password": PASSWORD,
            "birth_year": str(year - 38),
        },
    )

    user = User.objects.get(email="real@example.com")
    leader = Leader.objects.filter(user=user).first()
    assert leader is not None, "the invitation was lost by registering"
    assert not leader.is_approved, "registering must not approve anyone"
    assert leader.program_manager == invite.program_manager, "landed in the wrong world"


def test_the_real_name_arrives_with_the_account(client, db):
    """T-F-M.14.4-8: REQ-M.91.

    Avi was explicit: she may get the label wrong, and that is fine, because the
    person sets their own name when they register. So the label must not be
    copied onto them.
    """
    invite = make_invite(make_manager(), label="רונית מעתיד רמלה")
    client.get(reverse("matazim:invite_landing", args=[invite.token]))

    year = timezone.now().year
    client.post(
        reverse("matazim:register"),
        {
            "name": "רונית כהן אלגרבלי",
            "email": "real@example.com",
            "password": PASSWORD,
            "birth_year": str(year - 38),
        },
    )
    user = User.objects.get(email="real@example.com")
    assert user.profile.display_name == "רונית כהן אלגרבלי"


# ------------------------------------------------------- the standing door


def test_the_manager_has_a_standing_menu_entry(client, db):
    """T-F-M.14.1-1: REQ-M.89.

    Not buried one click inside ניהול. It is the thing her role exists to do.
    """
    manager = make_manager()
    client.force_login(manager)

    html = client.get(reverse("matazim:home")).content.decode()
    assert reverse("matazim:pm_leaders") in html


def test_nobody_else_sees_that_entry(client, db):
    """T-F-M.14.1-2: REQ-M.89."""
    client.force_login(make_user("kid@example.com"))
    html = client.get(reverse("matazim:home")).content.decode()
    assert reverse("matazim:pm_leaders") not in html


def test_the_screen_refuses_everyone_else(client, db):
    """T-F-M.14.1-3: a hidden entry is not access control."""
    client.force_login(make_user("kid@example.com"))
    assert client.get(reverse("matazim:pm_leaders")).status_code in (302, 403)
