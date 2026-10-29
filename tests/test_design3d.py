"""design3d: the door, the chat turn, builds, versions, sliders, sharing,
limits, files and the API. docs/design3d/spec.md.

No test calls OpenAI (the stub answers, or a fake replaces `llm.ask`) and
no test reaches the image check's outside service (mistakes 26, 47). The
builder is a fake that returns a cube, except in the one test that runs
the real OpenSCAD when it is on this machine.
"""

import io
import os
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from design3d import builder, jobs, llm, params, render
from design3d.models import Design, Maker, Message, Parameter, Picture, Version

pytestmark = pytest.mark.design3d

PASSWORD = "d3-pass-55821"
HEBREW = re.compile(r"[֐-׿]")

CUBE = (b"solid cube\n" + b"".join(
    b"facet normal 0 0 0\nouter loop\n" + b"".join(f"vertex {x} {y} {z}\n".encode() for x, y, z in tri) + b"endloop\nendfacet\n"
    for tri in [((0, 0, 0), (10, 0, 0), (10, 20, 0)), ((0, 0, 0), (10, 20, 0), (0, 20, 0)),
                ((0, 0, 5), (10, 0, 5), (10, 20, 5)), ((0, 0, 5), (10, 20, 5), (0, 20, 5)),
                ((0, 0, 0), (10, 0, 0), (10, 0, 5)), ((0, 0, 0), (10, 0, 5), (0, 0, 5))]) + b"endsolid cube\n")


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path, monkeypatch):
    settings.DESIGN3D_PRIVATE_DIR = tmp_path
    settings.DESIGN3D_SYNC = True
    settings.OPENAI_API_KEY = ""
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    monkeypatch.setattr("app.safety.image_is_safe", lambda *a, **k: (True, ""), raising=False)
    monkeypatch.setattr(builder, "build", lambda code: (builder.check(code), (CUBE, 0.4))[1])


def _user(email, superuser=False, first="", status=None):
    make = User.objects.create_superuser if superuser else User.objects.create_user
    u = make(email, email, PASSWORD, first_name=first)
    if status:
        Maker.objects.create(user=u, display_name=first or email, status=status)
    return u


@pytest.fixture
def world(db):
    return {"avi": _user("avi@example.com", True, "Avi"),
            "dana": _user("dana@example.com", first="Dana", status=Maker.APPROVED),
            "eli": _user("eli@example.com", first="Eli", status=Maker.APPROVED)}


def _design(client, user):
    client.force_login(user)
    r = client.post("/design3d/designs/new/")
    return Design.objects.get(pk=int(r["Location"].rstrip("/").split("/")[-1]))


def _say(client, d, text="A holder for my pencil", **files):
    return client.post(f"/design3d/d/{d.pk}/send/", {"text": text, **files}, HTTP_ACCEPT="application/json")


# ------------------------------------------------------------ the door


def test_the_door_sign_in_ask_wait_approve_and_ask_again(client, db):
    """REQ-D3.1 to D3.3"""
    html = client.get("/design3d/").content.decode()
    assert 'id="d3-signin"' in html and "by invitation" in html
    assert client.get("/design3d/designs/").status_code == 302

    noa = _user("noa@example.com", first="Noa")
    client.force_login(noa)
    assert 'id="d3-ask"' in client.get("/design3d/").content.decode()
    client.post("/design3d/ask/", {"reason": "I teach robotics"})
    m = Maker.objects.get(user=noa)
    assert m.status == Maker.PENDING and m.reason == "I teach robotics"
    assert 'id="d3-waiting"' in client.get("/design3d/").content.decode()
    assert client.get("/design3d/designs/").status_code == 302

    avi = _user("avi@example.com", True, "Avi")
    client.force_login(avi)
    html = client.get("/design3d/people/").content.decode()
    assert "I teach robotics" in html
    client.post("/design3d/people/", {"maker": m.pk, "action": "decline"})
    client.force_login(noa)
    assert 'id="d3-declined"' in client.get("/design3d/").content.decode()
    client.post("/design3d/ask/", {"reason": "Please, for my class"})
    m.refresh_from_db()
    assert m.status == Maker.PENDING and m.reason == "Please, for my class"

    client.force_login(avi)
    client.post("/design3d/people/", {"maker": m.pk, "action": "approve"})
    client.post("/design3d/people/", {"maker": m.pk, "action": "approve"})
    welcome = [x for x in mail.outbox if x.subject == "You are in design3d"]
    assert len(welcome) == 1 and "/design3d/" in welcome[0].body, "the welcome goes once"
    client.force_login(noa)
    assert client.get("/design3d/").status_code == 302
    assert client.get("/design3d/designs/").status_code == 200


def test_only_avi_sees_the_people_screen(client, world):
    client.force_login(world["dana"])
    assert client.get("/design3d/people/").status_code == 404
    assert "/design3d/people/" not in client.get("/design3d/designs/").content.decode()
    client.force_login(world["avi"])
    assert client.get("/design3d/people/").status_code == 200


def test_a_person_who_is_not_in_reaches_nothing(client, world):
    d = _design(client, world["dana"])
    _say(client, d)
    v = Version.objects.get(design=d)
    waiting = _user("w@example.com", status=Maker.PENDING)
    client.force_login(waiting)
    for path in (f"/design3d/d/{d.pk}/", f"/design3d/d/{d.pk}/poll/", "/design3d/shared/"):
        assert client.get(path).status_code == 302, path
    assert client.get(f"/design3d/files/{v.stl.name}").status_code == 404
    assert client.get("/design3d/api/designs/").status_code == 403


# ------------------------------------------------------------ a chat turn


def test_a_turn_builds_a_version_with_sliders_and_a_title(client, world):
    """REQ-D3.12, D3.15, D3.20, D3.22, D3.23 (stub mode)"""
    d = _design(client, world["dana"])
    r = _say(client, d)
    assert r.status_code == 200
    d.refresh_from_db()
    assistant = d.messages.get(role=Message.ASSISTANT)
    assert assistant.state == Message.DONE and assistant.version and assistant.version.number == 1
    assert d.current == assistant.version and d.title == "Pencil holder"
    v = d.current
    assert v.status == Version.READY and v.size_mm == "10 x 20 x 5" and v.stl and v.preview
    assert [p.name for p in v.parameters.all()] == ["diameter", "height", "wall"]
    poll = client.get(f"/design3d/d/{d.pk}/poll/").json()
    assert poll["current"]["number"] == 1 and poll["current"]["parameters"][0]["name"] == "diameter"
    html = client.get(f"/design3d/d/{d.pk}/").content.decode()
    assert f'data-stl="/design3d/files/{v.stl.name}"' in html and 'name="diameter"' in html


def test_the_chat_can_ask_first_without_building(client, world, monkeypatch):
    """REQ-D3.13: a photo with no scale gets a question, not a guess."""
    monkeypatch.setattr(llm, "ask", lambda items: ({"title": "", "message": "How thick is the pencil? A coin next to it helps.",
                                                    "assumptions": [], "code": None, "parameters": []}, {"in": 900, "cached": 0, "out": 80}, "gpt-6.1-terra"))
    d = _design(client, world["dana"])
    _say(client, d, "A holder for this")
    a = d.messages.get(role=Message.ASSISTANT)
    assert a.version is None and "coin" in a.text and not d.versions.exists()
    assert a.cost_usd == Decimal("0.00130"), "900 in + 80 out at terra's prices"


def test_a_failed_build_is_repaired_and_the_first_part_is_checked(client, world, monkeypatch, settings):
    """REQ-D3.21: the error goes back up to three times; the first ready
    part is shown to the model once (not in stub mode: a fake key here, and
    `llm.ask` is replaced, so nothing reaches OpenAI)."""
    settings.OPENAI_API_KEY = "test-key-not-real"
    calls, steps = [], []
    good = "size = 10;\ncube(size);"

    def ask(items):
        calls.append(items[-1]["content"])
        m = Message.objects.filter(role=Message.ASSISTANT).latest("id")
        d_now = Design.objects.get(pk=m.design_id)
        steps.append((m.state, m.step, d_now.current.number if d_now.current else None))
        n = len(calls)
        code = "cube(" if n == 1 else good
        return ({"title": "Cube", "message": f"turn {n}", "assumptions": [], "code": code if n < 3 else None,
                 "parameters": [{"name": "size", "label": "Size", "min": 5, "max": 50}]}, {"in": 10, "cached": 0, "out": 5}, "gpt-6.1-terra")

    def build(code):
        builder.check(code)
        if code == "cube(":
            raise builder.BuildError("ERROR: Parser error in line 1")
        return CUBE, 0.2

    monkeypatch.setattr(llm, "ask", ask)
    monkeypatch.setattr(builder, "build", build)
    d = _design(client, world["dana"])
    _say(client, d, "A 10 mm cube")
    assert len(calls) == 3, "ask, repair, self-check"
    assert "Parser error" in calls[1][0]["text"]
    assert calls[2][1]["type"] == "input_image", "the self-check shows the model a picture"
    assert [v.status for v in d.versions.order_by("number")] == ["failed", "ready"]
    d.refresh_from_db()
    assert d.current.number == 2
    # Avi, 2026-10-28: the page says what a turn is doing, so it never looks stuck;
    # and a ready part is on screen during the self-check, not after it.
    assert steps == [("thinking", "Reading your message", None),
                     ("building", "Fixing a build error, try 1 of 3", None),
                     ("building", "Checking the part against what you asked", 2)]
    done = d.messages.get(role=Message.ASSISTANT)
    assert done.state == Message.DONE and done.step == ""
    # Avi, 2026-10-28: "maybe I can peek into the conversation": the trail.
    assert [t[1] for t in done.trail] == [
        "Reading your message", "Building version 1", "Version 1 did not build: ERROR: Parser error in line 1",
        "Fixing a build error, try 1 of 3", "Building version 2", "Version 2 built in 0.2 s",
        "Checking the part against what you asked"]
    poll = client.get(f"/design3d/d/{d.pk}/poll/?after=0").json()
    assert [x for x in poll["messages"] if x["id"] == done.pk][0]["trail"] == done.trail
    page = client.get(f"/design3d/d/{d.pk}/").content.decode()
    assert "How this turn went" in page and "Version 1 did not build" in page

    calls.clear()
    _say(client, d, "Make it 20")
    assert len(calls) == 3, "every part the chat builds is checked (Avi, 2026-10-29)"


def test_code_that_reads_files_is_refused():
    """REQ-D3.20"""
    for bad in ('import("x.stl");', "include <a.scad>", "use <lib.scad>", "  import ( \"/etc/passwd\" );"):
        with pytest.raises(builder.BuildError):
            builder.check(bad)
    builder.check("difference(){ cube(10); }  // important note")


def test_a_build_past_its_time_limit_is_killed_with_its_children(settings, tmp_path):
    """Avi, 2026-10-28: a heavy part ran on past the limit. The launcher's
    child process is killed too, and the build returns at the limit."""
    import sys
    import time

    settings.DESIGN3D_BUILD_TIMEOUT = 1
    marker = tmp_path / "child-still-alive"
    child = f"import time; time.sleep(4); open(r'{marker}', 'w').write('x')"
    launcher = f"import subprocess, sys; subprocess.run([sys.executable, '-c', {child!r}])"
    t = time.time()
    out, err, code = builder._run([sys.executable, "-c", launcher], dict(os.environ), str(tmp_path))
    assert code is None and time.time() - t < 3
    time.sleep(4.5)
    assert not marker.exists(), "the child kept running after the limit"


def test_a_stuck_turn_ends_as_failed(client, world):
    """Methodology 22"""
    d = _design(client, world["dana"])
    m = Message.objects.create(design=d, role=Message.ASSISTANT, state=Message.THINKING)
    Message.objects.filter(pk=m.pk).update(created_at=timezone.now() - timedelta(minutes=30))
    poll = client.get(f"/design3d/d/{d.pk}/poll/").json()
    assert any(x["id"] == m.pk and x["state"] == "failed" and "again" in x["text"] for x in poll["messages"])


def test_poll_reports_the_step_and_its_seconds_from_the_server(client, world):
    d = _design(client, world["dana"])
    m = Message.objects.create(design=d, role=Message.ASSISTANT, state=Message.BUILDING, step="Building version 3")
    Message.objects.filter(pk=m.pk).update(created_at=timezone.now() - timedelta(seconds=42))
    got = [x for x in client.get(f"/design3d/d/{d.pk}/poll/").json()["messages"] if x["id"] == m.pk][0]
    assert got["step"] == "Building version 3" and 41 <= got["seconds"] <= 45
    html = client.get(f"/design3d/d/{d.pk}/").content.decode()
    assert "Building version 3" in html.split(f'id="m{m.pk}"', 1)[1].split("</article>", 1)[0]


def test_one_turn_at_a_time(client, world):
    d = _design(client, world["dana"])
    Message.objects.create(design=d, role=Message.ASSISTANT, state=Message.THINKING)
    assert _say(client, d).status_code == 409


# ------------------------------------------------------------ the daily limit


def test_the_daily_limit_stops_turns_and_avi_has_none(client, world):
    """REQ-D3.15"""
    d = _design(client, world["dana"])
    Message.objects.create(design=d, role=Message.ASSISTANT, cost_usd=Decimal("2.10"))
    r = _say(client, d)
    assert r.status_code == 429 and "midnight" in r.json()["error"]
    maker = Maker.objects.get(user=world["dana"])
    maker.daily_limit_usd = Decimal("5")
    maker.save()
    assert _say(client, d).status_code == 200
    a = _design(client, world["avi"])
    Message.objects.create(design=a, role=Message.ASSISTANT, cost_usd=Decimal("50"))
    assert _say(client, a).status_code == 200


def test_avi_sets_a_limit_on_the_people_screen(client, world):
    client.force_login(world["avi"])
    m = Maker.objects.get(user=world["eli"])
    client.post("/design3d/people/", {"maker": m.pk, "action": "limit", "limit": "0.5"})
    m.refresh_from_db()
    assert m.daily_limit_usd == Decimal("0.5") and m.limit == Decimal("0.5")
    client.post("/design3d/people/", {"maker": m.pk, "action": "limit", "limit": ""})
    m.refresh_from_db()
    assert m.daily_limit_usd is None and m.limit == Decimal("2")


# ------------------------------------------------------------ pictures


def _jpeg(size=(3000, 2000)):
    from PIL import Image

    out = io.BytesIO()
    ex = Image.Exif()
    ex[0x8825] = {2: (32.0, 4.0, 0.0)}
    Image.new("RGB", size, (200, 180, 40)).save(out, "JPEG", exif=ex.tobytes())
    return SimpleUploadedFile("pencil.jpg", out.getvalue(), content_type="image/jpeg")


def test_pictures_are_made_small_stripped_and_private(client, world):
    """REQ-D3.14"""
    d = _design(client, world["dana"])
    r = _say(client, d, "", pictures=[_jpeg(), _jpeg((800, 600))])
    assert r.status_code == 200
    pics = list(Picture.objects.filter(message__design=d))
    assert len(pics) == 2 and max(pics[0].width, pics[0].height) == 2000
    from PIL import Image

    with Image.open(pics[0].image.path) as img:
        assert not img.getexif().get(0x8825)
    assert client.get(f"/design3d/files/{pics[0].image.name}").status_code == 200
    client.force_login(world["eli"])
    assert client.get(f"/design3d/files/{pics[0].image.name}").status_code == 404
    bad = SimpleUploadedFile("x.jpg", b"not a picture", content_type="image/jpeg")
    client.force_login(world["dana"])
    assert _say(client, d, "hi", pictures=[bad]).status_code == 400


def test_the_model_sees_the_pictures(client, world, monkeypatch):
    seen = []
    monkeypatch.setattr(llm, "ask", lambda items: (seen.append(items), ({"title": "", "message": "ok", "assumptions": [], "code": None, "parameters": []}, {"in": 1, "cached": 0, "out": 1}, "gpt-6.1-terra"))[1])
    d = _design(client, world["dana"])
    _say(client, d, "This one", pictures=[_jpeg((400, 300))])
    parts = seen[0][-1]["content"]
    assert parts[0]["text"] == "This one" and parts[1]["image_url"].startswith("data:image/jpeg;base64,")
    assert seen[0][0]["role"] == "system" and "coin" in seen[0][0]["content"]


# ------------------------------------------------------------ versions and sliders


def test_sliders_build_a_new_version_without_the_model(client, world, monkeypatch):
    """REQ-D3.23"""
    d = _design(client, world["dana"])
    _say(client, d)
    monkeypatch.setattr(llm, "ask", lambda items: pytest.fail("the sliders must not call the model"))
    client.post(f"/design3d/d/{d.pk}/sliders/", {"from": 1, "diameter": "80", "height": "999", "wall": "3"}, HTTP_ACCEPT="application/json")
    d.refresh_from_db()
    v2 = d.current
    assert v2.number == 2 and v2.made_by == Version.SLIDERS and v2.parent.number == 1
    assert "diameter = 80;" in v2.code and "height = 150;" in v2.code and "wall = 3;" in v2.code, "clamped to the range"
    assert {p.name: p.value for p in v2.parameters.all()}["height"] == Decimal("150")


def test_continuing_from_an_old_version_keeps_the_newer_ones(client, world):
    """REQ-D3.22"""
    d = _design(client, world["dana"])
    _say(client, d)
    _say(client, d, "Taller")
    assert d.versions.count() == 2
    html = client.get(f"/design3d/d/{d.pk}/?v=1").content.decode()
    assert 'id="d3-continue"' in html
    client.post(f"/design3d/d/{d.pk}/v/1/use/")
    d.refresh_from_db()
    assert d.current.number == 1 and d.versions.count() == 2
    client.post(f"/design3d/d/{d.pk}/sliders/", {"from": 1, "height": "60"}, HTTP_ACCEPT="application/json")
    d.refresh_from_db()
    assert d.current.number == 3 and d.current.parent.number == 1


def test_params_apply_and_clean():
    code = "diameter = 70;\nheight=90 ;\nwall = 2;\ninner_height = height - 2;\n"
    out = params.apply(code, {"height": Decimal("60.5"), "wall": 3})
    assert "height=60.5 ;" in out and "wall = 3;" in out and "inner_height = height - 2;" in out
    cleaned = params.clean([{"name": "height", "min": 10, "max": 200}, {"name": "nope"}, {"name": "x; import"}, "junk",
                            {"name": "wall", "min": 5, "max": 1}], code)
    assert [c["name"] for c in cleaned] == ["height", "wall"]
    assert cleaned[1]["minimum"] == Decimal("1") and cleaned[1]["maximum"] == Decimal("5")


def test_downloads(client, world):
    """REQ-D3.25"""
    d = _design(client, world["dana"])
    _say(client, d)
    r = client.get(f"/design3d/d/{d.pk}/v/1/stl/")
    assert r.status_code == 200 and b"".join(r.streaming_content).startswith(b"solid")
    assert 'filename="pencil-holder-v1.stl"' in r["Content-Disposition"]
    r = client.get(f"/design3d/d/{d.pk}/v/1/scad/")
    assert r.status_code == 200 and b"diameter = 70;" in r.content
    assert client.get(f"/design3d/d/{d.pk}/v/1/exe/").status_code == 404


# ------------------------------------------------------------ sharing


def test_sharing_shows_the_model_only(client, world):
    """REQ-D3.30, D3.31"""
    d = _design(client, world["dana"])
    _say(client, d, "Holder", pictures=[_jpeg((400, 300))])
    pic = Picture.objects.get(message__design=d)
    client.force_login(world["eli"])
    assert client.get(f"/design3d/d/{d.pk}/").status_code == 404
    assert client.get(f"/design3d/d/{d.pk}/v/1/stl/").status_code == 404
    assert f'id="s{d.pk}"' not in client.get("/design3d/shared/").content.decode()

    client.force_login(world["dana"])
    client.post(f"/design3d/d/{d.pk}/edit/", {"action": "share", "shared": "1"})
    client.force_login(world["eli"])
    assert f'id="s{d.pk}"' in client.get("/design3d/shared/").content.decode()
    assert client.get(f"/design3d/d/{d.pk}/")["Location"] == f"/design3d/shared/{d.pk}/"
    page = client.get(f"/design3d/shared/{d.pk}/").content.decode()
    assert "Holder" not in page.split("<main", 1)[1].split("d3-head", 1)[0] and "Download STL" in page
    assert client.get(f"/design3d/d/{d.pk}/v/1/stl/").status_code == 200
    assert client.get(f"/design3d/d/{d.pk}/v/1/scad/").status_code == 404
    assert client.get(f"/design3d/files/{pic.image.name}").status_code == 404
    assert client.get(f"/design3d/d/{d.pk}/poll/").status_code == 404
    assert client.get(f"/design3d/api/messages/?design={d.pk}").json() == []

    client.force_login(world["dana"])
    client.post(f"/design3d/d/{d.pk}/edit/", {"action": "share", "shared": "0"})
    client.force_login(world["eli"])
    assert client.get(f"/design3d/shared/{d.pk}/").status_code == 404


def test_rename_and_delete(client, world):
    d = _design(client, world["dana"])
    client.post(f"/design3d/d/{d.pk}/edit/", {"action": "rename", "title": "Pen cup"})
    d.refresh_from_db()
    assert d.title == "Pen cup"
    client.force_login(world["eli"])
    assert client.post(f"/design3d/d/{d.pk}/edit/", {"action": "delete"}).status_code == 404
    client.force_login(world["dana"])
    client.post(f"/design3d/d/{d.pk}/edit/", {"action": "delete"})
    assert not Design.objects.filter(pk=d.pk).exists()


# ------------------------------------------------------------ the pictures of a part


def test_render_reads_stl_and_draws():
    tris = render.read_stl(CUBE)
    assert len(tris) == 6 and render.size_mm(tris) == "10 x 20 x 5"
    import struct

    binary = b"\0" * 80 + struct.pack("<I", 1) + struct.pack("<12fH", 0, 0, 1, 0, 0, 0, 3, 0, 0, 0, 4, 0, 0)
    assert render.size_mm(render.read_stl(binary)) == "3 x 4 x 0"
    assert render.preview(CUBE)[:8] == b"\x89PNG\r\n\x1a\n"
    assert render.sheet(CUBE)[:8] == b"\x89PNG\r\n\x1a\n"


def test_real_openscad_builds_the_stub_part(settings, monkeypatch):
    """REQ-D3.43, when OpenSCAD is on this machine (vendor/openscad-win here,
    vendor/openscad on Render)."""
    import importlib

    real = importlib.reload(builder)
    if not real.available():
        pytest.skip("OpenSCAD is not installed here")
    stl, took = real.build(llm.STUB_CODE)
    assert b"facet" in stl[:2000] and render.size_mm(render.read_stl(stl)).startswith("70 x 70 x 90")


# ------------------------------------------------------------ the API and the frame


def test_every_model_has_an_endpoint():
    from django.apps import apps

    from design3d.api import ROUTES

    assert {m for _p, _v, m in ROUTES} == set(apps.get_app_config("design3d").get_models())


def test_the_api_shows_your_rows_only(client, world):
    """REQ-D3.42"""
    d = _design(client, world["dana"])
    _say(client, d)
    client.force_login(world["eli"])
    for route in ("designs", "messages", "versions", "parameters", "pictures"):
        assert client.get(f"/design3d/api/{route}/").json() == [], route
    assert [m["display_name"] for m in client.get("/design3d/api/makers/").json()] == ["Eli"]
    assert client.patch(f"/design3d/api/makers/{Maker.objects.get(user=world['eli']).pk}/", {"daily_limit_usd": "99"},
                        content_type="application/json").status_code == 403
    client.force_login(world["dana"])
    assert len(client.get("/design3d/api/versions/").json()) == 1
    client.force_login(world["avi"])
    m = Maker.objects.create(user=_user("z@example.com"), display_name="Z")
    assert client.post(f"/design3d/api/makers/{m.pk}/approve/").json()["status"] == "approved"


def test_pages_are_english_and_never_link_to_babook(client, world):
    d = _design(client, world["dana"])
    _say(client, d)
    for path in ("/design3d/designs/", f"/design3d/d/{d.pk}/", "/design3d/shared/"):
        html = client.get(path).content.decode()
        assert not HEBREW.search(html), path
        inside = [h for h in re.findall(r'href="([^"]+)"', html)
                  if h.startswith("/") and not h.startswith(("/design3d/", "/static/", "/accounts/google/"))]
        assert inside == [], (path, inside)
    client.logout()
    for path in ("/design3d/", "/design3d/login/", "/design3d/signup/"):
        assert not HEBREW.search(client.get(path).content.decode()), path


def test_every_class_the_markup_uses_is_defined():
    """Mistake 13"""
    css = Path("static/design3d/design3d.css").read_text(encoding="utf-8")
    defined = set(re.findall(r"\.(d3-[a-z0-9_-]+)", css))
    used = set()
    for path in Path("templates/design3d").rglob("*.html"):
        for classes in re.findall(r'class="([^"]+)"', path.read_text(encoding="utf-8")):
            used |= {c for c in re.sub(r"\{[%{].*?[%}]\}", " ", classes).split() if c.startswith("d3-")}
    js = Path("static/design3d/design.js").read_text(encoding="utf-8")
    ids = set()
    for path in Path("templates/design3d").rglob("*.html"):
        ids |= set(re.findall(r'id="(d3-[a-z0-9-]+)"', path.read_text(encoding="utf-8")))
    used |= set(re.findall(r'"(d3-[a-z0-9-]+)', js)) - ids  # strings that are element ids are not classes
    assert used <= defined, sorted(used - defined)


# ---------- the engine (engine evaluation, 2026-10-28) ----------

BOX = [((0, 0, 0), (0, 1, 0), (1, 1, 0)), ((0, 0, 0), (1, 1, 0), (1, 0, 0)),  # bottom, facing down
       ((0, 0, 1), (1, 0, 1), (1, 1, 1)), ((0, 0, 1), (1, 1, 1), (0, 1, 1)),  # top, facing up
       ((0, 0, 0), (1, 0, 0), (1, 0, 1)), ((0, 0, 0), (1, 0, 1), (0, 0, 1)),
       ((1, 0, 0), (1, 1, 0), (1, 1, 1)), ((1, 0, 0), (1, 1, 1), (1, 0, 1)),
       ((1, 1, 0), (0, 1, 0), (0, 1, 1)), ((1, 1, 0), (0, 1, 1), (1, 1, 1)),
       ((0, 1, 0), (0, 0, 0), (0, 0, 1)), ((0, 1, 0), (0, 0, 1), (0, 1, 1))]


REAL_BUILD = builder.build  # the autouse `quiet` fixture replaces builder.build with a cube


def test_an_inside_out_mesh_has_a_negative_volume():
    assert abs(builder.signed_volume(BOX) - 1) < 1e-9
    assert abs(builder.signed_volume([(a, c, b) for a, b, c in BOX]) + 1) < 1e-9


@pytest.mark.skipif(not builder.available(), reason="no OpenSCAD on this PC")
def test_an_inside_out_polyhedron_goes_back_to_the_model():
    """The Manifold engine keeps a polyhedron with reversed faces inside out
    (2021 forgave it); the error tells the model how to fix it."""
    good = "polyhedron(points=[[0,0,0],[10,0,0],[0,10,0],[0,0,10]], faces=[[0,1,2],[0,3,1],[0,2,3],[1,3,2]]);"
    bad = "polyhedron(points=[[0,0,0],[10,0,0],[0,10,0],[0,0,10]], faces=[[0,2,1],[0,1,3],[0,3,2],[1,2,3]]);"
    REAL_BUILD(good)
    if builder.manifold():
        with pytest.raises(builder.BuildError, match="inside out"):
            REAL_BUILD(bad)


@pytest.mark.skipif(not builder.available() or not builder.manifold(), reason="needs the Manifold engine")
def test_rounding_a_part_with_a_hole_takes_seconds_not_minutes():
    """Avi, 2026-10-28: "fillet the edges" ran for minutes on the 2021 engine (159 s here)."""
    code = ("$fn=32; minkowski(){ difference(){ cube([90,90,90],center=true); "
            "cylinder(d=30,h=120,center=true);} sphere(r=5); }")
    stl, took = REAL_BUILD(code)
    assert took < 15 and builder.signed_volume(render.read_stl(stl)) > 0


def test_the_model_is_told_about_the_engine_on_the_server(monkeypatch):
    monkeypatch.setattr(builder, "engine", lambda: "2026.10.27")
    monkeypatch.setattr(builder, "manifold", lambda: True)
    fast = llm.system()
    assert "Manifold" in fast and "about a second" in fast and "{" + "speed}" not in fast
    monkeypatch.setattr(builder, "manifold", lambda: False)
    slow = llm.system()
    assert "2021.01" in slow and "Never" in slow and "minkowski or hull a shape" in slow
    for text in (fast, slow):
        assert '{"title"' in text and "clockwise" in text


def test_the_people_screen_names_the_engine(client, world, monkeypatch):
    monkeypatch.setattr(builder, "engine", lambda: "2026.10.27")
    monkeypatch.setattr(builder, "manifold", lambda: True)
    client.force_login(world["avi"])
    html = client.get("/design3d/people/").content.decode()
    assert "Engine: OpenSCAD 2026.10.27 (Manifold)" in html


# ---------- print-ready checks (D3.7) ----------

def _box(x0, y0, z0, x1, y1, z1):
    """A closed box as triangles, faces looking out."""
    return [tuple((x0 + (x1 - x0) * a, y0 + (y1 - y0) * b, z0 + (z1 - z0) * c) for a, b, c in t) for t in BOX]


def _stl(*boxes):
    tris = [t for b in boxes for t in b]
    return (b"solid t\n" + b"".join(
        b"facet normal 0 0 0\nouter loop\n" + b"".join(f"vertex {x} {y} {z}\n".encode() for x, y, z in t)
        + b"endloop\nendfacet\n" for t in tris) + b"endsolid t\n")


def _codes(stl):
    from design3d import printcheck

    return {c["code"]: c for c in printcheck.check(stl)}


def test_a_plain_block_is_ready_to_print():
    assert _codes(_stl(_box(0, 0, 0, 40, 30, 10))) == {}


def test_a_piece_in_the_air_and_two_that_will_fuse_are_warned():
    found = _codes(_stl(_box(0, 0, 0, 10, 10, 10), _box(10.1, 0, 0, 20, 10, 10), _box(30, 0, 4, 35, 5, 9)))
    assert found["floating"]["level"] == "warn" and "4.0 mm above the bed" in found["floating"]["text"]
    assert found["fuse"]["level"] == "warn" and "0.10 mm" in found["fuse"]["text"]


def test_a_thin_wall_and_a_part_too_big_are_warned():
    found = _codes(_stl(_box(0, 0, 0, 0.5, 30, 20), _box(5, 0, 0, 250, 30, 5)))
    assert found["thin_wall"]["level"] == "warn" and "0.50 mm" in found["thin_wall"]["text"]
    assert found["too_big"]["level"] == "warn"
    assert "1.2 mm" in found["thin_wall"]["fix"]


def test_a_part_balanced_on_an_edge_may_tip():
    # A block whose bottom is not at the bed; a slicer would drop it, so it is a note.
    found = _codes(_stl(_box(0, 0, 2, 20, 20, 12)))
    assert found["not_on_bed"]["level"] == "note"


def test_the_checks_are_stored_shown_and_told_to_the_model(client, world, monkeypatch, settings):
    """A built version keeps its findings; the chat line and the Files panel
    show them with Fix it; the self-check tells the model the warnings."""
    floating = _stl(_box(0, 0, 0, 10, 10, 10), _box(30, 0, 4, 35, 5, 9))
    monkeypatch.setattr(builder, "build", lambda code: (builder.check(code), (floating, 0.3))[1])
    d = _design(client, world["dana"])
    _say(client, d, "Two cubes")
    v = d.versions.get()
    assert [c["code"] for c in v.warnings] == ["floating"] and v.print_summary == "1 print warning"
    page = client.get(f"/design3d/d/{d.pk}/").content.decode()
    assert "1 print warning" in page and 'class="d3-btn d3-btn-small d3-btn-quiet d3-fix"' in page
    assert "Put every separate piece flat on z = 0" in page
    poll = client.get(f"/design3d/d/{d.pk}/poll/?after=0").json()
    assert poll["current"]["checks"][0]["code"] == "floating"
    assert any(m.get("print") == "1 print warning" for m in poll["messages"])
    assert "Put every separate piece flat" in jobs._findings(v)


def test_an_older_version_is_checked_when_first_shown(client, world):
    d = _design(client, world["dana"])
    _say(client, d, "A cube")
    v = d.versions.get()
    Version.objects.filter(pk=v.pk).update(checks=None)
    client.get(f"/design3d/d/{d.pk}/")
    v.refresh_from_db()
    assert v.checks is not None


def test_a_part_too_detailed_is_not_checked_beside_the_site(monkeypatch):
    """Memory: the checks run on the site's 512 MB server."""
    from design3d import printcheck

    monkeypatch.setattr(printcheck, "TOO_DETAILED", 10)
    found = printcheck.check(_stl(_box(0, 0, 0, 10, 10, 10), _box(30, 0, 4, 35, 5, 9)))
    assert [c["code"] for c in found] == ["too_detailed"] and found[0]["level"] == "note"


# ---------- "Email me this chat" (Avi, 2026-10-29) ----------

def test_avi_emails_himself_a_whole_chat(client, world):
    """Every message, the model and its cost, the trail, every version's
    code, the pictures, the previews and the current STL."""
    Maker.objects.create(user=world["avi"], display_name="Avi", status=Maker.APPROVED, is_admin=True)
    d = _design(client, world["avi"])
    _say(client, d, "A holder for three pencils", pictures=_jpeg((800, 600)))
    _say(client, d, "Make it taller")
    page = client.get(f"/design3d/d/{d.pk}/").content.decode()
    assert 'id="d3-email"' in page
    mail.outbox.clear()
    r = client.post(f"/design3d/d/{d.pk}/email/")
    assert r.status_code == 302
    sent = mail.outbox[-1]
    assert sent.to == ["avi@example.com"] and sent.subject.startswith(f"design3d chat #{d.pk}:")
    assert "PERSON\n  A holder for three pencils" in sent.body and "Make it taller" in sent.body
    assert "DESIGN3D (" in sent.body and "-> version 1" in sent.body and "Reading your message" in sent.body
    names = [a[0] for a in sent.attachments]
    assert {"v1.scad", "v2.scad", "v1.png", "v2.stl", f"design3d-{d.pk}-chat.txt"} <= set(names)
    assert any(n.startswith("msg") and n.endswith(".jpg") for n in names)


def test_nobody_else_can_email_a_chat(client, world):
    """The button is the admin's, on the admin's own designs: a maker's chat
    is theirs (REQ-D3.41)."""
    d = _design(client, world["dana"])
    _say(client, d, "A box")
    assert 'id="d3-email"' not in client.get(f"/design3d/d/{d.pk}/").content.decode()
    mail.outbox.clear()
    assert client.post(f"/design3d/d/{d.pk}/email/").status_code == 404
    client.force_login(world["avi"])
    assert client.post(f"/design3d/d/{d.pk}/email/").status_code == 404, "not even Avi, on Dana's design"
    assert mail.outbox == []


def test_the_chat_email_carries_the_code_and_a_link_for_a_day(client, world, monkeypatch):
    """Claude reads the mail through a connection that cannot open
    attachments, so the code is in the body and the pictures are on a page
    behind a signed link that lasts a day."""
    from design3d import mail as d3mail

    Maker.objects.create(user=world["avi"], display_name="Avi", status=Maker.APPROVED, is_admin=True)
    d = _design(client, world["avi"])
    _say(client, d, "A holder for this", pictures=_jpeg((800, 600)))
    mail.outbox.clear()
    client.post(f"/design3d/d/{d.pk}/email/")
    body = mail.outbox[-1].body
    assert "----- v1.scad -----" in body and d.versions.get().code[:30] in body
    link = re.search(r"https?://\S+/design3d/x/(\S+)/", body)
    assert link
    client.logout()
    page = client.get(f"/design3d/x/{link.group(1)}/")
    assert page.status_code == 200 and page["X-Robots-Tag"] == "noindex"
    html = page.content.decode()
    assert "data:image/jpeg;base64," in html and "data:image/png;base64," in html and "v1.scad" in html
    assert client.get(f"/design3d/x/{link.group(1)}x/").status_code == 404, "a changed link opens nothing"
    monkeypatch.setattr(d3mail, "EXPORT_HOURS", -1)
    assert client.get(f"/design3d/x/{link.group(1)}/").status_code == 404, "after a day it opens nothing"


# ---------- D3.9: a marked point, the Done page (Avi, 2026-10-29) ----------

def test_a_marked_point_goes_to_the_model_in_the_codes_coordinates(client, world):
    from design3d import llm as d3llm

    d = _design(client, world["dana"])
    _say(client, d, "A box")
    pin = '{"x": 12.5, "y": -3, "z": 40, "nx": 0, "ny": -0.98, "nz": 0.1, "version": 1}'
    client.post(f"/design3d/d/{d.pk}/send/", {"text": "Add a hook here", "pin": pin}, HTTP_ACCEPT="application/json")
    m = d.messages.filter(role=Message.PERSON).last()
    assert m.pin == {"x": 12.5, "y": -3.0, "z": 40.0, "nx": 0.0, "ny": -0.98, "nz": 0.1, "version": 1}
    said = [i for i in d3llm.history(d) if i["role"] == "user"][-1]["content"][0]["text"]
    assert said.startswith("Add a hook here") and "x=12.5, y=-3.0, z=40.0" in said and "the front (-y)" in said
    assert "of version 1" in said
    poll = client.get(f"/design3d/d/{d.pk}/poll/?after=0").json()
    assert [x["pin"] for x in poll["messages"] if x["id"] == m.pk] == [True]
    assert "Point marked on the part" in client.get(f"/design3d/d/{d.pk}/").content.decode()


def test_a_bad_marked_point_is_dropped(client, world):
    d = _design(client, world["dana"])
    for bad in ("not json", '{"x": 1}', '{"x": "nan", "y": 0, "z": 0, "nx": 0, "ny": 0, "nz": 1}',
                '{"x": 1e9, "y": 0, "z": 0, "nx": 0, "ny": 0, "nz": 1}'):
        Message.objects.filter(design=d).delete()
        client.post(f"/design3d/d/{d.pk}/send/", {"text": "here", "pin": bad}, HTTP_ACCEPT="application/json")
        assert d.messages.filter(role=Message.PERSON).get().pin is None, bad


def test_the_done_page_downloads_sends_shares_and_promises_a_print(client, world):
    d = _design(client, world["dana"])
    assert client.get(f"/design3d/d/{d.pk}/done/").status_code == 302, "no part yet: back to the chat"
    _say(client, d, "A box")
    page = client.get(f"/design3d/d/{d.pk}/").content.decode()
    assert f'href="/design3d/d/{d.pk}/done/"' in page and 'id="d3-done"' in page
    html = client.get(f"/design3d/d/{d.pk}/done/").content.decode()
    for words in ("Download STL", "OpenSCAD file", "Email me the files", "Share with people in design3d", "Coming soon"):
        assert words in html, words
    assert re.search(r"<button[^>]*disabled[^>]*>Coming soon", html)
    r = client.post(f"/design3d/d/{d.pk}/edit/", {"action": "share", "shared": "1", "next": "done"})
    assert r["Location"] == f"/design3d/d/{d.pk}/done/" and Design.objects.get(pk=d.pk).is_shared
    mail.outbox.clear()
    client.post(f"/design3d/d/{d.pk}/send-files/")
    sent = mail.outbox[-1]
    assert sent.to == ["dana@example.com"] and {a[0].rsplit(".", 1)[1] for a in sent.attachments} == {"stl", "scad"}
    client.force_login(world["eli"])
    assert client.get(f"/design3d/d/{d.pk}/done/").status_code == 404, "another person's part"
    assert client.post(f"/design3d/d/{d.pk}/send-files/").status_code == 404


# ---------- asking tells Avi; invitations (Avi, 2026-10-29) ----------

def test_asking_to_join_emails_avi_once_per_request(client, world):
    mail.outbox.clear()
    bob = _user("bob@example.com", first="Bob")
    client.force_login(bob)
    client.post("/design3d/ask/", {"reason": "I print parts for my class"})
    notice = [m for m in mail.outbox if "asks to join" in m.subject]
    assert len(notice) == 1 and notice[0].to == ["avi@example.com"]
    assert "I print parts for my class" in notice[0].body and "/design3d/people/" in notice[0].body
    client.post("/design3d/ask/", {"reason": "again"})
    assert len([m for m in mail.outbox if "asks to join" in m.subject]) == 1, "still waiting: no second mail"
    Maker.objects.filter(user=bob).update(status=Maker.DECLINED)
    client.post("/design3d/ask/", {"reason": "please"})
    assert len([m for m in mail.outbox if "asks to join" in m.subject]) == 2, "asking again after a decline mails again"


def _invite(client, world, email="new@example.com", name="Noa"):
    from design3d.models import Invite

    client.force_login(world["avi"])
    mail.outbox.clear()
    client.post("/design3d/people/", {"action": "invite", "email": email, "name": name})
    return Invite.objects.get(email=email)


def test_an_invitation_lets_one_person_in_once(client, world):
    from design3d.models import Invite

    inv = _invite(client, world)
    sent = [m for m in mail.outbox if m.subject == "You are invited to design3d"]
    assert len(sent) == 1 and sent[0].to == ["new@example.com"] and f"/design3d/i/{inv.token}/" in sent[0].body
    assert "Hi Noa" in sent[0].body
    people = client.get("/design3d/people/").content.decode()
    assert "new@example.com" in people and "open until" in people
    link = f"/design3d/i/{inv.token}/"

    client.logout()
    page = client.get(link)
    assert page.status_code == 200 and "Sign in to accept" in page.content.decode()
    assert Invite.objects.get(pk=inv.pk).status == "open", "looking signed out burns nothing"

    noa = _user("noa@example.com", first="Noa")
    client.force_login(noa)
    mail.outbox.clear()
    r = client.get(link)
    assert r.status_code == 302 and r["Location"] == "/design3d/designs/"
    inv.refresh_from_db()
    assert inv.status == "used" and inv.used_by == noa
    assert Maker.objects.get(user=noa).status == Maker.APPROVED
    assert [m.subject for m in mail.outbox] == ["You are in design3d"], "let in through the one function that mails"
    assert client.get(link)["Location"] == "/design3d/designs/", "the same person may open it again"

    eli = _user("eli2@example.com", first="Eli")
    client.force_login(eli)
    refused = client.get(link)
    assert refused.status_code == 410 and "already used" in refused.content.decode()
    assert not Maker.objects.filter(user=eli, status=Maker.APPROVED).exists()
    assert client.get("/design3d/i/not-a-token/").status_code == 404


def test_a_withdrawn_or_old_invitation_lets_nobody_in(client, world):
    from design3d.models import Invite

    inv = _invite(client, world)
    client.post("/design3d/people/", {"action": "revoke", "invite": inv.pk})
    assert Invite.objects.get(pk=inv.pk).status == "revoked"
    sam = _user("sam@example.com", first="Sam")
    client.force_login(sam)
    page = client.get(f"/design3d/i/{inv.token}/")
    assert page.status_code == 410 and "withdrew it" in page.content.decode()

    old = _invite(client, world, email="old@example.com")
    Invite.objects.filter(pk=old.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    client.force_login(sam)
    page = client.get(f"/design3d/i/{old.token}/")
    assert page.status_code == 410 and "14 days" in page.content.decode()
    assert not Maker.objects.filter(user=sam, status=Maker.APPROVED).exists()


def test_only_avi_invites(client, world):
    client.force_login(world["dana"])
    assert client.post("/design3d/people/", {"action": "invite", "email": "x@example.com"}).status_code == 404
    assert client.get("/design3d/api/invites/").status_code in (401, 403)
    client.force_login(world["avi"])
    assert client.get("/design3d/api/invites/").status_code == 200
