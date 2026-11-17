"""SPR-M.84 - בוגרי מטצים. Lital, 2026-11-17 (mail, 16:28).

Her request, short: a button "בוגרי מטצים" for tenth-graders who finished the
programme and now teach in the schools. On the first visit they give their
details, choose their school and their leader from a list, and a parent approves
with a signature; the leader approves them. The space has her welcome text, all
the programme's הדרכות for review, לומדים AI, איך מעבירים שיעור with the kit she
attached behind "להדרכה טובה, לחצו כאן", the practicum towards 120 hours approved
by the leader, and the two peak days. The leader follows their graduates; the
programme team sees everybody by school and leader, with the parents' approval,
progress and hours.
"""

import importlib
import os
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.utils import timezone

PASSWORD = "sprm84-pass-1117"
PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def _user(name, display=""):
    from app.models import UserProfile

    user = User.objects.create_user(username=f"{name}@example.com", email=f"{name}@example.com",
                                    password=PASSWORD)
    if display:
        UserProfile.objects.update_or_create(user=user, defaults={"display_name": display})
    return user


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, MemberProfile, School

    inst = Institution.objects.create(name="רשת עתיד")
    pm = _user("pm", "נעמי")
    inst.managers.add(pm)
    school = School.objects.create(name="אורט ראמה")
    other_school = School.objects.create(name="עתיד לוד")
    leader = Leader.objects.create(user=_user("lead", "רונית"), institution=inst, approved_at=timezone.now())
    MemberProfile.objects.update_or_create(user=leader.user, defaults={"school": school})
    other = Leader.objects.create(user=_user("other", "לירון"), institution=inst, approved_at=timezone.now())
    waiting_leader = Leader.objects.create(user=_user("cand", "מועמד"), institution=inst)
    grad_user = _user("grad", "דנה בוגרת")
    return {"inst": inst, "pm": pm, "school": school, "other_school": other_school,
            "leader": leader, "other": other, "candidate": waiting_leader, "grad_user": grad_user}


def _join(client, world, **over):
    data = {
        "full_name": "דנה כהן", "school": world["school"].pk, "leader": world["leader"].pk,
        "guardian_name": "רחל כהן", "guardian_email": "rachel@example.com",
        "guardian_consent": "on", "signature": PNG,
    }
    data.update(over)
    data = {k: v for k, v in data.items() if v is not None}
    return client.post("/matazim/graduates/join/", data)


def _graduate(world, approved=True):
    from matazim.models import Graduate

    return Graduate.objects.create(
        user=world["grad_user"], full_name="דנה כהן", school=world["school"], leader=world["leader"],
        guardian_name="רחל כהן", guardian_email="rachel@example.com", guardian_signature=PNG,
        guardian_signed_at=timezone.now(), approved_at=timezone.now() if approved else None,
    )


def _section(html, anchor):
    start = html.index(f'id="{anchor}"')
    return html[start:html.index("</section>", start)]


def _nav(html):
    start = html.index('id="mzNav"')
    return html[start:html.index("</nav>", start)]


# ------------------------------------------------------------------ the button


def test_the_button_is_on_the_front_page_and_in_the_footer(client, db):
    """Her logged-out menu of 15.10 (about and registration only) stands; the
    button is on the front page, and the footer reaches it from every page."""
    html = client.get("/matazim/").content.decode()
    button = html[html.index('id="mzHomeGraduates"'):]
    assert 'href="/matazim/graduates/"' in button[:300] and "בוגרי מטצים" in button[:300]
    footer = html[html.index('class="mz-footer"'):]
    assert 'href="/matazim/graduates/"' in footer
    assert "/matazim/graduates/" not in _nav(html)


def test_a_visitor_is_offered_registration_that_leads_to_the_form(client, db):
    html = client.get("/matazim/graduates/").content.decode()
    assert "/matazim/register/?next=/matazim/graduates/join/" in html
    assert "/matazim/login/?next=/matazim/graduates/join/" in html


# ------------------------------------------------------------------ joining


def test_joining_records_details_school_leader_and_the_parents_signature(client, world):
    from matazim.models import Graduate, Notification

    client.force_login(world["grad_user"])
    mail.outbox.clear()
    resp = _join(client, world)
    assert resp.status_code == 302 and resp["Location"] == "/matazim/graduates/"

    g = Graduate.objects.get(user=world["grad_user"])
    assert (g.full_name, g.school, g.leader) == ("דנה כהן", world["school"], world["leader"])
    assert g.guardian_name == "רחל כהן" and g.guardian_signature == PNG and g.guardian_signed_at
    assert not g.is_approved

    bell = Notification.objects.get(user=world["leader"].user)
    assert bell.kind == Notification.GRADUATE_WAITING and bell.url == "/matazim/leader/graduates/"
    sent = [m for m in mail.outbox if "lead@example.com" in m.to]
    assert len(sent) == 1 and "דנה" not in sent[0].body


@pytest.mark.parametrize("over, word", [
    ({"signature": ""}, "חתימה"),
    ({"signature": "data:image/png;base64,PHNjcmlwdD4="}, "חתימה"),
    ({"signature": "javascript:alert(1)"}, "חתימה"),
    ({"guardian_consent": None}, "אישור ההורה"),
    ({"guardian_email": "not-an-email"}, "אימייל של ההורה"),
    ({"full_name": ""}, "שם מלא"),
])
def test_joining_is_refused_without_each_part(client, world, over, word):
    from matazim.models import Graduate

    client.force_login(world["grad_user"])
    resp = _join(client, world, **over)
    assert resp.status_code == 200 and word in resp.content.decode()
    assert not Graduate.objects.exists()


def test_only_an_approved_active_leader_can_be_chosen(client, world):
    from matazim.models import Graduate

    client.force_login(world["grad_user"])
    page = client.get("/matazim/graduates/join/").content.decode()
    assert "רונית" in page and "לירון" in page and "מועמד" not in page
    assert _join(client, world, leader=world["candidate"].pk).status_code == 200
    world["other"].is_active = False
    world["other"].save()
    assert _join(client, world, leader=world["other"].pk).status_code == 200
    assert not Graduate.objects.exists()


def test_a_graduate_is_never_sent_to_this_years_entrance_test(client, world):
    from matazim.gate import learner_stage

    _graduate(world, approved=False)
    assert learner_stage(world["grad_user"]) is None
    client.force_login(world["grad_user"])
    assert client.get("/matazim/")["Location"] == "/matazim/graduates/"
    nav = _nav(client.get("/matazim/graduates/").content.decode())
    assert "בוגרי מטצים" in nav and "מבחן הכניסה" not in nav


# ------------------------------------------------------------------ the space


def test_waiting_for_the_leader_shows_the_waiting_note_and_nothing_to_report_yet(client, world):
    # SPR-M.85 (REQ-M.222): until the leader approves, the waiting note is all there is.
    _graduate(world, approved=False)
    client.force_login(world["grad_user"])
    html = client.get("/matazim/graduates/").content.decode()
    assert "רונית" in _section(html, "mzGradWaiting")
    assert 'id="mzGradPracticum"' not in html and 'id="mzGradCourses"' not in html
    assert client.get("/matazim/graduates/practicum/")["Location"] == "/matazim/graduates/"


def test_an_approved_graduate_sees_her_five_parts_in_her_order(client, world):
    from matazim.models import GraduateDate

    _graduate(world)
    GraduateDate.objects.all().delete()
    GraduateDate.objects.create(institution=world["inst"], title="יום שיא", on=date(2026, 12, 17))
    GraduateDate.objects.create(institution=world["inst"], title="יום שיא לסיום השנה", on=date(2027, 5, 24))
    client.force_login(world["grad_user"])
    html = client.get("/matazim/graduates/").content.decode()

    # SPR-M.87 (Lital, 2026-11-17 21:05): squares, in her new order.
    order = ["mzGradCourses", "mzGradPracticum", "mzGradTeaching", "mzGradAi", "mzGradAsk", "mzGradDates"]
    positions = [html.index(f'id="{a}"') for a in order]
    assert positions == sorted(positions)
    assert "כל ההדרכות שלי" in html and "לומדים AI" in html and "איך בונים הדרכה?" in html
    teaching = _section(html, "mzGradTeaching")
    assert "להדרכה טובה, לחצו כאן" in teaching and 'href="/matazim/graduates/kit/"' in teaching
    dates = _section(html, "mzGradDates")
    assert "17.12.2026" in dates and "24.5.2027" in dates
    assert "0 שעות אושרו מתוך 120" in _section(html, "mzGradPracticum")
    welcome = html[html.index('id="mzGradWelcome"'):]
    welcome = welcome[:welcome.index("</section>")]
    assert "ממשיכים לשלב הבא" in welcome and "–" not in welcome and "—" not in welcome


def test_the_kit_opens_for_graduates_leaders_and_the_team_only(client, world):
    from tests.matazim_helpers import attach

    _graduate(world, approved=False)
    for who in (world["grad_user"], world["leader"].user, world["pm"]):
        client.force_login(who)
        resp = client.get("/matazim/graduates/kit/")
        assert resp.status_code == 200 and resp["Content-Type"] == "application/pdf"
        assert b"".join(resp.streaming_content)[:5] == b"%PDF-"
    client.force_login(attach(_user("kid"), leader=world["other"]))
    assert client.get("/matazim/graduates/kit/").status_code == 403
    client.logout()
    assert client.get("/matazim/graduates/kit/").status_code == 302


def test_an_approved_graduate_may_take_every_live_hadracha_and_a_waiting_one_may_not(world):
    from matazim.access import visible_course_slugs
    from matazim.models import OfferedCourse

    OfferedCourse.objects.create(slug="sprm84-live", is_active=True)
    OfferedCourse.objects.create(slug="sprm84-retired", is_active=False)
    g = _graduate(world, approved=False)
    assert "sprm84-live" not in visible_course_slugs(world["grad_user"])
    g.approved_at = timezone.now()
    g.save()
    slugs = visible_course_slugs(world["grad_user"])
    assert "sprm84-live" in slugs and "sprm84-retired" not in slugs


# ------------------------------------------------------------------ the practicum


def _report(client, **over):
    data = {"happened_on": (timezone.localdate() - timedelta(days=1)).isoformat(),
            "place": "בית ספר יסודי", "topic": "סקראץ למתחילים", "hours": "2.5", "insight": "הם אהבו"}
    data.update(over)
    return client.post("/matazim/graduates/practicum/", data)


def test_a_report_goes_to_the_leader_and_only_approved_hours_count(client, world):
    from matazim.graduate_views import hours_of
    from matazim.models import Notification, PracticumReport

    g = _graduate(world)
    client.force_login(world["grad_user"])
    assert _report(client).status_code == 302
    report = PracticumReport.objects.get(graduate=g)
    assert (report.place, report.topic, report.hours, report.insight) == (
        "בית ספר יסודי", "סקראץ למתחילים", Decimal("2.5"), "הם אהבו")
    assert Notification.objects.filter(user=world["leader"].user, kind=Notification.PRACTICUM_WAITING).exists()
    assert hours_of(g)["approved"] == 0 and hours_of(g)["waiting"] == 2.5

    client.force_login(world["leader"].user)
    page = client.get("/matazim/leader/graduates/").content.decode()
    assert "סקראץ למתחילים" in page and "הם אהבו" in page
    client.post(f"/matazim/graduates/report/{report.pk}/decide/", {"action": "approve"})
    report.refresh_from_db()
    assert report.status == "approved"
    assert hours_of(g) == {"approved": 2.5, "waiting": 0, "left": 117.5, "pct": 2, "target": 120}

    client.force_login(world["grad_user"])
    html = client.get("/matazim/graduates/practicum/").content.decode()
    assert "117.5" in _section(html, "mzGradHours")
    assert Notification.objects.filter(user=world["grad_user"], kind=Notification.PRACTICUM_DECIDED).exists()


@pytest.mark.parametrize("over", [
    {"hours": "0.3"}, {"hours": "0"}, {"hours": "13"}, {"hours": "abc"}, {"place": ""}, {"topic": ""},
    {"happened_on": (date.today() + timedelta(days=3)).isoformat()},
])
def test_a_report_with_a_wrong_field_is_refused(client, world, over):
    from matazim.models import PracticumReport

    _graduate(world)
    client.force_login(world["grad_user"])
    assert _report(client, **over).status_code == 200
    assert not PracticumReport.objects.exists()


def test_a_returned_report_carries_the_note_and_can_be_deleted_an_approved_one_cannot(client, world):
    from matazim.models import PracticumReport

    g = _graduate(world)
    a = PracticumReport.objects.create(graduate=g, happened_on=date(2026, 11, 1), place="א", topic="ב", hours=2)
    b = PracticumReport.objects.create(graduate=g, happened_on=date(2026, 11, 2), place="א", topic="ג", hours=1)
    client.force_login(world["leader"].user)
    client.post(f"/matazim/graduates/report/{a.pk}/decide/", {"action": "approve"})
    client.post(f"/matazim/graduates/report/{b.pk}/decide/", {"action": "return", "note": "חסר מקום מדויק"})
    b.refresh_from_db()
    assert b.status == "returned" and b.decision_note == "חסר מקום מדויק"

    client.force_login(world["grad_user"])
    assert "חסר מקום מדויק" in client.get("/matazim/graduates/practicum/").content.decode()
    assert client.post(f"/matazim/graduates/practicum/{a.pk}/delete/").status_code == 403
    client.post(f"/matazim/graduates/practicum/{b.pk}/delete/")
    assert list(PracticumReport.objects.values_list("pk", flat=True)) == [a.pk]


# ------------------------------------------------------------------ the leader


def test_the_leader_approves_joining_and_another_leader_cannot(client, world):
    from matazim.models import Notification

    g = _graduate(world, approved=False)
    client.force_login(world["other"].user)
    assert client.post(f"/matazim/graduates/{g.pk}/approve/").status_code == 403
    assert "דנה כהן" not in client.get("/matazim/leader/graduates/").content.decode()

    client.force_login(world["grad_user"])
    assert client.post(f"/matazim/graduates/{g.pk}/approve/").status_code == 403

    client.force_login(world["leader"].user)
    page = client.get("/matazim/leader/graduates/").content.decode()
    assert "דנה כהן" in _section(page, "mzGradToApprove") and "נחתם" in page
    client.post(f"/matazim/graduates/{g.pk}/approve/")
    g.refresh_from_db()
    assert g.is_approved and g.approved_by == world["leader"].user
    assert Notification.objects.filter(user=world["grad_user"], kind=Notification.GRADUATE_APPROVED).exists()
    assert "דנה כהן" in _section(client.get("/matazim/leader/graduates/").content.decode(), "mzGradMine")


def test_another_leader_cannot_decide_a_report(client, world):
    from matazim.models import PracticumReport

    g = _graduate(world)
    r = PracticumReport.objects.create(graduate=g, happened_on=date(2026, 11, 1), place="א", topic="ב", hours=2)
    client.force_login(world["other"].user)
    assert client.post(f"/matazim/graduates/report/{r.pk}/decide/", {"action": "approve"}).status_code == 403
    r.refresh_from_db()
    assert r.status == "waiting"


def test_a_leader_has_a_door_to_their_graduates_on_the_home_page(client, world):
    client.force_login(world["leader"].user)
    html = client.get("/matazim/").content.decode()
    assert 'href="/matazim/leader/graduates/"' in html


# ------------------------------------------------------------------ the team


def test_the_team_sees_everybody_by_school_and_leader(client, world):
    from matazim.models import Graduate, PracticumReport

    g = _graduate(world)
    PracticumReport.objects.create(graduate=g, happened_on=date(2026, 11, 1), place="א", topic="ב",
                                   hours=4, status="approved")
    Graduate.objects.create(
        user=_user("g2"), full_name="יוסי לוי", school=world["other_school"], leader=world["other"],
        guardian_name="אבא", guardian_email="aba@example.com", guardian_signature=PNG,
        guardian_signed_at=timezone.now(),
    )
    client.force_login(world["pm"])
    html = client.get("/matazim/staff/graduates/").content.decode()
    all_ = _section(html, "mzGradAll")
    assert "אורט ראמה · רונית" in all_ and "עתיד לוד · לירון" in all_
    assert "דנה כהן" in all_ and "יוסי לוי" in all_
    assert "אישור הורים: נחתם" in all_ and "4 מתוך 120 שעות" in all_ and "התקדמות בהדרכות" in all_
    assert "2 נרשמו, 1 מאושרים" in html
    assert 'href="/matazim/staff/graduates/"' in client.get("/matazim/").content.decode()


def test_the_team_screen_is_closed_to_a_leader_and_a_graduate(client, world):
    _graduate(world)
    for who in (world["leader"].user, world["grad_user"]):
        client.force_login(who)
        assert client.get("/matazim/staff/graduates/").status_code == 403


def test_the_team_edits_the_dates_and_the_content_and_the_graduate_sees_them(client, world):
    from matazim.models import GraduateDate, GraduateResource

    _graduate(world)
    GraduateDate.objects.all().delete()
    client.force_login(world["pm"])
    client.post("/matazim/staff/graduates/", {"do": "add_date", "title": "יום שיא", "on": "2026-12-17"})
    d = GraduateDate.objects.get()
    client.post("/matazim/staff/graduates/", {"do": "edit_date", "id": d.pk, "title": "יום שיא", "on": "2026-12-18"})
    d.refresh_from_db()
    assert d.on == date(2026, 12, 18)
    client.post("/matazim/staff/graduates/", {"do": "add_resource", "section": "ai", "title": "פרומפטים טובים",
                                              "link": "https://example.com/ai"})
    assert client.post("/matazim/staff/graduates/", {"do": "add_resource", "section": "ai", "title": "רע",
                                                     "link": "javascript:alert(1)"}).status_code == 200
    assert GraduateResource.objects.count() == 1

    client.force_login(world["grad_user"])
    html = client.get("/matazim/graduates/").content.decode()
    assert 'href="/matazim/graduates/ai/"' in _section(html, "mzGradAi")
    assert "פרומפטים טובים" in client.get("/matazim/graduates/ai/").content.decode()
    assert "18.12.2026" in _section(html, "mzGradDates")

    client.force_login(world["pm"])
    client.post("/matazim/staff/graduates/", {"do": "delete_resource", "id": GraduateResource.objects.get().pk})
    client.post("/matazim/staff/graduates/", {"do": "delete_date", "id": d.pk})
    assert not GraduateResource.objects.exists() and not GraduateDate.objects.exists()


def test_the_two_dates_are_seeded_once_and_never_again(db):
    from django.apps import apps as django_apps

    from matazim.models import GraduateDate

    seed = importlib.import_module("matazim.migrations.0050_seed_graduate_dates").seed
    GraduateDate.objects.all().delete()
    seed(django_apps, None)
    assert sorted(GraduateDate.objects.values_list("on", flat=True)) == [date(2026, 12, 17), date(2027, 5, 24)]
    GraduateDate.objects.filter(on=date(2026, 12, 17)).update(on=date(2026, 12, 20))
    seed(django_apps, None)
    assert sorted(GraduateDate.objects.values_list("on", flat=True)) == [date(2026, 12, 20), date(2027, 5, 24)]


# ------------------------------------------------------------------ the API


def test_the_api_never_hands_out_the_signature_and_is_scoped(client, world):
    _graduate(world)
    client.force_login(world["leader"].user)
    body = client.get("/matazim/api/graduates/").content.decode()
    assert "דנה כהן" in body and "guardian_signature" not in body and "base64" not in body
    client.force_login(world["other"].user)
    assert "דנה כהן" not in client.get("/matazim/api/graduates/").content.decode()
    client.logout()
    for prefix in ("graduates", "practicum-reports", "graduate-dates", "graduate-resources"):
        assert client.get(f"/matazim/api/{prefix}/").status_code in (401, 403)


def test_the_api_lets_a_graduate_report_and_their_leader_approve(client, world):
    from matazim.models import PracticumReport

    _graduate(world)
    client.force_login(world["grad_user"])
    resp = client.post("/matazim/api/practicum-reports/", {
        "happened_on": "2026-11-10", "place": "א", "topic": "ב", "hours": "1.5", "status": "approved"},
        content_type="application/json")
    assert resp.status_code == 201
    report = PracticumReport.objects.get()
    assert report.status == "waiting"
    assert client.post(f"/matazim/api/practicum-reports/{report.pk}/approve/").status_code == 403

    client.force_login(world["leader"].user)
    assert client.post(f"/matazim/api/practicum-reports/{report.pk}/approve/").status_code == 200
    report.refresh_from_db()
    assert report.status == "approved"

    client.force_login(world["grad_user"])
    assert client.delete(f"/matazim/api/practicum-reports/{report.pk}/").status_code == 403


def test_a_waiting_graduate_cannot_report_through_the_api(client, world):
    _graduate(world, approved=False)
    client.force_login(world["grad_user"])
    resp = client.post("/matazim/api/practicum-reports/", {
        "happened_on": "2026-11-10", "place": "א", "topic": "ב", "hours": "1"}, content_type="application/json")
    assert resp.status_code == 403


# ------------------------------------------------------------------ on a phone

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")


@pytest.fixture
def phone():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={"width": 360, "height": 780}, device_scale_factor=2,
                                          is_mobile=True, has_touch=True)
            yield context
            browser.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


def _signed_in(context, live_server, user):
    from django.test import Client

    c = Client()
    c.force_login(user)
    context.add_cookies([{"name": "sessionid", "value": c.cookies["sessionid"].value,
                          "url": live_server.url}])


def test_on_a_phone_a_graduate_signs_up_with_a_drawn_signature(phone, live_server, transactional_db):
    """Rule 27: the flow itself, at a narrow phone, start to finish."""
    from matazim.models import Graduate, Institution, Leader, MemberProfile, School

    inst = Institution.objects.create(name="רשת עתיד")
    school = School.objects.create(name="אורט ראמה")
    Leader.objects.create(user=_user("lead2", "רונית"), institution=inst, approved_at=timezone.now())
    user = _user("phonegrad", "דנה")
    MemberProfile.objects.update_or_create(user=user, defaults={"welcome_accepted_at": timezone.now()})
    _signed_in(phone, live_server, user)
    page = phone.new_page()
    page.goto(live_server.url + "/matazim/graduates/join/", wait_until="domcontentloaded")

    page.fill('input[name="full_name"]', "דנה כהן")
    page.select_option('select[name="school"]', str(school.pk))
    page.select_option('select[name="leader"]', index=1)
    page.fill('input[name="guardian_name"]', "רחל כהן")
    page.fill('input[name="guardian_email"]', "rachel@example.com")
    page.check('input[name="guardian_consent"]')

    box = page.locator("#mzSig").bounding_box()
    page.mouse.move(box["x"] + 20, box["y"] + 30)
    page.mouse.down()
    for step in range(1, 12):
        page.mouse.move(box["x"] + 20 + step * 20, box["y"] + 30 + (step % 3) * 15)
    page.mouse.up()

    wide = page.evaluate("""() => [...document.querySelectorAll('main *')].filter(
        el => el.getBoundingClientRect().right > document.documentElement.clientWidth + 1).length""")
    assert wide == 0, "the form is wider than a 360px phone"

    page.click('#mzGradJoin button[type="submit"]')
    page.wait_for_url("**/matazim/graduates/")
    g = Graduate.objects.get(user=user)
    assert g.guardian_signature.startswith("data:image/png;base64,") and len(g.guardian_signature) > 200
    assert "ההצטרפות מחכה לאישור" in page.content()
