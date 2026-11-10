"""SPR-M.83 - Lital, 2026-11-10 (mail, 21:33).

Her words: "נכנסתי למובילה עפיפה וראיתי שכאשר היא נכנסת להתקדמות של תלמיד היא לא רואה
את כל המסלול השנתי ... 2 קורסים של סקראץ, הגעה ליום שיא באינטל, 2 קורסים טינקד קאד,
2 קורסים בחירה, השתתפות בדנה הדרכה טוב, 2 פרקטיקטומים והגעה ליום שיא מסכם ... התלמיד
יכול להוסיף מעבר ל6 קורסים עוד קורסים שירצה זה לבחירתו".
"""

from datetime import date

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

PASSWORD = "sprm83-pass-1110"
ORDER = ["2 הדרכות סקראץ","הגעה ליום שיא באינטל", "2 הדרכות טינקרקאד",
         "2 הדרכות לבחירה", "השתתפות ביום הדרכה טובה", "2 פרקטיקומים", "הגעה ליום שיא מסכם"]


def _user(name):
    return User.objects.create_user(username=f"{name}@example.com", email=f"{name}@example.com",
                                    password=PASSWORD)


def _cert(user, slug):
    from app.models import Course, CourseCertificate

    course, _ = Course.objects.get_or_create(slug=slug, defaults={"title": slug, "is_published": True})
    CourseCertificate.objects.create(user=user, course=course)


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, Student
    from tests.matazim_helpers import attach

    inst = Institution.objects.create(name="רשת עתיד")
    leader = Leader.objects.create(user=_user("afifa"), institution=inst, approved_at=timezone.now())
    kid = attach(_user("kid"), leader=leader)
    return {"leader": leader, "kid": kid, "student": Student.objects.get(user=kid)}


def _panel(html, anchor):
    start = html.index(f'id="{anchor}"')
    return html[start:html.index("</section>", start)]


def test_the_steps_are_her_list_in_her_order(world):
    from matazim.track import path_steps

    steps = path_steps(world["kid"], world["student"], {}, [], today=date(2026, 11, 20))
    assert [s["title"] for s in steps] == [
        "2 הדרכות סקראץ'", "הגעה ליום שיא באינטל", "2 הדרכות טינקרקאד",
        "2 הדרכות לבחירה, מתוך ההדרכות שנשארו", "השתתפות ביום הדרכה טובה",
        "2 פרקטיקומים", "הגעה ליום שיא מסכם"]
    assert not any("פייתון" in s["title"] for s in steps)


def test_the_leader_sees_the_whole_year_on_the_students_page(client, world):
    client.force_login(world["leader"].user)
    resp = client.get(f"/matazim/leader/students/{world['student'].pk}/")
    assert resp.status_code == 200
    panel = _panel(resp.content.decode(), "mzStudentPath")
    assert "המסלול השנתי" in panel
    positions = [panel.index(item) for item in ORDER]
    assert positions == sorted(positions)
    assert panel.count('class="mz-path-node') == 7
    assert "השלב הנוכחי" in panel and "המשימה הנוכחית" not in panel
    # the student's own learning links are not the leader's to follow
    assert "/matazim/learn/" not in panel
    assert "עוד הדרכות לבחירה, כמה שרוצים" in panel


def test_the_path_counts_what_the_student_finished(world):
    from matazim.models import TeachingSession
    from matazim.track import path_steps

    kid, student = world["kid"], world["student"]
    for slug in ("scratch", "scratch-advanced", "tinkercad", "python", "fusion360", "arduino", "micropython-thonny"):
        _cert(kid, slug)
    TeachingSession.objects.create(student=student, title="מפגש", happened_on=date(2027, 3, 1))

    steps = {s["key"]: s for s in path_steps(kid, student, {}, [], today=date(2027, 3, 2))}
    assert steps["scratch"]["status"] == "done" and steps["scratch"]["word"] == "2 מתוך 2"
    assert steps["tinkercad"]["status"] == "doing" and steps["tinkercad"]["word"] == "1 מתוך 2"
    # beyond the two electives, the rest are counted as her "more if they want"
    assert steps["electives"]["status"] == "done"
    assert steps["electives"]["word"] == "2 מתוך 2, ועוד 2 לבחירה"
    assert steps["practicum"]["word"] == "1 מתוך 2"

    _cert(kid, "arduino-tinkercad")
    steps = {s["key"]: s for s in path_steps(kid, student, {}, [], today=date(2027, 3, 2))}
    assert steps["tinkercad"]["status"] == "done" and steps["tinkercad"]["word"] == "2 מתוך 2"


def test_the_student_still_sees_the_same_path_with_links(client, world):
    client.force_login(world["kid"])
    panel = _panel(client.get("/matazim/my-path/").content.decode(), "mzTrainingPath")
    positions = [panel.index(item) for item in ORDER]
    assert positions == sorted(positions)
    assert "/matazim/learn/scratch/" in panel and "/matazim/learn/tinkercad/" in panel


def test_another_leaders_student_is_still_out_of_reach(client, world):
    from matazim.models import Institution, Leader

    other = Leader.objects.create(user=_user("other"), institution=Institution.objects.first(),
                                  approved_at=timezone.now())
    client.force_login(other.user)
    assert client.get(f"/matazim/leader/students/{world['student'].pk}/").status_code == 404


def test_the_winter_row_says_tinkercad_unless_the_team_changed_it(db):
    import importlib

    from django.apps import apps

    from matazim.models import Institution, ProgramMilestone

    inst = Institution.objects.create(name="רשת בדיקה")
    kept = ProgramMilestone.objects.create(
        institution=inst, order=1, when_text="x", starts_on=date(2026, 12, 18), title="למידה",
        activities="הצוות כתב משהו אחר")
    old = ProgramMilestone.objects.create(
        institution=inst, order=2, when_text="x", starts_on=date(2026, 12, 18), title="למידה",
        activities="הדרכה על פייתון והכנת תוצר.")
    importlib.import_module("matazim.migrations.0048_tinkercad_in_the_winter_row").change(apps, None)
    kept.refresh_from_db()
    old.refresh_from_db()
    assert kept.activities == "הצוות כתב משהו אחר"
    assert old.activities == "שתי הדרכות טינקרקאד והכנת תוצר."
