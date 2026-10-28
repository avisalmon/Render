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
    assert len(mail.outbox) == 1 and "/design3d/" in mail.outbox[0].body, "the welcome goes once"
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
    assert len(calls) == 2, "no self-check after the first part"


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
    used |= set(re.findall(r'"(d3-[a-z0-9-]+)', js)) - {"d3-msgs", "d3-composer", "d3-text", "d3-files", "d3-camera", "d3-chosen",
                                                          "d3-send", "d3-tools", "d3-busy", "d3-work", "d3-size", "d3-slider-list",
                                                          "d3-apply", "d3-sliders", "d3-versions", "d3-hello", "d3-view", "d3-view-empty", "d3-title"}
    assert used <= defined, sorted(used - defined)
