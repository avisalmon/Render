"""SPR-M.33 — four things Avi found by using the site.

REQ-M.135 to REQ-M.138. Not a feature sprint: four corrections, each of which
came from him signing in and out of the live site rather than from a review.

The guardian-consent half lives in `tests/test_spr_m_10.py`, beside the gate it
switches off, because a test about a safeguard belongs next to the safeguard
and not in whichever sprint happened to touch it. The rest is here.

Traces: REQ-M.135, M.136, M.137, M.138, M.93, M.114.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm33

PASSWORD = "sprm33-pass-9930"


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _root(email="avi@example.com"):
    user = _user(email, "אבי")
    user.is_superuser = True
    user.is_staff = True
    user.save(update_fields=["is_superuser", "is_staff"])
    return user


# ----------------------------------- REQ-M.136: whoever is signed in is named


def test_the_header_names_whoever_is_signed_in(client, db):
    """T-F-M.33.2-1: REQ-M.136.

    Avi, 2026-09-14: "when a user is connected marked at the top [name]."

    "האזור האישי" is true of everybody and so tells the reader nothing about
    which account they are in, which matters most for the people who hold more
    than one.
    """
    user = _user("noa@example.com", "נעה מורה")
    client.force_login(user)

    html = client.get(reverse("matazim:home")).content.decode()
    assert "נעה מורה" in html, "the signed-in person is not named in the header"


def test_a_person_with_no_name_still_gets_a_labelled_door(client, db):
    """T-F-M.33.2-2: REQ-M.136.

    The fallback is not decoration. Without it somebody whose profile carries
    no display name gets a button with nothing written on it, which is worse
    than the generic label this replaced.
    """
    from app.models import UserProfile

    user = User.objects.create_user(
        username="blank@example.com", email="blank@example.com", password=PASSWORD
    )
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": ""})
    client.force_login(user)

    html = client.get(reverse("matazim:home")).content.decode()
    assert "האזור האישי" in html


def test_a_visitor_is_not_named_anything(client, db):
    """T-F-M.33.2-3: the header still offers a way in, not an empty name."""
    html = client.get(reverse("matazim:home")).content.decode()
    assert "התחברות" in html


# ------------------- REQ-M.137: granting the role is itself the approval


def test_making_a_pending_leader_a_program_manager_approves_them(client, db):
    """T-F-M.33.3-1: REQ-M.137.

    Avi, 2026-09-14: "If I assign a leader as a program manager, no need to
    wait for me to approve it. It's approved."

    The symptom was real and worse than untidy: `leader_of()` refuses an
    unapproved row, so somebody could hold the highest role in the product and
    at the same time be unable to reach their own students.
    """
    from matazim.access import candidate_of, leader_of
    from matazim.models import Leader

    root = _root()
    teacher = _user("noa@example.com", "נעה מורה")
    Leader.objects.create(user=teacher, institution=_inst(root), approved_at=None)

    assert candidate_of(teacher) is not None, "the fixture is not the state under test"

    client.force_login(root)
    client.post(
        reverse("matazim:staff_admins"), {"email": "noa@example.com", "action": "grant"}
    )

    assert leader_of(teacher) is not None, "a program manager was left waiting for approval"
    assert candidate_of(teacher) is None


def test_granting_the_role_does_not_invent_a_leader(client, db):
    """T-F-M.33.3-2: REQ-M.137, §4.9.

    A program manager is not a leader. Somebody who never taught a class must
    not acquire a teaching record as a side effect of being given a role.
    """
    from matazim.models import Leader

    root = _root()
    person = _user("dana@example.com", "דנה")

    client.force_login(root)
    client.post(
        reverse("matazim:staff_admins"), {"email": "dana@example.com", "action": "grant"}
    )

    assert not Leader.objects.filter(user=person).exists()


def test_an_already_approved_leader_keeps_their_original_approval(client, db):
    """T-F-M.33.3-3: REQ-M.93 — approval is an act by a person, with its date.

    Re-stamping it on an unrelated grant would rewrite the record of when
    somebody was actually let in.
    """
    from matazim.models import Leader

    root = _root()
    teacher = _user("noa@example.com", "נעה מורה")
    long_ago = timezone.now() - timezone.timedelta(days=200)
    leader = Leader.objects.create(
        user=teacher, institution=_inst(root), approved_at=long_ago
    )

    client.force_login(root)
    client.post(
        reverse("matazim:staff_admins"), {"email": "noa@example.com", "action": "grant"}
    )

    leader.refresh_from_db()
    assert leader.approved_at == long_ago, "an old approval date was overwritten"


def test_revoking_the_role_does_not_un_approve_the_leader(client, db):
    """T-F-M.33.3-4: REQ-M.137, deliberately not the mirror image.

    Cutting somebody off from students they are in the middle of teaching, over
    a decision that was about a different role, would be a surprise nobody
    asked for.
    """
    from matazim.access import is_program_manager, leader_of
    from matazim.models import Leader

    root = _root()
    teacher = _user("noa@example.com", "נעה מורה")
    Leader.objects.create(user=teacher, institution=_inst(root), approved_at=None)

    client.force_login(root)
    client.post(
        reverse("matazim:staff_admins"), {"email": "noa@example.com", "action": "grant"}
    )
    client.post(
        reverse("matazim:staff_admins"), {"email": "noa@example.com", "action": "revoke"}
    )

    assert not is_program_manager(teacher)
    assert leader_of(teacher) is not None, "revoking a role also cancelled a teaching approval"


def test_the_bootstrap_command_grants_the_same_way_the_screen_does(db):
    """T-F-M.33.3-5: REQ-M.137, REQ-M.68.

    `matazim_admins` is how the *first* program manager is made, and she is the
    likeliest of all of them to already be a pending leader. Two ways to grant
    one role must not come to mean two different things.
    """
    from django.core.management import call_command

    from matazim.access import leader_of
    from matazim.models import Leader

    root = _root()
    teacher = _user("noa@example.com", "נעה מורה")
    Leader.objects.create(user=teacher, institution=_inst(root), approved_at=None)

    call_command("matazim_admins", "--grant", "noa@example.com")

    assert leader_of(teacher) is not None


# ------------------- REQ-M.138 lives in test_spr_m_2.py, beside the notice


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
