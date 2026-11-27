"""Academia360 sprint E.4: the letter (spec 4.3 "Letters", "Reviewing the
letters"; backlog E.4): a general section edited once changes every draft
that uses it; first open makes the draft with the addressee and the general
sections; unticking removes a section row; "draft from the reviews" writes
a section per criterion that has material; an emptied section is deleted;
comments sit under the draft; the history lists the changes; a leader is
refused.
"""

import pytest
from academia360_d2_world import build, sign_in

from academia360 import discuss, letters
from academia360.models import (
    ChangeLog,
    Discussion,
    LetterSection,
    LetterTemplateSection,
    Notification,
    ResponseLetter,
)

pytestmark = pytest.mark.django_db

GENERAL = "/academia360/committee/letters/general/"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = ""


@pytest.fixture
def world(db):
    w = build()
    w["g1"] = LetterTemplateSection.objects.create(program=w["program"], title="הערות כלליות", body="הוועדה קראה את כל ההגשות.", order=0)
    w["g2"] = LetterTemplateSection.objects.create(program=w["program"], title="לוח הזמנים", body="דיווח ראשון עד **סוף תשפ״ו**.", order=1)
    return w


def url(world, key="st"):
    return f"/academia360/committee/letter/{world[key].pk}/"


def test_the_letter_screens_are_the_committees(client, world):
    for who in (None, world["lead"], world["dana"]):
        if who is not None:
            sign_in(client, who)
        assert client.get(GENERAL).status_code == 403
        assert client.get(url(world)).status_code == 403
        client.logout()
    assert ResponseLetter.objects.filter(submission=world["st"]).count() == 0  # a refused visit makes no draft
    sign_in(client, world["noa"])
    assert client.get(GENERAL).status_code == 200
    assert client.get(url(world)).status_code == 200


def test_general_sections_are_written_once_and_change_every_draft(client, world):
    sign_in(client, world["noa"])
    page = client.get(GENERAL).content.decode()
    assert "הוועדה קראה את כל ההגשות." in page and "לוח הזמנים" in page
    g1, g2 = world["g1"], world["g2"]
    r = client.post(GENERAL, {
        f"g{g1.pk}_title": "הערות כלליות", f"g{g1.pk}_body": "הוועדה קראה את כל 28 ההגשות.",
        f"g{g2.pk}_title": "", f"g{g2.pk}_body": "",  # removed
        "new_title": "מה הלאה", "new_body": "פגישת מעקב בחורף.",
    })
    assert r.status_code == 302
    rows = letters.general_sections(world["program"])
    assert [(x.title, x.body, x.order) for x in rows] == [("הערות כלליות", "הוועדה קראה את כל 28 ההגשות.", 0), ("מה הלאה", "פגישת מעקב בחורף.", 1)]
    assert ChangeLog.objects.filter(model="academia360.LetterTemplateSection", row_id=str(g1.pk), field="body").exists()
    assert ChangeLog.objects.filter(model="academia360.LetterTemplateSection", row_id=str(g2.pk), old="deleted").exists()
    # a draft that uses the section shows the new text, through the one shared row
    client.get(url(world))
    letter = ResponseLetter.objects.get(submission=world["st"])
    assert "הוועדה קראה את כל 28 ההגשות." in letters.text_of(letter)
    LetterTemplateSection.objects.filter(pk=g1.pk).update(body="נוסח שלישי.")
    assert "נוסח שלישי." in letters.text_of(ResponseLetter.objects.get(pk=letter.pk))
    # the sent letter of haifa is untouched: it has its own specific text and no general rows
    assert "נוסח שלישי." not in letters.text_of(world["letter"])


def test_first_open_makes_the_draft_with_the_addressee_and_the_general_sections(client, world):
    sign_in(client, world["shira"])
    assert client.get(url(world)).status_code == 200
    letter = ResponseLetter.objects.get(submission=world["st"])
    assert letter.addressee_name == "רונית כהן" and letter.addressee_title == "סמנכ״לית אקדמית" and letter.drafted_by_id == world["shira"].pk
    assert letter.sent_at is None
    parts = letters.sections_of(letter)
    assert [s.template_id for s in parts["general"]] == [world["g1"].pk, world["g2"].pk] and parts["specific"] == [] and parts["closing"] is None
    assert ChangeLog.objects.filter(model="academia360.ResponseLetter", row_id=str(letter.pk), new="created").exists()
    client.get(url(world))
    assert ResponseLetter.objects.filter(submission=world["st"]).count() == 1
    page = client.get(url(world)).content.decode()
    assert 'value="רונית כהן"' in page and f'name="general_{world["g1"].pk}" value="1" checked' in page
    assert "לשלוח למוסד" in page  # shira is a chair
    sign_in(client, world["noa"])
    assert "לשלוח למוסד" not in client.get(url(world)).content.decode()
    # the board and the file point at the draft
    board = client.get("/academia360/committee/").content.decode()
    assert f'href="{url(world)}"' in board
    # sapir has no letter yet: the file offers to write one, the board links the same way
    assert f'href="{url(world, "ss")}"' in client.get("/academia360/committee/sapir/").content.decode()


def test_saving_keeps_the_addressee_the_ticked_generals_the_specifics_and_the_closing(client, world):
    sign_in(client, world["noa"])
    client.get(url(world))
    letter = ResponseLetter.objects.get(submission=world["st"])
    g1, g2 = world["g1"], world["g2"]
    r = client.post(url(world), {
        "action": "save", "addressee_name": "פרופ׳ רונית כהן", "addressee_title": "המשנה לנשיא",
        f"general_{g1.pk}": "1",  # g2 unticked
        "s_new": "חדשנות בהוראה\n- לפרט שיטות הערכה", "closing_body": "נשמח לעמוד לרשותכם.",
    })
    assert r.status_code == 302
    letter.refresh_from_db()
    assert letter.addressee_name == "פרופ׳ רונית כהן" and letter.addressee_title == "המשנה לנשיא"
    parts = letters.sections_of(letter)
    assert [s.template_id for s in parts["general"]] == [g1.pk]
    assert [s.body for s in parts["specific"]] == ["חדשנות בהוראה\n- לפרט שיטות הערכה"] and parts["closing"].body == "נשמח לעמוד לרשותכם."
    assert ChangeLog.objects.filter(model="academia360.LetterSection", old="deleted").count() == 1
    spec = parts["specific"][0]
    # edit one, empty the closing, tick g2 back, add another
    client.post(url(world), {
        "action": "save", "addressee_name": "פרופ׳ רונית כהן", "addressee_title": "המשנה לנשיא",
        f"general_{g1.pk}": "1", f"general_{g2.pk}": "1",
        f"s{spec.pk}_body": "חדשנות בהוראה\n- לפרט שיטות הערכה\n- להוסיף מדד", "s_new": "קהילה\n- לציין שותפים", "closing_body": "",
    })
    parts = letters.sections_of(letter)
    assert [s.template_id for s in parts["general"]] == [g1.pk, g2.pk]
    assert [s.body for s in parts["specific"]] == ["חדשנות בהוראה\n- לפרט שיטות הערכה\n- להוסיף מדד", "קהילה\n- לציין שותפים"]
    assert parts["closing"] is None
    assert ChangeLog.objects.filter(model="academia360.LetterSection", row_id=str(spec.pk), field="body").exists()
    # emptying a specific removes it
    client.post(url(world), {"action": "save", f"general_{g1.pk}": "1", f"general_{g2.pk}": "1", f"s{spec.pk}_body": ""})
    assert not LetterSection.objects.filter(pk=spec.pk).exists()
    # the history lists it all, newest first
    page = client.get(url(world)).content.decode()
    assert "ההיסטוריה" in page and "נמחק" in page and "נוצר" in page
    text = letters.text_of(letter)
    assert "לכבוד" in text and "פרופ׳ רונית כהן" in text and "הטכניון" in text and "הנדון:" in text and "קהילה" in text
    assert "סוף תשפ״ו" in text and "**" not in text  # markdown marks are dropped in the plain text


def test_draft_from_the_reviews_writes_a_section_per_criterion_with_material(client, world):
    sign_in(client, world["noa"])
    # technion: yossi's done review has one note under innovation; no analysis yet
    drafted = letters.drafted_specific(world["st"], [world["formal"], world["innovation"]])
    assert [(c.slug, lines) for c, lines in drafted] == [("innovation", ["לפרט שיטות הערכה"])]
    r = client.post(url(world), {"action": "draft", f"general_{world['g1'].pk}": "1"})
    assert r.status_code == 302 and r["Location"].endswith("#specific")
    letter = ResponseLetter.objects.get(submission=world["st"])
    specifics = letters.sections_of(letter)["specific"]
    assert [s.body for s in specifics] == ["חדשנות בהוראה\n- לפרט שיטות הערכה"]
    # haifa's analysis has a challenge under innovation and its letter was sent: drafting works on the material alone
    drafted = letters.drafted_specific(world["sh"], [world["formal"], world["innovation"]])
    assert [(c.slug, lines) for c, lines in drafted] == [("innovation", ["אין תכנית הערכה"])]
    # sapir has nothing: the draft says so and writes nothing
    r = client.post(url(world, "ss"), {"action": "draft"}, follow=True)
    assert "אין עדיין חומר" in r.content.decode()
    assert letters.sections_of(ResponseLetter.objects.get(submission=world["ss"]))["specific"] == []
    # drafting again replaces, never doubles
    client.post(url(world), {"action": "draft", f"general_{world['g1'].pk}": "1"})
    assert LetterSection.objects.filter(letter=letter, kind="specific").count() == 1


def test_comments_on_the_draft_live_in_one_thread_under_it(client, world):
    sign_in(client, world["noa"])
    client.get(url(world))
    page = client.get(url(world)).content.decode()
    assert "עוד אין הערות על הטיוטה" in page
    thread = Discussion.objects.get(submission=world["st"], title=discuss.LETTER_THREAD)
    r = client.post(f"/academia360/committee/discuss/{thread.pk}/", {"action": "reply", "body": "הסיום **חלש**.", "next": url(world) + "#comments",
                                                                      "mention": [world["shira"].pk]})
    assert r.status_code == 302 and r["Location"] == url(world) + "#comments"
    page = client.get(url(world)).content.decode()
    assert "<strong>חלש</strong>" in page and "נועה" in page
    assert Notification.objects.filter(user=world["shira"], kind="mention").exists()
    # a foreign "next" is ignored
    r = client.post(f"/academia360/committee/discuss/{thread.pk}/", {"action": "reply", "body": "עוד", "next": "https://evil.example/"})
    assert r["Location"].startswith(f"/academia360/committee/discuss/{thread.pk}/")
    # the file shows the thread among the submission's discussions
    assert discuss.LETTER_THREAD in client.get("/academia360/committee/technion/").content.decode()
