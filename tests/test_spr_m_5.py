"""SPR-M.5 — Small things that were wrong.

Three from Avi on 2026-09-10, all found by using the site rather than reading
it, which is the pattern worth noticing: none of these would have surfaced from
the spec alone.

- The target bank had no door. A screen you have to know the URL for is a screen
  nobody uses.
- Someone who passed the test was still being invited to take it, everywhere.
- The replay control, built as a testing tool, was offered to every member.

Traces: REQ-M.62 to M.64.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm5

PASSWORD = "sprm5-pass-8823"


def make_user(email="tal@example.com", staff=False):
    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    if staff:
        # "Staff" became מט״צים adminship in SPR-M.6: is_staff was a stand-in while
        # this app had no roles of its own. Granting the real thing, not the
        # stand-in, so the test exercises the rule that actually ships.
        from matazim.models import MemberProfile

        MemberProfile.objects.update_or_create(user=user, defaults={"is_admin": True})
    from app.models import UserProfile

    UserProfile.objects.update_or_create(user=user, defaults={"display_name": "טל"})
    return user


def sign_in(client, email="tal@example.com", staff=False, passed=False):
    from matazim.models import MemberProfile

    user = make_user(email, staff=staff)
    client.force_login(user)
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "welcome_accepted_at": timezone.now(),
            "entrance_test_passed_at": timezone.now() if passed else None,
        },
    )
    return user


# ---------------------------------------------------------------- F-M.5.1


def test_staff_see_a_door_to_the_bank(client, db):
    """T-F-M.5.1-1: REQ-M.62. A screen with no link is a screen nobody uses.

    Narrowed by REQ-M.69 in SPR-M.6: the nav now carries one ניהול door rather
    than an item per tool, so what this checks is that staff can *get* to the
    bank, which is the requirement. The bank is one click further in.
    """
    sign_in(client, "boss@example.com", staff=True)
    html = client.get(reverse("matazim:home")).content.decode()
    assert reverse("matazim:staff_home") in html

    staff_area = client.get(reverse("matazim:staff_home")).content.decode()
    assert reverse("matazim:staff_targets") in staff_area


def test_members_and_visitors_never_see_it(client, db):
    """T-F-M.5.1-2: it is a staff tool, not a section of the site."""
    anon = client.get(reverse("matazim:home")).content.decode()
    assert reverse("matazim:staff_home") not in anon

    sign_in(client, "member@example.com")
    member = client.get(reverse("matazim:home")).content.decode()
    assert reverse("matazim:staff_home") not in member


# ---------------------------------------------------------------- F-M.5.2


def test_a_passed_test_is_marked_in_the_nav(client, db):
    """T-F-M.5.2-1: REQ-M.63. Nobody should be invited twice to what they finished."""
    sign_in(client, "done@example.com", passed=True)
    html = client.get(reverse("matazim:home")).content.decode()
    nav = html.split('id="mzNav"')[1].split("</nav>")[0]
    assert "mz-nav-done" in nav


def test_someone_who_has_not_passed_is_not_marked(client, db):
    """T-F-M.5.2-2: the mark has to mean something."""
    sign_in(client, "notyet@example.com", passed=False)
    html = client.get(reverse("matazim:home")).content.decode()
    assert "mz-nav-done" not in html


@pytest.mark.parametrize(
    "name",
    ["matazim:home", "matazim:about", "matazim:courses", "matazim:track", "matazim:entrance_test"],
)
def test_no_page_still_invites_someone_who_passed(client, db, name):
    """T-F-M.5.2-3: every call to action on the front, not just the hero.

    Checked on the buttons rather than on the words: "איך מתחילים" is a heading
    on אודות and banning the word would have meant rewriting good prose to
    satisfy a test. What must not happen is a *button* asking someone who
    already passed to go and take the test.
    """
    sign_in(client, "done2@example.com", passed=True)
    html = client.get(reverse(name)).content.decode()
    body = html.split("<main>")[1].split("</main>")[0]
    for target in (reverse("matazim:entrance_test"), reverse("matazim:test_lessons")):
        assert (
            f'mz-btn-primary" href="{target}"' not in body
        ), f"{name} still offers the test to a member who passed"


def test_the_profile_shows_the_pass(client, db):
    """T-F-M.5.2-4: REQ-M.63, the profile half."""
    sign_in(client, "done3@example.com", passed=True)
    html = client.get(reverse("matazim:profile")).content.decode()
    assert "עבר" in html


# ---------------------------------------------------------------- F-M.5.3


def test_only_staff_are_offered_the_replay_control(client, db):
    """T-F-M.5.3-1: REQ-M.64. It is a testing tool, not a feature."""
    sign_in(client, "member2@example.com")
    assert (
        reverse("matazim:profile_reset_welcome")
        not in client.get(reverse("matazim:profile")).content.decode()
    )

    client.logout()
    sign_in(client, "boss2@example.com", staff=True)
    assert (
        reverse("matazim:profile_reset_welcome")
        in client.get(reverse("matazim:profile")).content.decode()
    )


def test_a_member_posting_to_it_directly_is_refused(client, db):
    """T-F-M.5.3-2: hiding a button is not access control.

    The button is gone from the page, but the URL is still a URL, so the
    endpoint has to say no on its own.
    """
    from matazim.models import MemberProfile

    user = sign_in(client, "sneaky@example.com")
    response = client.post(reverse("matazim:profile_reset_welcome"))
    assert response.status_code in (302, 403)
    # And the acknowledgement they gave is still on record.
    assert MemberProfile.objects.get(user=user).welcome_accepted_at is not None
