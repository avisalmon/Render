"""Academia360 sprint E.1: notifications (spec 4.8, backlog E.1): a bell row
per person and never the actor; the mail count is the backend's; the bell
shows the count and nothing at zero; following marks read and redirects
inside the app only; the API shows one's own rows and everything to the
admin; the events fire from the places that make them.
"""

import pytest
from academia360_d2_world import build, sign_in
from django.core import mail as dj_mail

from academia360 import notify, people
from academia360.models import CommitteeAttribute, Notification, Role, Submission

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = ""


@pytest.fixture
def world(db):
    return build()


def test_tell_writes_a_row_per_person_but_the_actor_and_mails_when_asked(world):
    rows, mailed = notify.tell([world["shira"], world["noa"], world["shira"], world["avi"]], "post", "משהו קרה",
                               "/academia360/committee/", actor=world["shira"], mail_body="שלום")
    assert rows == 2 and mailed == 1
    assert set(Notification.objects.values_list("user__email", flat=True)) == {"noa@example.com", "avi@example.com"}
    assert Notification.objects.filter(user=world["shira"]).count() == 0
    assert len(dj_mail.outbox) == 1
    sent = dj_mail.outbox[0]
    assert sorted(sent.to) == ["avi@example.com", "noa@example.com"]
    assert "משהו קרה" in sent.subject and "/academia360/committee/" in sent.body and "פיילוט" in sent.body
    # bell only: no mail
    rows, mailed = notify.tell([world["noa"]], "post", "עוד", "/academia360/committee/")
    assert (rows, mailed) == (1, 0) and len(dj_mail.outbox) == 1
    # nobody to tell
    assert notify.tell([], "post", "x") == (0, 0)


def test_a_submission_arriving_tells_the_reviewers_a_review_waits_and_the_rest_of_the_committee(world):
    rows, mailed = notify.submission_arrived(world["st"], actor=world["lead"])
    assert rows == 3 and mailed == 2  # one mail to the two reviewers, one to the rest
    by = {n.user.email: n for n in Notification.objects.select_related("user")}
    assert by["noa@example.com"].kind == "review" and by["yossi@example.com"].kind == "review"
    assert by["shira@example.com"].kind == "submission"
    assert "lead@example.com" not in by
    assert by["noa@example.com"].url == f"/academia360/committee/review/{world['st'].pk}/"
    assert by["shira@example.com"].url.startswith("/academia360/committee/technion/")
    assert "הטכניון" in by["noa@example.com"].title and "סקירה מחכה לך" in by["noa@example.com"].title


def test_the_api_fires_the_arrival_once_when_a_package_becomes_submitted(client, world):
    sign_in(client, world["lead"])
    r = client.post("/academia360/api/submissions/", {"participation": world["pt"].pk, "kind": "updated_plan", "status": "draft"})
    assert r.status_code == 201, r.content
    pk = r.json()["id"]
    assert Notification.objects.count() == 0
    r = client.patch(f"/academia360/api/submissions/{pk}/", {"status": "submitted"}, content_type="application/json")
    assert r.status_code == 200, r.content
    assert Notification.objects.filter(kind="review").count() == 2 and Notification.objects.filter(kind="submission").count() == 1
    client.patch(f"/academia360/api/submissions/{pk}/", {"cover_note": "עוד מילה"}, content_type="application/json")
    assert Notification.objects.count() == 3  # a later edit is not another arrival
    # created already submitted: fires too
    r = client.post("/academia360/api/submissions/", {"participation": world["pt"].pk, "kind": "kpi_report", "status": "submitted"})
    assert r.status_code == 201
    assert Notification.objects.count() == 6
    assert Submission.objects.filter(participation=world["pt"]).count() == 3


def test_the_bell_counts_the_page_lists_and_following_marks_read(client, world):
    notify.tell([world["shira"]], "submission", "הגשה הגיעה: ספיר", "/academia360/committee/sapir/")
    notify.tell([world["shira"]], "review", "סקירה מחכה לך: הטכניון", f"/academia360/committee/review/{world['st'].pk}/")
    sign_in(client, world["shira"])
    html = client.get("/academia360/committee/").content.decode()
    assert 'aria-label="התראות, 2 חדשות"' in html and 'class="a360-bell-n">2<' in html
    page = client.get("/academia360/notifications/")
    assert page.status_code == 200
    body = page.content.decode()
    assert "2 חדשות" in body and "הגשה הגיעה: ספיר" in body and "סקירה מחכה לך: הטכניון" in body and "לסמן את הכול כנקרא" in body
    newest = Notification.objects.filter(user=world["shira"]).first()
    assert "הטכניון" in newest.title  # newest first
    r = client.get(f"/academia360/notifications/{newest.pk}/go/")
    assert r.status_code == 302 and r["Location"] == f"/academia360/committee/review/{world['st'].pk}/"
    newest.refresh_from_db()
    assert newest.read_at is not None
    html = client.get("/academia360/committee/").content.decode()
    assert 'aria-label="התראות, 1 חדשות"' in html
    r = client.post("/academia360/notifications/read-all/")
    assert r.status_code == 302
    assert Notification.objects.filter(user=world["shira"], read_at__isnull=True).count() == 0
    html = client.get("/academia360/committee/").content.decode()
    assert 'aria-label="התראות"' in html and "a360-bell-n" not in html
    body = client.get("/academia360/notifications/").content.decode()
    assert "חדשות" not in body and "לסמן את הכול כנקרא" not in body
    # another person's item is not mine to follow
    other = Notification.objects.create(user=world["noa"], kind="post", title="x", url="/academia360/committee/")
    assert client.get(f"/academia360/notifications/{other.pk}/go/").status_code == 404
    # anonymous: to the sign-in
    client.logout()
    r = client.get("/academia360/notifications/")
    assert r.status_code == 302 and "/academia360/login/" in r["Location"]


def test_following_an_item_never_leaves_the_app(client, world):
    row = Notification.objects.create(user=world["shira"], kind="post", title="x", url="https://evil.example/go")
    blank = Notification.objects.create(user=world["shira"], kind="post", title="y", url="")
    sign_in(client, world["shira"])
    r = client.get(f"/academia360/notifications/{row.pk}/go/")
    assert r.status_code == 302 and r["Location"] == "/academia360/notifications/"
    r = client.get(f"/academia360/notifications/{blank.pk}/go/")
    assert r.status_code == 302 and r["Location"] == "/academia360/notifications/"
    assert Notification.objects.filter(user=world["shira"], read_at__isnull=True).count() == 0


def test_the_api_shows_mine_only_and_everything_to_the_admin(client, world):
    Notification.objects.create(user=world["noa"], kind="post", title="לנועה", url="/academia360/")
    Notification.objects.create(user=world["shira"], kind="post", title="לשירה", url="/academia360/")
    sign_in(client, world["noa"])
    r = client.get("/academia360/api/notifications/")
    assert r.status_code == 200
    titles = [row["title"] for row in r.json()["results"]] if isinstance(r.json(), dict) else [row["title"] for row in r.json()]
    assert titles == ["לנועה"]
    # a member may not plant a notification for another through the API
    r = client.post("/academia360/api/notifications/", {"user": world["shira"].pk, "kind": "post", "title": "ספאם"})
    assert r.status_code == 403
    sign_in(client, world["avi"])
    r = client.get("/academia360/api/notifications/")
    data = r.json()
    rows = data["results"] if isinstance(data, dict) else data
    assert sorted(row["title"] for row in rows) == ["לנועה", "לשירה"]


def test_a_new_reviewer_of_an_open_institution_is_told_a_review_waits(world):
    dana = world["dana"]
    Role.objects.create(user=dana, kind=Role.COMMITTEE_MEMBER)
    done = people.set_attribute(world["avi"], dana, CommitteeAttribute.REVIEWER, world["technion"])
    assert done.ok
    row = Notification.objects.get(user=dana)
    assert row.kind == "review" and row.url == f"/academia360/committee/review/{world['st'].pk}/"
    # haifa was answered: nothing waits there
    people.set_attribute(world["avi"], dana, CommitteeAttribute.REVIEWER, world["haifa"])
    assert Notification.objects.filter(user=dana).count() == 1


def test_a_correction_from_the_public_tells_the_admin_and_the_chairs(client, world):
    sign_in(client, world["dana"])
    dj_mail.outbox.clear()
    r = client.post("/academia360/talk/correct/", {"institution": "technion", "field": "city", "proposed_value": "חיפה, נשר", "reason": "האתר"})
    assert r.status_code == 302
    told = set(Notification.objects.filter(kind="correction").values_list("user__email", flat=True))
    assert told == {"avi@example.com", "shira@example.com"}
    assert any("הצעת תיקון" in m.subject for m in dj_mail.outbox)
    assert Notification.objects.filter(kind="correction").first().url == "/academia360/manage/#corrections"
