"""SPR-M.62 - a certificate follows the hand-in (REQ-M.179, Atid 2026-10-15).

"הענקת תעודה מהאתר רק לאחר הגשת התוצר למוביל." The gate is in matazim's
`finish_course`, server side. What these tests refuse to do is read the page
for the word: each one posts the press, which is the thing a person does.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from tests.test_spr_m_51 import (  # noqa: F401  (member is a fixture)
    PASSWORD,
    _course,
    _hand_in,
    _watch_everything,
    member,
)

pytestmark = pytest.mark.sprm62


def _ready(client, member, monkeypatch, slug="scratch"):
    """Everything babook asks for is done; only the hand-in to the leader is not."""
    course = _course(slug=slug)
    client.force_login(member)
    _watch_everything(member, course)
    _hand_in(client, course, 1, "111111111", monkeypatch)
    _hand_in(client, course, 2, "222222222", monkeypatch)
    return course


def _hand_in_and_approve(client, course, approve=True):
    """The product handed to the leader, and (Q27) approved by them."""
    from matazim.models import Submission

    client.post("/matazim/my-work/", {"title": "המבוך", "link": "https://a.example/x",
                                      "course": course.slug})
    if approve:
        Submission.objects.filter(title="המבוך").update(status=Submission.APPROVED)


def _finish(client, course):
    return client.post(f"/matazim/learn/{course.slug}/finish/")


def test_without_a_hand_in_the_press_is_refused_and_nothing_is_issued(client, member, monkeypatch):
    from app.models import CourseCertificate

    course = _ready(client, member, monkeypatch)
    resp = _finish(client, course)
    assert resp["Location"].endswith("?cert=handin"), resp["Location"]
    assert not CourseCertificate.objects.filter(user=member, course=course).exists()


def test_a_hand_in_for_a_different_course_does_not_open_it(client, member, monkeypatch):
    """The gate is per course, so one product cannot buy every certificate."""
    from app.models import CourseCertificate

    course = _ready(client, member, monkeypatch)
    _course(slug="scratch-advanced")
    client.post("/matazim/my-work/", {"title": "x", "link": "https://a.example/x",
                                      "course": "scratch-advanced"})
    assert _finish(client, course)["Location"].endswith("?cert=handin")
    assert not CourseCertificate.objects.filter(user=member, course=course).exists()


def test_a_free_standing_hand_in_with_no_course_does_not_open_it(client, member, monkeypatch):
    course = _ready(client, member, monkeypatch)
    client.post("/matazim/my-work/", {"title": "x", "link": "https://a.example/x"})
    assert _finish(client, course)["Location"].endswith("?cert=handin")


def test_a_made_up_course_name_is_not_stored(client, member, monkeypatch):
    """A hand-in filed under a name that is no course would satisfy nothing and
    look as if it did."""
    from matazim.models import Submission

    _ready(client, member, monkeypatch)
    client.post("/matazim/my-work/", {"title": "x", "link": "https://a.example/x",
                                      "course": "no-such-course"})
    assert Submission.objects.get(title="x").course_slug == ""


def test_an_approved_hand_in_opens_the_certificate(client, member, monkeypatch):
    from app.models import CourseCertificate
    from matazim.models import Submission

    course = _ready(client, member, monkeypatch)
    _hand_in_and_approve(client, course)
    sub = Submission.objects.get(title="המבוך")
    assert sub.course_slug == course.slug and sub.leader_id == member.matazim_student.first().leader_id
    assert _finish(client, course)["Location"].endswith("?cert=issued")
    assert CourseCertificate.objects.filter(user=member, course=course).exists()


@pytest.mark.parametrize("state", ["waiting", "returned"])
def test_a_hand_in_the_leader_has_not_approved_does_not_open_it(client, member, monkeypatch, state):
    """Q27, Avi 2026-10-15: "must be approved by the leader". Handed in and
    waiting is not enough, and neither is returned."""
    from app.models import CourseCertificate
    from matazim.models import Submission

    course = _ready(client, member, monkeypatch)
    _hand_in_and_approve(client, course, approve=False)
    Submission.objects.filter(title="המבוך").update(status=state)
    assert _finish(client, course)["Location"].endswith("?cert=handin")
    assert not CourseCertificate.objects.filter(user=member, course=course).exists()


def test_a_returned_then_resubmitted_then_approved_version_opens_it(client, member, monkeypatch):
    """The furthest the product has got is what counts, not the earlier versions."""
    from matazim.models import Submission

    course = _ready(client, member, monkeypatch)
    _hand_in_and_approve(client, course, approve=False)
    Submission.objects.filter(title="המבוך").update(status=Submission.RETURNED)
    client.post("/matazim/my-work/", {"title": "המבוך 2", "link": "https://a.example/y",
                                      "course": course.slug})
    Submission.objects.filter(title="המבוך 2").update(status=Submission.APPROVED)
    assert _finish(client, course)["Location"].endswith("?cert=issued")


def test_the_course_page_says_which_state_the_product_is_in(client, member, monkeypatch):
    from matazim.models import Submission

    course = _ready(client, member, monkeypatch)
    _hand_in_and_approve(client, course, approve=False)

    def panel():
        html = client.get(f"/matazim/learn/{course.slug}/").content.decode()
        start = html.index('id="mzCert"')
        return html[start:html.index("</section>", start)]

    assert "מחכה למוביל/ה" in panel()
    Submission.objects.filter(title="המבוך").update(status=Submission.RETURNED)
    assert "הוחזר לתיקון" in panel()


def test_the_course_page_shows_the_hand_in_as_the_next_step(client, member, monkeypatch):
    course = _ready(client, member, monkeypatch)
    html = client.get(f"/matazim/learn/{course.slug}/").content.decode()
    start = html.index('id="mzCert"')
    panel = html[start:html.index("</section>", start)]
    assert f'href="/matazim/my-work/?course={course.slug}"' in panel
    assert "להנפקת התעודה" not in panel  # the issue button is not offered yet
