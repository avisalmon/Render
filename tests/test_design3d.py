"""design3d: the door, the chat turn, builds, versions, sliders, sharing,
limits, files and the API. docs/design3d/spec.md.

No test calls OpenAI (the stub answers, or a fake replaces `llm.ask`) and
no test reaches the image check's outside service (mistakes 26, 47). The
builder is a fake that returns a cube, except in the one test that runs
the real OpenSCAD when it is on this machine.
"""

import io
import json
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
    settings.DESIGN3D_TOUR = False  # the tour's own tests turn it on
    settings.OPENAI_API_KEY = ""
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    monkeypatch.setattr("app.safety.image_is_safe", lambda *a, **k: (True, ""), raising=False)
    monkeypatch.setattr(builder, "build", lambda code, part=None, reference=None: (builder.check(code), (CUBE, 0.4))[1])


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
    monkeypatch.setattr(llm, "ask", lambda items, **kw: ({"title": "", "message": "How thick is the pencil? A coin next to it helps.",
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

    def ask(items, **kw):
        calls.append(items[-1]["content"])
        m = Message.objects.filter(role=Message.ASSISTANT).latest("id")
        d_now = Design.objects.get(pk=m.design_id)
        steps.append((m.state, m.step, d_now.current.number if d_now.current else None))
        n = len(calls)
        code = "cube(" if n == 1 else good
        return ({"title": "Cube", "message": f"turn {n}", "assumptions": [], "code": code if n < 3 else None,
                 "parameters": [{"name": "size", "label": "Size", "min": 5, "max": 50}]}, {"in": 10, "cached": 0, "out": 5}, "gpt-6.1-terra")

    def build(code, **kw):
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
        "Checking the part against what you asked", "Checked: turn 3"]
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
    monkeypatch.setattr(llm, "ask", lambda items, **kw: (seen.append(items), ({"title": "", "message": "ok", "assumptions": [], "code": None, "parameters": []}, {"in": 1, "cached": 0, "out": 1}, "gpt-6.1-terra"))[1])
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
    monkeypatch.setattr(llm, "ask", lambda items, **kw: pytest.fail("the sliders must not call the model"))
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
    monkeypatch.setattr(builder, "build", lambda code, part=None, reference=None: (builder.check(code), (floating, 0.3))[1])
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


def _invite(client, world):
    """Avi taps Invite a friend: one link, nothing typed (2026-10-30)."""
    from design3d.models import Invite

    client.force_login(world["avi"])
    mail.outbox.clear()
    r = client.post("/design3d/people/", {"action": "invite"})
    inv = Invite.objects.order_by("-pk").first()
    assert r["Location"] == f"/design3d/people/?new={inv.pk}#d3-invites"
    return inv


def test_an_invitation_link_lets_one_person_in_once(client, world):
    """Avi, 2026-10-30: like a coupon. One tap makes it, he sends it by
    WhatsApp, mail or any share sheet; whoever uses it first is in, and it is
    used up."""
    from urllib.parse import unquote

    from design3d.models import Invite

    inv = _invite(client, world)
    assert mail.outbox == [], "design3d mails nothing: Avi sends the link himself"
    people = client.get(f"/design3d/people/?new={inv.pk}").content.decode()
    link = f"/design3d/i/{inv.token}/"
    assert 'class="d3-share"' in people and link in people
    whatsapp = re.search(r'data-share="whatsapp" href="([^"]+)"', people).group(1)
    assert whatsapp.startswith("https://wa.me/?text=") and link in unquote(whatsapp.replace("&amp;", "&"))
    assert "chat that turns a few words, a hand sketch or a photo" in unquote(whatsapp)
    assert 'data-share="mail" href="mailto:?subject=' in people and 'data-share="copy"' in people
    assert "Open link" in people and "open until" in people

    client.logout()
    page = client.get(link)
    html = page.content.decode()
    assert page.status_code == 200 and "invited to design3d" in html and "Continue with Google" in html
    assert f"next={link}" in html, "signing in or up comes back to the link"
    assert Invite.objects.get(pk=inv.pk).status == "open", "looking signed out burns nothing"

    # A new person signs up through the link and is in at once.
    r = client.post(f"/design3d/signup/?next={link}", {"email": "noa@example.com", "name": "Noa",
                                                       "password1": "d3-noa-pass-8812", "password2": "d3-noa-pass-8812",
                                                       "next": link})
    assert r.status_code == 302 and r["Location"] == link, r.content.decode()[:300]
    mail.outbox.clear()
    r = client.get(link)
    assert r.status_code == 302 and r["Location"] == "/design3d/designs/"
    from django.contrib.auth.models import User

    noa = User.objects.get(email="noa@example.com")
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


def test_an_existing_member_who_opens_a_link_is_let_in(client, world):
    """Someone who already has a babook account (and even asked and was
    declined) is let in by the link at once."""
    inv = _invite(client, world)
    bob = _user("bob@example.com", first="Bob", status=Maker.DECLINED)
    client.force_login(bob)
    assert client.get(f"/design3d/i/{inv.token}/")["Location"] == "/design3d/designs/"
    assert Maker.objects.get(user=bob).status == Maker.APPROVED


def test_a_withdrawn_or_old_invitation_lets_nobody_in(client, world):
    from design3d.models import Invite

    inv = _invite(client, world)
    client.post("/design3d/people/", {"action": "revoke", "invite": inv.pk})
    assert Invite.objects.get(pk=inv.pk).status == "revoked"
    sam = _user("sam@example.com", first="Sam")
    client.force_login(sam)
    page = client.get(f"/design3d/i/{inv.token}/")
    assert page.status_code == 410 and "withdrew it" in page.content.decode()

    old = _invite(client, world)
    Invite.objects.filter(pk=old.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    client.force_login(sam)
    page = client.get(f"/design3d/i/{old.token}/")
    assert page.status_code == 410 and "14 days" in page.content.decode()
    assert not Maker.objects.filter(user=sam, status=Maker.APPROVED).exists()


def test_only_avi_invites(client, world):
    client.force_login(world["dana"])
    assert client.post("/design3d/people/", {"action": "invite"}).status_code == 404
    assert client.get("/design3d/api/invites/").status_code in (401, 403)
    client.force_login(world["avi"])
    assert client.get("/design3d/api/invites/").status_code == 200


# ---------- Chapter 7: several parts (approved by Avi 2026-10-29) ----------

BOX_AND_LID = """
part = "all";
clear = 0.3;
w = 60; d = 40; h = 30; wall = 2; lid_h = 4; lip = 5;
module box() { difference() { cube([w, d, h]); translate([wall, wall, wall]) cube([w - 2*wall, d - 2*wall, h]); } }
module lid() {
  translate([0, 0, h]) cube([w, d, lid_h]);
  translate([wall + clear, wall + clear, h - lip]) cube([w - 2*wall - 2*clear, d - 2*wall - 2*clear, lip]);
}
if (part == "all" || part == "box") box();
if (part == "all" || part == "lid") lid();
"""
TWO_PARTS = [{"name": "box", "label": "Box", "count": 1, "printed": True, "print": [0, 0, 0]},
             {"name": "lid", "label": "Lid", "count": 1, "printed": True, "print": [0, 0, 0]}]


def _parts_reply(monkeypatch, code, declared=TWO_PARTS):
    monkeypatch.setattr(llm, "ask", lambda items, **kw: ({"title": "Box with lid", "message": "Here it is.", "assumptions": [],
                                                    "code": code, "parameters": [{"name": "clear", "label": "Fit", "min": 0, "max": 1}],
                                                    "parts": declared}, {"in": 1, "cached": 0, "out": 1}, "stub"))
    monkeypatch.setattr(builder, "build", REAL_BUILD)


@pytest.mark.skipif(not builder.available(), reason="no OpenSCAD on this PC")
def test_a_box_and_its_lid_are_built_as_two_parts(client, world, monkeypatch):
    import zipfile

    _parts_reply(monkeypatch, BOX_AND_LID)
    d = _design(client, world["dana"])
    _say(client, d, "A box with a lid")
    v = d.versions.get()
    assert v.status == Version.READY, v.error
    box, lid = v.parts.order_by("position")
    assert (box.name, lid.name) == ("box", "lid") and box.printed and lid.printed
    assert lid.orientation == "180,0,0 auto", "the lid is drawn on its plug and printed upside down"
    assert v.fit == [] and v.print_summary == "ready to print"
    assert v.size_mm == "60 x 40 x 34", "the assembly's size"
    with zipfile.ZipFile(v.file_3mf.open("rb")) as z:
        model = z.read("3D/3dmodel.model").decode()
    assert model.count("<object ") == 2 and 'name="Box"' in model and 'name="Lid"' in model

    data = client.get(f"/design3d/d/{d.pk}/poll/?after=0").json()["current"]
    assert [p["name"] for p in data["parts"]] == ["box", "lid"] and data["file_3mf"].endswith("/3mf/")
    assert client.get(data["file_3mf"]).status_code == 200
    assert client.get(data["parts"][1]["download"]).status_code == 200
    assert client.get(data["parts"][0]["stl"]).status_code == 200, "a part's file passes the private file check"
    client.force_login(world["eli"])
    assert client.get(data["parts"][0]["stl"]).status_code == 404, "and only for its owner"
    client.force_login(world["dana"])

    # Sliders keep the parts; the model is told them next time.
    client.post(f"/design3d/d/{d.pk}/sliders/", {"from": 1, "clear": "0.4"})
    v2 = d.versions.get(number=2)
    assert v2.status == Version.READY and [p.name for p in v2.parts.all()] == ["box", "lid"] and "clear = 0.4;" in v2.code
    said = [i for i in llm.history(d) if i["role"] == "assistant"][-1]["content"]
    assert '"parts"' in said and '"lid"' in said


@pytest.mark.skipif(not builder.available(), reason="no OpenSCAD on this PC")
def test_a_lid_too_tight_or_overlapping_is_a_fit_warning(client, world, monkeypatch):
    for clear, code_name in (("0.05", "too_tight"), ("-0.5", "overlap")):
        _parts_reply(monkeypatch, BOX_AND_LID.replace("clear = 0.3;", f"clear = {clear};"))
        d = _design(client, world["dana"])
        _say(client, d, "A box with a lid")
        v = d.versions.get()
        assert [f["code"] for f in v.fit] == [code_name], clear
        assert v.warnings and v.print_summary.endswith("print warning")
        assert "Box and Lid" in client.get(f"/design3d/d/{d.pk}/").content.decode()


@pytest.mark.skipif(not builder.available(), reason="no OpenSCAD on this PC")
def test_a_part_the_code_does_not_draw_fails_the_build_with_a_reason(client, world, monkeypatch):
    declared = TWO_PARTS + [{"name": "handle", "label": "Handle", "count": 1, "printed": True, "print": [0, 0, 0]}]
    _parts_reply(monkeypatch, BOX_AND_LID, declared)
    d = _design(client, world["dana"])
    _say(client, d, "A box with a lid and a handle")
    v = d.versions.order_by("number").first()
    assert v.status == Version.FAILED and 'part "handle" came out empty' in v.error
    assert not v.parts.exists()


def test_the_part_list_is_cleaned():
    from design3d import parts

    assert parts.clean([{"name": "only"}]) == [], "one part is not several"
    got = parts.clean([{"name": "Box"}, {"name": "box"}, {"name": "bad name"}, {"name": "all"}, {"name": "lid", "count": 99,
                                                                                                   "printed": False, "print": "x"}])
    assert [(p["name"], p["count"], p["printed"], p["print"]) for p in got] == [("box", 1, True, [0, 0, 0]), ("lid", 20, False, [0, 0, 0])]
    assert len(parts.clean([{"name": f"p{i}"} for i in range(12)])) == 8


# ---------- a copy of a shared design; a picture full size (Avi, 2026-10-29) ----------

def test_a_shared_design_is_copied_without_its_chat(client, world):
    d = _design(client, world["dana"])
    _say(client, d, "A secret pencil holder", pictures=_jpeg((800, 600)))
    client.post(f"/design3d/d/{d.pk}/edit/", {"action": "share", "shared": "1"})
    d.refresh_from_db()
    client.force_login(world["eli"])
    assert 'id="d3-copy"' in client.get(f"/design3d/shared/{d.pk}/").content.decode()
    r = client.post(f"/design3d/shared/{d.pk}/copy/")
    mine = Design.objects.get(owner__user=world["eli"])
    assert r["Location"] == f"/design3d/d/{mine.pk}/" and mine.copied_from == d and mine.title.endswith("(copy)")
    v = mine.current
    assert v.number == 1 and v.made_by == Version.COPY and v.code == d.current.code and v.status == Version.READY
    assert v.stl.name != d.current.stl.name, "its own files"
    assert client.get(f"/design3d/files/{v.stl.name}").status_code == 200
    said = list(mine.messages.values_list("role", "text"))
    assert len(said) == 1 and said[0][0] == Message.ASSISTANT and "Dana" in said[0][1]
    assert not Picture.objects.filter(message__design=mine).exists(), "the pictures stay with their owner"
    assert "secret pencil holder" not in client.get(f"/design3d/d/{mine.pk}/").content.decode().lower()
    assert [p.name for p in v.parameters.all()] == [p.name for p in d.current.parameters.all()]
    _say(client, mine, "Make it taller")
    assert mine.versions.count() == 2, "and it carries on in its new owner's chat"
    assert Design.objects.get(pk=d.pk).versions.count() == 1, "the original is untouched"


def test_only_a_shared_design_can_be_copied(client, world):
    d = _design(client, world["dana"])
    _say(client, d, "A box")
    client.force_login(world["eli"])
    assert client.post(f"/design3d/shared/{d.pk}/copy/").status_code == 404
    assert not Design.objects.filter(owner__user=world["eli"]).exists()


def test_a_picture_in_the_chat_opens_full_size_and_saves(client, world):
    d = _design(client, world["dana"])
    _say(client, d, "Like this", pictures=_jpeg((800, 600)))
    page = client.get(f"/design3d/d/{d.pk}/").content.decode()
    src = re.search(r'class="d3-pic" data-full="([^"]+)"', page).group(1)
    assert 'id="d3-lightbox"' in page and 'id="d3-pic-save"' in page
    saved = client.get(src + "?download=1")
    assert saved.status_code == 200 and saved["Content-Disposition"].startswith("attachment")
    assert "attachment" not in client.get(src).get("Content-Disposition", "")
    client.force_login(world["eli"])
    assert client.get(src + "?download=1").status_code == 404, "still the owner's only"



# ---------- friends: everyone's own link, and who brought whom (Avi, 2026-10-30) ----------

def test_a_member_link_brings_a_friend_who_is_in_at_once_and_counted(client, world):
    from design3d.models import Maker as M

    client.force_login(world["dana"])
    page = client.get("/design3d/designs/").content.decode()
    dana = M.objects.get(user=world["dana"])
    link = re.search(r"/design3d/r/[\w-]+/", page).group(0)
    assert "Invite friends" in page and 'data-share="whatsapp"' in page and "Each send gets its own link" in page
    assert "Dana invites you to try design3d" in page

    client.logout()
    assert client.get(link)["Location"] == "/design3d/"
    door = client.get("/design3d/").content.decode()
    assert "Dana invited you." in door
    assert "Continue with Google" in door, "signing in from here lets them in"
    bob = _user("bob@example.com", first="Bob")
    client.force_login(bob)
    assert client.get("/design3d/")["Location"] == "/design3d/designs/", "Chapter 8: in at once, no waiting for Avi"
    joined = M.objects.get(user=bob)
    assert joined.status == M.APPROVED and joined.referred_by == dana and joined.invited and joined.turns_left == 30
    assert access_can_enter(bob)

    client.force_login(world["avi"])
    people = client.get("/design3d/people/").content.decode()
    assert "invited by Dana" in people and "brought 1" in people
    client.force_login(world["dana"])
    assert "So far 1 joined through you" in client.get("/design3d/designs/").content.decode()


def access_can_enter(user):
    from design3d import access

    return access.can_enter(user)


def test_a_friend_link_never_credits_yourself_or_an_unknown_code(client, world):
    from design3d.models import Maker as M

    client.get("/design3d/r/nothing-here/")
    assert "invited you" not in client.get("/design3d/").content.decode()
    carl = _user("carl@example.com", first="Carl")
    client.force_login(carl)
    client.post("/design3d/ask/", {"reason": "me"})
    me = M.objects.get(user=carl)
    assert me.referred_by is None
    M.objects.filter(pk=me.pk).update(status=M.APPROVED)
    client.get(f"/design3d/r/{me.code()}/")
    M.objects.filter(pk=me.pk).update(status=M.DECLINED)
    client.post("/design3d/ask/", {"reason": "again"})
    assert M.objects.get(pk=me.pk).referred_by is None, "never your own friend"


def test_a_coupon_credits_avi(client, world):
    from design3d.models import Maker as M

    inv = _invite(client, world)
    zoe = _user("zoe@example.com", first="Zoe")
    client.force_login(zoe)
    client.get(f"/design3d/i/{inv.token}/")
    assert M.objects.get(user=zoe).referred_by == M.objects.get(user=world["avi"])


# ---------- Chapter 8: seats, turns, the tour, analysis (Avi, 2026-10-30) ----------

def _by_friend(client, friend_user, email, first):
    """A newcomer who opens a friend's link and signs in."""
    from design3d.models import Maker as M

    code = M.objects.get(user=friend_user).code()
    client.logout()
    client.get(f"/design3d/r/{code}/")
    u = _user(email, first=first)
    client.force_login(u)
    client.get("/design3d/")
    return M.objects.get(user=u)


def test_past_the_seat_limit_newcomers_wait_and_come_in_when_it_rises(client, world):
    from design3d.models import Maker as M, Settings

    cfg = Settings.get()
    cfg.seat_limit = 1
    cfg.save()
    first = _by_friend(client, world["dana"], "f1@example.com", "First")
    assert first.status == M.APPROVED and first.turns_left == 30
    mail.outbox.clear()
    second = _by_friend(client, world["dana"], "f2@example.com", "Second")
    assert second.status == M.WAITING_SEAT and not access_can_enter(second.user)
    door = client.get("/design3d/").content.decode()
    assert "You are on the waiting list." in door and mail.outbox == []

    client.force_login(world["avi"])
    people = client.get("/design3d/people/").content.decode()
    assert "1 of 1 seats used · 1 waiting" in people and "Waiting for a seat" in people and "f2@example.com" in people
    client.post("/design3d/people/", {"action": "seats", "seat_limit": "2"})
    second.refresh_from_db()
    assert second.status == M.APPROVED and second.turns_left == 30
    assert [m.to for m in mail.outbox if m.subject == "You are in design3d"] == [["f2@example.com"]]
    client.force_login(world["dana"])
    assert client.post("/design3d/people/", {"action": "seats", "seat_limit": "99"}).status_code == 404, "Avi's alone"


def test_a_one_time_link_is_an_invitation_with_30_turns(client, world):
    from design3d.models import Maker as M

    inv = _invite(client, world)
    zoe = _user("zoe2@example.com", first="Zoe")
    client.force_login(zoe)
    client.get(f"/design3d/i/{inv.token}/")
    m = M.objects.get(user=zoe)
    assert m.status == M.APPROVED and m.invited and m.turns_left == 30


def test_whom_avi_approves_has_no_turn_limit(client, world):
    from design3d.models import Maker as M

    bob = _user("bob3@example.com", first="Bob")
    client.force_login(bob)
    client.post("/design3d/ask/", {"reason": "please"})
    m = M.objects.get(user=bob)
    client.force_login(world["avi"])
    client.post("/design3d/people/", {"maker": m.pk, "action": "approve"})
    m.refresh_from_db()
    assert m.status == M.APPROVED and m.turns_left is None and not m.invited


def test_a_message_is_a_turn_and_at_zero_the_chat_stops(client, world):
    from design3d.models import Maker as M

    M.objects.filter(user=world["dana"]).update(turns_left=2)
    d = _design(client, world["dana"])
    assert 'id="d3-turns"' in client.get(f"/design3d/d/{d.pk}/").content.decode()
    _say(client, d, "A box")
    assert M.objects.get(user=world["dana"]).turns_left == 1
    client.post(f"/design3d/d/{d.pk}/sliders/", {"from": 1, "height": "60"})
    assert M.objects.get(user=world["dana"]).turns_left == 1, "sliders are free"
    _say(client, d, "Taller")
    assert client.get(f"/design3d/d/{d.pk}/poll/").json()["turns_left"] == 0
    r = _say(client, d, "Wider")
    assert r.status_code == 402 and "Invite a friend" in r.json()["error"]
    assert M.objects.get(user=world["dana"]).turns_left == 0 and d.messages.filter(text="Wider").count() == 0


def test_a_friends_first_part_gives_30_turns_once(client, world):
    from design3d.models import Maker as M

    M.objects.filter(user=world["dana"]).update(turns_left=5)
    newcomer = _by_friend(client, world["dana"], "n1@example.com", "Nell")
    d = _design(client, newcomer.user)
    _say(client, d, "A box")
    assert M.objects.get(user=world["dana"]).turns_left == 35
    _say(client, d, "Taller")
    assert M.objects.get(user=world["dana"]).turns_left == 35, "once per friend"
    assert M.objects.get(pk=newcomer.pk).rewarded_at is not None


def test_the_tour_comes_first_and_cannot_be_skipped(client, world, settings):
    from design3d.models import Maker as M

    settings.DESIGN3D_TOUR = True
    newcomer = _by_friend(client, world["dana"], "t1@example.com", "Tal")
    assert client.get("/design3d/designs/")["Location"] == "/design3d/welcome/"
    page = client.get("/design3d/welcome/?step=7").content.decode()
    assert 'data-step="1"' in page, "no jumping ahead"
    assert client.post("/design3d/welcome/")["Location"] == "/design3d/welcome/?step=2", "no finishing early"
    for n in range(2, 8):
        html = client.get(f"/design3d/welcome/?step={n}").content.decode()
        assert f'data-step="{n}"' in html
    assert "You have 30 turns" in html and "+30 FOR EVERY FRIEND" in html and 'id="d3-tour-start"' in html
    assert client.post("/design3d/welcome/")["Location"] == "/design3d/designs/"
    assert M.objects.get(pk=newcomer.pk).tour_done_at is not None
    assert client.get("/design3d/designs/").status_code == 200
    for n, pic in ((2, "words-3d"), (3, "sketch-3d"), (4, "cup-3d"), (5, "pin-3d")):
        assert pic in client.get(f"/design3d/welcome/?step={n}").content.decode()


def test_avi_sends_the_new_chats_for_analysis(client, world):
    import io
    import zipfile

    d = _design(client, world["dana"])
    _say(client, d, "A holder like this", pictures=_jpeg((600, 400)))
    client.force_login(world["avi"])
    mail.outbox.clear()
    client.post("/design3d/people/", {"action": "export"})
    sent = mail.outbox[-1]
    assert sent.to == ["avi.salmon@gmail.com", "avisalmon@intel.com"] and sent.subject.startswith("design3d chats for analysis")
    link = re.search(r"https?://\S+(/design3d/x/a/\S+/)", sent.body).group(1)
    z = zipfile.ZipFile(io.BytesIO(sent.attachments[0][1]))
    names = z.namelist()
    root = f"design-{d.pk}"
    assert {f"{root}/chat.txt", f"{root}/design.json", f"{root}/v1.scad", "README.txt"} <= set(names)
    assert any(n.startswith(f"{root}/pictures/") for n in names)
    assert "A holder like this" in z.read(f"{root}/chat.txt").decode()
    client.logout()
    got = client.get(link)
    assert got.status_code == 200 and got["Content-Type"] == "application/zip"
    assert client.get(link.replace("/a/", "/a/x")).status_code == 404

    # The next send carries only what is new.
    client.force_login(world["avi"])
    mail.outbox.clear()
    client.post("/design3d/people/", {"action": "export"})
    assert "0 designs, 0 new messages" in mail.outbox[-1].body
    _say_as = _design(client, world["dana"])
    _say(client, _say_as, "Another")
    client.force_login(world["avi"])
    client.post("/design3d/people/", {"action": "export"})
    assert "1 designs, 2 new messages" in mail.outbox[-1].body
    client.force_login(world["dana"])
    assert client.post("/design3d/people/", {"action": "export"}).status_code == 404


def test_every_send_of_a_friend_link_is_unique_and_lets_one_person_in(client, world):
    """Avi, 2026-10-30: "rotate the key every time I access the page or copy
    it or share it, so I won't send the same one twice"."""
    from design3d.models import FriendLink, Maker as M

    client.force_login(world["dana"])
    one = re.search(r"/design3d/r/([\w-]+)/", client.get("/design3d/designs/").content.decode()).group(1)
    two = re.search(r"/design3d/r/([\w-]+)/", client.get("/design3d/designs/").content.decode()).group(1)
    three = client.post("/design3d/r/new/").json()
    assert len({one, two, three["link"].rstrip("/").rsplit("/", 1)[1]}) == 3, "a new link every time"
    assert "Dana invites you" in three["text"] and three["whatsapp"].startswith("https://wa.me/?text=")

    client.logout()
    client.get(f"/design3d/r/{one}/")
    kim = _user("kim@example.com", first="Kim")
    client.force_login(kim)
    assert client.get("/design3d/")["Location"] == "/design3d/designs/"
    fl = FriendLink.objects.get(code=one)
    assert fl.used_by == kim and M.objects.get(user=kim).referred_by.user == world["dana"]
    client.get(f"/design3d/r/{one}/")
    assert client.get("/design3d/")["Location"] == "/design3d/designs/", "the same person may open it again"

    client.logout()
    client.get(f"/design3d/r/{one}/")
    lee = _user("lee@example.com", first="Lee")
    client.force_login(lee)
    door = client.get("/design3d/").content.decode()
    assert "already used" in door and not M.objects.filter(user=lee, status=M.APPROVED).exists()
    client.get(f"/design3d/r/{two}/")
    assert client.get("/design3d/")["Location"] == "/design3d/designs/", "a fresh link works"
    assert client.get("/design3d/api/friend-links/").status_code == 200


# ---------- an attached STL, web search, an email answered in place (Avi, 2026-10-30) ----------

def _stl_upload(name="bracket.stl"):
    return SimpleUploadedFile(name, _stl(_box(0, 0, 0, 40, 20, 10)), content_type="model/stl")


def test_an_attached_stl_is_kept_measured_and_shown_to_the_model(client, world):
    from design3d.models import Reference

    d = _design(client, world["dana"])
    r = client.post(f"/design3d/d/{d.pk}/send/", {"text": "A holder for this", "pictures": [_stl_upload()]},
                    HTTP_ACCEPT="application/json")
    assert r.status_code == 200
    ref = Reference.objects.get(message__design=d)
    assert ref.name == "bracket.stl" and ref.size_mm == "40 x 20 x 10" and ref.triangles == 12 and ref.sheet
    assert ref.bounds == [[0, 0, 0], [40, 20, 10]]
    said = [i for i in llm.history(d) if i["role"] == "user"][0]["content"]
    assert 'attached an STL, "bracket.stl": 40 x 20 x 10 mm' in said[0]["text"] and 'import("reference.stl")' in said[0]["text"]
    assert said[1]["type"] == "input_image", "its three views go along"
    page = client.get(f"/design3d/d/{d.pk}/").content.decode()
    assert "bracket.stl · 40 x 20 x 10 mm" in page


def test_a_bad_stl_is_refused_with_a_reason(client, world):
    d = _design(client, world["dana"])
    bad = SimpleUploadedFile("broken.stl", b"not an stl at all", content_type="model/stl")
    r = client.post(f"/design3d/d/{d.pk}/send/", {"text": "this", "pictures": [bad]}, HTTP_ACCEPT="application/json")
    assert r.status_code == 400 and "could not be read" in r.json()["error"]


def test_only_reference_stl_may_be_imported_and_only_when_attached():
    builder.check('difference(){ import("reference.stl"); cube(5); }', allow_reference=True)
    with pytest.raises(builder.BuildError):
        builder.check('import("reference.stl");')
    for bad in ('import("/etc/passwd");', 'import("reference.stl"); import("other.stl");', 'include <reference.stl>'):
        with pytest.raises(builder.BuildError):
            builder.check(bad, allow_reference=True)
    with pytest.raises(builder.BuildError, match="no STL is attached"):
        REAL_BUILD('import("reference.stl");')


@pytest.mark.skipif(not builder.available(), reason="no OpenSCAD on this PC")
def test_the_code_builds_on_the_attached_stl():
    stl, _ = REAL_BUILD('difference(){ import("reference.stl"); translate([5, 5, 5]) cube([30, 10, 10]); }',
                        reference=_stl(_box(0, 0, 0, 40, 20, 10)))
    assert render.size_mm(render.read_stl(stl)) == "40 x 20 x 10"


def test_web_search_is_offered_once_a_turn_noted_and_counted(client, world, monkeypatch, settings):
    from types import SimpleNamespace as NS

    settings.OPENAI_API_KEY = "sk-test"
    calls = []

    class Fake:
        class responses:
            @staticmethod
            def create(**kw):
                calls.append(kw)
                out = [NS(type="web_search_call", action=NS(query="DE10-Lite dimensions")), NS(type="message")]
                text = json.dumps({"title": "Plate", "message": "Terasic lists 97.5 x 80 mm.?utm_source=openai",
                                   "assumptions": [], "code": None, "parameters": []})
                return NS(output=out, output_text=text,
                          usage=NS(input_tokens=1000, output_tokens=100, input_tokens_details=NS(cached_tokens=0)))

    monkeypatch.setattr(llm, "_openai", lambda: Fake)
    d = _design(client, world["dana"])
    _say(client, d, "Find the DE10-Lite dimensions")
    assert calls[0].get("tools") == [{"type": "web_search"}]
    done = d.messages.get(role=Message.ASSISTANT)
    assert "Searched the web: DE10-Lite dimensions" in [t[1] for t in done.trail]
    assert done.text == "Terasic lists 97.5 x 80 mm." and done.cost_usd >= llm.SEARCH_COST


def test_email_me_this_chat_answers_in_place(client, world):
    Maker.objects.create(user=world["avi"], display_name="Avi", status=Maker.APPROVED, is_admin=True)
    d = _design(client, world["avi"])
    _say(client, d, "A box")
    page = client.get(f"/design3d/d/{d.pk}/").content.decode()
    assert re.search(r'action="/design3d/d/\d+/email/"[^>]*data-async', page)
    r = client.post(f"/design3d/d/{d.pk}/email/", HTTP_ACCEPT="application/json")
    assert r.status_code == 200 and r.json() == {"ok": True, "message": "Sent to avi@example.com."}


# ---------- the first analysis's fixes; sizes on the part (Avi, 2026-10-30) ----------

def test_a_server_error_is_not_sent_back_to_the_model(client, world, monkeypatch, settings):
    settings.OPENAI_API_KEY = "sk-test"
    calls = []

    def ask(items, **kw):
        calls.append(1)
        return ({"title": "Box", "message": "Here it is.", "assumptions": [], "code": "cube(10);", "parameters": []},
                {"in": 1, "cached": 0, "out": 1}, "stub")

    def build(code, **kw):
        raise builder.ServerError("AppRun: error while loading shared libraries: libOpenGL.so.0")

    monkeypatch.setattr(llm, "ask", ask)
    monkeypatch.setattr(builder, "build", build)
    d = _design(client, world["dana"])
    _say(client, d, "A box")
    done = d.messages.get(role=Message.ASSISTANT)
    assert len(calls) == 1, "no repair calls on our own problem"
    assert "Something on our side stopped the build" in done.text
    assert any("not sent back to the model" in t[1] for t in done.trail)


def test_a_corrected_part_comes_with_one_answer(client, world, monkeypatch, settings):
    settings.OPENAI_API_KEY = "sk-test"
    answers = iter([("First answer: a box. How wide?", "cube(10);"), ("The whole answer, corrected: a box 20 wide.", "cube(20);")])

    def ask(items, **kw):
        text, code = next(answers)
        return ({"title": "Box", "message": text, "assumptions": [], "code": code, "parameters": []},
                {"in": 1, "cached": 0, "out": 1}, "stub")

    monkeypatch.setattr(llm, "ask", ask)
    monkeypatch.setattr(llm, "stub_mode", lambda: False)
    d = _design(client, world["dana"])
    _say(client, d, "A box")
    done = d.messages.get(role=Message.ASSISTANT)
    assert done.text == "The whole answer, corrected: a box 20 wide.", "not two answers glued together"


def test_older_pictures_go_at_low_detail_and_the_newest_in_full(client, world):
    d = _design(client, world["dana"])
    _say(client, d, "This", pictures=_jpeg((400, 300)))
    _say(client, d, "And this", pictures=_jpeg((400, 300)))
    _say(client, d, "And now this", pictures=_jpeg((400, 300)))
    pics = [p for i in llm.history(d) if i["role"] == "user" for p in i["content"] if p["type"] == "input_image"]
    assert [p["detail"] for p in pics] == ["low", "low", "auto"]


def test_the_chat_answers_in_the_language_of_the_latest_message():
    assert "language of the person's latest message" in llm.SYSTEM


def test_sizes_on_the_part_are_kept_tagged_and_measured_without_the_model(client, world, monkeypatch):
    code = "width = 86;\nheight = 33;\ncube([width, 40, height]);"
    sizes = [{"name": "width", "label": "Board width", "min": 40, "max": 120, "from": [0, 0, 0], "to": [86, 0, 0], "measure": True},
             {"name": "height", "label": "Height", "min": 10, "max": 60, "from": [0, 0, 0], "to": [0, 0, 33]}]
    monkeypatch.setattr(llm, "ask", lambda items, **kw: ({"title": "Case", "message": "Here.", "assumptions": [], "code": code,
                                                          "parameters": sizes}, {"in": 1, "cached": 0, "out": 1}, "stub"))
    d = _design(client, world["dana"])
    _say(client, d, "A case for my board")
    v = d.versions.get()
    w, h = v.parameters.order_by("position")
    assert (w.tag, w.needs_measuring, w.dim) == ("M1", True, {"from": [0, 0, 0], "to": [86, 0, 0], "at": 86.0})
    assert (h.tag, h.needs_measuring) == ("D1", False)
    poll = client.get(f"/design3d/d/{d.pk}/poll/").json()["current"]["parameters"]
    assert poll[0]["tag"] == "M1" and poll[0]["measure"] and poll[0]["dim"]["to"] == [86, 0, 0]
    page = client.get(f"/design3d/d/{d.pk}/").content.decode()
    assert 'id="d3-sizes"' in page and 'id="d3-to-measure"' in page and 'id="d3-dim-edit"' in page

    # The person measures 130, outside the slider's range: it is kept, with no call to the model.
    monkeypatch.setattr(llm, "ask", lambda items, **kw: pytest.fail("measuring must not call the model"))
    client.post(f"/design3d/d/{d.pk}/sliders/", {"from": 1, "width": "130", "height": "33", "measured": "width"})
    v2 = d.versions.get(number=2)
    w2 = v2.parameters.get(name="width")
    assert "width = 130;" in v2.code and w2.value == 130 and w2.maximum >= 130
    assert w2.needs_measuring is False and w2.tag == "M1" and w2.dim["at"] == 86.0
    said = [i for i in llm.history(d) if i["role"] == "assistant"][-1]["content"]
    assert "M1 width = 86 (to measure)" in said


# ---------- the second analysis's learnings (Avi, 2026-10-30) ----------

def test_the_chat_knows_what_it_does_well_and_models_the_object_first():
    s = llm.SYSTEM
    assert "beyond it" in s and "Fusion 360 or SolidWorks" in s and '"printed": false' in s
    assert "Ask once" in s and "never repeat a question" in " ".join(s.split())


@pytest.mark.skipif(not builder.available(), reason="no OpenSCAD on this PC")
def test_parts_that_overlap_go_back_to_the_model_to_fix(client, world, monkeypatch, settings):
    """Like a build error: the fit findings are sent back, up to twice."""
    settings.OPENAI_API_KEY = "sk-test"
    bad = BOX_AND_LID.replace("clear = 0.3;", "clear = -0.5;")
    good = BOX_AND_LID
    answers = iter([bad, good, None])
    calls = []

    def ask(items, **kw):
        calls.append(items[-1]["content"][0]["text"] if isinstance(items[-1]["content"], list) else items[-1]["content"])
        code = next(answers)
        return ({"title": "Box", "message": "Here.", "assumptions": [], "code": code, "parameters": [], "parts": TWO_PARTS},
                {"in": 1, "cached": 0, "out": 1}, "stub")

    monkeypatch.setattr(llm, "ask", ask)
    monkeypatch.setattr(builder, "build", REAL_BUILD)
    monkeypatch.setattr(llm, "stub_mode", lambda: False)
    d = _design(client, world["dana"])
    _say(client, d, "A box with a lid")
    assert "parts that overlap in the assembly" in calls[1] and "Box and Lid overlap" in calls[1]
    done = d.messages.get(role=Message.ASSISTANT)
    assert "Fixing the fit, try 1 of 2" in [t[1] for t in done.trail]
    assert done.version.fit == [] and done.version.number == 2
    assert len(calls) == 3, "the bad one, the fix, the self-check"


def test_the_self_check_sends_only_what_it_needs(client, world, monkeypatch, settings):
    settings.OPENAI_API_KEY = "sk-test"
    seen = []

    def ask(items, **kw):
        seen.append(items)
        return ({"title": "Box", "message": "Here.", "assumptions": [], "code": "cube(10);" if len(seen) == 1 else None,
                 "parameters": []}, {"in": 1, "cached": 0, "out": 1}, "stub")

    monkeypatch.setattr(llm, "ask", ask)
    monkeypatch.setattr(llm, "stub_mode", lambda: False)
    d = _design(client, world["dana"])
    for text in ("One", "Two", "Three"):
        seen.clear()
        _say(client, d, text, pictures=_jpeg((300, 200)))
    first, check = seen
    assert len(first) == 1 + 2 * 2 + 1, "the whole history goes to the design call: two done turns and this message"
    assert [i["role"] for i in check] == ["system", "user", "assistant", "user"], "the check gets the latest message only"
    assert check[1]["content"][0]["text"].startswith("Three")


def test_two_posts_with_the_same_outline_are_not_an_overlap():
    """Found on 2026-10-30: a vertex exactly on the other part's vertical
    face made the ray graze it and read as inside."""
    from design3d import parts

    code = ('part = "all"; $fn = 48;\n'
            'module a() { translate([0,0,0]) cylinder(d=7, h=10); }\n'
            'module b() { translate([0,0,10.3]) cylinder(d=7, h=10); }\n'
            'if (part == "all" || part == "a") a();\nif (part == "all" || part == "b") b();')
    if not builder.available():
        pytest.skip("no OpenSCAD on this PC")
    ta = render.read_stl(REAL_BUILD(code, part="a")[0])
    tb = render.read_stl(REAL_BUILD(code, part="b")[0])
    assert parts.fit([("a", "A", True, ta), ("b", "B", True, tb)]) == []


def test_the_analysis_export_carries_the_sizes(client, world, monkeypatch):
    import io
    import zipfile

    code = "width = 86;\ncube([width, 40, 20]);"
    sizes = [{"name": "width", "label": "Board width", "min": 40, "max": 120, "from": [0, 0, 0], "to": [86, 0, 0], "measure": True}]
    monkeypatch.setattr(llm, "ask", lambda items, **kw: ({"title": "Case", "message": "Here.", "assumptions": [], "code": code,
                                                          "parameters": sizes}, {"in": 1, "cached": 0, "out": 1}, "stub"))
    d = _design(client, world["dana"])
    _say(client, d, "A case")
    client.force_login(world["avi"])
    mail.outbox.clear()
    client.post("/design3d/people/", {"action": "export"})
    z = zipfile.ZipFile(io.BytesIO(mail.outbox[-1].attachments[0][1]))
    meta = json.loads(z.read(f"design-{d.pk}/design.json"))
    assert meta["versions"][0]["sizes"] == [{"tag": "M1", "name": "width", "value": "86.000", "measure": True, "placed": True}]
    assert "sizes M1 width=86?" in z.read(f"design-{d.pk}/chat.txt").decode()
