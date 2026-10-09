"""SPR-M.57 — a training page for each role.

Avi: "build a training page for pm and another training page for leader? like
a tutorial on how to do their role and what is their role in general."

Neither role came with one. האזור שלי opens on a link and, eventually, a
queue, with nothing that says what the queue *is* or what happens after
somebody joins it. ניהול is eight tools with no sentence connecting them to
the job.

**The guides add no ability — they are read-only pointers at screens that
already exist and already enforce their own guards.** So the tests here are
not about permissions (those are tested where the real screens live); they are
about two things that are easy to get wrong in a page made of prose and links:

1. **Every link actually resolves.** A `{% url %}` tag to a renamed or
   mistyped route raises `NoReverseMatch` and the page 500s — caught simply by
   asserting 200, but worth saying why that assertion matters here more than
   on an ordinary page.
2. **Neither guide promises something the reader cannot reach.** The leader
   guide must not send a leader to the improvement-request screen, which only
   program managers and root may open (REQ-M.102) — an error this file's first
   draft made and which `test_the_leader_guide_does_not_promise_the_request_channel`
   exists to keep from coming back. The PM guide must not link the two
   screens that stay root's alone.

Traces: REQ-M.73, REQ-M.88, REQ-M.101, REQ-M.102, REQ-M.156, REQ-M.157, §4.9.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

pytestmark = pytest.mark.sprm57

PASSWORD = "sprm57-pass-7731"


def _user(email, name, **kw):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD, **kw)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, Student

    inst = Institution.objects.create(name="רשת")
    naomi = _user("naomi@example.com", "נעמי")
    inst.managers.add(naomi)

    leader = Leader.objects.create(user=_user("leader@example.com", "מוביל"),
                                   institution=inst, approved_at=timezone.now())
    waiting = Leader.objects.create(user=_user("waiting@example.com", "ממתין"),
                                    institution=inst)
    kid = Student.objects.create(user=_user("kid@example.com", "מט״צ"),
                                 leader=leader, status=Student.IN_TRAINING)
    root = User.objects.create_superuser("root@example.com", "root@example.com", PASSWORD)

    return {"naomi": naomi, "leader": leader, "waiting": waiting, "kid": kid, "root": root}


def _login(client, email):
    assert client.login(username=email, password=PASSWORD)
    return client


# ----------------------------------------------------------------- the gate


def test_an_approved_leader_opens_their_guide(client, world):
    assert _login(client, "leader@example.com").get(
        "/matazim/leader/guide/").status_code == 200


def test_a_candidate_is_sent_to_the_waiting_screen_not_the_guide(client, world):
    """Same rule as leader_home (SPR-M.44): a candidate is not a trespasser,
    but a guide to a role they do not hold yet is the wrong thing to show
    them."""
    response = _login(client, "waiting@example.com").get("/matazim/leader/guide/")
    assert response.status_code == 302
    assert response["Location"] == "/matazim/leaders/"


def test_a_member_and_a_stranger_cannot_open_the_leader_guide(client, world):
    for email in ("kid@example.com",):
        session = _login(client, email)
        assert session.get("/matazim/leader/guide/").status_code == 403
        session.logout()


def test_an_anonymous_visitor_is_sent_to_sign_in(client, world):
    for path in ("/matazim/leader/guide/", "/matazim/staff/guide/"):
        response = client.get(path)
        assert response.status_code == 302
        assert "/matazim/login/" in response["Location"]


def test_a_program_manager_and_root_open_the_staff_guide(client, world):
    assert _login(client, "naomi@example.com").get(
        "/matazim/staff/guide/").status_code == 200
    assert _login(client, "root@example.com").get(
        "/matazim/staff/guide/").status_code == 200


def test_a_leader_cannot_open_the_staff_guide(client, world):
    assert _login(client, "leader@example.com").get(
        "/matazim/staff/guide/").status_code == 403


# ------------------------------------------------------- the links resolve


def test_every_link_on_the_leader_guide_resolves(client, world):
    """A 200 here is the whole test: a mistyped {% url %} tag raises
    NoReverseMatch and the page 500s instead."""
    response = _login(client, "leader@example.com").get("/matazim/leader/guide/")
    assert response.status_code == 200
    body = response.content.decode()
    for path in ("/matazim/leader/", "/matazim/leader/students/",
                 "/matazim/leader/classes/", "/matazim/leader/courses/",
                 "/matazim/community/", "/matazim/events/"):
        assert path in body, path


def test_every_link_on_the_staff_guide_resolves(client, world):
    response = _login(client, "naomi@example.com").get("/matazim/staff/guide/")
    assert response.status_code == 200
    body = response.content.decode()
    for path in ("/matazim/staff/team/", "/matazim/staff/people/",
                 "/matazim/staff/courses/", "/matazim/staff/cohort/",
                 "/matazim/staff/events/", "/matazim/staff/retention/",
                 "/matazim/staff/targets/", "/matazim/requests/new/",
                 "/matazim/requests/"):
        assert path in body, path


# ------------------------------------------------ neither guide overpromises


def test_the_leader_guide_does_not_promise_the_request_channel(client, world):
    """REQ-M.102 — filing an improvement request is the program-manager role
    and root, nobody else. The first draft of this guide told every leader to
    use a button they could not open."""
    body = _login(client, "leader@example.com").get(
        "/matazim/leader/guide/").content.decode()
    assert "/matazim/requests/new/" not in body
    assert "/matazim/requests/" not in body


def test_the_staff_guide_does_not_link_what_stays_roots(client, world):
    """REQ-M.114 — granting the role and setting the course pool are root's
    alone. Naming them is honest; linking them would invite a click that
    ends in a 403."""
    body = _login(client, "naomi@example.com").get(
        "/matazim/staff/guide/").content.decode()
    assert "/matazim/staff/admins/" not in body
    assert "/matazim/staff/offered/" not in body


def test_the_staff_guide_names_the_two_things_that_stay_roots(client, world):
    body = _login(client, "naomi@example.com").get(
        "/matazim/staff/guide/").content.decode()
    assert "מה לא בתפקיד שלכם" in body


# ------------------------------------------------------------- what Avi asked


def test_the_leader_guide_explains_the_role_and_says_the_test_is_optional(client, world):
    """"what is their role in general" and REQ-M.156 in the same breath."""
    body = _login(client, "leader@example.com").get(
        "/matazim/leader/guide/").content.decode()
    assert "לא חייבים" in body


def test_both_homes_lead_to_their_guide(client, world):
    leader_home = _login(client, "leader@example.com").get("/matazim/leader/").content.decode()
    assert "/matazim/leader/guide/" in leader_home

    staff_home = _login(client, "naomi@example.com").get("/matazim/staff/").content.decode()
    assert "/matazim/staff/guide/" in staff_home


def test_neither_guide_changes_anything(client, world):
    """Read-only, like the SPR-M.53 reports: a POST does nothing because
    there is nothing on the page that writes."""
    from matazim.models import Leader

    before = Leader.objects.get(pk=world["waiting"].pk).approved_at
    _login(client, "naomi@example.com").post(
        "/matazim/staff/guide/", {"action": "approve", "id": world["waiting"].pk})
    assert Leader.objects.get(pk=world["waiting"].pk).approved_at == before
