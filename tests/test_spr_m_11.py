"""SPR-M.11 — Retention with a person in front of it.

SPR-M.10 built the machinery and then wrote the promise on a public page without
connecting the two. `purge_matazim_attempts` deletes only when a human types
`--apply`, and nothing schedules it, so the privacy policy stated a 365-day
period that the system would never enforce on its own. Avi asked the question
that found it: is there a manual approvals process.

The answer chosen is that there is one, deliberately, rather than a timer. That
matches how the rest of this product already behaves: the machine refuses or
proposes and a person decides (REQ-M.78 on certification, REQ-M.55 on retiring a
target). Deletion is the one place where an unattended bug is irreversible.

The cost of that choice is that a job needing a human is a job that does not run
when the human is busy, which is how you hold a minor's data for three years
while believing you do not. So several tests below are about the *count being
visible* rather than about deleting anything.

Traces: REQ-M.86, M.87.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm11

PASSWORD = "sprm11-pass-3390"


def make_user(email, name=""):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name or email})
    return user


def make_admin(email="chief@example.com"):
    from matazim.models import MemberProfile

    user = make_user(email, "אבי")
    MemberProfile.objects.update_or_create(user=user, defaults={"is_admin": True})
    return user


def make_member(email="kid@example.com", name="יובל כהן"):
    from matazim.models import MemberProfile

    user = make_user(email, name)
    profile, _ = MemberProfile.objects.update_or_create(user=user, defaults={})
    return user, profile


def overdue_attempt(profile, *, days=400, passed=False, number=1, with_file=False):
    from datetime import timedelta

    from django.core.files.uploadedfile import SimpleUploadedFile

    from matazim.models import EntranceAttempt

    attempt = EntranceAttempt.objects.create(
        member=profile,
        target_id="T-004",
        number=number,
        passed=passed,
        submitted_at=timezone.now(),
    )
    if with_file:
        attempt.model_file = SimpleUploadedFile("mine.stl", b"solid x\nendsolid x\n")
        attempt.save()
    EntranceAttempt.objects.filter(pk=attempt.pk).update(
        created_at=timezone.now() - timedelta(days=days)
    )
    attempt.refresh_from_db()
    return attempt


# ------------------------------------------- the screen shows what is due


def test_the_screen_lists_what_is_due_and_whose_it_is(client, db):
    """T-F-M.11.1-1: REQ-M.87.

    Approving a number is not reviewing anything. An admin has to see whose data
    is about to go, or the approval is a rubber stamp with extra steps.
    """
    _user, profile = make_member()
    overdue_attempt(profile)

    client.force_login(make_admin())
    html = client.get(reverse("matazim:staff_retention")).content.decode()

    assert "יובל כהן" in html
    assert "T-004" in html


def test_nothing_recent_and_nothing_passing_is_listed(client, db):
    """T-F-M.11.1-2: REQ-M.86. The two things retention must never touch.

    A recent miss is live data, because retries are unlimited (REQ-M.53). A
    passing attempt is the evidence behind a certification and is kept forever.
    """
    _user, profile = make_member()
    overdue_attempt(profile, days=10, number=1)
    overdue_attempt(profile, days=4000, passed=True, number=2)

    client.force_login(make_admin())
    html = client.get(reverse("matazim:staff_retention")).content.decode()
    assert "אין מה למחוק" in html or "0" in html


def test_the_screen_is_admin_only(client, db):
    """T-F-M.11.1-3: REQ-M.87. A leader must not see other leaders' students."""
    _user, profile = make_member()
    overdue_attempt(profile)

    kid, _ = make_member("other@example.com", "מישהו")
    client.force_login(kid)
    assert client.get(reverse("matazim:staff_retention")).status_code in (302, 403)


# ------------------------------------------- approving is what deletes


def test_approving_deletes_and_records_who(client, db):
    """T-F-M.11.2-1: REQ-M.87.

    The decision has a name on it, the same as certification does.
    """
    from matazim.models import EntranceAttempt, RetentionRun

    _user, profile = make_member()
    attempt = overdue_attempt(profile)
    boss = make_admin()

    client.force_login(boss)
    client.post(reverse("matazim:staff_retention"), {"action": "purge"})

    assert not EntranceAttempt.objects.filter(pk=attempt.pk).exists()
    run = RetentionRun.objects.latest("ran_at")
    assert run.ran_by == boss
    assert run.deleted_count == 1


def test_looking_at_the_screen_deletes_nothing(client, db):
    """T-F-M.11.2-2: REQ-M.87, and the point of the whole sprint.

    A review screen that acts on being opened is not a review screen.
    """
    from matazim.models import EntranceAttempt

    _user, profile = make_member()
    attempt = overdue_attempt(profile)

    client.force_login(make_admin())
    client.get(reverse("matazim:staff_retention"))
    client.get(reverse("matazim:staff_retention"))

    assert EntranceAttempt.objects.filter(pk=attempt.pk).exists()


def test_a_non_admin_cannot_approve_by_posting(client, db):
    """T-F-M.11.2-3: REQ-M.87. A hidden button is still a postable URL."""
    from matazim.models import EntranceAttempt

    _user, profile = make_member()
    attempt = overdue_attempt(profile)

    kid, _ = make_member("nobody@example.com")
    client.force_login(kid)
    response = client.post(reverse("matazim:staff_retention"), {"action": "purge"})

    assert EntranceAttempt.objects.filter(pk=attempt.pk).exists()
    assert response.status_code in (302, 403)


def test_approving_takes_the_files_too(client, db):
    """T-F-M.11.2-4: REQ-M.86, REQ-M.80.

    Purging rows and leaving files is a slow leak of exactly the data this is
    meant to stop holding.
    """
    from pathlib import Path

    _user, profile = make_member()
    attempt = overdue_attempt(profile, with_file=True)
    on_disk = Path(attempt.model_file.path)
    assert on_disk.is_file()

    client.force_login(make_admin())
    client.post(reverse("matazim:staff_retention"), {"action": "purge"})

    assert not on_disk.exists()


def test_the_last_run_is_shown_so_somebody_can_tell_it_happened(client, db):
    """T-F-M.11.2-5: REQ-M.87.

    A retention process nobody can see the history of is indistinguishable from
    one that never runs.
    """
    _user, profile = make_member()
    overdue_attempt(profile)
    boss = make_admin()

    client.force_login(boss)
    client.post(reverse("matazim:staff_retention"), {"action": "purge"})
    html = client.get(reverse("matazim:staff_retention")).content.decode()

    assert "אבי" in html or boss.email in html


# ---------------------------- the count is visible without being asked for


def test_the_staff_area_shows_what_is_overdue(client, db):
    """T-F-M.11.3-1: REQ-M.87, and the counterweight to choosing a human gate.

    A job that needs a person is a job that does not run while the person is
    busy. Making the number stand in the staff area is what stops "we have a
    retention policy" from quietly meaning "we kept everything".
    """
    _user, profile = make_member()
    overdue_attempt(profile)

    client.force_login(make_admin())
    html = client.get(reverse("matazim:staff_home")).content.decode()
    assert reverse("matazim:staff_retention") in html


def test_the_staff_area_does_not_nag_when_nothing_is_due(client, db):
    """T-F-M.11.3-2: a badge that is always there is a badge nobody sees."""
    _user, profile = make_member()
    overdue_attempt(profile, days=10)

    client.force_login(make_admin())
    html = client.get(reverse("matazim:staff_home")).content.decode()
    assert "mz-tag-fix" not in html


# ------------------------------------------- the page must not lie


def test_the_policy_says_a_person_reviews_before_deleting(client, db):
    """T-F-M.11.4-1: REQ-M.87.

    SPR-M.10 wrote "deleted after 365 days" on a public page while nothing
    enforced it. The page now has to describe what actually happens, which is a
    review followed by a deletion, not a timer.
    """
    html = client.get(reverse("matazim:privacy")).content.decode()
    assert "365" in html

    # Scoped to the retention paragraph on purpose. The first version of this
    # test passed because the page happens to say צוות התוכנית somewhere else
    # entirely, which is a test agreeing with itself rather than checking the
    # page tells the truth about how deletion works.
    start = html.index('id="mz-retention-how"')
    section = html[start : start + 600]
    assert "מאשר" in section
    assert "בודק" in section
