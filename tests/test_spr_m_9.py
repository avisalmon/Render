"""SPR-M.9 — Close the holes, then say what we do.

These tests are written as an attacker and as a fourteen-year-old, because those
are the two people the sprint is for.

The attacker tests are the unusual ones here. Most of this suite checks that the
right person can do the right thing; these check that the *wrong* person cannot,
from outside, with nothing but a guessed integer. Both holes they cover were
real on 2026-09-11 and are recorded as findings P1 and P2 in spec §4.10.

Traces: REQ-M.79, M.80, M.81, M.82, M.83.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm9

PASSWORD = "sprm9-pass-7731"


def make_user(email, name=""):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name or email})
    return user


def make_leader(email="noa@example.com", name="נעה מורה"):
    from matazim.models import Leader

    return Leader.objects.create(user=make_user(email, name))


def make_admin(email="chief@example.com"):
    from matazim.models import MemberProfile

    user = make_user(email, "אבי")
    MemberProfile.objects.update_or_create(user=user, defaults={"is_program_manager": True})
    return user


def make_member(email="kid@example.com", name="יובל"):
    from matazim.models import MemberProfile

    user = make_user(email, name)
    profile, _ = MemberProfile.objects.update_or_create(
        user=user, defaults={"entrance_test_passed_at": timezone.now()}
    )
    return user, profile


# ------------------------------------------ F-M.9.1: the invite link is not public


def test_a_stranger_cannot_fetch_a_leaders_qr(client, db):
    """T-F-M.9.1-1: REQ-M.79, finding P1. The sharpest hole in the product.

    The id is a sequential integer, so an open endpoint here is not a leak, it is
    a harvest: a join code attaches its holder to that leader with no
    confirmation (REQ-M.9), which makes it an unauthenticated write to somebody
    else's roster.
    """
    leader = make_leader()
    response = client.get(reverse("matazim:leader_qr", args=[leader.pk]))
    assert response.status_code in (302, 403, 404)
    assert response.get("Content-Type") != "image/png"


def test_another_leader_cannot_fetch_your_qr(client, db):
    """T-F-M.9.1-2: REQ-M.79. Signed in is not the same as entitled."""
    mine = make_leader("mine@example.com")
    theirs = make_leader("theirs@example.com")

    client.force_login(mine.user)
    response = client.get(reverse("matazim:leader_qr", args=[theirs.pk]))
    assert response.status_code in (302, 403, 404)


def test_a_member_cannot_fetch_a_leaders_qr(client, db):
    """T-F-M.9.1-3: REQ-M.79. A student holding a code could invite others in."""
    leader = make_leader()
    user, _ = make_member()

    client.force_login(user)
    response = client.get(reverse("matazim:leader_qr", args=[leader.pk]))
    assert response.status_code in (302, 403, 404)


def test_a_leader_still_gets_their_own_qr(client, db):
    """T-F-M.9.1-4: REQ-M.79. The fix must not break the feature.

    It gets printed and stuck on a classroom wall, so it has to stay an image.
    """
    leader = make_leader()
    client.force_login(leader.user)

    response = client.get(reverse("matazim:leader_qr", args=[leader.pk]))
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_an_admin_gets_any_leaders_qr(client, db):
    """T-F-M.9.1-5: REQ-M.79. The staff screen prints these for people."""
    leader = make_leader()
    client.force_login(make_admin())

    response = client.get(reverse("matazim:leader_qr", args=[leader.pk]))
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"


# ------------------------------- F-M.9.2: a minor's work is not served publicly


def _attempt_with_file(profile, name="יובל כהן מודל.stl", body=b"solid x\nendsolid x\n"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from matazim.models import EntranceAttempt

    attempt = EntranceAttempt.objects.create(member=profile, target_id="T-001", number=1)
    attempt.model_file = SimpleUploadedFile(name, body)
    attempt.save()
    return attempt


def test_an_upload_is_not_stored_under_the_name_the_teenager_chose(db):
    """T-F-M.9.2-1: REQ-M.80, finding P2.

    School work is named after the pupil roughly always. A path built from the
    filename is therefore a minor's name in a URL, and a guessable one.
    """
    _user, profile = make_member()
    attempt = _attempt_with_file(profile)

    stored = attempt.model_file.name
    assert "יובל" not in stored, f"the pupil's name is in the path: {stored}"
    assert "כהן" not in stored


def test_an_upload_does_not_live_in_the_public_media_directory(db):
    """T-F-M.9.2-2: REQ-M.80, finding P2.

    `/media/` is served with no authentication at all, which settings.py says out
    loud. Anything under `MEDIA_ROOT` is public by construction, so the fix is
    not a better filename, it is a different directory.
    """
    from pathlib import Path

    from django.conf import settings

    _user, profile = make_member()
    attempt = _attempt_with_file(profile)

    stored = Path(attempt.model_file.path).resolve()
    media = Path(settings.MEDIA_ROOT).resolve()
    assert media not in stored.parents, f"a minor's upload is under public MEDIA_ROOT: {stored}"


def test_a_stranger_cannot_fetch_a_minors_upload(client, db):
    """T-F-M.9.2-3: REQ-M.80."""
    _user, profile = make_member()
    attempt = _attempt_with_file(profile)

    response = client.get(reverse("matazim:attempt_file", args=[attempt.pk]))
    assert response.status_code in (302, 403, 404)


def test_a_member_can_fetch_their_own_upload(client, db):
    """T-F-M.9.2-4: REQ-M.80. It is their work; they may have it back."""
    user, profile = make_member()
    attempt = _attempt_with_file(profile)

    client.force_login(user)
    response = client.get(reverse("matazim:attempt_file", args=[attempt.pk]))
    assert response.status_code == 200


def test_a_leader_can_fetch_their_own_students_upload(client, db):
    """T-F-M.9.2-5: REQ-M.80, REQ-M.17.

    A leader reviews the attempt, so a leader has to be able to open it.
    """
    from matazim.models import Student

    leader = make_leader()
    user, profile = make_member()
    Student.objects.create(user=user, leader=leader)
    attempt = _attempt_with_file(profile)

    client.force_login(leader.user)
    assert client.get(reverse("matazim:attempt_file", args=[attempt.pk])).status_code == 200


def test_a_leader_cannot_fetch_someone_elses_students_upload(client, db):
    """T-F-M.9.2-6: REQ-M.80, REQ-M.22 on a file this time."""
    from matazim.models import Student

    mine = make_leader("mine@example.com")
    theirs = make_leader("theirs@example.com")
    user, profile = make_member()
    Student.objects.create(user=user, leader=theirs)
    attempt = _attempt_with_file(profile)

    client.force_login(mine.user)
    response = client.get(reverse("matazim:attempt_file", args=[attempt.pk]))
    assert response.status_code in (302, 403, 404)


# ------------------------------------------- F-M.9.3: מט״צים carries its own terms


def test_the_privacy_policy_exists_inside_the_walls(client, db):
    """T-F-M.9.3-1: REQ-M.81, finding P3."""
    response = client.get(reverse("matazim:privacy"))
    assert response.status_code == 200
    assert "מט״צים" in response.content.decode()


def test_the_terms_exist_inside_the_walls(client, db):
    """T-F-M.9.3-2: REQ-M.81."""
    assert client.get(reverse("matazim:terms")).status_code == 200


def test_the_legal_pages_do_not_break_rule_1(client, db):
    """T-F-M.9.3-3: REQ-M.81, RULE-1 and its one exception.

    The temptation on a legal page is to link to the parent site's policy, which
    is exactly what RULE-1 forbids and the reason these pages exist at all.

    But RULE-1 had to give way an inch here, and the shape of the inch matters.
    A privacy policy must name who actually holds the data and give a contact
    that works. So the rule keeps its grip on **navigation** (a member still
    cannot click their way out of /matazim/) and yields on **disclosure** (the
    policy may say whose inbox that is). This asserts the distinction rather
    than grepping for a word, because grepping for a word is what would quietly
    push someone into inventing a dead contact address instead.
    """
    import re

    for name in ("matazim:privacy", "matazim:terms"):
        html = client.get(reverse(name)).content.decode()
        for href in re.findall(r'href=["\']([^"\']+)', html):
            if href.startswith(("mailto:", "#", "https://")):
                # mailto is disclosure, not navigation. https is already
                # excepted by RULE-1 as written, and what is out there is
                # policed by test_no_third_party_script_has_crept_into_the_walls.
                continue
            assert href.startswith(
                ("/matazim/", "/static/")
            ), f"{name} navigates out of the walls: {href}"


def test_every_page_can_reach_the_policy(client, db):
    """T-F-M.9.3-4: REQ-M.81.

    A policy you have to know the URL for is a policy nobody reads, which is the
    same mistake as the target bank having no door.
    """
    for path in ("matazim:home", "matazim:register", "matazim:login"):
        html = client.get(reverse(path)).content.decode()
        assert reverse("matazim:privacy") in html, f"{path} cannot reach the policy"


def test_the_policy_says_a_leader_will_see_them(client, db):
    """T-F-M.9.3-5: REQ-M.81, REQ-M.82.

    The clause a teenager would actually want to know, and the one a generic
    policy always buries.
    """
    html = client.get(reverse("matazim:privacy")).content.decode()
    assert "מוביל" in html


# ------------------------------------------- F-M.9.4: told before they type


def test_registration_says_what_happens_to_the_data(client, db):
    """T-F-M.9.4-1: REQ-M.82, §11 חובת יידוע.

    The duty is owed at the point of collection, not on a page elsewhere. This
    is the screen where a fourteen-year-old types their email.
    """
    html = client.get(reverse("matazim:register")).content.decode()
    assert reverse("matazim:privacy") in html
    assert "מוביל" in html, "the registration screen must say a leader will see them"


# ------------------------------------------- F-M.9.5: cookies, disclosed


def test_the_policy_names_the_cookies_we_set(client, db):
    """T-F-M.9.5-1: REQ-M.83."""
    html = client.get(reverse("matazim:privacy")).content.decode()
    assert "עוגי" in html
    assert "sessionid" in html and "csrftoken" in html


def test_there_is_no_consent_banner_because_there_is_nothing_to_consent_to(client, db):
    """T-F-M.9.5-2: REQ-M.83.

    Deliberate, not an omission. Both cookies are strictly necessary, so they are
    disclosed rather than negotiated, and a banner asking permission for cookies
    we set regardless is consent theatre on a teenager's phone.

    This test exists to make the omission a decision somebody has to argue with,
    rather than something that quietly gets "fixed".
    """
    html = client.get(reverse("matazim:home")).content.decode()
    assert "cookie-banner" not in html


def test_no_third_party_script_has_crept_into_the_walls(client, db):
    """T-F-M.9.5-3: REQ-M.83, and the real guard in this sprint.

    The no-banner judgement holds only while nothing here is set for our benefit
    rather than the member's. The day an analytics tag ships, consent is owed
    before it does, and this is what makes that day announce itself.
    """
    import re

    hosts = (
        "plausible",
        "googletagmanager",
        "google-analytics",
        "gtag",
        "facebook",
        "hotjar",
        "segment",
        "mixpanel",
        "clarity.ms",
    )

    for path in (
        "matazim:home",
        "matazim:register",
        "matazim:login",
        "matazim:privacy",
        "matazim:terms",
        "matazim:entrance_test",
    ):
        html = client.get(reverse(path)).content.decode()
        for src in re.findall(r'<script[^>]+src=["\']([^"\']+)', html):
            assert src.startswith("/"), f"{path} loads a third-party script: {src}"
        for host in hosts:
            assert host not in html.lower(), f"{path} mentions {host}"


def test_nothing_in_the_walls_phones_a_third_party_at_all(client, db):
    """T-F-M.9.5-4: REQ-M.83, and the wider version of the script guard.

    A script tag is the obvious way to leak a visitor. A stylesheet is the quiet
    one: the Google Fonts <link> that used to sit in base.html sent every
    visitor's IP to Google on every page load, before they had agreed to
    anything, on a site whose visitors are fourteen. It also made the privacy
    policy's "no third parties here" not quite true.

    So this checks every fetching tag, not just scripts. Rubik is served from
    our own disk now, and the only correct number of external origins in this
    product is zero.
    """
    import re

    pages = (
        "matazim:home",
        "matazim:register",
        "matazim:login",
        "matazim:privacy",
        "matazim:terms",
        "matazim:entrance_test",
        "matazim:about",
    )
    pattern = re.compile(r'<(?:link|script|img|iframe)[^>]+(?:href|src)=["\']([^"\']+)', re.I)

    for path in pages:
        html = client.get(reverse(path)).content.decode()
        for url in pattern.findall(html):
            assert not url.startswith(
                ("http://", "https://", "//")
            ), f"{path} fetches from a third party: {url}"


def test_the_migration_rescues_files_that_are_already_public(db, settings):
    """T-F-M.9.2-7: REQ-M.80, and the half of the fix that actually matters.

    Changing where new uploads go protects nobody who already uploaded. Every
    entrance-test model submitted before today is sitting in
    `MEDIA_ROOT/matazim_entrance/` under the name the teenager's own file had,
    and `/media/` is served with no authentication.

    So this reconstructs that exact pre-fix state and runs the mover over it.
    """
    import importlib
    from pathlib import Path

    from django.apps import apps as real_apps

    from matazim.models import EntranceAttempt

    _user, profile = make_member()
    attempt = EntranceAttempt.objects.create(member=profile, target_id="T-1", number=1)

    old_rel = "matazim_entrance/יובל כהן מודל.stl"
    old_abs = Path(settings.MEDIA_ROOT) / old_rel
    old_abs.parent.mkdir(parents=True, exist_ok=True)
    old_abs.write_bytes(b"solid x\nendsolid x\n")
    EntranceAttempt.objects.filter(pk=attempt.pk).update(model_file=old_rel)

    mover = importlib.import_module("matazim.migrations.0007_move_uploads_out_of_public_media")
    mover.move_files(real_apps, None)

    attempt.refresh_from_db()
    assert attempt.model_file.name.startswith("entrance/")
    assert "יובל" not in attempt.model_file.name, "the pupil's name survived the move"
    assert not old_abs.exists(), "the publicly served copy is still there"
    assert attempt.model_file.read() == b"solid x\nendsolid x\n", "the work itself was lost"


def test_deleting_the_account_takes_the_uploaded_file_with_it(db):
    """T-F-M.9.2-8: REQ-M.80, REQ-M.85.

    Avi, mid-sprint: use babook's infrastructure. Correct, and babook already
    has self-service deletion (`app.views.delete_account`), whose `User.delete()`
    cascades cleanly through `MemberProfile`, `Student` and `EntranceAttempt`.
    So מט״צים needs no deletion path of its own.

    What reuse does not do on its own is delete files: Django stopped doing that
    in 1.3. Without the signal this covers, a teenager who asked to be deleted
    would have every row removed and their uploaded model left on the disk,
    which is the one piece of it unmistakably theirs.
    """
    from pathlib import Path

    user, profile = make_member()
    attempt = _attempt_with_file(profile)
    on_disk = Path(attempt.model_file.path)
    assert on_disk.is_file()

    user.delete()  # exactly what babook's delete_account does

    assert not on_disk.exists(), "the account is gone but their work is still on the disk"
