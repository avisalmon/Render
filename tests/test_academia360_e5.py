"""Academia360 sprint E.5: sending, the letter page, the PDF (spec 4.4 "Send
letters", 2.6.5, 4.7; backlog E.5): a member cannot send; sending stamps,
files a PDF that opens, moves the statuses, notifies and mails the leaders;
before sending the leader gets "no access" and after it reads the page; a
leader of another institution is refused; the PDF holds the addressee and
the sections; an uploaded signed file is kept.
"""

import pytest
from academia360_d2_world import build, sign_in
from django.core import mail as dj_mail
from django.core.files.base import ContentFile

from academia360 import letter_pdf, letters
from academia360.models import (
    AccessLog,
    ChangeLog,
    LetterTemplateSection,
    Notification,
    Participation,
    ResponseLetter,
    Submission,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = ""


@pytest.fixture
def world(db):
    w = build()
    LetterTemplateSection.objects.create(program=w["program"], title="הערות כלליות", body="הוועדה קראה את כל ההגשות.", order=0)
    return w


def draft_url(world, key="st"):
    return f"/academia360/committee/letter/{world[key].pk}/"


def pdf_text(data):
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return doc.page_count, "\n".join(page.get_text() for page in doc)


def test_the_pdf_is_drawn_from_the_composition_and_opens(world):
    letter = world["letter"]  # haifa's sent letter, one specific section
    blocks = letters.compose(letter)
    kinds = [k for k, _ in blocks]
    texts = [t for _, t in blocks]
    assert kinds[:3] == ["header", "date", "to"] and "subject" in kinds and kinds[-2:] == ["sign", "sign"]
    assert "פרופ׳ גור אלרואי" in texts and "הנשיא" in texts and "אוניברסיטת חיפה" in texts
    assert any(t.startswith("הנדון:") for t in texts) and "הוועדה מברכת על התכנית." in texts
    assert texts[1] == "01.04.2025" and texts[-1] == "שירה"
    data = letter_pdf.render(letter)
    assert data[:5] == b"%PDF-"
    pages, text = pdf_text(data)
    assert pages == 1 and "360" in text and "01.04.2025" in text
    # a long letter turns the page and keeps the pilot line on each
    long_blocks = blocks[:-2] + [("p", "שורה של טקסט שחוזרת על עצמה כדי למלא את העמוד " * 3)] * 60 + blocks[-2:]
    pages, text = pdf_text(letter_pdf.render_blocks(long_blocks))
    assert pages >= 2 and text.count("פיילוט") == pages  # the pilot line on every page


def test_only_a_chair_sends_and_sending_opens_the_letter_to_the_leaders(client, world):
    sign_in(client, world["noa"])
    client.get(draft_url(world))
    letter = ResponseLetter.objects.get(submission=world["st"])
    r = client.post(draft_url(world), {"action": "send", "addressee_name": "רונית כהן"})
    assert r.status_code == 403
    letter.refresh_from_db()
    assert letter.sent_at is None
    # the leader cannot read the draft, as a page or as a PDF
    sign_in(client, world["lead"])
    assert client.get(f"/academia360/letters/{letter.pk}/").status_code == 403
    assert client.get(f"/academia360/letters/{letter.pk}/pdf/").status_code == 403
    # the chair sends
    sign_in(client, world["shira"])
    dj_mail.outbox.clear()
    r = client.post(draft_url(world), {"action": "send", "addressee_name": "רונית כהן", "addressee_title": "סמנכ״לית אקדמית",
                                       "s_new": "חדשנות בהוראה\n- לפרט שיטות הערכה", "closing_body": "בהצלחה."})
    assert r.status_code == 302
    letter.refresh_from_db()
    assert letter.sent_at is not None and letter.sent_by_id == world["shira"].pk
    assert letter.file and letter.file.name.endswith(".pdf")
    with letter.file.storage.open(letter.file.name, "rb") as fh:
        pages, text = pdf_text(fh.read())
    assert pages >= 1 and "360" in text
    assert "רונית כהן" in letter.extracted_text and "לפרט שיטות הערכה" in letter.extracted_text
    assert Submission.objects.get(pk=world["st"].pk).status == "responded"
    assert Participation.objects.get(pk=world["pt"].pk).status == "responded"
    assert ChangeLog.objects.filter(model="academia360.ResponseLetter", row_id=str(letter.pk), field="sent_at").exists()
    assert ChangeLog.objects.filter(model="academia360.Submission", row_id=str(world["st"].pk), field="status", new="responded").exists()
    told = Notification.objects.filter(kind="letter")
    assert list(told.values_list("user__email", flat=True)) == ["lead@example.com"]
    assert told.first().url == f"/academia360/letters/{letter.pk}/"
    assert len(dj_mail.outbox) == 1 and dj_mail.outbox[0].to == ["lead@example.com"] and f"/academia360/letters/{letter.pk}/" in dj_mail.outbox[0].body
    # the draft screen is now a record
    page = client.get(draft_url(world)).content.decode()
    assert 'name="addressee_name"' not in page and 'name="s_new"' not in page and "לשלוח למוסד" not in page
    assert "נשלח" in page and "רונית כהן" in page and "לפרט שיטות הערכה" in page
    r = client.post(draft_url(world), {"action": "save", "addressee_name": "אחר"})
    assert r.status_code == 302 and ResponseLetter.objects.get(pk=letter.pk).addressee_name == "רונית כהן"
    # the board and the file show "sent"
    assert "נשלח" in client.get("/academia360/committee/").content.decode()
    # sending twice does nothing
    assert letters.send(_Req(world["shira"]), letter) == (False, 0)


class _Req:
    def __init__(self, user):
        self.user = user
        self.GET = {}
        self.headers = {}
        self.META = {"HTTP_HOST": "testserver"}

    def build_absolute_uri(self, path):
        return "http://testserver" + path


def test_the_leader_reads_the_sent_letter_as_a_page_and_as_a_pdf_and_nobody_else_does(client, world):
    letter = world["letter"]  # haifa, sent; technion's lead is not haifa's
    sign_in(client, world["lead"])
    assert client.get(f"/academia360/letters/{letter.pk}/").status_code == 403
    from academia360.models import LeaderOf
    LeaderOf.objects.create(user=world["lead"], institution=world["haifa"], title="רקטור")
    world["lead"]._a360_leads = None
    r = client.get(f"/academia360/letters/{letter.pk}/")
    assert r.status_code == 200
    page = r.content.decode()
    assert "פרופ׳ גור אלרואי" in page and "הוועדה מברכת על התכנית." in page and "הנדון:" in page
    assert "לערוך את הטיוטה" not in page and "committee/" not in page.split('class="a360-letter-paper"')[0].split("</nav>")[1]
    assert AccessLog.objects.filter(target_model="academia360.ResponseLetter", target_id=str(letter.pk), action="view").count() == 1
    r = client.get(f"/academia360/letters/{letter.pk}/pdf/")
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf" and r.content[:5] == b"%PDF-"
    assert AccessLog.objects.filter(target_model="academia360.ResponseLetter", target_id=str(letter.pk), action="download").count() == 1
    # the public and a stranger: no access
    sign_in(client, world["dana"])
    assert client.get(f"/academia360/letters/{letter.pk}/").status_code == 403
    client.logout()
    assert client.get(f"/academia360/letters/{letter.pk}/").status_code == 403
    # the committee reads any letter, a draft too
    sign_in(client, world["noa"])
    assert client.get(f"/academia360/letters/{letter.pk}/").status_code == 200


def test_an_uploaded_signed_file_is_kept_when_the_letter_is_sent(client, world):
    sign_in(client, world["shira"])
    client.get(draft_url(world))
    letter = ResponseLetter.objects.get(submission=world["st"])
    letter.file.save("signed.pdf", ContentFile(b"%PDF-1.4 signed by hand"), save=True)
    client.post(draft_url(world), {"action": "send", "addressee_name": "רונית כהן"})
    letter.refresh_from_db()
    assert letter.sent_at is not None and letter.file.name.endswith("signed.pdf")
    with letter.file.storage.open(letter.file.name, "rb") as fh:
        assert fh.read() == b"%PDF-1.4 signed by hand"
    # the institution without a leader: sent, nobody mailed, the message says so
    dj_mail.outbox.clear()
    client.get(draft_url(world, "ss"))
    r = client.post(draft_url(world, "ss"), {"action": "send"}, follow=True)
    assert "אין מוביל עם מייל" in r.content.decode() and dj_mail.outbox == []
    assert ResponseLetter.objects.get(submission=world["ss"]).sent_at is not None
