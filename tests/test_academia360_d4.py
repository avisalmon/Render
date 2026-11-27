"""Academia360 sprint D2.4: the review form (spec 4.3 "Review", backlog
D2.4): opening creates one review per member and moves a fresh submission
to "under review"; saving keeps answers; done sets the time and shows on the
board; another member's answers are hidden until mine is done and shown to
a chair; a leader is refused; every save is logged.
"""

import pytest
from academia360_d2_world import build, sign_in

from academia360.models import ChangeLog, Participation, Review, ReviewAnswer, Submission

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = ""


@pytest.fixture
def world(db):
    return build()


def url(world, sub="st"):
    return f"/academia360/committee/review/{world[sub].pk}/"


def test_opening_creates_my_review_once_and_moves_the_submission_to_under_review(client, world):
    assert client.get(url(world)).status_code == 403
    sign_in(client, world["lead"])
    assert client.get(url(world)).status_code == 403
    assert Review.objects.filter(submission=world["st"]).count() == 1  # yossi's only; a refused visit makes nothing
    sign_in(client, world["noa"])
    r = client.get(url(world))
    assert r.status_code == 200
    mine = Review.objects.get(submission=world["st"], reviewer=world["noa"])
    assert mine.status == "in_progress"
    assert Submission.objects.get(pk=world["st"].pk).status == "under_review"
    assert Participation.objects.get(pk=world["pt"].pk).status == "under_review"
    client.get(url(world))
    assert Review.objects.filter(submission=world["st"], reviewer=world["noa"]).count() == 1
    html = r.content.decode()
    # the form asks every active question, grouped, and not the retired one
    assert "ההגשה כוללת את כל הפרטים הנדרשים" in html and "נספח א׳ צורף" in html and "התייחסות למגוון שיטות פדגוגיות" in html
    assert "שאלה שבוטלה" not in html
    assert html.index("עמידה בדרישות פורמליות") < html.index("חדשנות בהוראה")
    assert ">0/3<" in html
    assert ChangeLog.objects.filter(model="academia360.Review", row_id=str(mine.pk), new="created").exists()
    assert ChangeLog.objects.filter(model="academia360.Submission", row_id=str(world["st"].pk), field="status",
                                    old="submitted", new="under_review").exists()


def test_saving_keeps_the_answers_and_done_stamps_the_time(client, world):
    sign_in(client, world["noa"])
    q1, q2, q3 = world["q1"], world["q2"], world["q3"]
    r = client.post(url(world), {
        "action": "save", f"q{q1.pk}_answer": "yes", f"q{q1.pk}_main": "הכול שם",
        f"q{q3.pk}_answer": "no", f"q{q3.pk}_notes": "חסרות שיטות", "overall_note": "בינתיים",
    })
    assert r.status_code == 302 and r["Location"] == url(world)
    mine = Review.objects.get(submission=world["st"], reviewer=world["noa"])
    assert mine.status == "in_progress" and mine.done_at is None and mine.overall_note == "בינתיים"
    answers = {a.question_id: a for a in mine.answers.all()}
    assert set(answers) == {q1.pk, q3.pk}
    assert answers[q1.pk].answer == "yes" and answers[q1.pk].main_points == "הכול שם"
    assert answers[q3.pk].answer == "no" and answers[q3.pk].improvement_notes == "חסרות שיטות"
    html = client.get(url(world)).content.decode()
    assert f'name="q{q1.pk}_answer" value="yes" checked' in html and "הכול שם" in html and ">2/3<" in html
    # a second save changes one answer, adds one, and is logged field by field
    before = ChangeLog.objects.count()
    client.post(url(world), {
        "action": "done", f"q{q1.pk}_answer": "partly", f"q{q1.pk}_main": "הכול שם",
        f"q{q2.pk}_answer": "na", f"q{q3.pk}_answer": "no", f"q{q3.pk}_notes": "חסרות שיטות", "overall_note": "סיימתי",
    })
    mine.refresh_from_db()
    assert mine.status == "done" and mine.done_at is not None and mine.overall_note == "סיימתי"
    assert mine.answers.count() == 3 and mine.answers.get(question=q1).answer == "partly"
    assert ChangeLog.objects.filter(model="academia360.ReviewAnswer", field="answer", old="yes", new="partly").exists()
    assert ChangeLog.objects.filter(model="academia360.Review", field="status", old="in_progress", new="done").exists()
    assert ChangeLog.objects.count() > before
    # the board and the file show it
    board = client.get("/academia360/committee/").content.decode()
    assert ">2/2<" in board and "שום סקירה לא מחכה לך" in board
    # reopen
    client.post(url(world), {"action": "reopen", f"q{q1.pk}_answer": "partly", f"q{q2.pk}_answer": "na", f"q{q3.pk}_answer": "no"})
    mine.refresh_from_db()
    assert mine.status == "in_progress" and mine.done_at is None
    # a junk mark is dropped, not saved
    client.post(url(world), {"action": "save", f"q{q1.pk}_answer": "maybe"})
    assert ReviewAnswer.objects.get(review=mine, question=q1).answer == ""


def test_another_members_answers_open_after_mine_is_done_and_always_for_a_chair(client, world):
    sign_in(client, world["noa"])
    ry = world["ry"]
    other = f"/academia360/committee/review/{world['st'].pk}/{ry.pk}/"
    html = client.get(url(world)).content.decode()
    assert "יוסי" in html and "נפתחת אחרי שהסקירה שלך תושלם" in html and f'href="{other}"' not in html
    assert client.get(other).status_code == 403
    assert "תכנית בשלה" not in html
    client.post(url(world), {"action": "done", f"q{world['q1'].pk}_answer": "yes"})
    html = client.get(url(world)).content.decode()
    assert f'href="{other}"' in html
    r = client.get(other)
    assert r.status_code == 200
    page = r.content.decode()
    assert "הסקירה של" in page and "יוסי" in page and "תכנית בשלה" in page and "הכול צורף" in page
    assert "<textarea" not in page  # read only
    assert "לפרט שיטות הערכה" in page
    # a chair reads it without a review of her own
    sign_in(client, world["shira"])
    assert client.get(other).status_code == 200
    # my own review's "other" link goes to my form
    sign_in(client, world["yossi"])
    r = client.get(other)
    assert r.status_code == 302 and r["Location"] == url(world)
    # a review of another submission is not reachable through this one
    sign_in(client, world["shira"])
    assert client.get(f"/academia360/committee/review/{world['sh'].pk}/{ry.pk}/").status_code == 404


def test_a_responded_submission_can_still_be_reviewed_without_moving_back(client, world):
    sign_in(client, world["shira"])
    assert client.get(url(world, "sh")).status_code == 200
    assert Submission.objects.get(pk=world["sh"].pk).status == "responded"
    assert Participation.objects.get(institution=world["haifa"]).status == "responded"
