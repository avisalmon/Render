"""SPR-M.48 — the improvement loop reaches the chat that runs the sprints.

Avi, 2026-09-17, after talking to נעמי: she will send a lot of feedback, and he
wants to read it, approve it and turn it into a sprint from a chat while working
remote, and then have her told what shipped and how to see it.

Most of that existed. `Request` already carries status, `decided_by`, `sprint`,
`outcome` and even `summary_sent_at`, and `manage.py matazim_requests` already
reads and closes them. The one thing that did not work was the part he actually
asked about: **reaching production's rows from a chat.** Measured before
building anything, `GET https://babook.co.il/matazim/api/requests/` answers
`403 Authentication credentials were not provided`, because that API takes a
session cookie and an agent in a chat has none and must never be handed one.

So this adds the narrow key, to the BKM in `docs/building_an_app.md` that came
out of ustrip's family endpoint. **The refusals are written first and they are
most of this file**, because the interesting question about a key is never what
it opens.

What a stolen token here can do: read staff feedback about a website, and mark
it decided. What it cannot do is reach a student, a leader, a submission, a
certificate or any user account, and that is enforced by the code rather than
by the caller's good manners.

Traces: REQ-M.105, M.110, M.111, M.112, §4.11.
"""

import pytest
from django.contrib.auth.models import User

pytestmark = pytest.mark.sprm48

TOKEN = "sprm48-secret-9f2a7c"
URL = "/matazim/internal/requests/"


@pytest.fixture
def naomi(db):
    from app.models import UserProfile

    user = User.objects.create_user(
        username="naomi@example.com", email="naomi@example.com", password="sprm48-pass"
    )
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": "נעמי"})
    return user


@pytest.fixture
def a_request(naomi):
    from matazim.models import Request

    return Request.objects.create(
        author=naomi,
        body="הרוסטר מבלבל כשיש שתי כיתות באותו בית ספר.",
        from_screen="/matazim/leader/students/",
        status=Request.NEW,
    )


def _with_token(client, settings, method="get", **kw):
    settings.MATAZIM_ADMIN_TOKEN = TOKEN
    fn = getattr(client, method)
    return fn(URL, HTTP_AUTHORIZATION=f"Bearer {TOKEN}", **kw)


# ----------------------------------------------------------- the refusals


def test_no_token_is_refused(client, db, settings):
    settings.MATAZIM_ADMIN_TOKEN = TOKEN
    assert client.get(URL).status_code in (401, 403)


def test_a_wrong_token_is_refused(client, db, settings):
    settings.MATAZIM_ADMIN_TOKEN = TOKEN
    assert client.get(URL, HTTP_AUTHORIZATION="Bearer nope").status_code in (401, 403)


def test_an_unset_secret_means_closed_not_open(client, db, settings):
    """The classic version of this mistake: a deploy forgets the variable and
    the door is removed rather than locked."""
    settings.MATAZIM_ADMIN_TOKEN = ""
    assert client.get(URL, HTTP_AUTHORIZATION="Bearer ").status_code in (401, 403)
    assert client.get(URL, HTTP_AUTHORIZATION="Bearer anything").status_code in (401, 403)


def test_an_ordinary_member_session_is_refused(client, naomi, settings):
    """Being signed in is not being allowed. נעמי writes these rows and still
    cannot read the queue through this door."""
    settings.MATAZIM_ADMIN_TOKEN = TOKEN
    client.force_login(naomi)
    assert client.get(URL).status_code in (401, 403)


def test_the_token_cannot_create_a_request(client, db, settings, naomi):
    """A request is somebody's own words about their own experience. A key that
    could write one could manufacture a mandate for work nobody asked for."""
    from matazim.models import Request

    before = Request.objects.count()
    resp = _with_token(
        client, settings, "post",
        data={"action": "create", "body": "invented"},
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert Request.objects.count() == before


def test_the_token_cannot_rewrite_what_she_said(client, settings, a_request):
    """REQ-M.112 — the text is hers and is never edited."""
    original = a_request.body
    _with_token(
        client, settings, "post",
        data={"id": a_request.pk, "action": "approve", "body": "something else"},
        content_type="application/json",
    )
    a_request.refresh_from_db()
    assert a_request.body == original


def test_closing_without_saying_what_was_built_is_refused(client, settings, a_request):
    """The same rule a leader's feedback has: a status with no words tells the
    person nothing."""
    from matazim.models import Request

    resp = _with_token(
        client, settings, "post",
        data={"id": a_request.pk, "action": "done", "sprint": "SPR-M.48"},
        content_type="application/json",
    )
    assert resp.status_code == 400
    a_request.refresh_from_db()
    assert a_request.status != Request.DONE


def test_the_endpoint_touches_nothing_but_requests(client, settings, a_request, naomi):
    """The blast radius, asserted rather than described.

    A fingerprint of everything else מט״צים holds, before and after a full run
    of every verb this endpoint has.
    """
    from matazim.models import Leader, Student

    def fingerprint():
        return {
            "users": set(User.objects.values_list("pk", "username", "email", "is_staff", "is_superuser")),
            "students": set(Student.objects.values_list("pk", "status")),
            "leaders": set(Leader.objects.values_list("pk", "approved_at")),
        }

    before = fingerprint()
    _with_token(client, settings, "post",
                data={"id": a_request.pk, "action": "approve"}, content_type="application/json")
    _with_token(client, settings, "post",
                data={"id": a_request.pk, "action": "done", "outcome": "built it"},
                content_type="application/json")
    _with_token(client, settings)
    assert fingerprint() == before


# ----------------------------------------------------------- what it is for


def test_a_superuser_session_works_without_any_token(client, db, settings):
    """So the endpoint is usable from a browser even where no token exists."""
    settings.MATAZIM_ADMIN_TOKEN = ""
    root = User.objects.create_superuser("root@example.com", "root@example.com", "sprm48-root")
    client.force_login(root)
    assert client.get(URL).status_code == 200


def test_the_queue_can_be_read_and_filtered(client, settings, a_request):
    from matazim.models import Request

    Request.objects.create(author=a_request.author, body="עוד משהו", status=Request.APPROVED)

    everything = _with_token(client, settings).json()
    assert everything["counts"]["new"] == 1
    assert everything["counts"]["approved"] == 1

    settings.MATAZIM_ADMIN_TOKEN = TOKEN
    approved = client.get(
        URL, {"status": "approved"}, HTTP_AUTHORIZATION=f"Bearer {TOKEN}"
    ).json()
    assert len(approved["requests"]) == 1
    assert approved["requests"][0]["body"] == "עוד משהו"


def test_her_words_arrive_whole_not_truncated(client, settings, a_request):
    """A queue that shows first lines teaches people to decide on first lines."""
    body = _with_token(client, settings).json()["requests"][0]["body"]
    assert body == a_request.body


def test_a_draft_is_not_in_the_queue(client, settings, naomi):
    """REQ-M.107 — a draft is somebody mid-sentence, not something waiting."""
    from matazim.models import Request

    Request.objects.create(author=naomi, body="חצי משפט", status=Request.DRAFT)
    assert _with_token(client, settings).json()["requests"] == []


def test_approving_records_who_and_starts_nothing(client, settings, a_request):
    """REQ-M.110. The trigger for work is Avi in conversation, every time."""
    from matazim.models import Request

    resp = _with_token(client, settings, "post",
                       data={"id": a_request.pk, "action": "approve"},
                       content_type="application/json")
    assert resp.status_code == 200
    a_request.refresh_from_db()
    assert a_request.status == Request.APPROVED
    assert a_request.decided_at is not None
    # Nothing was scheduled, nobody was told, no sprint exists yet.
    assert a_request.sprint == ""
    assert a_request.done_at is None
    assert a_request.summary_sent_at is None


def test_closing_records_the_sprint_and_mails_her_with_demo_steps(client, settings, a_request):
    """REQ-M.111, and Avi's two additions: how to see it, and thanks."""
    from django.core import mail

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    mail.outbox = []

    resp = _with_token(
        client, settings, "post",
        data={
            "id": a_request.pk, "action": "done", "sprint": "SPR-M.48",
            "outcome": "הרוסטר מקבץ לפי כיתה.",
            "demo": "נכנסים להמט״צים שלי ורואים כותרת כיתה.",
            "mail": True,
        },
        content_type="application/json",
    )
    assert resp.status_code == 200

    a_request.refresh_from_db()
    assert a_request.sprint == "SPR-M.48"
    assert a_request.summary_sent_at is not None

    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert a_request.author.email in sent.recipients()
    assert a_request.body in sent.body, "her words, verbatim"
    assert "הרוסטר מקבץ לפי כיתה." in sent.body
    assert "נכנסים להמט״צים שלי ורואים כותרת כיתה." in sent.body, "how to demo it"
    assert "תודה" in sent.body, "and thank her"


def test_nothing_is_mailed_unless_asked(client, settings, a_request):
    """Closing a row and telling somebody are two decisions."""
    from django.core import mail

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    mail.outbox = []
    _with_token(client, settings, "post",
                data={"id": a_request.pk, "action": "done", "outcome": "done quietly"},
                content_type="application/json")
    assert mail.outbox == []
    a_request.refresh_from_db()
    assert a_request.summary_sent_at is None


# ------------------------------------- two rules behaviour cannot demonstrate


def test_the_secret_is_compared_in_constant_time():
    """Principle 6 of the BKM, and the one no functional test can show.

    `==` on a secret and `constant_time_compare` on a secret behave
    identically; the difference is how long the wrong answer takes, which
    leaks length and prefix to somebody patient. So this reads the source,
    which is the only place the difference is visible.

    Written after watching the perturbation run: swapping in `==` was caught by
    nothing, correctly, because nothing functional had changed.
    """
    import pathlib

    src = (pathlib.Path(__file__).resolve().parent.parent / "matazim" / "requests_api.py").read_text(
        encoding="utf-8"
    )
    assert "constant_time_compare(presented, expected)" in src
    assert "presented == expected" not in src


def test_the_unset_secret_is_refused_explicitly():
    """Principle 5, also invisible to behaviour here.

    An empty secret cannot match anything anyway, because the comparison is
    guarded by `bool(presented)`, so removing the explicit check changes no
    outcome and the suite stays green. It stays in the source because the next
    person to edit this function should meet the intent, not deduce it from two
    interacting conditions.
    """
    import pathlib

    src = (pathlib.Path(__file__).resolve().parent.parent / "matazim" / "requests_api.py").read_text(
        encoding="utf-8"
    )
    assert "if not expected:" in src
