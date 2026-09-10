"""SPR-M.2 — Who you are here.

Login, the profile, the first-time welcome, and the gate that holds the student
joining door shut until the entrance test is passed.

The shape of it, decided with Avi on 2026-09-10:

- The test gates כניסת תלמידים only. כניסת מובילים is not gated, because the
  test measures a teenager's commitment and a teacher confirming a roster has
  no reason to model a 3D object.
- התחברות in the header is never gated, or the gate locks out everyone who
  already passed and came back.
- מט״צים keeps its own flags in its own table and reads identity and training
  from the shared babook profile, so a person has one name and one history.

Traces: REQ-M.6, M.7, M.35 to M.44.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

pytestmark = pytest.mark.sprm2

PASSWORD = "sprm2-pass-9271"


def make_user(email="noa@example.com", name="נועה לוי"):
    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    from app.models import UserProfile

    # babook creates a blank UserProfile on a post_save signal (app/models.py),
    # so the row already exists by the time we get here. update_or_create, not
    # get_or_create, or the display name is silently dropped.
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def sign_in(client, email="noa@example.com"):
    user = make_user(email)
    client.force_login(user)
    return user


# ---------------------------------------------------------------- F-M.2.1


def test_member_profile_is_one_row_per_user(db):
    """T-F-M.2.1-1."""
    from matazim.models import MemberProfile

    user = make_user()
    profile, created = MemberProfile.objects.get_or_create(user=user)
    assert created
    assert profile.entered_via_matazim is False
    assert profile.welcome_accepted_at is None
    assert profile.entrance_test_passed_at is None

    again, created_again = MemberProfile.objects.get_or_create(user=user)
    assert not created_again and again.pk == profile.pk


def test_passing_the_test_is_read_through_a_method(db):
    """T-F-M.2.1-2.

    The column is provisional: it becomes derived from EntranceAttempt when the
    real test lands (REQ-M.17). Callers must go through the method so that swap
    is invisible to them.
    """
    from django.utils import timezone

    from matazim.models import MemberProfile

    profile = MemberProfile.objects.create(user=make_user())
    assert profile.has_passed_entrance_test() is False
    profile.entrance_test_passed_at = timezone.now()
    assert profile.has_passed_entrance_test() is True


# ---------------------------------------------------------------- F-M.2.2


def test_login_page_is_ours(client, db):
    """T-F-M.2.2-1."""
    html = client.get(reverse("matazim:login")).content.decode()
    assert "מט״צים" in html
    for marker in ("babook", "site-drawer", "nav-link px-2"):
        assert marker not in html


def test_correct_credentials_sign_in(client, db):
    """T-F-M.2.2-2."""
    make_user()
    resp = client.post(
        reverse("matazim:login"),
        {"email": "noa@example.com", "password": PASSWORD},
    )
    assert resp.status_code == 302
    assert resp.url.startswith("/matazim/")
    assert client.session.get("_auth_user_id")


def test_wrong_credentials_say_so(client, db):
    """T-F-M.2.2-3."""
    make_user()
    resp = client.post(
        reverse("matazim:login"),
        {"email": "noa@example.com", "password": "not-the-password"},
    )
    assert resp.status_code == 200
    assert not client.session.get("_auth_user_id")
    assert "שגוי" in resp.content.decode() or "לא נכון" in resp.content.decode()


def test_logout_returns_to_matazim(client, db):
    """T-F-M.2.2-4."""
    sign_in(client)
    resp = client.post(reverse("matazim:logout"))
    assert resp.status_code == 302
    assert resp.url.startswith("/matazim/")
    assert not client.session.get("_auth_user_id")


def test_an_account_made_on_babook_signs_in_here(client, db):
    """T-F-M.2.2-5: REQ-M.7. One identity, no linking step."""
    User.objects.create_user(
        username="veteran@example.com", email="veteran@example.com", password=PASSWORD
    )
    resp = client.post(
        reverse("matazim:login"),
        {"email": "veteran@example.com", "password": PASSWORD},
    )
    assert resp.status_code == 302
    assert client.session.get("_auth_user_id")


# ---------------------------------------------------------------- F-M.2.3


def test_register_page_is_ours(client, db):
    """T-F-M.2.3-1."""
    html = client.get(reverse("matazim:register")).content.decode()
    assert "מט״צים" in html
    assert "babook" not in html


def test_registering_stamps_entry_through_this_door(client, db):
    """T-F-M.2.3-2: REQ-M.35."""
    from matazim.models import MemberProfile

    resp = client.post(
        reverse("matazim:register"),
        {"name": "יובל כהן", "email": "yuval@example.com", "password": PASSWORD},
    )
    assert resp.status_code == 302
    user = User.objects.get(email="yuval@example.com")
    assert client.session.get("_auth_user_id") == str(user.pk)
    assert MemberProfile.objects.get(user=user).entered_via_matazim is True
    assert user.profile.display_name == "יובל כהן"


def test_an_email_already_in_use_is_refused(client, db):
    """T-F-M.2.3-3."""
    make_user("taken@example.com")
    resp = client.post(
        reverse("matazim:register"),
        {"name": "מישהו", "email": "taken@example.com", "password": PASSWORD},
    )
    assert resp.status_code == 200
    assert User.objects.filter(email="taken@example.com").count() == 1


# ---------------------------------------------------------------- F-M.2.4


def test_first_visit_shows_the_prototype_welcome(client, db):
    """T-F-M.2.4-1: REQ-M.39."""
    html = client.get(reverse("matazim:home")).content.decode()
    assert "mz-welcome" in html
    assert "אב טיפוס" in html
    assert "אינטל" in html


def test_a_visitor_can_dismiss_it_and_it_stays_dismissed(client, db):
    """T-F-M.2.4-2: nobody to attribute it to, but it must not nag."""
    client.post(reverse("matazim:welcome_accept"))
    html = client.get(reverse("matazim:home")).content.decode()
    assert "mz-welcome" not in html


def test_a_signed_in_acceptance_is_stored(client, db):
    """T-F-M.2.4-3: REQ-M.40. We can show who was told, and when."""
    from matazim.models import MemberProfile

    user = sign_in(client)
    client.post(reverse("matazim:welcome_accept"))
    assert MemberProfile.objects.get(user=user).welcome_accepted_at is not None


def test_someone_who_accepted_never_sees_it_again(client, db):
    """T-F-M.2.4-4."""
    from django.utils import timezone

    from matazim.models import MemberProfile

    user = sign_in(client)
    MemberProfile.objects.update_or_create(
        user=user, defaults={"welcome_accepted_at": timezone.now()}
    )
    html = client.get(reverse("matazim:home")).content.decode()
    assert "mz-welcome" not in html


def test_an_acknowledgement_made_before_signing_in_is_carried_over(client, db):
    """T-F-M.2.4-5: nobody should be told the same thing twice.

    Found by walking the flow rather than by a unit: dismiss the notice as a
    stranger, register, and it reappeared, because the new profile had no
    acceptance on it. The acceptance was real, so it moves onto the profile and
    REQ-M.40 keeps the timestamp it is meant to keep.
    """
    from matazim.models import MemberProfile

    client.post(reverse("matazim:welcome_accept"))
    client.post(
        reverse("matazim:register"),
        {"name": "רון", "email": "ron@example.com", "password": PASSWORD},
    )
    user = User.objects.get(email="ron@example.com")
    assert MemberProfile.objects.get(user=user).welcome_accepted_at is not None
    assert "mz-welcome" not in client.get(reverse("matazim:home")).content.decode()


# ---------------------------------------------------------------- F-M.2.9


def test_google_is_offered_without_leaving_the_prefix(client, db):
    """T-F-M.2.9-1: REQ-M.45, and RULE-1 is not bent to get it.

    For a 14-year-old a Google button is the difference between joining and
    giving up on a password field. But a direct link to the provider would be
    an href out of /matazim/, so the page links to our own handoff instead.
    """
    for page in ("matazim:login", "matazim:register"):
        html = client.get(reverse(page)).content.decode()
        assert "Google" in html
        assert reverse("matazim:google_start") in html
        assert "/accounts/" not in html


def test_the_handoff_names_a_return_address_inside_the_prefix(client, db):
    """T-F-M.2.9-2."""
    resp = client.get(reverse("matazim:google_start"))
    assert resp.status_code == 302
    assert resp.url.startswith("/accounts/google/login/")
    assert reverse("matazim:auth_done") in resp.url


def test_coming_back_stamps_entry_and_carries_the_welcome(client, db):
    """T-F-M.2.9-3: how someone got in must not change what we record."""
    from matazim.models import MemberProfile

    client.post(reverse("matazim:welcome_accept"))
    user = sign_in(client, "viagoogle@example.com")
    resp = client.get(reverse("matazim:auth_done"))
    assert resp.status_code == 302
    assert resp.url.startswith("/matazim/")

    profile = MemberProfile.objects.get(user=user)
    assert profile.entered_via_matazim is True
    assert profile.welcome_accepted_at is not None


def test_cancelling_at_google_returns_you_to_our_login(client, db):
    """T-F-M.2.9-4: an abandoned consent screen is not an error page."""
    resp = client.get(reverse("matazim:auth_done"))
    assert resp.status_code == 302
    assert resp.url.startswith(reverse("matazim:login"))


# ---------------------------------------------------------------- F-M.2.5


def test_profile_needs_a_login_and_sends_you_to_ours(client, db):
    """T-F-M.2.5-1: RULE-1 holds even on a redirect."""
    resp = client.get(reverse("matazim:profile"))
    assert resp.status_code == 302
    assert resp.url.startswith("/matazim/")


def test_the_name_is_the_shared_one(client, db):
    """T-F-M.2.5-2: REQ-M.42. One person, one name, edited from either side."""
    user = sign_in(client)
    html = client.get(reverse("matazim:profile")).content.decode()
    assert "נועה לוי" in html

    client.post(reverse("matazim:profile"), {"display_name": "נועה לוי-כהן"})
    user.profile.refresh_from_db()
    assert user.profile.display_name == "נועה לוי-כהן"


def test_program_standing_reads_as_not_yet_assigned(client, db):
    """T-F-M.2.5-3: REQ-M.43. Honest placeholder beats a hidden row."""
    sign_in(client)
    html = client.get(reverse("matazim:profile")).content.decode()
    assert "בית ספר" in html
    assert "טרם" in html


def test_every_training_anywhere_on_babook_is_listed(client, db):
    """T-F-M.2.5-4: REQ-M.44, read live and never copied."""
    from app.models import Course, Enrollment

    user = sign_in(client)
    done = Course.objects.create(slug="done-course", title="הדרכה שהושלמה")
    doing = Course.objects.create(slug="doing-course", title="הדרכה בתהליך")
    Enrollment.objects.create(user=user, course=done, completed_at="2026-01-01T00:00:00Z")
    Enrollment.objects.create(user=user, course=doing)

    html = client.get(reverse("matazim:profile")).content.decode()
    assert "הדרכה שהושלמה" in html
    assert "הדרכה בתהליך" in html


# ---------------------------------------------------------------- F-M.2.6


def test_the_replay_control_brings_the_welcome_back(client, db):
    """T-F-M.2.6-1: REQ-M.41, narrowed by REQ-M.64 on 2026-09-10.

    This originally replayed the welcome as an ordinary member. It is a testing
    tool rather than a feature, so it is staff only now, and the user here is
    staff for that reason and not by accident.
    """
    from django.utils import timezone

    from matazim.models import MemberProfile

    user = sign_in(client)
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    MemberProfile.objects.update_or_create(
        user=user, defaults={"welcome_accepted_at": timezone.now()}
    )
    client.post(reverse("matazim:profile_reset_welcome"))
    assert MemberProfile.objects.get(user=user).welcome_accepted_at is None
    assert "mz-welcome" in client.get(reverse("matazim:home")).content.decode()


# ---------------------------------------------------------------- F-M.2.7


def test_without_a_passed_test_the_student_door_is_shut(client, db):
    """T-F-M.2.7-1: REQ-M.36, and it says why rather than simply refusing."""
    html = client.get(reverse("matazim:home")).content.decode()
    assert "mz-door-locked" in html
    assert "מבחן הכניסה" in html


def test_the_leader_door_is_never_gated(client, db):
    """T-F-M.2.7-2: the test measures a teenager's commitment, not a teacher's."""
    html = client.get(reverse("matazim:home")).content.decode()
    leader = html.split("כניסת מובילים")[0][-400:]
    assert "mz-door-locked" not in leader


def test_the_header_login_is_never_gated(client, db):
    """T-F-M.2.7-3: without this the gate locks returning members out."""
    html = client.get(reverse("matazim:home")).content.decode()
    header = html.split("</header>")[0]
    assert reverse("matazim:login") in header
    assert "mz-door-locked" not in header


def test_passing_the_test_opens_the_student_door(client, db):
    """T-F-M.2.7-4."""
    from django.utils import timezone

    from matazim.models import MemberProfile

    user = sign_in(client)
    MemberProfile.objects.update_or_create(
        user=user, defaults={"entrance_test_passed_at": timezone.now()}
    )
    html = client.get(reverse("matazim:home")).content.decode()
    assert "mz-door-locked" not in html


# ---------------------------------------------------------------- F-M.2.8


def test_the_entrance_test_page_serves_without_an_account(client, db):
    """T-F-M.2.8-1: REQ-M.5d, the test is public."""
    resp = client.get(reverse("matazim:entrance_test"))
    assert resp.status_code == 200
    assert "מבחן הכניסה" in resp.content.decode()


def test_the_shut_door_points_at_the_test(client, db):
    """T-F-M.2.8-2: a lock with no way forward is a dead end."""
    html = client.get(reverse("matazim:home")).content.decode()
    assert reverse("matazim:entrance_test") in html
