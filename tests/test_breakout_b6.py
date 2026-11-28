"""breakout B.6: writing a challenge with AI (spec 14).

A creator talks with the AI about an idea, may attach a sketch, and the card
("הרעיון שלנו") fills as they agree; "בנו את האתגר" writes the whole challenge
as the creator's draft, checked (stations, puzzles, the code from the
pieces) and sent back once when it cannot be right; after that, a change
asked in the chat is a proposal applied only on the teacher's click. Costs
are logged per answer and capped in our own code. No real model is called:
the key is blank (stub mode), and tests that need a model's words replace
`ai._call`.
"""

import io
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from breakout import access, ai
from breakout.models import Experience, Idea, IdeaMessage, Material

pytestmark = [pytest.mark.breakout, pytest.mark.django_db]

PASSWORD = "paper-rooms-2211"


@pytest.fixture(autouse=True)
def _no_outside(settings, monkeypatch, tmp_path):
    settings.IMAGE_MODERATION_ENABLED = False
    settings.BREAKOUT_PRIVATE_DIR = tmp_path / "breakout_private"
    monkeypatch.delenv("BREAKOUT_AI_DAILY_USD", raising=False)
    monkeypatch.delenv("BREAKOUT_AI_MONTHLY_USD", raising=False)


def _teacher(username, creator=False):
    user = User.objects.create_user(username, f"{username}@example.com", PASSWORD, first_name=username)
    p = access.profile_for(user)
    p.is_teacher, p.is_creator = True, creator
    p.save()
    return user


@pytest.fixture
def seeded(db):
    User.objects.create_superuser("avi", "avi@example.com", PASSWORD, first_name="אבי")
    call_command("seed_breakout", verbosity=0)


@pytest.fixture
def maya(seeded):
    return _teacher("maya", creator=True)


@pytest.fixture
def dana(seeded):
    return _teacher("dana")


def _as(user):
    c = Client()
    c.force_login(user)
    return c


def _idea(c):
    r = c.post("/breakout/ideas/new/")
    assert r.status_code == 302
    return Idea.objects.get(pk=int(r["Location"].rstrip("/").rsplit("/", 1)[1]))


def _png(color=(200, 30, 30)):
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (40, 30), color).save(out, "PNG")
    return SimpleUploadedFile("sketch.png", out.getvalue(), content_type="image/png")


def _built(c, idea):
    c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "מסע בזמן לכיתות ז"})
    c.post(f"/breakout/ideas/{idea.pk}/build/")
    idea.refresh_from_db()
    return idea


# ------------------------------------------------------------------ access


def test_only_creators_talk_and_each_conversation_is_its_authors(seeded, maya, dana):
    assert _as(dana).get("/breakout/ideas/").status_code == 404
    assert _as(dana).post("/breakout/ideas/new/").status_code == 404
    assert _as(dana).get("/breakout/api/ideas/").status_code == 403
    assert "השיחות שלי" not in _as(dana).get("/breakout/").content.decode()
    c = _as(maya)
    home = c.get("/breakout/").content.decode()
    assert "השיחות שלי" in home and 'id="br-create" href="/breakout/ideas/"' in home
    idea = _idea(c)
    assert c.get(f"/breakout/ideas/{idea.pk}/").status_code == 200
    other = _teacher("gal", creator=True)
    for path in (f"/breakout/ideas/{idea.pk}/", f"/breakout/ideas/{idea.pk}/status/"):
        assert _as(other).get(path).status_code == 404
    assert _as(other).post(f"/breakout/ideas/{idea.pk}/say/", {"text": "שלום"}).status_code == 404
    assert _as(other).post(f"/breakout/ideas/{idea.pk}/delete/").status_code == 404
    # The superuser is a curator, and a conversation is still not theirs to read.
    assert _as(User.objects.get(username="avi")).get(f"/breakout/ideas/{idea.pk}/").status_code == 404
    # A stranger is sent to sign in; a signed-in non-teacher to the door.
    assert Client().get("/breakout/ideas/")["Location"].startswith("/breakout/login/")
    noa = User.objects.create_user("noa", "noa@example.com", PASSWORD)
    assert _as(noa).get("/breakout/ideas/")["Location"] == "/breakout/welcome/"


# ------------------------------------------------------------- the chat


def test_talking_fills_the_card_and_opens_the_build_button(maya):
    c = _as(maya)
    idea = _idea(c)
    html = c.get(f"/breakout/ideas/{idea.pk}/").content.decode()
    assert "ספרו לי על האתגר" in html and 'id="br-idea-build"' not in html
    r = c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "אתגר על מסע בזמן בין תקופות"})
    assert r.status_code == 302
    idea.refresh_from_db()
    assert "מסע בזמן" in idea.theme and len(idea.plan_lines) == 3 and idea.ready
    assert (idea.audience_from, idea.audience_to, idea.station_count) == (6, 8, 3)
    roles = list(idea.messages.values_list("role", "kind", "state"))
    assert roles == [("teacher", "chat", "done"), ("ai", "chat", "done")]
    html = c.get(f"/breakout/ideas/{idea.pk}/").content.decode()
    assert 'id="br-idea-build"' in html and "מוכן לבנייה" in html and "כיתות ו-ח" in html
    assert "מצרים העתיקה" in html and 'id="br-stub"' in html
    assert c.get(f"/breakout/ideas/{idea.pk}/status/").json() == {"thinking": False}
    # An empty message is refused, and nothing is written.
    c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "  "})
    assert idea.messages.count() == 2


def test_the_model_sees_the_card_and_the_conversation(maya, monkeypatch):
    seen = []

    def fake(kind, model, items):
        seen.append((kind, items))
        return json.dumps({"message": "בסדר", "brief": {"theme": "חלל", "stations_plan": ["ירח"]}}), {"in": 0, "cached": 0, "out": 0}

    monkeypatch.setattr(ai, "_call", fake)
    c = _as(maya)
    idea = _idea(c)
    c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "על החלל"})
    c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "ארבע תחנות"})
    kind, items = seen[-1]
    assert kind == "chat" and items[0]["role"] == "system" and '"theme": "חלל"' in items[0]["content"]
    said = [i for i in items if i["role"] in ("user", "assistant")]
    assert [i["role"] for i in said] == ["user", "assistant", "user"]
    assert said[-1]["content"][0]["text"] == "ארבע תחנות"
    # A model answer that is not JSON is shown as text, and the card stays.
    monkeypatch.setattr(ai, "_call", lambda *a: ("סתם טקסט", {"in": 0, "cached": 0, "out": 0}))
    c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "?"})
    idea.refresh_from_db()
    assert idea.theme == "חלל" and idea.messages.last().text == "סתם טקסט"


def test_a_sketch_is_checked_kept_and_shown_to_its_author_only(maya, monkeypatch):
    seen = []
    real = ai._call

    def spy(kind, model, items):
        seen.append(items)
        return real(kind, model, items)

    monkeypatch.setattr(ai, "_call", spy)
    c = _as(maya)
    idea = _idea(c)
    c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "ככה אני מדמיינת את הגלגל", "picture": _png()})
    msg = idea.messages.get(role="teacher")
    assert msg.picture and msg.picture.name.startswith(f"ideas/{idea.pk}/")
    parts = seen[-1][-1]["content"]
    assert parts[1]["type"] == "input_image" and parts[1]["image_url"].startswith("data:image/jpeg;base64,")
    r = c.get(f"/breakout/ideas/{idea.pk}/pictures/{msg.pk}/")
    assert r.status_code == 200 and r["Content-Type"] == "image/jpeg"
    r.close()
    assert f"/breakout/ideas/{idea.pk}/pictures/{msg.pk}/" in c.get(f"/breakout/ideas/{idea.pk}/").content.decode()
    assert _as(_teacher("gal", creator=True)).get(f"/breakout/ideas/{idea.pk}/pictures/{msg.pk}/").status_code == 404
    # Not an image: refused with a reason, nothing written.
    before = idea.messages.count()
    bad = SimpleUploadedFile("sketch.png", b"not a picture", content_type="image/png")
    r = c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "", "picture": bad}, follow=True)
    assert idea.messages.count() == before and "תמונה תקינה" in r.content.decode()
    # The site's moderation says no: refused too.
    monkeypatch.setattr("app.safety.image_is_safe", lambda *a, **k: (False, "flagged"))
    r = c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "", "picture": _png()}, follow=True)
    assert idea.messages.count() == before and "בדיקת התוכן" in r.content.decode()
    # Deleting the conversation deletes its pictures.
    name = msg.picture.name
    storage = msg.picture.storage
    c.post(f"/breakout/ideas/{idea.pk}/delete/")
    assert not Idea.objects.filter(pk=idea.pk).exists() and not storage.exists(name)


# ------------------------------------------------------------ the build


def test_building_writes_the_whole_challenge_as_the_creators_draft(maya):
    c = _as(maya)
    idea = _idea(c)
    assert c.post(f"/breakout/ideas/{idea.pk}/build/").status_code == 302  # not ready yet
    assert Experience.objects.filter(author=maya).count() == 0
    idea = _built(c, idea)
    exp = idea.experience
    assert idea.state == Idea.BUILT and exp.author == maya and exp.status == Experience.DRAFT
    stations = list(exp.stations.all())
    assert [s.contribution for s in stations] == ["4", "2", "7"] and exp.final_lock.final_code == "427"
    assert all(s.puzzle_text and s.solution and s.hints.count() == 2 for s in stations)
    names = list(Material.objects.filter(is_active=True).values_list("name", flat=True)[:2])
    assert sorted(stations[0].materials.values_list("material__name", flat=True)) == sorted(names)
    build_msg = idea.messages.get(kind="build", role="ai")
    assert build_msg.state == "done" and "נבנה כטיוטה" in build_msg.text
    # Not in the library; in the editor, with the way back to the chat.
    assert exp.slug not in _as(_teacher("lee")).get("/breakout/").content.decode()
    hub = c.get(f"/breakout/x/{exp.slug}/edit/").content.decode()
    assert f'id="br-idea-back" href="/breakout/ideas/{idea.pk}/"' in hub
    html = c.get(f"/breakout/ideas/{idea.pk}/").content.decode()
    assert f'id="br-idea-edit" href="/breakout/x/{exp.slug}/edit/"' in html and "מה לשנות באתגר?" in html
    # A second build goes to the editor; nothing new is written.
    assert c.post(f"/breakout/ideas/{idea.pk}/build/")["Location"] == f"/breakout/x/{exp.slug}/edit/"
    assert Experience.objects.filter(author=maya).count() == 1
    # Deleting the conversation keeps the challenge.
    c.post(f"/breakout/ideas/{idea.pk}/delete/")
    assert Experience.objects.filter(pk=exp.pk).exists()


def _challenge(code="123", pieces=("1", "2", "3"), material="מספריים"):
    return json.dumps({
        "title": "אתגר בדיקה", "tagline": "שורה", "story": "סיפור", "difficulty": "hard",
        "audience_from": 9, "audience_to": 7, "subjects": ["no-such-subject"],
        "stations": [{"name": f"תחנה {p}", "puzzle_text": "חידה", "solution": p, "contribution": p,
                      "mechanic": "no-such", "hints": ["א", "ב", "ג", "ד", "ה", "ו"],
                      "materials": [{"name": material, "quantity": "2"}, {"name": "לייזר", "quantity": 1}]}
                     for p in pieces],
        "lock": {"final_code": code, "code_rule": "לפי הסדר"},
    }, ensure_ascii=False)


def test_a_build_that_cannot_be_right_goes_back_once_with_the_findings(maya, monkeypatch):
    c = _as(maya)
    idea = _idea(c)
    c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "שלוש תחנות"})
    calls = []
    answers = [_challenge(code="999"), _challenge(code="123")]

    def fake(kind, model, items):
        calls.append(items)
        return answers[len(calls) - 1], {"in": 0, "cached": 0, "out": 0}

    monkeypatch.setattr(ai, "_call", fake)
    c.post(f"/breakout/ideas/{idea.pk}/build/")
    assert len(calls) == 2
    sent_back = calls[1][-1]["content"][0]["text"]
    assert "'123'" in sent_back and "'999'" in sent_back
    idea.refresh_from_db()
    exp = idea.experience
    assert exp.final_lock.final_code == "123"
    # What the app does with the model's words: grades in order, unknowns dropped, hints capped.
    assert (exp.audience_from, exp.audience_to, exp.difficulty) == (7, 9, "hard")
    assert exp.subjects.count() == 0
    s = exp.stations.first()
    assert s.mechanic == "other" and s.hints.count() == 5
    text = idea.messages.get(kind="build", role="ai").text
    assert "לייזר" in text and "שימו לב" not in text


def test_a_build_still_wrong_after_the_second_try_is_saved_and_said(maya, monkeypatch):
    c = _as(maya)
    idea, other = _idea(c), _idea(c)
    c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "שלוש תחנות"})
    c.post(f"/breakout/ideas/{other.pk}/say/", {"text": "שוב"})
    monkeypatch.setattr(ai, "_call", lambda *a: (_challenge(code="999"), {"in": 0, "cached": 0, "out": 0}))
    c.post(f"/breakout/ideas/{idea.pk}/build/")
    idea.refresh_from_db()
    assert idea.experience.final_lock.final_code == "999"
    assert "הקוד הסופי לא יוצא בדיוק מהחלקים של התחנות" in idea.messages.get(kind="build", role="ai").text
    # Nothing usable at all: no draft, an honest message, the chat goes on.
    monkeypatch.setattr(ai, "_call", lambda *a: ("לא JSON", {"in": 0, "cached": 0, "out": 0}))
    c.post(f"/breakout/ideas/{other.pk}/build/")
    other.refresh_from_db()
    assert other.experience is None and "לא הצלחתי לבנות" in other.messages.last().text


# ----------------------------------------------------------- changes


def test_a_change_asked_in_the_chat_is_a_proposal_applied_only_on_a_click(maya, monkeypatch):
    c = _as(maya)
    idea = _built(c, _idea(c))
    exp = idea.experience
    proposal = {"message": "הנה", "changes": [
        {"target": "experience", "field": "tagline", "value": "משפט חדש"},
        {"target": "station", "station": 2, "field": "puzzle_text", "value": "חידה קשה יותר"},
        {"target": "hints", "station": 2, "value": ["רמז חדש"]},
        {"target": "lock", "field": "final_message", "value": "הצלחתם"},
        {"target": "station", "station": 9, "field": "name", "value": "אין כזו"},
        {"target": "experience", "field": "author", "value": "1"},
        {"target": "experience", "field": "status", "value": "published"},
    ]}
    seen = []

    def fake(kind, model, items):
        seen.append((kind, items))
        return json.dumps(proposal, ensure_ascii=False), {"in": 0, "cached": 0, "out": 0}

    monkeypatch.setattr(ai, "_call", fake)
    c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "תעשו את תחנה 2 קשה יותר"})
    kind, items = seen[-1]
    assert kind == "edit" and '"puzzle_text"' in items[0]["content"] and exp.title in items[0]["content"]
    msg = idea.messages.filter(role="ai").last()
    assert msg.kind == "edit" and msg.changes_state == "pending" and len(msg.changes) == 4
    exp.refresh_from_db()
    assert exp.tagline != "משפט חדש"  # nothing changed yet
    html = c.get(f"/breakout/ideas/{idea.pk}/").content.decode()
    assert "תחנה 2: החידה" in html and "חידה קשה יותר" in html and "להחיל את השינויים" in html
    r = c.post(f"/breakout/ideas/{idea.pk}/changes/{msg.pk}/", {"action": "apply"})
    assert r.status_code == 302
    exp.refresh_from_db()
    s2 = exp.stations.all()[1]
    assert exp.tagline == "משפט חדש" and s2.puzzle_text == "חידה קשה יותר"
    assert list(s2.hints.values_list("text", flat=True)) == ["רמז חדש"]
    assert exp.final_lock.final_message == "הצלחתם" and exp.status == Experience.DRAFT and exp.author == maya
    # Applied once: the route is closed for it now.
    assert c.post(f"/breakout/ideas/{idea.pk}/changes/{msg.pk}/", {"action": "apply"}).status_code == 404
    # Declined: nothing changes.
    proposal["changes"] = [{"target": "experience", "field": "title", "value": "שם אחר"}]
    c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "שם אחר?"})
    msg = idea.messages.filter(role="ai").last()
    c.post(f"/breakout/ideas/{idea.pk}/changes/{msg.pk}/", {"action": "decline"})
    msg.refresh_from_db()
    exp.refresh_from_db()
    assert msg.changes_state == "declined" and exp.title != "שם אחר"


def test_applying_to_a_published_challenge_bumps_its_version(maya):
    c = _as(maya)
    idea = _built(c, _idea(c))
    exp = idea.experience
    Experience.objects.filter(pk=exp.pk).update(status=Experience.PUBLISHED, published_at=timezone.now())
    c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "שורה חדשה לכרטיס"})
    msg = idea.messages.filter(role="ai").last()
    c.post(f"/breakout/ideas/{idea.pk}/changes/{msg.pk}/", {"action": "apply"})
    exp.refresh_from_db()
    assert exp.version == 2 and exp.tagline.startswith("גרסה מעודכנת")


# ------------------------------------------------------ cost and caps


def test_every_answer_logs_its_cost_and_the_caps_stop_the_calls(maya, settings, monkeypatch):
    settings.OPENAI_API_KEY = "sk-test-not-real"
    settings.BREAKOUT_AI_INLINE = True
    calls = []

    def fake(kind, model, items):
        calls.append(model)
        return json.dumps({"message": "שלום", "brief": {}}), {"in": 1000, "cached": 0, "out": 500}

    monkeypatch.setattr(ai, "_call", fake)
    c = _as(maya)
    idea = _idea(c)
    c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "שלום"})
    msg = idea.messages.get(role="ai")
    assert calls == ["gpt-6.1-terra"] and msg.model == "gpt-6.1-terra"
    assert (msg.tokens_in, msg.tokens_out, msg.cost_usd) == (1000, 500, Decimal("0.00350"))
    assert ai.spent_today(maya) == Decimal("0.00350") and ai.spent_this_month() == Decimal("0.00350")
    # The curators' page shows each creator's month.
    teachers = _as(User.objects.get(username="avi")).get("/breakout/curators/teachers/").content.decode()
    assert "$0.00" in teachers  # 0.0035 rounds to cents
    # The daily cap: the chat says so and makes no call.
    monkeypatch.setenv("BREAKOUT_AI_DAILY_USD", "0.003")
    c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "עוד"})
    assert len(calls) == 1 and "תקרת השימוש היומית" in idea.messages.last().text
    html = c.get(f"/breakout/ideas/{idea.pk}/").content.decode()
    assert 'id="br-stop"' in html and 'id="br-composer"' not in html
    # Tomorrow it opens again; the monthly cap is for the whole app.
    IdeaMessage.objects.update(created_at=timezone.now() - timedelta(days=1))
    monkeypatch.setenv("BREAKOUT_AI_MONTHLY_USD", "0.001")
    if timezone.localtime().day > 1:
        c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "ושוב"})
        assert len(calls) == 1 and "התקרה החודשית" not in idea.messages.last().text
        assert "תקרת השימוש החודשית" in idea.messages.last().text


def test_a_stuck_answer_is_released_and_one_answer_at_a_time(maya, settings, monkeypatch):
    c = _as(maya)
    idea = _idea(c)
    stuck = IdeaMessage.objects.create(idea=idea, role="ai", state="thinking")
    html = c.get(f"/breakout/ideas/{idea.pk}/").content.decode()
    assert 'data-status-url="/breakout/ideas/' in html and "כותב תשובה" in html
    assert c.get(f"/breakout/ideas/{idea.pk}/status/").json() == {"thinking": True}
    c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "שלום"})
    assert idea.messages.count() == 1  # refused while one is being written
    IdeaMessage.objects.filter(pk=stuck.pk).update(created_at=timezone.now() - timedelta(minutes=10))
    assert c.get(f"/breakout/ideas/{idea.pk}/status/").json() == {"thinking": False}
    stuck.refresh_from_db()
    assert stuck.state == "failed" and "נסו לשלוח שוב" in stuck.text
    # A model call that throws leaves a failed message, not a stuck one.
    monkeypatch.setattr(ai, "_call", lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    c.post(f"/breakout/ideas/{idea.pk}/say/", {"text": "שלום"})
    last = idea.messages.last()
    assert last.state == "failed" and "משהו השתבש" in last.text


# ------------------------------------------------------------------ API


def test_the_api_serves_a_creators_own_ideas_and_reads_their_messages(maya):
    c = _as(maya)
    idea = _built(c, _idea(c))
    mine = c.get("/breakout/api/ideas/").json()
    rows = mine["results"] if isinstance(mine, dict) else mine
    assert [r["id"] for r in rows] == [idea.pk] and rows[0]["experience"] == idea.experience_id
    r = c.post("/breakout/api/ideas/", {"title": "רעיון", "author": 999, "state": "built"}, content_type="application/json")
    assert r.status_code == 201
    made = Idea.objects.get(pk=r.json()["id"])
    assert made.author == maya and made.state == "talking"
    assert c.patch(f"/breakout/api/ideas/{made.pk}/", {"title": "שם"}, content_type="application/json").status_code == 200
    msgs = c.get(f"/breakout/api/idea-messages/?idea={idea.pk}").json()
    msgs = msgs["results"] if isinstance(msgs, dict) else msgs
    assert {m["kind"] for m in msgs} == {"chat", "build"}
    assert c.post("/breakout/api/idea-messages/", {"idea": idea.pk, "text": "x"}, content_type="application/json").status_code == 405
    other = _as(_teacher("gal", creator=True))
    assert other.get(f"/breakout/api/ideas/{idea.pk}/").status_code == 404
    assert other.get("/breakout/api/idea-messages/").json() in ([], {"count": 0, "next": None, "previous": None, "results": []})
    assert c.delete(f"/breakout/api/ideas/{made.pk}/").status_code == 204
