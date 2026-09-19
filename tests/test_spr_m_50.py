"""SPR-M.50 — the API's write paths, and three things the review found.

The second full review measured what the first had not: whether journeys close,
what the bytes on disk are, and which code 727 tests never execute.

**The coverage answer was uncomfortable in a specific way.** `api.py` sat at 77%
and the uncovered lines were almost exactly its write paths: `perform_create`
thirty lines of it, `perform_update`, `perform_destroy`, `_decide`, `retire`,
`restore`, `revoke`. SPR-M.34's sweep proved every endpoint refuses the wrong
reader and scopes every read, which was the right thing to prove first. Nothing
proved that a write *through* the API produces the right row.

That matters more here than on most products, because this API is what an agent
in a chat uses. A refusal that holds and a create that quietly files a row under
whoever the caller named are a bad combination: the door is locked and the
window is open.

So the load-bearing test is `test_no_endpoint_lets_a_caller_write_in_somebody_
elses_name`. It walks every writable endpoint, hands each one a body naming a
different person as the owner, and asserts the row that comes back belongs to
the caller. A sweep rather than six hand-written cases, for the reason the
tenancy sweep is a sweep: the endpoint that trusts the client is the one nobody
remembered to check.

Traces: REQ-M.139, REQ-M.19, REQ-M.32, REQ-M.105, Rule 6.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

pytestmark = pytest.mark.sprm50

PASSWORD = "sprm50-pass-4417"


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _member(user):
    from matazim.models import MemberProfile

    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now(),
            "birth_year": timezone.now().year - 14,
            "guardian_consent_at": timezone.now(),
            "welcome_accepted_at": timezone.now(),
        },
    )


@pytest.fixture
def world(db):
    """One institution, one leader, two members. Two, because every assertion
    below is about one of them not being able to write as the other."""
    from matazim.models import Institution, Leader, Student

    manager = _user("pm@example.com", "נעמי")
    inst = Institution.objects.create(name="רשת אחת")
    inst.managers.add(manager)
    leader = Leader.objects.create(
        user=_user("leader@example.com", "נעה"), institution=inst, approved_at=timezone.now()
    )
    made = {}
    for key, email, name in (("me", "kid1@example.com", "אלמה"),
                             ("them", "kid2@example.com", "נועה")):
        user = _user(email, name)
        _member(user)
        made[key] = Student.objects.create(
            user=user, leader=leader, status=Student.IN_TRAINING
        )
    return {"manager": manager, "leader": leader, **made}


# ------------------------------------------------- the sweep that matters


def test_no_endpoint_lets_a_caller_write_in_somebody_elses_name(client, world):
    """Ownership comes from the session on every writable endpoint.

    Each case hands the API a body that names the *other* member as the owner.
    The row that comes back must belong to the caller. A 400 or a 403 counts as
    passing too: refusing the write is a fine answer, and silently filing it
    under the caller is the correct one. The only failure is a row owned by
    somebody the caller merely named.
    """
    from matazim.models import Post, Submission, TeachingSession

    me, them = world["me"], world["them"]
    client.force_login(me.user)

    cases = [
        ("/matazim/api/submissions/", Submission, "student_id",
         {"title": "המבוך שלי", "link": "https://scratch.mit.edu/projects/1",
          "student": them.pk, "student_id": them.pk}),
        ("/matazim/api/teaching/", TeachingSession, "student_id",
         {"topic": "לולאות", "happened_on": str(timezone.localdate()), "minutes": 45,
          "student": them.pk, "student_id": them.pk}),
        ("/matazim/api/posts/", Post, "author_id",
         {"body": "בניתי משחק חדש והוא עובד", "kind": "note",
          "author": them.user_id, "author_id": them.user_id}),
    ]

    for url, model, owner_field, payload in cases:
        before = set(model.objects.values_list("pk", flat=True))
        resp = client.post(url, payload, content_type="application/json")
        assert resp.status_code in (200, 201, 400, 403), f"{url} answered {resp.status_code}"
        new = set(model.objects.values_list("pk", flat=True)) - before
        for pk in new:
            row = model.objects.get(pk=pk)
            owner = getattr(row, owner_field)
            expected = me.pk if owner_field == "student_id" else me.user_id
            assert owner == expected, (
                f"{url} filed a row under {owner}, which the caller named, "
                f"rather than {expected}, which is who the caller is"
            )


def test_a_member_cannot_write_feedback_on_their_own_work(client, world):
    """REQ-M.19, from the other side. The feedback is a leader's judgement of a
    teenager's work, and a teenager who can write it can certify themselves by
    degrees."""
    from matazim.models import Feedback, Submission

    sub = Submission.objects.create(
        student=world["me"], leader=world["leader"], title="עבודה",
        link="https://scratch.mit.edu/projects/2", status=Submission.WAITING,
    )
    client.force_login(world["me"].user)
    before = Feedback.objects.count()
    resp = client.post("/matazim/api/feedback/",
                       {"submission": sub.pk, "body": "מצוין, אני מאשר לעצמי"},
                       content_type="application/json")
    assert resp.status_code in (400, 403, 404)
    assert Feedback.objects.count() == before


def test_a_leaders_feedback_is_attributed_to_the_leader(client, world):
    """And the happy path, because a test suite that only proves refusals does
    not prove the feature works."""
    from matazim.models import Feedback, Submission

    sub = Submission.objects.create(
        student=world["me"], leader=world["leader"], title="עבודה",
        link="https://scratch.mit.edu/projects/3", status=Submission.WAITING,
    )
    client.force_login(world["leader"].user)
    resp = client.post(
        "/matazim/api/feedback/",
        {"submission": sub.pk, "body": "הבסיס צריך להיות רחב יותר", "author": world["me"].user_id},
        content_type="application/json",
    )
    assert resp.status_code in (200, 201), resp.content[:200]
    said = Feedback.objects.get(submission=sub)
    assert said.author_id == world["leader"].user_id, "attributed to whoever the body named"
    assert said.body == "הבסיס צריך להיות רחב יותר"


def test_a_request_is_attributed_to_whoever_sent_it(client, world):
    """REQ-M.112 — the words are the author's, and so is the name on them. The
    improvement queue is read from a chat now (SPR-M.48), which makes a request
    filed under the wrong name harder to notice, not easier."""
    from matazim.models import Request

    client.force_login(world["manager"])
    resp = client.post(
        "/matazim/api/requests/",
        {"body": "הרוסטר מבלבל", "kind": "problem", "author": world["me"].user_id},
        content_type="application/json",
    )
    assert resp.status_code in (200, 201), resp.content[:200]
    row = Request.objects.latest("created_at")
    assert row.author_id == world["manager"].pk
    assert row.body == "הרוסטר מבלבל"


def test_creating_a_leader_refuses_an_account_that_does_not_exist(client, world):
    """A typo must never conjure a record holding a role. The view says so in
    words; nothing had ever run it."""
    from matazim.models import Leader

    client.force_login(world["manager"])
    before = Leader.objects.count()
    resp = client.post("/matazim/api/leaders/", {"user_id": 999999},
                       content_type="application/json")
    assert resp.status_code == 400
    assert Leader.objects.count() == before


def test_creating_a_leader_refuses_somebody_who_already_is_one(client, world):
    from matazim.models import Leader

    client.force_login(world["manager"])
    before = Leader.objects.count()
    resp = client.post("/matazim/api/leaders/",
                       {"user_id": world["leader"].user_id}, content_type="application/json")
    assert resp.status_code == 400
    assert Leader.objects.count() == before


def test_a_member_can_delete_their_own_work_and_only_their_own(client, world):
    """Before certification, work belongs completely to whoever made it.

    The sweep expected approved work with a leader's feedback on it to be
    undeletable, and it was not: `perform_destroy` checked ownership and
    nothing else. That was a missing rule rather than a broken one, so it went
    to Avi, and this test pinned the behaviour meanwhile.

    **He decided it on 2026-09-20 and the answer is below, in
    `test_a_certified_mataz_cannot_delete_the_work_that_certified_them`.** The
    line he drew is certification, not feedback, so this half stands unchanged:
    a member in training deletes their own work and only their own.
    """
    from matazim.models import Submission

    mine = Submission.objects.create(
        student=world["me"], leader=world["leader"], title="שלי",
        link="https://scratch.mit.edu/projects/4", status=Submission.APPROVED,
    )
    theirs = Submission.objects.create(
        student=world["them"], leader=world["leader"], title="שלהם",
        link="https://scratch.mit.edu/projects/5", status=Submission.APPROVED,
    )
    client.force_login(world["me"].user)

    assert client.delete(f"/matazim/api/submissions/{theirs.pk}/").status_code in (403, 404)
    assert Submission.objects.filter(pk=theirs.pk).exists(), "somebody else's work was deleted"

    assert client.delete(f"/matazim/api/submissions/{mine.pk}/").status_code == 204
    assert not Submission.objects.filter(pk=mine.pk).exists()


# ------------------------------------------- F-M.50.8, as Avi decided it


def _certify(student):
    """The certificate row itself, which is what the freeze reads."""
    from matazim.models import MatazCertificate

    return MatazCertificate.objects.create(
        student=student, name_on_certificate="אלמה", awarded_by_name="נעה",
        awarded_at=timezone.now(),
    )


def test_a_certified_mataz_cannot_delete_the_work_that_certified_them(client, world):
    """Avi, 2026-09-20: "if mataz was certified, he can't delete his work. The
    conditions that granted him the mataz title must be frozen."

    A leader certifies by hand, having read this evidence. A title granted on
    evidence the holder can delete afterwards is a title nobody can defend, and
    the feedback goes with it on the cascade, so the leader's words vanish too.
    """
    from matazim.models import Feedback, Submission

    mine = Submission.objects.create(
        student=world["me"], leader=world["leader"], title="שלי",
        link="https://scratch.mit.edu/projects/6", status=Submission.APPROVED,
    )
    Feedback.objects.create(submission=mine, author=world["leader"].user,
                            body="עבודה יפה, אני מאשר")
    _certify(world["me"])

    client.force_login(world["me"].user)
    assert client.delete(f"/matazim/api/submissions/{mine.pk}/").status_code == 403
    assert Submission.objects.filter(pk=mine.pk).exists()
    assert Feedback.objects.filter(submission=mine).exists(), "the leader's words went too"


def test_a_certified_mataz_cannot_edit_it_either(client, world):
    """Deleting is the obvious hole and editing is the quiet one: swapping the
    link on approved work changes what the leader approved, while leaving a row
    that says they approved it."""
    from matazim.models import Submission

    mine = Submission.objects.create(
        student=world["me"], leader=world["leader"], title="שלי",
        link="https://scratch.mit.edu/projects/7", status=Submission.APPROVED,
    )
    _certify(world["me"])

    client.force_login(world["me"].user)
    resp = client.patch(f"/matazim/api/submissions/{mine.pk}/",
                        {"link": "https://scratch.mit.edu/projects/999"},
                        content_type="application/json")
    assert resp.status_code == 403
    mine.refresh_from_db()
    assert mine.link.endswith("/7")


def test_the_practicum_is_frozen_too(client, world):
    """REQ-M.32. A leader certifies "having taught them", and the practicum is
    the record of that teaching. Same evidence, same freeze."""
    from matazim.models import TeachingSession

    session = TeachingSession.objects.create(
        student=world["me"], title="לולאות", happened_on=timezone.localdate(),
        minutes=45, learners=12,
    )
    _certify(world["me"])

    client.force_login(world["me"].user)
    assert client.delete(f"/matazim/api/teaching/{session.pk}/").status_code == 403
    assert TeachingSession.objects.filter(pk=session.pk).exists()


def test_revoking_the_title_does_not_unfreeze_anything(client, world):
    """The freeze reads "a certificate ever existed", not "is valid now".

    A revocation is exactly when the record matters most: somebody is asking
    what happened, and a member who could clear the trail as the question
    arrives would be able to erase the case. `MatazCertificate` is never
    deleted for the same reason (REQ-M.78), only marked withdrawn.
    """
    from matazim.models import Submission

    mine = Submission.objects.create(
        student=world["me"], leader=world["leader"], title="שלי",
        link="https://scratch.mit.edu/projects/8", status=Submission.APPROVED,
    )
    cert = _certify(world["me"])
    cert.revoked_at = timezone.now()
    cert.save(update_fields=["revoked_at"])

    client.force_login(world["me"].user)
    assert client.delete(f"/matazim/api/submissions/{mine.pk}/").status_code == 403
    assert Submission.objects.filter(pk=mine.pk).exists()


def test_one_persons_certificate_does_not_freeze_anybody_else(client, world):
    """The freeze is per person, and the obvious way to get this wrong is a
    query that asks whether *any* certificate exists."""
    from matazim.models import Submission

    _certify(world["me"])
    theirs = Submission.objects.create(
        student=world["them"], leader=world["leader"], title="שלהם",
        link="https://scratch.mit.edu/projects/9", status=Submission.APPROVED,
    )

    client.force_login(world["them"].user)
    assert client.delete(f"/matazim/api/submissions/{theirs.pk}/").status_code == 204
    assert not Submission.objects.filter(pk=theirs.pk).exists()
