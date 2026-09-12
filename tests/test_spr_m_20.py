"""SPR-M.20 — The certificate.

REQ-M.20 and REQ-M.28. The same shape of gap as the dead end SPR-M.19 closed:
the system said you had achieved something and handed you nothing. A leader
certified a student, the status flipped, and the payoff of the whole programme
was a sentence on a page nobody else could see.

Two tensions run through these tests.

**A verification page must be readable by a stranger**, because a school
checking a certificate is not a member and never will be. **And the person on it
is a minor**, so §4.10 governs what a stranger may see. The resolution is that
the public view shows the least that still verifies and nothing more, and
several tests below exist only to hold that line as the page inevitably grows.

**A certificate is a current fact, not a permanent one.** Certification is
revocable (REQ-M.78), so a verifier must be told the truth at the moment they
ask rather than the truth as of printing.

Traces: REQ-M.20, M.28, M.78, §4.10.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm20

PASSWORD = "sprm20-pass-5518"


def make_user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def make_leader(email="noa@example.com", name="נעה מורה", school="עתיד רמלה"):
    from matazim.models import Leader, StudyClass

    leader = Leader.objects.create(user=make_user(email, name), approved_at=timezone.now())
    StudyClass.objects.create(leader=leader, name="ט1", school_name=school)
    return leader


def make_track():
    """The track, idempotently: two certified people in one test means this runs
    twice, and a course slug is unique."""
    from app.models import Course, Video

    made = []
    for slug, title in (("scratch", "סקראץ׳ למתחילים"), ("scratch-advanced", "סקראץ׳ מתקדם")):
        course, created = Course.objects.get_or_create(
            slug=slug, defaults={"title": title, "is_published": True}
        )
        if created:
            for i in range(3):
                Video.objects.create(course=course, title=f"{title} {i}", lesson_order=i + 1)
        made.append(course)
    return made


def a_certified_mataz(name="יובל כהן", email="kid@example.com"):
    """Somebody who has actually earned it, through the real path."""
    from app.models import CourseCertificate
    from matazim.certification import certify
    from matazim.models import MemberProfile, Student

    # A leader of their own, so two calls to this helper build two separate
    # worlds rather than colliding on one email.
    leader = make_leader(f"leader-{email}", f"מוביל של {name}")
    user = make_user(email, name)
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now(),
            "birth_year": timezone.now().year - 14,
            "guardian_consent_at": timezone.now(),
        },
    )
    student = Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)
    student.classes.set(leader.classes.all())
    for course in make_track():
        CourseCertificate.objects.get_or_create(user=user, course=course)

    certify(leader.user, student)
    student.refresh_from_db()
    return student, leader


# ------------------------------------------------- F-M.20.1: it exists


def test_certifying_produces_a_certificate(db):
    """T-F-M.20.1-1: REQ-M.20, in its own words: doing so produces one."""
    from matazim.models import MatazCertificate

    student, _leader = a_certified_mataz()
    certificate = MatazCertificate.objects.get(student=student)

    assert certificate.public_id
    assert certificate.is_valid
    assert certificate.name_on_certificate == "יובל כהן"


def test_the_name_is_captured_not_looked_up(db):
    """T-F-M.20.1-2: REQ-M.20.

    A certificate says who it was awarded to on the day. If the name were read
    live, somebody correcting their display name in 2029 would silently rewrite
    a document a school is holding a printed copy of.
    """
    from app.models import UserProfile
    from matazim.models import MatazCertificate

    student, _leader = a_certified_mataz()
    UserProfile.objects.filter(user=student.user).update(display_name="שם אחר לגמרי")

    assert MatazCertificate.objects.get(student=student).name_on_certificate == "יובל כהן"


def test_certifying_twice_does_not_make_two(db):
    """T-F-M.20.1-3: a person has one certification, so one certificate."""
    from matazim.certification import certify, revoke
    from matazim.models import MatazCertificate

    student, leader = a_certified_mataz()
    first = MatazCertificate.objects.get(student=student).public_id

    revoke(leader.user, student)
    certify(leader.user, student)

    assert MatazCertificate.objects.filter(student=student).count() == 1
    assert (
        MatazCertificate.objects.get(student=student).public_id == first
    ), "re-certifying must not invalidate a printed copy by issuing a new id"


# ------------------------------------------------- F-M.20.2: worth printing


def test_the_member_can_open_their_own_certificate(client, db):
    """T-F-M.20.2-1: REQ-M.28."""
    student, _leader = a_certified_mataz()
    client.force_login(student.user)

    response = client.get(reverse("matazim:my_certificate"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "יובל כהן" in html
    assert "מוביל של יובל כהן" in html, "who certified them belongs on it"


def test_it_is_built_to_print(client, db):
    """T-F-M.20.2-2: REQ-M.20.

    "Printable" is not "a page you could screenshot". A print stylesheet is the
    difference between a certificate and a browser window with a nav bar in it.
    """
    student, _leader = a_certified_mataz()
    client.force_login(student.user)

    html = client.get(reverse("matazim:my_certificate")).content.decode()
    assert "@media print" in html or "mz-cert-sheet" in html


def test_somebody_not_certified_does_not_get_one(client, db):
    """T-F-M.20.2-3: REQ-M.20, REQ-M.78.

    The certificate follows the decision; it is not a thing you can reach by
    guessing the URL before anyone has said yes.
    """
    from matazim.models import MemberProfile, Student

    leader = make_leader()
    user = make_user("nobody@example.com", "מישהו")
    MemberProfile.objects.update_or_create(user=user, defaults={})
    Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)

    client.force_login(user)
    assert client.get(reverse("matazim:my_certificate")).status_code in (302, 404)


# ------------------------------------------------- F-M.20.3: verifiable


def test_a_stranger_can_verify_one(client, db):
    """T-F-M.20.3-1: REQ-M.20, and the whole point of a certificate.

    A school checking one is not a member and never will be, so this page is
    public on purpose.
    """
    from matazim.models import MatazCertificate

    student, _leader = a_certified_mataz()
    certificate = MatazCertificate.objects.get(student=student)

    response = client.get(reverse("matazim:verify", args=[certificate.public_id]))
    assert response.status_code == 200
    assert "יובל כהן" in response.content.decode()


def test_the_public_page_shows_the_least_that_verifies(client, db):
    """T-F-M.20.3-2: §4.10, and the line this sprint has to hold.

    The person on it is a minor and the reader is a stranger. A name, a date,
    and "valid" is enough to answer the only question being asked. Everything
    else is a detail about a child given to somebody who typed a URL.
    """
    from matazim.models import MatazCertificate

    student, leader = a_certified_mataz()
    certificate = MatazCertificate.objects.get(student=student)

    html = client.get(reverse("matazim:verify", args=[certificate.public_id])).content.decode()

    assert "יובל כהן" in html
    for leaked in ("kid@example.com", "עתיד רמלה", "noa@example.com"):
        assert leaked not in html, f"the public page reveals {leaked!r} about a minor"


def test_an_unknown_id_says_so_rather_than_pretending(client, db):
    """T-F-M.20.3-3: a verifier who typed it wrong needs to know that."""
    import uuid

    response = client.get(reverse("matazim:verify", args=[uuid.uuid4()]))
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert "לא נמצאה" in response.content.decode()


def test_the_id_cannot_be_walked(db):
    """T-F-M.20.3-4: §4.10.

    A sequential id on a public page is an invitation to enumerate every
    certified child in the programme. This is the same mistake the QR endpoint
    made in SPR-M.9, and the fix is the same: an identifier nobody can guess.
    """
    import uuid

    from matazim.models import MatazCertificate

    student, _leader = a_certified_mataz()
    certificate = MatazCertificate.objects.get(student=student)

    assert isinstance(certificate.public_id, uuid.UUID)
    assert str(certificate.public_id) != str(certificate.pk)


# ------------------------------------------------- F-M.20.5: it tells the truth


def test_revoking_invalidates_the_certificate(db):
    """T-F-M.20.5-1: REQ-M.78.

    Certification is revocable, so a certificate is a current fact rather than a
    permanent one.
    """
    from matazim.certification import revoke
    from matazim.models import MatazCertificate

    student, leader = a_certified_mataz()
    revoke(leader.user, student)

    assert not MatazCertificate.objects.get(student=student).is_valid


def test_a_revoked_certificate_verifies_as_revoked(client, db):
    """T-F-M.20.5-2: REQ-M.78, and the reason a verify page exists at all.

    A printed copy outlives a revocation, which cannot be helped. The page that
    somebody checks against must say what is true when they ask, not what was
    true when it was printed. Saying nothing, or 404ing, would let a withdrawn
    certificate pass as unverifiable rather than as withdrawn.
    """
    from matazim.certification import revoke
    from matazim.models import MatazCertificate

    student, leader = a_certified_mataz()
    certificate = MatazCertificate.objects.get(student=student)
    revoke(leader.user, student)

    html = client.get(reverse("matazim:verify", args=[certificate.public_id])).content.decode()
    assert "בוטלה" in html or "אינה בתוקף" in html
    assert "תקפה" not in html.replace("אינה בתוקף", "")


def test_re_certifying_makes_it_valid_again(db):
    """T-F-M.20.5-3: REQ-M.78. Revocation is reversible, like everything here."""
    from matazim.certification import certify, revoke
    from matazim.models import MatazCertificate

    student, leader = a_certified_mataz()
    revoke(leader.user, student)
    certify(leader.user, student)

    assert MatazCertificate.objects.get(student=student).is_valid


# ------------------------------------------------- F-M.20.4: reachable


def test_the_member_finds_it_from_their_own_path(client, db):
    """T-F-M.20.4-1: REQ-M.28. The lesson this project keeps relearning."""
    student, _leader = a_certified_mataz()
    client.force_login(student.user)

    html = client.get(reverse("matazim:my_path")).content.decode()
    assert reverse("matazim:my_certificate") in html


def test_the_leader_can_reach_it_from_the_student_page(client, db):
    """T-F-M.20.4-2: REQ-M.28. They granted it; they can see what they granted."""
    from matazim.models import MatazCertificate

    student, leader = a_certified_mataz()
    certificate = MatazCertificate.objects.get(student=student)
    client.force_login(leader.user)

    html = client.get(reverse("matazim:student", args=[student.pk])).content.decode()
    assert reverse("matazim:verify", args=[certificate.public_id]) in html


def test_nobody_elses_certificate_is_reachable_from_my_page(client, db):
    """T-F-M.20.4-3: REQ-M.22, on the newest screen.

    Built from request.user, so there is no identifier here to tamper with.
    """
    student, _leader = a_certified_mataz()
    other, _ = a_certified_mataz("דני זר", "other@example.com")

    client.force_login(student.user)
    html = client.get(reverse("matazim:my_certificate")).content.decode()
    assert "דני זר" not in html


def test_being_certified_and_having_a_certificate_cannot_come_apart(db):
    """T-F-M.20.1-4: the invariant, and the demo broke it within the hour.

    `certification.certify` is what issues a certificate, so anything that sets
    `Student.status` to CERTIFIED by another route produces somebody who *is* a
    certified מט״צ with nothing to show for it. The demo seeder did exactly that
    and the screen 404d, which is how it was found.

    This checks the rule at its source rather than in one code path: nothing
    outside `certification.py` may name `Student.CERTIFIED` when setting status.
    """
    import re
    from pathlib import Path

    offenders = []
    for src in Path("matazim").rglob("*.py"):
        if src.name == "certification.py" or "migrations" in src.parts:
            continue
        for n, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
            # A write, not a read. `filter(status=Student.CERTIFIED)` is a
            # perfectly good question to ask; `student.status = ...` is the
            # thing that must not happen outside certification.py, and the dot
            # is what tells them apart.
            writes = re.search(r"set_status\([^)]*CERTIFIED", line) or re.search(
                r"\.status\s*=\s*Student\.CERTIFIED", line
            )
            if writes:
                offenders.append(f"{src.name}:{n} {line.strip()[:60]}")

    assert not offenders, (
        "certification happens somewhere other than certification.certify(), "
        "which produces a certified מט״צ with no certificate:\n  " + "\n  ".join(offenders)
    )


def test_the_printed_url_is_direction_isolated(client, db):
    """T-F-M.20.2-4: found by printing it, not by reading the template.

    A left-to-right URL inside a right-to-left paragraph gets reordered by the
    bidi algorithm: the trailing slash jumps to the front and the line reads
    "/http://…". On a page whose entire purpose is to be printed and typed back
    in, that is a dead link rather than a cosmetic nit.
    """
    from matazim.models import MatazCertificate

    student, _leader = a_certified_mataz()
    certificate = MatazCertificate.objects.get(student=student)
    client.force_login(student.user)

    html = client.get(reverse("matazim:my_certificate")).content.decode()
    marker = '<span dir="ltr">'
    assert marker in html, "the verification URL is not direction-isolated"
    start = html.index(marker)
    assert str(certificate.public_id) in html[start : start + 300]


def test_a_verifier_is_not_asked_to_dismiss_a_welcome(client, db):
    """T-F-M.20.3-5: found by loading the page as a stranger would.

    The prototype welcome (REQ-M.39) introduces the programme to somebody
    arriving at it. A school checking a certificate typed a URL off a printed
    page to answer one question and is joining nothing, so a modal they must
    dismiss before they can read the answer is the wrong first move.
    """
    from matazim.models import MatazCertificate

    student, _leader = a_certified_mataz()
    certificate = MatazCertificate.objects.get(student=student)

    html = client.get(reverse("matazim:verify", args=[certificate.public_id])).content.decode()
    assert "mz-welcome" not in html, "a verifier is blocked by the welcome notice"
    assert "אב טיפוס" not in html
