"""SPR-M.82 - Beside each name: passed, or did not pass, and the student is told.

Lital, by mail, 2026-10-31 11:29: "אבל אני ביקשתי ממך שלמוביל תהיה אופציה
לאשר/לא לאשר את הקובץ של התלמיד. ליד כל שם של תלמיד יכול המוביל לאשר לנבחרת או
להחליט שלא אישר (מי שלא אישר תשלח הודעה לתלמיד שלא עבר לסיירת התלמידים של מטצים)
שמי שכן עבר יישלח הודעה שכן עבר" (REQ-M.214).
"""

import re

from django.core import mail
from django.urls import reverse

from tests.test_spr_m_78 import _attempt, _decide, world  # noqa: F401

LUCK = "הפעם לא עברת את מבחן המיון לסיירת התלמידים של מטצים. אנחנו מאחלים לך המון הצלחה."
PATROL = "עברת את מבחני המיון לתכנית מטצים ונכנסת לסיירת"


def _row(html, attempt):
    found = re.search(rf'<article[^>]*id="attempt-{attempt.pk}".*?</article>', html, re.S)
    assert found, "the row is on the page"
    return found.group(0)


def _page(client):
    return client.get(reverse("matazim:leader_tests")).content.decode()


def test_each_name_has_passed_and_did_not_pass_side_by_side(client, world):  # noqa: F811
    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    row = _row(_page(client), attempt)

    choice = re.search(r'<p class="mz-entrance-choice">(.*?)</p>', row, re.S)
    assert choice, "the two buttons sit together"
    buttons = re.findall(r'<button[^>]*value="(\w+)"[^>]*>([^<]*)</button>', choice.group(1))
    assert buttons == [
        ("approve", "עבר/ה: אישור והכנסה לסיירת"),
        ("not_passed", "לא עבר/ה: לא לאשר"),
    ]
    # The message on approving is ticked, as Lital asked on 31.10 07:49.
    assert 'name="tell" value="1" checked' in row
    # Sending back for fixing is still there, folded, and the old box is gone.
    fix = re.search(r'<details class="mz-entrance-fix">.*?</details>', row, re.S)
    assert fix and 'value="return"' in fix.group(0) and 'name="note"' in fix.group(0)
    assert 'name="luck"' not in row


def test_did_not_pass_tells_the_student_in_one_press(client, world):  # noqa: F811
    from matazim.models import EntranceAttempt, Notification

    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    mail.outbox.clear()

    resp = _decide(client, attempt, action="not_passed")
    assert resp.status_code == 302 and "luck=1" in resp["Location"]

    attempt.refresh_from_db()
    assert attempt.decision == EntranceAttempt.RETURNED and attempt.not_passed
    assert attempt.decided_by == world["liron"].user
    assert not attempt.member.has_passed_entrance_test()
    assert list(Notification.objects.filter(user=world["noa"]).values_list("text", flat=True)) == [LUCK]
    assert [m.to for m in mail.outbox] == [["noa@example.com"]]
    assert LUCK in mail.outbox[0].body

    row = _row(client.get(resp["Location"]).content.decode(), attempt)
    assert "לא עבר/ה, נשלחה הודעה" in row
    assert "נשלחה לנועה הודעה שלא עבר/ה את מבחן המיון" in row
    # Told once: the button does not offer itself again, but a change of mind can approve.
    assert 'value="not_passed"' not in row and 'value="approve"' in row
    # The wish is not shown as a note "what to fix".
    assert "מה נכתב לתלמיד/ה" not in row


def test_passed_tells_the_student_and_clears_did_not_pass(client, world):  # noqa: F811
    from matazim.models import EntranceAttempt, Notification

    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    _decide(client, attempt, action="not_passed")
    mail.outbox.clear()

    _decide(client, attempt, action="approve", tell="1")
    attempt.refresh_from_db()
    assert attempt.decision == EntranceAttempt.APPROVED and not attempt.not_passed
    assert attempt.member.has_passed_entrance_test()
    assert Notification.objects.filter(user=world["noa"], text__contains=PATROL).count() == 1
    assert PATROL in mail.outbox[0].body


def test_did_not_pass_after_a_fix_note_keeps_the_note(client, world):  # noqa: F811
    from matazim.models import Notification

    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    _decide(client, attempt, action="return", note="המידות לא נכונות")
    attempt.refresh_from_db()
    assert not attempt.not_passed
    assert "לא אושר, נשלח לתיקון" in _row(_page(client), attempt)

    _decide(client, attempt, action="not_passed")
    attempt.refresh_from_db()
    assert attempt.not_passed and attempt.decision_note == "המידות לא נכונות"
    assert Notification.objects.filter(user=world["noa"], text=LUCK).count() == 1


def test_an_approved_student_cannot_be_told_they_did_not_pass(client, world):  # noqa: F811
    from matazim.models import EntranceAttempt, Notification

    attempt = _attempt(world["noa"])
    client.force_login(world["liron"].user)
    _decide(client, attempt, action="approve")
    _decide(client, attempt, action="not_passed")
    attempt.refresh_from_db()
    assert attempt.decision == EntranceAttempt.APPROVED and not attempt.not_passed
    assert not Notification.objects.filter(user=world["noa"], text=LUCK).exists()


def test_the_programme_team_sees_the_leaders_buttons_and_cannot_press_them(client, world):  # noqa: F811
    from matazim.models import Notification

    attempt = _attempt(world["noa"])
    client.force_login(world["pm"])
    client.get(f"/matazim/as-leader/?leader={world['liron'].pk}")

    html = _page(client)
    row = _row(html, attempt)
    preview = re.search(r'<div class="mz-entrance-decide mz-entrance-preview">(.*?)</div>', row, re.S)
    assert preview, "the leader's buttons are shown to the team"
    labels = re.findall(r"<button[^>]*disabled>([^<]*)</button>", preview.group(1))
    assert labels == ["עבר/ה: אישור והכנסה לסיירת", "לא עבר/ה"]
    assert "<form" not in row
    assert reverse("matazim:leader_decide", args=[attempt.pk]) not in html
    assert "רק המוביל/ה יכולים ללחוץ עליהם" in html

    assert _decide(client, attempt, action="not_passed").status_code == 403
    assert not Notification.objects.filter(user=world["noa"]).exists()
