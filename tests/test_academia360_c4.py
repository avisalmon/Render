"""Academia360 sprints C.4 and C.5: the admin's room (spec 4.5; backlog C.4,
C.5): /academia360/manage/people/ (the queue, everyone with a role, grant,
invite, revoke, chair, reviewer) and /academia360/manage/ (the overview).

Admin only: committee members, leaders and anonymous visitors get the plain
"no access" page. Every form posts to the one act view, which calls people.py
and says whether the mail left. Every number on the overview is read against
the seed; hiding a comment works and is logged.
"""

from datetime import date

import pytest
from django.contrib.auth.models import User
from django.core import mail as dj_mail

from academia360.models import (
    AgentRun,
    AiUsage,
    ChangeLog,
    CommitteeAttribute,
    CorrectionProposal,
    Institution,
    Invitation,
    LeaderOf,
    Participation,
    Program,
    PublicComment,
    Role,
    RoleRequest,
    Submission,
)

pytestmark = pytest.mark.django_db

PW = "manage-4410-pw"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = ""


@pytest.fixture
def world(db):
    program = Program.objects.create(slug="academia-360", name="אקדמיה 360")
    technion = Institution.objects.create(slug="technion", name_he="הטכניון", short_name_he="הטכניון", kind=Institution.UNIVERSITY)
    haifa = Institution.objects.create(slug="haifa", name_he="אוניברסיטת חיפה", short_name_he="חיפה", kind=Institution.UNIVERSITY)
    bezalel = Institution.objects.create(slug="bezalel", name_he="בצלאל", kind=Institution.COLLEGE)
    pt = Participation.objects.create(program=program, institution=technion, applied=True, status="submitted")
    Participation.objects.create(program=program, institution=haifa, applied=True, status="responded")
    Participation.objects.create(program=program, institution=bezalel, applied=False, status="did_not_apply")
    Submission.objects.create(participation=pt, kind="proposal", status="submitted", cover_note="x")
    avi = User.objects.create_user("avi@example.com", "avi@example.com", PW, is_superuser=True, is_staff=True, first_name="אבי")
    Role.objects.create(user=avi, kind=Role.ADMIN)
    shira = User.objects.create_user("shira@example.com", "shira@example.com", PW, first_name="שירה")
    Role.objects.create(user=shira, kind=Role.COMMITTEE_MEMBER)
    CommitteeAttribute.objects.create(user=shira, kind=CommitteeAttribute.CHAIR, program=program)
    noa = User.objects.create_user("noa@example.com", "noa@example.com", PW, first_name="נועה")
    Role.objects.create(user=noa, kind=Role.COMMITTEE_MEMBER)
    CommitteeAttribute.objects.create(user=noa, kind=CommitteeAttribute.REVIEWER, program=program, institution=technion)
    lead = User.objects.create_user("lead@example.com", "lead@example.com", PW, first_name="דקלה")
    Role.objects.create(user=lead, kind=Role.LEADER)
    LeaderOf.objects.create(user=lead, institution=technion, title="דיקנית")
    dana = User.objects.create_user("dana@example.com", "dana@example.com", PW, first_name="דנה")
    req = RoleRequest.objects.create(user=dana, role_kind="leader", institution=haifa, title="רקטורית", message="אני אחראית")
    CorrectionProposal.objects.create(proposer=dana, model="academia360.Institution", row_id=str(technion.pk), field="founded",
                                      current_value="1912", proposed_value="1924", reason="אתר")
    comment = PublicComment.objects.create(author=dana, institution=technion, body="תגובה גלויה")
    AgentRun.objects.create(purpose="העשרת הטכניון", sources="x", rows_touched=7)
    AiUsage.objects.create(user=shira, date=date.today(), calls=3, tokens=1000, cost_usd="0.1234")
    return {"program": program, "technion": technion, "haifa": haifa, "avi": avi, "shira": shira, "noa": noa,
            "lead": lead, "dana": dana, "req": req, "comment": comment}


def _in(client, who):
    assert client.login(username=who.email, password=PW)


# ------------------------------------------------------------------- the gate

def test_the_room_is_the_admins_alone(client, world):
    for url in ("/academia360/manage/", "/academia360/manage/people/"):
        r = client.get(url)
        assert r.status_code == 403 and "העמוד הזה סגור לכם" in r.content.decode()
        for who in (world["shira"], world["lead"], world["dana"]):
            _in(client, who)
            r = client.get(url)
            assert r.status_code == 403, (url, who.email)
            assert "ניהול" not in client.get("/academia360/").content.decode().split("<header", 1)[1].split("</header>", 1)[0]
            client.logout()
    r = client.post("/academia360/manage/act/", {"action": "approve", "request": world["req"].pk})
    assert r.status_code == 403 and RoleRequest.objects.get(pk=world["req"].pk).status == "open"
    _in(client, world["avi"])
    bar = client.get("/academia360/").content.decode().split("<header", 1)[1].split("</header>", 1)[0]
    assert 'href="/academia360/manage/"' in bar and "ניהול" in bar


# --------------------------------------------------------------- the people page

def test_the_people_page_shows_the_queue_and_everyone_grouped(client, world):
    _in(client, world["avi"])
    html = client.get("/academia360/manage/people/").content.decode()
    queue = html.split('id="queue"', 1)[1].split('class="a360-room-grid"', 1)[0]
    assert "דנה" in queue and "אוניברסיטת חיפה" in queue and "רקטורית" in queue and "אני אחראית" in queue
    assert 'value="approve"' in queue and 'value="decline"' in queue
    committee = html.split('id="committee"', 1)[1].split('id="admins"', 1)[0]
    assert "שירה" in committee and "יו״ר" in committee and "נועה" in committee and "סוקר/ת: הטכניון" in committee
    leaders = html.split('id="leaders"', 1)[1].split('id="grant"', 1)[0]
    assert "הטכניון" in leaders and "דקלה" in leaders and "דיקנית" in leaders
    assert "4 אנשים עם תפקיד: 1 מנהלים, 2 חברי ועדה, 1 מובילים ב־1 מוסדות" in html


def test_approving_from_the_screen_grants_mails_and_says_so(client, world):
    _in(client, world["avi"])
    r = client.post("/academia360/manage/act/", {"action": "approve", "request": world["req"].pk}, follow=True)
    assert r.redirect_chain[-1][0] == "/academia360/manage/people/"
    flash = r.content.decode().split('class="a360-flash"', 1)[1].split("</div>", 1)[0]
    assert "אושר" in flash and "המייל נשלח" in flash
    assert LeaderOf.objects.filter(user=world["dana"], institution=world["haifa"], title="רקטורית", active=True).exists()
    assert len(dj_mail.outbox) == 1 and dj_mail.outbox[0].to == ["dana@example.com"]
    html = r.content.decode()
    assert "אין בקשות פתוחות" in html and "אושר" in html.split('id="decided"', 1)[1]


def test_declining_with_a_word_mails_the_word(client, world):
    _in(client, world["avi"])
    r = client.post("/academia360/manage/act/", {"action": "decline", "request": world["req"].pk, "note": "לא השנה"}, follow=True)
    assert "נדחה" in r.content.decode() and "המייל נשלח" in r.content.decode()
    req = RoleRequest.objects.get(pk=world["req"].pk)
    assert req.status == "declined" and req.decision_note == "לא השנה" and req.decided_by == world["avi"]
    assert "לא השנה" in dj_mail.outbox[0].body and not Role.objects.filter(user=world["dana"]).exists()


def test_every_form_of_the_room_does_its_act(client, world):
    _in(client, world["avi"])
    act = "/academia360/manage/act/"
    technion, haifa = world["technion"], world["haifa"]
    # grant by email, unknown email, revoke
    r = client.post(act, {"action": "grant", "email": "dana@example.com", "kind": "committee"}, follow=True)
    assert Role.objects.filter(user=world["dana"], kind=Role.COMMITTEE_MEMBER, active=True).exists() and "המייל נשלח" in r.content.decode()
    r = client.post(act, {"action": "grant", "email": "ghost@example.com", "kind": "committee"}, follow=True)
    assert "אין חשבון" in r.content.decode()
    client.post(act, {"action": "revoke", "email": "lead@example.com", "kind": "leader", "institution": technion.pk})
    assert not LeaderOf.objects.filter(user=world["lead"], active=True).exists()
    assert not Role.objects.filter(user=world["lead"], kind=Role.LEADER, active=True).exists()
    # chair on and off, reviewer on and off
    client.post(act, {"action": "chair", "email": "noa@example.com"})
    assert CommitteeAttribute.objects.filter(user=world["noa"], kind=CommitteeAttribute.CHAIR).exists()
    client.post(act, {"action": "unchair", "email": "noa@example.com"})
    assert not CommitteeAttribute.objects.filter(user=world["noa"], kind=CommitteeAttribute.CHAIR).exists()
    client.post(act, {"action": "reviewer", "email": "shira@example.com", "institution": haifa.pk})
    assert CommitteeAttribute.objects.filter(user=world["shira"], kind=CommitteeAttribute.REVIEWER, institution=haifa).exists()
    client.post(act, {"action": "unreviewer", "email": "shira@example.com", "institution": haifa.pk})
    assert not CommitteeAttribute.objects.filter(user=world["shira"], kind=CommitteeAttribute.REVIEWER, institution=haifa).exists()
    # invite and resend
    n = len(dj_mail.outbox)
    r = client.post(act, {"action": "invite", "email": "new@example.com", "kind": "leader", "institution": technion.pk,
                          "title": "סגן נשיא"}, follow=True)
    inv = Invitation.objects.get(email="new@example.com")
    assert inv.sent_at is not None and len(dj_mail.outbox) == n + 1 and "new@example.com" in r.content.decode()
    client.post(act, {"action": "resend", "invitation": inv.pk})
    assert len(dj_mail.outbox) == n + 2
    r = client.post(act, {"action": "dance"}, follow=True)
    assert "לא ברור" in r.content.decode()
    # a next inside the app is honoured, one outside is not
    r = client.post(act, {"action": "chair", "email": "noa@example.com", "next": "/academia360/manage/"})
    assert r.status_code == 302 and r.url == "/academia360/manage/"
    r = client.post(act, {"action": "unchair", "email": "noa@example.com", "next": "https://evil.example/"})
    assert r.url == "/academia360/manage/people/"


# ----------------------------------------------------------------- the overview

def test_the_overview_reads_the_seed(client, world):
    _in(client, world["avi"])
    html = client.get("/academia360/manage/").content.decode()
    assert "4 אנשים עם תפקיד: 1 מנהלים, 2 חברי ועדה (1 יו״ר), 1 מובילים ב־1 מוסדות. 2 מתוך 3 המוסדות הגישו" in html
    waiting = html.split("מה מחכה למישהו", 1)[1].split("המוסדות בתכנית", 1)[0]
    rows = waiting.split('class="a360-row"')[1:5]
    assert [r.split('class="a360-num">', 1)[1][0] for r in rows] == ["1", "1", "1", "0"]
    assert "מוביל/ת תכנית במוסד בחיפה" in waiting  # the open request, by institution (its short name)
    assert "1 הגיש, 1 נענה." in html
    assert "1 מוסדות שהגישו ועוד אין להם מוביל" in html and 'href="/academia360/institutions/haifa/"' in html
    public = html.split("מה הציבור שלח השבוע", 1)[1].split("מה הסוכן עשה", 1)[0]
    assert "1 תגובות, 0 לייקים" in public and "תגובה גלויה" in public and 'value="hide"' in public
    agent = html.split("מה הסוכן עשה", 1)[1].split("AI היום", 1)[0]
    assert "העשרת הטכניון" in agent and "7 שורות" in agent
    assert "3 קריאות" in html and "$0.12" in html


def test_hiding_a_comment_from_the_overview_hides_it_everywhere_and_is_logged(client, world):
    _in(client, world["avi"])
    r = client.post("/academia360/manage/act/", {"action": "hide", "comment": world["comment"].pk, "next": "/academia360/manage/"}, follow=True)
    assert r.redirect_chain[-1][0] == "/academia360/manage/" and "הוסתרה" in r.content.decode()
    assert PublicComment.objects.get(pk=world["comment"].pk).hidden
    assert ChangeLog.objects.filter(model="academia360.PublicComment", field="hidden", new="True").exists()
    page = client.get("/academia360/institutions/technion/").content.decode()
    assert "תגובה גלויה" not in page.split('id="talk"', 1)[1]
    client.post("/academia360/manage/act/", {"action": "unhide", "comment": world["comment"].pk})
    assert not PublicComment.objects.get(pk=world["comment"].pk).hidden
