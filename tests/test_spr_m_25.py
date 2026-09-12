"""SPR-M.25 — the improvement loop.

§4.11. נעמי can say anything about the app from wherever she is standing in it,
Avi approves with one press, a sprint happens when he says so, and a summary
goes to both of them when it ships.

The test that matters most here is `test_approving_starts_nothing`. A queue
that executes itself is a different product from this one, with a different
risk profile, and the difference is invisible from the screens. REQ-M.110 makes
that a requirement rather than a convention, and a requirement nothing checks
is a convention again.

Traces: REQ-M.105 to M.113, §4.4, §4.11.
"""

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm25

PASSWORD = "sprm25-pass-4417"


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _manager(email="naomi@example.com", name="נעמי"):
    from matazim.models import MemberProfile

    user = _user(email, name)
    MemberProfile.objects.update_or_create(user=user, defaults={"is_program_manager": True})
    return user


def _root(email="avi@example.com"):
    user = User.objects.create_superuser(email, email, PASSWORD)
    from app.models import UserProfile

    UserProfile.objects.update_or_create(user=user, defaults={"display_name": "אבי"})
    return user


def _member(email="kid@example.com"):
    from matazim.models import MemberProfile

    user = _user(email, "יובל")
    MemberProfile.objects.update_or_create(
        user=user, defaults={"birth_year": timezone.now().year - 14}
    )
    return user


def _leader(email="noa@example.com", manager=None):
    from matazim.models import Leader

    return Leader.objects.create(
        user=_user(email, "נעה מורה"),
        program_manager=manager or _manager(),
        approved_at=timezone.now(),
    )


# ------------------------------------------- F-M.25.1/3: she can say something


def test_she_can_file_a_request_and_it_remembers_the_screen(client, db):
    """T-F-M.25.1-1: REQ-M.105.

    "The roster is confusing" and "the roster is confusing, sent from the
    roster" are different reports, and only the second is actionable.
    """
    from matazim.models import Request

    naomi = _manager()
    client.force_login(naomi)

    response = client.post(
        reverse("matazim:new_request"),
        {
            "body": "במסך המט״צים שלי אני לא מצליחה להבין מי מחכה לאישור שלי",
            "kind": Request.PROBLEM,
            "from_screen": "/matazim/leader/students/",
        },
    )
    assert response.status_code == 302

    row = Request.objects.get()
    assert row.author == naomi
    assert row.from_screen == "/matazim/leader/students/"
    assert row.status == Request.NEW, "a manager's request waits for Avi"
    assert row.author_role, "nothing records who was speaking"


def test_her_words_are_stored_exactly(client, db):
    """T-F-M.25.1-2: REQ-M.112.

    The exact words are the evidence. A paraphrase of a complaint is a
    complaint that has already been answered.
    """
    from matazim.models import Request

    said = "זה   מבלבל.\n\nובמיוחד השורה השנייה!! "
    client.force_login(_manager())
    client.post(
        reverse("matazim:new_request"),
        {"body": said, "kind": Request.PROBLEM, "from_screen": ""},
    )

    # Stripped at the edges, untouched inside: the leading spaces of a line and
    # the blank line between the two sentences are hers.
    assert Request.objects.get().body == said.strip()


def test_avis_own_request_arrives_approved(client, db):
    """T-F-M.25.1-3: REQ-M.108. Approving his own request has no reader."""
    from matazim.models import Request

    avi = _root()
    client.force_login(avi)
    client.post(
        reverse("matazim:new_request"),
        {"body": "להוסיף כפתור ייצוא לדוח המחזור", "kind": Request.IDEA, "from_screen": "/matazim/staff/cohort/"},
    )

    row = Request.objects.get()
    assert row.status == Request.APPROVED
    assert row.decided_by == avi
    assert row.decided_at is not None


def test_an_empty_request_is_refused_with_a_reason(client, db):
    """T-F-M.25.1-4: an empty form must say what is missing, not shrug."""
    from matazim.models import Request

    client.force_login(_manager())
    response = client.post(
        reverse("matazim:new_request"), {"body": "  ", "kind": Request.IDEA}
    )
    assert response.status_code == 200
    assert not Request.objects.exists()
    assert "כתבו" in response.content.decode()


# ------------------------------------------- F-M.25.8: the safety property


def test_approving_starts_nothing(client, db):
    """T-F-M.25.8-1: REQ-M.110, and the most important test in this sprint.

    Approving marks a row ready. It must not send mail, queue a job, schedule
    anything or otherwise begin work. A queue that executes itself is a
    different product and the difference cannot be seen from the screens.
    """
    from matazim.models import Request

    naomi = _manager()
    row = Request.objects.create(author=naomi, body="להוסיף חיפוש ברשימה", kind=Request.IDEA)

    client.force_login(_root())
    mail.outbox.clear()
    client.post(reverse("matazim:decide_request", args=[row.pk]), {"action": "approve"})

    row.refresh_from_db()
    assert row.status == Request.APPROVED
    assert row.decided_at is not None
    assert mail.outbox == [], "approving sent mail, so approving is doing something"
    assert row.done_at is None and not row.outcome, "approving recorded an outcome"
    assert row.summary_sent_at is None


def test_nothing_in_the_loop_can_schedule_work():
    """T-F-M.25.8-2: REQ-M.110, checked against the source.

    The behavioural test above proves approving does nothing today. This one
    fails if a later change gives this code the *ability* to start work, which
    is the thing the requirement actually forbids.
    """
    import ast
    from pathlib import Path

    # Parsed rather than grepped. The first version of this guard searched the
    # source for the word "schedule" and failed on the docstring that explains
    # the rule, which is exactly the kind of false positive that gets a check
    # switched off. Imports and calls are code; prose is not.
    banned_modules = {
        "celery", "threading", "subprocess", "sched", "multiprocessing",
        "schedule", "apscheduler", "rq", "huey", "asyncio",
    }
    banned_calls = {"apply_async", "delay", "Popen", "Thread", "spawn", "call_later"}

    offenders = []
    for name in ("request_views.py", "request_mail.py", "assess.py"):
        tree = ast.parse((Path("matazim") / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in banned_modules:
                        offenders.append(f"{name} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] in banned_modules:
                    offenders.append(f"{name} imports from {node.module}")
            elif isinstance(node, ast.Call):
                called = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if called in banned_calls:
                    offenders.append(f"{name} calls {called}()")

    assert not offenders, (
        "the improvement loop grew a way to start work on its own, which "
        f"REQ-M.110 forbids: {offenders}"
    )


# ------------------------------------------- F-M.25.5: only Avi decides


def test_a_program_manager_cannot_approve_anything(client, db):
    """T-F-M.25.5-1: REQ-M.108. A gate everybody can open is not a gate."""
    from matazim.models import Request

    naomi = _manager()
    row = Request.objects.create(author=naomi, body="בקשה", kind=Request.IDEA)

    client.force_login(naomi)
    assert client.get(reverse("matazim:request_queue")).status_code == 403
    response = client.post(reverse("matazim:decide_request", args=[row.pk]), {"action": "approve"})
    assert response.status_code == 403

    row.refresh_from_db()
    assert row.status == Request.NEW, "she approved her own request"


# ------------------------------------------- F-M.25.4: scope and need-to-know


def test_a_manager_sees_only_her_own_requests(client, db):
    """T-F-M.25.4-1: REQ-M.107, §4.4.

    Two institutions, two worlds. The same rule as every other staff screen.
    """
    from matazim.models import Request

    naomi = _manager("naomi@example.com")
    other = _manager("other@example.com", "מנהלת אחרת")
    Request.objects.create(author=naomi, body="שלי", kind=Request.IDEA)
    Request.objects.create(author=other, body="של מישהי אחרת", kind=Request.IDEA)

    client.force_login(naomi)
    html = client.get(reverse("matazim:my_requests")).content.decode()

    assert "שלי" in html
    assert "של מישהי אחרת" not in html


def test_root_sees_every_world(client, db):
    """T-F-M.25.4-2: §4.4. Root crosses all of them."""
    from matazim.models import Request

    Request.objects.create(author=_manager("a@example.com"), body="ראשונה", kind=Request.IDEA)
    Request.objects.create(author=_manager("b@example.com", "שנייה"), body="שנייה", kind=Request.IDEA)

    client.force_login(_root())
    html = client.get(reverse("matazim:request_queue")).content.decode()

    assert "ראשונה" in html and "שנייה" in html


@pytest.mark.parametrize("view", ["new_request", "my_requests", "request_queue"])
def test_a_member_and_a_leader_cannot_reach_any_of_it(client, db, view):
    """T-F-M.25.4-3: REQ-M.102.

    This is a tool for the people who own the programme. A member must not even
    be able to see that it exists.
    """
    for user in (_member(), _leader().user):
        client.force_login(user)
        assert client.get(reverse(f"matazim:{view}")).status_code == 403, f"{view} open to {user}"


def test_the_lamp_is_only_shown_to_the_roles_that_own_it(client, db):
    """T-F-M.25.4-4: REQ-M.106, REQ-M.102."""
    lamp = 'class="mz-lamp"'

    client.force_login(_manager())
    assert lamp in client.get(reverse("matazim:profile")).content.decode()

    client.force_login(_member())
    assert lamp not in client.get(reverse("matazim:profile")).content.decode()

    client.logout()
    assert lamp not in client.get(reverse("matazim:home")).content.decode()


def test_only_avi_is_told_how_many_are_waiting(client, db):
    """T-F-M.25.4-5: a count of somebody else's queue is a nag."""
    from matazim.models import Request

    naomi = _manager()
    Request.objects.create(author=naomi, body="בקשה", kind=Request.IDEA)

    client.force_login(naomi)
    assert client.get(reverse("matazim:profile")).context["requests_waiting"] == 0

    client.force_login(_root())
    assert client.get(reverse("matazim:profile")).context["requests_waiting"] == 1


# ------------------------------------------- F-M.25.6: the assessment


def test_a_request_saves_even_when_the_model_is_unreachable(client, db, settings):
    """T-F-M.25.6-1: REQ-M.109, fail-open.

    A model having a bad afternoon must never cost somebody their request.
    """
    from matazim.models import Request

    settings.OPENAI_API_KEY = ""
    client.force_login(_manager())
    client.post(
        reverse("matazim:new_request"),
        {"body": "בקשה בזמן שהמודל למטה", "kind": Request.IDEA},
    )

    row = Request.objects.get()
    assert row.body == "בקשה בזמן שהמודל למטה"
    assert row.assessment == "", "a stub string was stored as though it were an opinion"


def test_the_assessment_is_read_as_a_verdict_for_the_list(db):
    """T-F-M.25.6-2: REQ-M.109.

    Read from the text rather than stored, so a reworded prompt cannot leave a
    stale verdict disagreeing with the assessment printed beside it.
    """
    from matazim.assess import verdict_of

    assert verdict_of("כבר קיים\nREQ-M.94 כבר מכסה את זה.\nאין מה לבנות.") == "כבר קיים"
    assert verdict_of("רעיון טוב.\nכי...\nנוגע ברוסטר.") == "רעיון טוב"
    assert verdict_of("") == ""
    assert verdict_of("משהו אחר לגמרי") == ""


# ------------------------------------------- F-M.25.7: the loop closes


def test_closing_a_request_records_it_and_mails_both_of_them(db):
    """T-F-M.25.7-1: REQ-M.111.

    She will not go and check a log to see whether anything happened. The
    screen is where she looks when she wonders; the mail is what means she did
    not have to.
    """
    from matazim.models import Request
    from matazim.request_mail import send_request_summary

    naomi = _manager()
    avi = _root()
    row = Request.objects.create(
        author=naomi,
        body="לא ברור מי מחכה לאישור שלי",
        kind=Request.PROBLEM,
        status=Request.APPROVED,
        decided_by=avi,
        decided_at=timezone.now(),
        sprint="SPR-M.26",
        outcome="הוספנו תג 'מחכה לאישור' לכל שורה ברוסטר.",
        done_at=timezone.now(),
    )

    mail.outbox.clear()
    sent = send_request_summary(row)

    assert set(sent) == {naomi.email, avi.email}
    assert len(mail.outbox) == 1
    body = mail.outbox[0].body
    assert "לא ברור מי מחכה לאישור שלי" in body, "her words are not in the summary"
    assert "הוספנו תג" in body, "what was built is not in the summary"
    assert "SPR-M.26" in mail.outbox[0].subject

    row.refresh_from_db()
    assert row.summary_sent_at is not None


def test_a_declined_request_cannot_be_closed_as_done(db):
    """T-F-M.25.7-2: REQ-M.108.

    Closing something nobody approved would make the gate decorative.
    """
    from django.core.management import call_command
    from django.core.management.base import CommandError

    from matazim.models import Request

    row = Request.objects.create(
        author=_manager(), body="בקשה", kind=Request.IDEA, status=Request.DECLINED
    )

    with pytest.raises(CommandError):
        call_command("matazim_requests", "done", str(row.pk), "--outcome", "משהו")

    row.refresh_from_db()
    assert row.status == Request.DECLINED


def test_the_command_can_read_and_close_a_request(db, capsys):
    """T-F-M.25.7-3: how a sprint actually records what it built."""
    from django.core.management import call_command

    from matazim.models import Request

    row = Request.objects.create(
        author=_manager(), body="להוסיף חיפוש", kind=Request.IDEA, status=Request.APPROVED
    )

    call_command("matazim_requests", "show", str(row.pk))
    assert "להוסיף חיפוש" in capsys.readouterr().out

    call_command(
        "matazim_requests", "done", str(row.pk),
        "--sprint", "SPR-M.26", "--outcome", "נבנה חיפוש בראש הרשימה.",
    )
    row.refresh_from_db()
    assert row.status == Request.DONE
    assert row.sprint == "SPR-M.26"
    assert row.done_at is not None


def test_she_can_see_what_happened_to_her_request(client, db):
    """T-F-M.25.7-4: REQ-M.111.

    A log whose requester cannot see the end of it is a suggestion box.
    """
    from matazim.models import Request

    naomi = _manager()
    Request.objects.create(
        author=naomi,
        body="לא ברור מי מחכה",
        kind=Request.PROBLEM,
        status=Request.DONE,
        sprint="SPR-M.26",
        outcome="הוספנו תג לכל שורה.",
        done_at=timezone.now(),
    )

    client.force_login(naomi)
    html = client.get(reverse("matazim:my_requests")).content.decode()

    assert "הוספנו תג לכל שורה." in html
    assert "SPR-M.26" in html


# ------------------------------------------- REQ-M.114: only root appoints


def test_a_program_manager_cannot_appoint_another_program_manager(client, db):
    """T-REQ-M.114-1: the role must not be able to replicate itself.

    Found while wiring the improvement loop: the screen that grants the highest
    role in the product was gated on `is_program_manager`, so anybody holding
    it could hand it out, including to somebody in another institution's world.
    §4.4 would not have caught that, because tenancy scopes leaders and
    students rather than roles.
    """
    from django.urls import reverse

    from matazim.models import MemberProfile

    naomi = _manager()
    outsider = _user("outsider@example.com", "זר")

    client.force_login(naomi)
    assert client.get(reverse("matazim:staff_admins")).status_code == 403

    response = client.post(
        reverse("matazim:staff_admins"),
        {"action": "grant", "email": outsider.email},
    )
    assert response.status_code == 403
    assert not MemberProfile.objects.filter(
        user=outsider, is_program_manager=True
    ).exists(), "a program manager appointed another one"


def test_root_can_appoint_by_searching_rather_than_by_typing(client, db):
    """T-REQ-M.114-2: REQ-M.71.

    Avi's ask: the same user-search method as assigning a leader. Nobody should
    have to remember an exact address to grant a role, and the search endpoint
    already existed for exactly this picker.
    """
    from django.urls import reverse

    from matazim.models import MemberProfile

    _user("noa.cohen@example.com", "נעה כהן")
    client.force_login(_root())

    # The picker is on the screen, and the search finds her by Hebrew name.
    html = client.get(reverse("matazim:staff_admins")).content.decode()
    assert 'class="mz-picker"' in html

    found = client.get(reverse("matazim:staff_user_search"), {"q": "נעה"}).json()
    assert any("noa.cohen@example.com" == r.get("email") for r in found["results"]), found

    client.post(
        reverse("matazim:staff_admins"),
        {"action": "grant", "email": "noa.cohen@example.com"},
    )
    assert MemberProfile.objects.filter(
        user__email="noa.cohen@example.com", is_program_manager=True
    ).exists()


def test_the_door_to_it_is_hidden_from_a_program_manager(client, db):
    """T-REQ-M.114-3: a card whose button returns 403 reads as a fault."""
    from django.urls import reverse

    client.force_login(_manager())
    assert reverse("matazim:staff_admins") not in client.get(
        reverse("matazim:staff_home")
    ).content.decode()

    client.force_login(_root())
    assert reverse("matazim:staff_admins") in client.get(
        reverse("matazim:staff_home")
    ).content.decode()
