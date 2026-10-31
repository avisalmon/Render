"""SPR-M.80 - A good-luck message for a student who did not pass, and the parents' note.

Lital, by mail, 2026-10-31 08:58: "מבקשת גם אופציה לשלוח הודעה לתלמיד שלא עבר את
מבחן המיון ונאחל לו המון בהצלחה" (REQ-M.211).

Lital, by mail, 2026-10-31 08:59: "חשוב שבאישור הורים יבינו שזה אתר למידה עצמית ...
שבמהלכו התלמידים יכולים ללמוד עצמאית וכל מה שהם צריכים להכניס זה שם מלא ומייל"
(REQ-M.212).
"""

import re

import pytest
from django.core import mail
from django.urls import reverse

from tests.test_spr_m_78 import _attempt, _decide, world  # noqa: F401

# SPR-M.82 took Lital's words of 11:29: "לסיירת התלמידים של מטצים".
LUCK = "הפעם לא עברת את מבחן המיון לסיירת התלמידים של מטצים. אנחנו מאחלים לך המון הצלחה."


def _row(html, attempt):
    found = re.search(rf'<article[^>]*id="attempt-{attempt.pk}".*?</article>', html, re.S)
    assert found, "the row is on the page"
    return found.group(0)


def test_the_form_offers_the_good_luck_message(client, world):  # noqa: F811
    # SPR-M.82: the unticked box became its own button, `לא עבר/ה` (REQ-M.214).
    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    row = _row(client.get(reverse("matazim:leader_tests")).content.decode(), attempt)
    assert 'value="not_passed"' in row
    assert "הודעה שלא עבר/ה את מבחן המיון לסיירת, עם איחולי הצלחה" in row


def test_not_approving_with_good_luck_tells_the_student_and_needs_no_note(client, world):  # noqa: F811
    from matazim.models import EntranceAttempt, Notification

    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    mail.outbox.clear()

    resp = _decide(client, attempt, action="return", luck="1", note="")
    assert resp.status_code == 302 and "luck=1" in resp["Location"]

    attempt.refresh_from_db()
    assert attempt.decision == EntranceAttempt.RETURNED
    assert attempt.decision_note == LUCK
    assert not attempt.member.has_passed_entrance_test()

    notes = Notification.objects.filter(user=world["noa"])
    assert [n.text for n in notes] == [LUCK], "one message, the wish, not also 'back for fixing'"
    assert [m.to for m in mail.outbox] == [["noa@example.com"]]
    assert LUCK in mail.outbox[0].body

    row = _row(client.get(resp["Location"]).content.decode(), attempt)
    assert "נשלחה לנועה הודעה שלא עבר/ה את מבחן המיון" in row


def test_good_luck_keeps_the_leaders_note(client, world):  # noqa: F811
    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    _decide(client, attempt, action="return", luck="1", note="אפשר לנסות שוב בשנה הבאה")
    attempt.refresh_from_db()
    assert attempt.decision_note == "אפשר לנסות שוב בשנה הבאה"


def test_not_approving_without_the_box_is_as_before(client, world):  # noqa: F811
    from matazim.models import Notification

    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    resp = _decide(client, attempt, action="return", note="")
    assert "error=note" in resp["Location"]
    assert not Notification.objects.filter(user=world["noa"]).exists()

    _decide(client, attempt, action="return", note="המידות לא נכונות")
    texts = list(Notification.objects.filter(user=world["noa"]).values_list("text", flat=True))
    assert texts == ["מבחן הכניסה הוחזר לתיקון. יש הערה בשבילכם."]


def test_a_returned_row_sends_the_wish_on_its_own(client, world):  # noqa: F811
    from matazim.models import Notification

    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    _decide(client, attempt, action="return", note="המידות לא נכונות")

    row = _row(client.get(reverse("matazim:leader_tests")).content.decode(), attempt)
    # SPR-M.82: a row sent back for fixing still has `לא עבר/ה`, which sends the wish.
    assert 'value="not_passed"' in row

    resp = _decide(client, attempt, action="luck")
    assert "luck=1" in resp["Location"]
    assert Notification.objects.filter(user=world["noa"], text=LUCK).count() == 1


def test_the_wish_alone_needs_a_test_not_approved(client, world):  # noqa: F811
    from matazim.models import Notification

    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    _decide(client, attempt, action="luck")  # still waiting
    _decide(client, attempt, action="approve")
    _decide(client, attempt, action="luck")  # approved
    assert not Notification.objects.filter(user=world["noa"], text=LUCK).exists()


def test_looking_as_the_leader_cannot_send_the_wish(client, world):  # noqa: F811
    from matazim.models import Notification

    attempt = _attempt(world["noa"])
    client.force_login(world["pm"])
    client.get(f"/matazim/as-leader/?leader={world['liron'].pk}")
    assert _decide(client, attempt, action="return", luck="1").status_code == 403
    assert not Notification.objects.filter(user=world["noa"]).exists()


@pytest.mark.django_db
def test_the_parents_read_what_the_site_is_and_what_is_asked_of_them(client):
    html = client.get(reverse("matazim:register")).content.decode()
    block = re.search(r'<div id="mzGuardianBlock".*?</div>', html, re.S)
    assert block, "the parents' block is on the sign-up page"
    text = re.sub(r"\s+", " ", block.group(0))
    assert "זהו אתר למידה עצמית שבנו מתנדבי אינטל" in text
    assert "התלמידים לומדים בעצמם" in text
    assert "כל מה שצריך מההורה הוא שם מלא ואימייל" in text
    assert "שם מלא של ההורה או האפוטרופוס" in text
    # Exactly the two things it promises, and the yes.
    assert re.findall(r'name="(guardian_\w+)"', block.group(0)) == [
        "guardian_name", "guardian_email", "guardian_consent",
    ]
