"""SPR-M.73 - Leaders who were appointed get the mail, and can get it again.

Lital, by mail, 2026-10-26 11:06: "2 מובילים שלי לירון ורונית לא קיבלו מיילים
גישה לכניסה לאתר כמובילים".

Three gaps behind it:
- appointing by email on /matazim/staff/leaders/ (the screen the bot pointed her
  to) made a leader in silence, and left a waiting candidate unapproved;
- there was no way to send the mail again;
- the screens said "sent" whenever the provider's error was swallowed.
"""

import pytest
from django.contrib.auth.models import User
from django.core import mail

LEADERS = "/matazim/staff/leaders/"


def _user(name):
    return User.objects.create_user(username=f"{name}@example.com", email=f"{name}@example.com",
                                    password="sprm73-pass")


@pytest.fixture
def pm(db):
    from matazim.models import Institution

    user = _user("pm")
    Institution.objects.create(name="רשת עתיד").managers.add(user)
    return user


def test_appointing_by_email_sends_the_leader_mail(client, pm):
    from matazim.models import Leader

    ronit = _user("ronit")
    client.force_login(pm)
    mail.outbox.clear()

    resp = client.post(LEADERS, {"action": "add", "email": ronit.email})

    leader = Leader.objects.get(user=ronit)
    assert leader.is_approved and leader.is_active
    assert [m.to for m in mail.outbox] == [[ronit.email]]
    body = mail.outbox[0].body
    assert "/matazim/leader/" in body
    assert f"נכנסים עם האימייל הזה: {ronit.email}" in body
    assert "נשלח אליו/ה מייל" in resp.content.decode()


def test_appointing_a_waiting_candidate_approves_them(client, pm):
    """Signed up through the open invite, then appointed here: a leader now."""
    from matazim.access import institution_of, leader_of
    from matazim.models import Leader

    liron = _user("liron")
    Leader.objects.create(user=liron, institution=institution_of(pm), is_active=True)
    assert leader_of(liron) is None
    client.force_login(pm)

    client.post(LEADERS, {"action": "add", "email": liron.email})

    assert leader_of(liron) is not None
    assert Leader.objects.filter(user=liron).count() == 1


def test_another_programmes_leader_is_not_taken_over(client, pm):
    from django.utils import timezone

    from matazim.models import Institution, Leader

    far = _user("far")
    other = Institution.objects.create(name="רשת אחרת")
    Leader.objects.create(user=far, institution=other, approved_at=timezone.now())
    client.force_login(pm)
    mail.outbox.clear()

    resp = client.post(LEADERS, {"action": "add", "email": far.email})

    assert Leader.objects.get(user=far).institution == other
    assert mail.outbox == []
    assert "כבר משויך לתוכנית אחרת" in resp.content.decode()


def test_the_leader_page_sends_the_mail_again(client, pm):
    from django.utils import timezone

    from matazim.access import institution_of
    from matazim.models import Leader

    ronit = _user("ronit")
    leader = Leader.objects.create(user=ronit, institution=institution_of(pm),
                                   approved_at=timezone.now(), approved_by=pm)
    client.force_login(pm)
    url = f"{LEADERS}{leader.pk}/"

    page = client.get(url).content.decode()
    assert 'value="send_access"' in page
    assert 'value="http://testserver/matazim/leader/"' in page

    mail.outbox.clear()
    resp = client.post(url, {"action": "send_access"})
    assert [m.to for m in mail.outbox] == [[ronit.email]]
    assert f"נשלח מייל אל {ronit.email}" in resp.content.decode()


def test_a_candidate_gets_no_access_mail_from_the_leader_page(client, pm):
    """The mail says "you are a leader"; a candidate is not one yet."""
    from matazim.access import institution_of
    from matazim.models import Leader

    cand = Leader.objects.create(user=_user("cand"), institution=institution_of(pm))
    client.force_login(pm)
    url = f"{LEADERS}{cand.pk}/"

    assert 'value="send_access"' not in client.get(url).content.decode()
    mail.outbox.clear()
    client.post(url, {"action": "send_access"})
    assert mail.outbox == []


def test_another_programmes_leader_page_cannot_send(client, pm):
    from django.utils import timezone

    from matazim.models import Institution, Leader

    other = Institution.objects.create(name="רשת אחרת")
    far = Leader.objects.create(user=_user("far"), institution=other, approved_at=timezone.now())
    client.force_login(pm)
    mail.outbox.clear()

    resp = client.post(f"{LEADERS}{far.pk}/", {"action": "send_access"})

    assert resp.status_code == 404
    assert mail.outbox == []


def test_a_mail_that_did_not_go_is_not_called_sent(client, pm, monkeypatch):
    """The provider failing used to read "נשלח"; now the screen says it did not."""
    from django.core.mail.backends.locmem import EmailBackend

    def refuse(self, messages):
        raise ConnectionError("provider down")

    monkeypatch.setattr(EmailBackend, "send_messages", refuse)
    ronit = _user("ronit")
    client.force_login(pm)

    html = client.post(LEADERS, {"action": "add", "email": ronit.email}).content.decode()
    assert "לא הצלחנו לשלוח מייל" in html
    assert "נשלח אליו/ה מייל" not in html

    html = client.post("/matazim/staff/team/", {"action": "approve", "email": ronit.email}).content.decode()
    assert "לא הצלחנו לשלוח מייל" in html


def test_an_emailed_invite_that_did_not_go_is_not_marked_sent(client, pm, monkeypatch):
    from django.core.mail.backends.locmem import EmailBackend

    from matazim.models import LeaderInvite

    monkeypatch.setattr(EmailBackend, "send_messages", lambda self, m: 0)
    client.force_login(pm)

    html = client.post("/matazim/staff/team/", {
        "action": "invite_personal", "label": "רונית", "email": "ronit@example.com",
    }).content.decode()

    assert LeaderInvite.objects.get().sent_at is None
    assert "לא הצלחנו לשלוח מייל" in html
