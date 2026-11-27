"""Academia360 sprint E.3: the chair's decision (spec 2.6.3, 4.4; backlog
E.3): a member is refused, a chair records, the admin records; a second
record changes the row and logs the change; the amount accepts "5,000,000";
the admin's bell and mail; nothing the institution sees changes.
"""

from decimal import Decimal

import pytest
from academia360_d2_world import build, sign_in
from django.core import mail as dj_mail

from academia360 import deciding
from academia360.models import ChangeLog, Decision, Notification, Participation, Submission

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = ""


@pytest.fixture
def world(db):
    return build()


def url(world, key="st"):
    return f"/academia360/committee/decide/{world[key].pk}/"


def test_amounts_are_read_the_way_people_write_them():
    assert deciding.amount_from("5,000,000") == Decimal("5000000")
    assert deciding.amount_from(" 5000000.50 ₪") == Decimal("5000000.50")
    assert deciding.amount_from("") is None and deciding.amount_from(None) is None
    assert deciding.amount_from("חמישה מיליון") is None and deciding.amount_from("-3") is None


def test_only_a_chair_or_the_admin_decides(client, world):
    for who in (None, world["lead"], world["noa"], world["yossi"]):
        if who is not None:
            sign_in(client, who)
        assert client.get(url(world)).status_code == 403
        assert client.post(url(world), {"outcome": "approved"}).status_code == 403
        client.logout()
    assert Decision.objects.filter(submission=world["st"]).count() == 0
    sign_in(client, world["shira"])
    assert client.get(url(world)).status_code == 200
    sign_in(client, world["avi"])
    assert client.get(url(world)).status_code == 200
    # a member sees the decision on the file and the board but no link to the form
    sign_in(client, world["noa"])
    assert f'href="{url(world, "sh")}"' not in client.get("/academia360/committee/haifa/").content.decode()
    assert "committee/decide/" not in client.get("/academia360/committee/").content.decode()


def test_the_chair_records_and_re_records_and_the_admin_hears(client, world):
    sign_in(client, world["shira"])
    dj_mail.outbox.clear()
    r = client.post(url(world), {"outcome": "conditional", "approved_amount_nis": "5,500,000", "conditions": "דיווח חצי־שנתי"})
    assert r.status_code == 302 and r["Location"] == f"/academia360/committee/technion/#decision-{world['st'].pk}"
    row = Decision.objects.get(submission=world["st"])
    assert row.outcome == "conditional" and row.approved_amount_nis == Decimal("5500000") and row.conditions == "דיווח חצי־שנתי"
    assert row.decided_by_id == world["shira"].pk and row.decided_at is not None
    assert ChangeLog.objects.filter(model="academia360.Decision", row_id=str(row.pk), new="created").exists()
    told = Notification.objects.filter(kind="decision")
    assert set(told.values_list("user__email", flat=True)) == {"avi@example.com"}
    assert told.first().url == f"/academia360/committee/technion/#decision-{world['st'].pk}"
    assert len(dj_mail.outbox) == 1 and dj_mail.outbox[0].to == ["avi@example.com"] and "אושר בתנאים" in dj_mail.outbox[0].subject
    # nothing the institution sees moved
    assert Submission.objects.get(pk=world["st"].pk).status == "submitted"
    assert Participation.objects.get(pk=world["pt"].pk).status == "submitted"
    # the file and the board show it, with the chair's link
    page = client.get("/academia360/committee/technion/").content.decode()
    assert "אושר בתנאים" in page and "דיווח חצי־שנתי" in page and f'href="{url(world)}"' in page
    board = client.get("/academia360/committee/").content.decode()
    assert f'href="{url(world)}"' in board
    # the form comes back filled
    form = client.get(url(world)).content.decode()
    assert 'value="conditional" checked' in form and 'value="5500000"' in form and "דיווח חצי־שנתי" in form
    # re-recorded in place, logged field by field
    r = client.post(url(world), {"outcome": "approved", "approved_amount_nis": "", "conditions": ""})
    assert r.status_code == 302
    assert Decision.objects.filter(submission=world["st"]).count() == 1
    row.refresh_from_db()
    assert row.outcome == "approved" and row.approved_amount_nis is None and row.conditions == ""
    assert ChangeLog.objects.filter(model="academia360.Decision", row_id=str(row.pk), field="outcome", old="conditional", new="approved").exists()
    # junk is refused and keeps the row
    r = client.post(url(world), {"outcome": "maybe"})
    assert r.status_code == 200 and "צריך לבחור" in r.content.decode()
    r = client.post(url(world), {"outcome": "declined", "approved_amount_nis": "הרבה"})
    assert r.status_code == 200 and "לא נקרא כמספר" in r.content.decode()
    assert Decision.objects.get(submission=world["st"]).outcome == "approved"


def test_the_admin_records_too_and_is_not_told_about_their_own_act(client, world):
    sign_in(client, world["avi"])
    r = client.post(url(world), {"outcome": "revise", "conditions": "להשלים את נספח ב׳"})
    assert r.status_code == 302
    assert Decision.objects.get(submission=world["st"]).outcome == "revise"
    assert Notification.objects.filter(kind="decision").count() == 0
