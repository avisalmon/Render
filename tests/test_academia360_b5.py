"""Academia360 sprint B.5: the public talks back (spec 4.1; backlog B.5).

Anonymous visitors read comments and are sent to sign in when they try to
write; a signed-in person comments, likes and proposes a correction, and
sees their own proposals' status at /academia360/me/; a chair's decision
through the API shows on the proposer's page; every write is logged; typed
text is kept as text.
"""

import pytest
from django.contrib.auth.models import User

from academia360.models import (
    ChangeLog,
    CommitteeAttribute,
    CorrectionProposal,
    Institution,
    Like,
    Program,
    PublicComment,
    Researcher,
    Role,
)

pytestmark = pytest.mark.django_db

PW = "talk-4410-pw"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"


@pytest.fixture
def world(db):
    program = Program.objects.create(slug="academia-360", name="אקדמיה 360")
    inst = Institution.objects.create(slug="technion", name_he="הטכניון", kind=Institution.UNIVERSITY, city="חיפה", founded=1912)
    r = Researcher.objects.create(institution=inst, slug="mannor", name_he="שי מנור", areas="למידת חיזוק")
    dana = User.objects.create_user("dana@example.com", "dana@example.com", PW, first_name="דנה")
    chair = User.objects.create_user("chair@example.com", "chair@example.com", PW)
    Role.objects.create(user=chair, kind=Role.COMMITTEE_MEMBER)
    CommitteeAttribute.objects.create(user=chair, kind=CommitteeAttribute.CHAIR, program=program)
    return {"inst": inst, "r": r, "dana": dana, "chair": chair}


def _in(client, who):
    assert client.login(username=who.email, password=PW)


def test_anonymous_reads_the_comments_and_is_sent_to_sign_in_to_write(client, world):
    PublicComment.objects.create(author=world["dana"], institution=world["inst"], body="תגובה קיימת")
    html = client.get("/academia360/institutions/technion/").content.decode()
    talk = html.split('id="talk"', 1)[1]
    assert "תגובה קיימת" in talk and "דנה" in talk
    assert "כניסה" in talk and 'name="body"' not in talk
    r = client.post("/academia360/talk/comment/", {"institution": "technion", "body": "שלום"})
    assert r.status_code == 302 and r.url.startswith("/academia360/login/?next=")
    assert PublicComment.objects.count() == 1
    r = client.post("/academia360/talk/like/", {"institution": "technion"})
    assert r.status_code == 302 and "/login/" in r.url and Like.objects.count() == 0


def test_a_signed_in_person_comments_likes_and_unlikes_and_it_is_all_logged(client, world):
    _in(client, world["dana"])
    r = client.post("/academia360/talk/comment/", {"institution": "technion", "body": "<b>נהדר</b> <script>x</script>",
                                                   "next": "/academia360/institutions/technion/"})
    assert r.status_code == 302 and r.url == "/academia360/institutions/technion/"
    c = PublicComment.objects.get()
    assert c.body == "נהדר" and c.author == world["dana"] and c.institution == world["inst"]
    assert ChangeLog.objects.filter(model="academia360.PublicComment", row_id=str(c.pk), by=world["dana"],
                                    actor_kind=ChangeLog.PERSON).exists()
    client.post("/academia360/talk/like/", {"researcher": "mannor"})
    assert Like.objects.filter(user=world["dana"], researcher=world["r"]).count() == 1
    page = client.get("/academia360/researchers/mannor/").content.decode()
    assert 'aria-pressed="true"' in page and 'name="body"' in page
    client.post("/academia360/talk/like/", {"researcher": "mannor"})
    assert Like.objects.count() == 0
    assert ChangeLog.objects.filter(model="academia360.Like", new="deleted").exists()


def test_an_empty_comment_and_a_flood_are_refused(client, world):
    _in(client, world["dana"])
    client.post("/academia360/talk/comment/", {"institution": "technion", "body": " "})
    assert PublicComment.objects.count() == 0
    for i in range(20):
        PublicComment.objects.create(author=world["dana"], institution=world["inst"], body=f"תגובה {i}")
    client.post("/academia360/talk/comment/", {"institution": "technion", "body": "עוד אחת"})
    assert PublicComment.objects.count() == 20


def test_a_correction_is_proposed_decided_by_a_chair_and_its_status_reaches_the_proposer(client, world):
    _in(client, world["dana"])
    r = client.post("/academia360/talk/correct/", {"institution": "technion", "field": "founded",
                                                   "proposed_value": "1924", "reason": "אתר הטכניון"})
    assert r.status_code == 302
    p = CorrectionProposal.objects.get()
    assert (p.model, p.row_id, p.field, p.current_value, p.proposed_value, p.status) == \
        ("academia360.Institution", str(world["inst"].pk), "founded", "1912", "1924", "open")
    me = client.get("/academia360/me/").content.decode()
    assert "הטכניון" in me and "שנת ההקמה" in me and "1924" in me and "פתוחה" in me
    page = client.get("/academia360/institutions/technion/").content.decode()
    assert "פתוחה" in page.split('id="talk"', 1)[1]
    client.logout()
    _in(client, world["chair"])
    r = client.patch(f"/academia360/api/correctionproposals/{p.pk}/", {"status": "accepted"},
                     content_type="application/json")
    assert r.status_code == 200, r.content
    client.logout()
    _in(client, world["dana"])
    me = client.get("/academia360/me/").content.decode()
    assert "התקבלה" in me and "פתוחה" not in me.split("הצעות התיקון שלי", 1)[1].split("</section>", 1)[0]


def test_an_unknown_field_falls_back_to_other_and_a_bad_target_is_404(client, world):
    _in(client, world["dana"])
    client.post("/academia360/talk/correct/", {"researcher": "mannor", "field": "salary", "proposed_value": "משהו"})
    p = CorrectionProposal.objects.get()
    assert p.field == "" and p.current_value == "" and p.model == "academia360.Researcher"
    assert client.post("/academia360/talk/correct/", {"institution": "nope", "proposed_value": "x"}).status_code == 404
    assert client.get("/academia360/talk/comment/").status_code == 405


def test_me_needs_sign_in_and_the_bar_shows_it_only_to_the_signed_in(client, world):
    r = client.get("/academia360/me/")
    assert r.status_code == 302 and "/login/" in r.url
    anon = client.get("/academia360/").content.decode().split("<header", 1)[1].split("</header>", 1)[0]
    assert "/academia360/me/" not in anon
    _in(client, world["dana"])
    bar = client.get("/academia360/").content.decode().split("<header", 1)[1].split("</header>", 1)[0]
    assert "/academia360/me/" in bar
