"""SPR-M.10 — Consent, rights, and an end date.

Policy becoming machinery. §4.10 findings P4 and P5.

The hard part here is not the consent form, it is what a consent gate does to
people who are already inside. Retrofitting one in front of everybody locks out
the teenager who is halfway through the entrance test, having done nothing
wrong. So the gate sits in front of **joining a leader**, which is the moment
their data starts being shown to another person, and nowhere earlier. Several
tests below exist only to hold that line.

Traces: REQ-M.84, M.85, M.86.
"""

import json

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm10

PASSWORD = "sprm10-pass-2284"
THIS_YEAR = timezone.now().year


def make_user(email, name=""):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name or email})
    return user


def make_member(email="kid@example.com", name="יובל", born=None, passed=True, consent=False):
    from matazim.models import MemberProfile

    user = make_user(email, name)
    fields = {"entrance_test_passed_at": timezone.now() if passed else None}
    if born is not None:
        fields["birth_year"] = born
    if consent:
        fields.update(
            guardian_name="רונית כהן",
            guardian_email="parent@example.com",
            guardian_consent_at=timezone.now(),
        )
    profile, _ = MemberProfile.objects.update_or_create(user=user, defaults=fields)
    return user, profile


def make_leader(email="noa@example.com", name="נעה מורה"):
    from matazim.models import Leader

    return Leader.objects.create(user=make_user(email, name))


def make_admin(email="chief@example.com"):
    from matazim.models import MemberProfile

    user = make_user(email, "אבי")
    MemberProfile.objects.update_or_create(user=user, defaults={"is_program_manager": True})
    return user


# --------------------------------------------- F-M.10.1: who needs a parent


def test_a_fourteen_year_old_needs_a_parent(db):
    """T-F-M.10.1-1: REQ-M.84. The ordinary case: ninth-graders are fourteen."""
    from matazim.consent import needs_guardian_consent

    _user, profile = make_member(born=THIS_YEAR - 14)
    assert needs_guardian_consent(profile)


def test_an_adult_does_not(db):
    """T-F-M.10.1-2: REQ-M.84. Leaders and staff hold accounts here too."""
    from matazim.consent import needs_guardian_consent

    _user, profile = make_member(born=THIS_YEAR - 34)
    assert not needs_guardian_consent(profile)


def test_recorded_consent_settles_it(db):
    """T-F-M.10.1-3: REQ-M.84."""
    from matazim.consent import needs_guardian_consent

    _user, profile = make_member(born=THIS_YEAR - 14, consent=True)
    assert not needs_guardian_consent(profile)


def test_an_unknown_age_is_not_treated_as_an_adult(db):
    """T-F-M.10.1-4: REQ-M.84, and the one that decides whether this is safe.

    Everyone registered before today has no birth year. Reading a blank as
    "adult" would mean the entire existing population silently skips the gate,
    which is the failure mode nobody would notice. A blank means we have to ask.
    """
    from matazim.consent import needs_guardian_consent

    _user, profile = make_member(born=None)
    assert needs_guardian_consent(profile)


def test_registration_records_the_year_and_the_parent(client, db):
    """T-F-M.10.1-5: REQ-M.84."""
    from matazim.models import MemberProfile

    client.post(
        reverse("matazim:register"),
        {
            "name": "יובל כהן",
            "email": "new@example.com",
            "password": PASSWORD,
            "birth_year": str(THIS_YEAR - 14),
            "guardian_name": "רונית כהן",
            "guardian_email": "parent@example.com",
            "guardian_consent": "on",
        },
    )
    profile = MemberProfile.objects.get(user__email="new@example.com")
    assert profile.birth_year == THIS_YEAR - 14
    assert profile.guardian_consent_at is not None
    assert profile.guardian_email == "parent@example.com"


# ------------------------------------- F-M.10.1: the gate, and where it is not


def test_without_consent_you_cannot_join_a_leader(client, db):
    """T-F-M.10.1-6: REQ-M.84. The moment their data starts being shown to
    somebody else is the moment consent is owed."""
    from matazim.models import Student

    leader = make_leader()
    user, _profile = make_member(born=THIS_YEAR - 14)
    client.force_login(user)

    client.post(reverse("matazim:join", args=[leader.join_code]), {"action": "join"})
    assert not Student.objects.filter(user=user, leader=leader).exists()


def test_without_consent_you_cannot_apply_to_a_leader_either(client, db):
    """T-F-M.10.1-7: REQ-M.84. Both doors, or neither."""
    from matazim.models import Student

    leader = make_leader()
    user, _profile = make_member(born=THIS_YEAR - 14)
    client.force_login(user)

    client.post(
        reverse("matazim:apply"),
        {"grade": "ט1", "motivation": "כי כן", "built_before": "כלום", "leader": leader.pk},
    )
    assert not Student.objects.filter(user=user).exists()


def test_with_consent_joining_works_normally(client, db):
    """T-F-M.10.1-8: REQ-M.84. The gate must open, not merely close."""
    from matazim.models import Student

    leader = make_leader()
    user, _profile = make_member(born=THIS_YEAR - 14, consent=True)
    client.force_login(user)

    client.post(reverse("matazim:join", args=[leader.join_code]), {"action": "join"})
    assert Student.objects.filter(user=user, leader=leader).exists()


def test_the_gate_does_not_lock_anyone_out_of_their_account(client, db):
    """T-F-M.10.1-9: REQ-M.84, and the retrofit decision.

    Everybody already registered has no birth year and therefore no consent. If
    the gate sat on the account, every one of them would be locked out of work
    they have already done, for a rule that arrived after they started. It sits
    on joining a leader instead.
    """
    user, _profile = make_member(born=None)
    client.force_login(user)

    for page in ("matazim:home", "matazim:profile", "matazim:entrance_test"):
        assert client.get(reverse(page)).status_code == 200


def test_the_gate_does_not_block_the_entrance_test(client, db):
    """T-F-M.10.1-10: REQ-M.84.

    The test is done alone and shown to nobody until they join someone. Blocking
    it would punish a teenager for a form their parent has not filled in yet.
    """
    user, _profile = make_member(born=THIS_YEAR - 14, passed=False)
    client.force_login(user)
    assert client.get(reverse("matazim:test_lessons")).status_code == 200


def test_a_member_is_told_what_is_missing_rather_than_just_refused(client, db):
    """T-F-M.10.1-11: REQ-M.84, the same principle as REQ-M.77.

    A blocked teenager who cannot see why will assume the site is broken.
    """
    user, _profile = make_member(born=THIS_YEAR - 14)
    client.force_login(user)

    html = client.get(reverse("matazim:profile")).content.decode()
    assert "הורה" in html or "אפוטרופוס" in html


# ------------------------------ F-M.10.2: a school's consent, recorded not assumed


def test_an_admin_records_consent_collected_on_paper(client, db):
    """T-F-M.10.2-1: REQ-M.84.

    Schools collect consent on paper. Assuming they did is how nobody has it;
    recording who said so and when is the difference.
    """
    from matazim.models import MemberProfile

    user, profile = make_member(born=THIS_YEAR - 14)
    boss = make_admin()
    client.force_login(boss)

    client.post(
        reverse("matazim:staff_consent", args=[profile.pk]),
        {"action": "record", "guardian_name": "בית ספר עתיד רמלה"},
    )
    profile.refresh_from_db()
    assert profile.guardian_consent_at is not None
    assert profile.guardian_consent_recorded_by == boss
    assert MemberProfile.objects.get(pk=profile.pk).guardian_name


def test_only_an_admin_can_record_consent(client, db):
    """T-F-M.10.2-2: REQ-M.84. A leader vouching for a parent is not consent."""
    _user, profile = make_member(born=THIS_YEAR - 14)
    leader = make_leader()
    client.force_login(leader.user)

    response = client.post(
        reverse("matazim:staff_consent", args=[profile.pk]), {"action": "record"}
    )
    profile.refresh_from_db()
    assert profile.guardian_consent_at is None
    assert response.status_code in (302, 403, 404)


# --------------------------------------- F-M.10.3, F-M.10.4: see it, take it, delete it


def test_a_member_sees_everything_held_about_them(client, db):
    """T-F-M.10.3-1: REQ-M.85."""
    user, _profile = make_member(born=THIS_YEAR - 14)
    client.force_login(user)

    html = client.get(reverse("matazim:my_data")).content.decode()
    assert user.email in html


def test_the_export_is_a_file_of_their_own_data(client, db):
    """T-F-M.10.4-1: REQ-M.85. A right to a copy means a copy they can keep."""
    user, _profile = make_member(born=THIS_YEAR - 14)
    client.force_login(user)

    response = client.get(reverse("matazim:my_data_export"))
    assert response.status_code == 200
    payload = json.loads(response.content.decode())
    assert payload["account"]["email"] == user.email
    assert "entrance_attempts" in payload


def test_the_export_is_only_ever_your_own(client, db):
    """T-F-M.10.4-2: REQ-M.85. An export endpoint is a lovely thing to walk."""
    user_a, _ = make_member("a@example.com", "א")
    _user_b, _ = make_member("b@example.com", "ב")

    client.force_login(user_a)
    payload = json.loads(client.get(reverse("matazim:my_data_export")).content.decode())
    assert payload["account"]["email"] == "a@example.com"
    assert "b@example.com" not in json.dumps(payload, ensure_ascii=False)


def test_deleting_yourself_needs_your_email_typed(client, db):
    """T-F-M.10.4-3: REQ-M.85, reusing babook's confirm-by-typing pattern.

    Irreversible, so a stray double-tap must not do it.
    """
    user, _profile = make_member()
    client.force_login(user)

    client.post(reverse("matazim:delete_me"), {"confirm_email": "wrong@example.com"})
    assert User.objects.filter(pk=user.pk).exists()


def test_deleting_yourself_removes_everything(client, db):
    """T-F-M.10.4-4: REQ-M.85.

    Reuses the mechanism babook's `delete_account` relies on rather than a
    second deletion path: `User.delete()` cascades into every מט״צים table, and
    the post_delete receiver from SPR-M.9 takes the uploaded file with it.
    """
    from matazim.models import MemberProfile, Student

    leader = make_leader()
    user, _profile = make_member()
    Student.objects.create(user=user, leader=leader)

    client.force_login(user)
    client.post(reverse("matazim:delete_me"), {"confirm_email": user.email})

    assert not User.objects.filter(pk=user.pk).exists()
    assert not MemberProfile.objects.filter(user_id=user.pk).exists()
    assert not Student.objects.filter(user_id=user.pk).exists()


def test_my_data_is_reachable_from_the_profile(client, db):
    """T-F-M.10.3-2: REQ-M.85. A right nobody can find is not a right."""
    user, _profile = make_member()
    client.force_login(user)

    html = client.get(reverse("matazim:profile")).content.decode()
    assert reverse("matazim:my_data") in html


# ------------------------------------------------ F-M.10.5: nothing kept forever


def test_a_failed_attempt_is_purged_after_its_period(db):
    """T-F-M.10.5-1: REQ-M.86.

    A failed audition, not a record worth keeping for years. This is the
    shortest-lived thing in the product on purpose.
    """
    from datetime import timedelta

    from matazim.models import EntranceAttempt
    from matazim.retention import purge_failed_attempts

    _user, profile = make_member()
    old = EntranceAttempt.objects.create(
        member=profile, target_id="T-1", number=1, passed=False, submitted_at=timezone.now()
    )
    EntranceAttempt.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - timedelta(days=400)
    )

    removed = purge_failed_attempts(apply=True)
    assert removed == 1
    assert not EntranceAttempt.objects.filter(pk=old.pk).exists()


def test_a_passing_attempt_is_never_purged(db):
    """T-F-M.10.5-2: REQ-M.86.

    The attempt that passed is the evidence behind a certification. Retention is
    about not hoarding, never about destroying the thing the programme rests on.
    """
    from datetime import timedelta

    from matazim.models import EntranceAttempt
    from matazim.retention import purge_failed_attempts

    _user, profile = make_member()
    kept = EntranceAttempt.objects.create(
        member=profile, target_id="T-1", number=1, passed=True, submitted_at=timezone.now()
    )
    EntranceAttempt.objects.filter(pk=kept.pk).update(
        created_at=timezone.now() - timedelta(days=4000)
    )

    purge_failed_attempts(apply=True)
    assert EntranceAttempt.objects.filter(pk=kept.pk).exists()


def test_a_recent_failure_is_left_alone(db):
    """T-F-M.10.5-3: REQ-M.86. Retries are unlimited (REQ-M.53), so a recent
    miss is live data, not litter."""
    from matazim.models import EntranceAttempt
    from matazim.retention import purge_failed_attempts

    _user, profile = make_member()
    recent = EntranceAttempt.objects.create(
        member=profile, target_id="T-1", number=1, passed=False, submitted_at=timezone.now()
    )
    purge_failed_attempts(apply=True)
    assert EntranceAttempt.objects.filter(pk=recent.pk).exists()


def test_the_purge_reports_before_it_deletes(db):
    """T-F-M.10.5-4: REQ-M.86, following babook's purge_* pattern.

    Report-only by default is what makes a destructive command safe to run when
    you are not sure.
    """
    from datetime import timedelta

    from matazim.models import EntranceAttempt
    from matazim.retention import purge_failed_attempts

    _user, profile = make_member()
    old = EntranceAttempt.objects.create(
        member=profile, target_id="T-1", number=1, passed=False, submitted_at=timezone.now()
    )
    EntranceAttempt.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - timedelta(days=400)
    )

    would = purge_failed_attempts(apply=False)
    assert would == 1
    assert EntranceAttempt.objects.filter(pk=old.pk).exists(), "a dry run deleted something"


def test_the_purge_takes_the_file_with_the_row(db):
    """T-F-M.10.5-5: REQ-M.86, REQ-M.80.

    Purging rows and leaving files is a slow leak of exactly the data this is
    meant to stop holding.
    """
    from datetime import timedelta
    from pathlib import Path

    from django.core.files.uploadedfile import SimpleUploadedFile

    from matazim.models import EntranceAttempt
    from matazim.retention import purge_failed_attempts

    _user, profile = make_member()
    old = EntranceAttempt.objects.create(
        member=profile, target_id="T-1", number=1, passed=False, submitted_at=timezone.now()
    )
    old.model_file = SimpleUploadedFile("mine.stl", b"solid x\nendsolid x\n")
    old.save()
    on_disk = Path(old.model_file.path)
    EntranceAttempt.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - timedelta(days=400)
    )

    purge_failed_attempts(apply=True)
    assert not on_disk.exists(), "the row went but the file stayed"


def test_the_policy_states_the_retention_period(client, db):
    """T-F-M.10.5-6: REQ-M.86.

    A period nobody can read is not a policy, it is a setting.
    """
    from matazim.retention import FAILED_ATTEMPT_DAYS

    html = client.get(reverse("matazim:privacy")).content.decode()
    assert str(FAILED_ATTEMPT_DAYS) in html
