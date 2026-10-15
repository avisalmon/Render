"""SPR-M.66 - the main site waits for the test (REQ-M.189, request #12 from the site).

ליטל, filed from the site on 2026-10-15 and approved by Avi: only someone who
passed the screening test can enter the main site. What these tests protect: a
programme participant who has not been approved is turned back from the learning,
the hand-ins, the practicum and the community and told why; approval opens all of
it; leaders, program managers and root are never gated; the open door (nobody to
answer to) is a separate promise and stays open; and the places a gated person
needs in order to get through (the test, their path, the bell) stay reachable.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from tests.test_spr_m_51 import _course

pytestmark = pytest.mark.sprm66

PASSWORD = "sprm66-pass-3304"
GATED_PAGES = [
    "/matazim/learn/scratch/",
    "/matazim/my-work/",
    "/matazim/my-teaching/",
    "/matazim/community/",
]


def _user(name):
    return User.objects.create_user(username=f"{name}@example.com", email=f"{name}@example.com",
                                    password=PASSWORD)


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, MemberProfile

    inst = Institution.objects.create(name="רשת עתיד")
    pm = _user("pm")
    inst.managers.add(pm)
    leader = Leader.objects.create(user=_user("leader"), institution=inst,
                                   approved_at=timezone.now())
    _course("scratch")
    ready = dict(birth_year=timezone.now().year - 14, guardian_consent_at=timezone.now(),
                 welcome_accepted_at=timezone.now())

    def member(name, *, leader_=leader, pending=None, passed=False):
        from matazim.models import Student

        user = _user(name)
        MemberProfile.objects.update_or_create(user=user, defaults={
            **ready, "entrance_test_passed_at": timezone.now() if passed else None})
        Student.objects.create(user=user, leader=leader_, pending_leader=pending,
                               status="in_training")
        return user

    return {"inst": inst, "pm": pm, "leader": leader, "member": member, "ready": ready}


@pytest.mark.parametrize("url", GATED_PAGES)
def test_a_participant_who_has_not_passed_is_turned_back_and_told_why(client, world, url):
    kid = world["member"]("kid")
    client.force_login(kid)
    resp = client.get(url)
    assert resp.status_code == 302 and resp["Location"] == "/matazim/test/?gate=1", url

    page = client.get(resp["Location"]).content.decode()
    start = page.index('id="mzGateWhy"')
    assert "אדם מצוות התוכנית מאשר" in page[start:page.index("</div>", start)]


@pytest.mark.parametrize("url", GATED_PAGES)
def test_approval_opens_it(client, world, url):
    kid = world["member"]("kid", passed=True)
    client.force_login(kid)
    assert client.get(url).status_code == 200, url


def test_a_gated_person_cannot_press_finish_or_hand_in(client, world):
    from app.models import CourseCertificate

    kid = world["member"]("kid")
    client.force_login(kid)
    resp = client.post("/matazim/learn/scratch/finish/")
    assert resp["Location"] == "/matazim/test/?gate=1"
    resp = client.post("/matazim/my-work/", {"title": "x", "link": "https://a.example/x"})
    assert resp["Location"] == "/matazim/test/?gate=1"
    assert not CourseCertificate.objects.filter(user=kid).exists()


def test_someone_who_only_asked_for_a_leader_is_gated_too(client, world):
    kid = world["member"]("asked", leader_=None, pending=world["leader"])
    client.force_login(kid)
    assert client.get("/matazim/my-work/")["Location"] == "/matazim/test/?gate=1"


@pytest.mark.parametrize("who", ["leader", "pm"])
def test_leaders_and_managers_are_never_gated(client, world, who):
    client.force_login(world["leader"].user if who == "leader" else world["pm"])
    assert client.get("/matazim/learn/scratch/").status_code == 200


def test_root_is_never_gated(client, world):
    root = User.objects.create_superuser("root@example.com", "root@example.com", PASSWORD)
    client.force_login(root)
    assert client.get("/matazim/learn/scratch/").status_code == 200


def test_the_open_door_is_gated_too_until_the_team_approves(client, world):
    """Q28, answered by Avi 2026-10-15: "Litala's definition is priority".

    Nobody to answer to is no exemption. SPR-M.59's open learning and SPR-M.60's
    open classes wait for the same approval as everything else.
    """
    from matazim.models import MemberProfile

    user = _user("open")
    MemberProfile.objects.update_or_create(user=user, defaults=world["ready"])
    client.force_login(user)
    for url in ("/matazim/learn/scratch/", "/matazim/classes/", "/matazim/classes/open/new/"):
        assert client.get(url)["Location"] == "/matazim/test/?gate=1", url

    # Approved, but with nobody to join yet: the stage after the test (REQ-M.192).
    MemberProfile.objects.filter(user=user).update(entrance_test_passed_at=timezone.now())
    assert client.get("/matazim/learn/scratch/")["Location"] == "/matazim/join-leader/"

    from tests.matazim_helpers import attach

    attach(user)
    assert client.get("/matazim/learn/scratch/").status_code == 200
    assert client.get("/matazim/classes/").status_code == 200


def test_what_a_gated_person_needs_to_get_through_stays_reachable(client, world):
    kid = world["member"]("kid")
    client.force_login(kid)
    for url in ("/matazim/test/", "/matazim/my-path/", "/matazim/notices/", "/matazim/",
                "/matazim/track/", "/matazim/test/task/"):
        assert client.get(url).status_code == 200, url


def test_the_gate_and_the_approval_work_end_to_end(client, world):
    """The whole of request #12 in one walk: turned back, approved, let in."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from matazim import entrance_review
    from matazim.models import EntranceAttempt
    from matazim.targets import sync_bank
    from tests.test_spr_m_3 import target_stl

    sync_bank()
    kid = world["member"]("kid")
    client.force_login(kid)
    assert client.get("/matazim/learn/scratch/")["Location"] == "/matazim/test/?gate=1"

    client.get("/matazim/test/task/")
    attempt = EntranceAttempt.objects.get(member__user=kid)
    client.post("/matazim/test/task/", {"model_file": SimpleUploadedFile(
        "m.stl", target_stl(attempt.target_id))})
    assert client.get("/matazim/learn/scratch/").status_code == 302  # measured is not approved

    attempt.refresh_from_db()
    entrance_review.approve(attempt, world["pm"])
    assert client.get("/matazim/learn/scratch/").status_code == 200
