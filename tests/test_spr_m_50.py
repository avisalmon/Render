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
    """What the API actually does, recorded rather than wished at.

    The sweep expected approved work with a leader's feedback on it to be
    undeletable, and it is not: `perform_destroy` checks ownership and nothing
    else, so a member can remove a submission a leader has already answered,
    and the `Feedback` rows go with it on the cascade.

    That is not a broken rule, it is a missing one, and inventing it here would
    be a test asserting a decision nobody made. REQ-M.125 keeps every attempt
    so feedback keeps the version it was about, which argues one way; a
    teenager's right to remove their own work argues the other. Written up for
    Avi in the backlog; this test pins today's behaviour so the day somebody
    changes it, they change it on purpose.
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
