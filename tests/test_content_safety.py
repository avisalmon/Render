"""Site-wide content safety + correctness gates (app/safety.py).

Three layers, all FAIL OPEN:
  1. structural validation (local): real image / real STL mesh
  2. image safety moderation (free omni-moderation; here stubbed/monkeypatched)
  3. text relevance (political / off-topic; cheap LLM, cached, gated)

No real API calls: tests run in stub mode (OPENAI_API_KEY="") and monkeypatch
the ai_chat layer to simulate a flag, so the suite spends $0.
"""
import io
import struct

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from app import safety
from app.models import Course, LessonModelSubmission, Video

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- #
# fixtures / builders
# --------------------------------------------------------------------------- #

ASCII_STL = (b"solid cube\nfacet normal 0 0 0\nouter loop\n"
             b"vertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid cube\n")


def _png_bytes(color=(120, 200, 60)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (12, 12), color).save(buf, format="PNG")
    return buf.getvalue()


def _binary_stl_bytes(n_triangles=2):
    out = bytearray(b"\x00" * 80)            # 80-byte header
    out += struct.pack("<I", n_triangles)    # uint32 triangle count
    for _ in range(n_triangles):
        out += struct.pack("<12fH", *([0.0] * 12), 0)  # 48 bytes floats + 2 attr
    return bytes(out)


def _upload(content, name, ctype):
    return SimpleUploadedFile(name, content, content_type=ctype)


# --------------------------------------------------------------------------- #
# 1. structural validation (local, no API)
# --------------------------------------------------------------------------- #

def test_validate_image_accepts_real_png():
    ok, reason = safety.validate_image(_upload(_png_bytes(), "p.png", "image/png"))
    assert ok and reason == ""


def test_validate_image_rejects_non_image():
    ok, reason = safety.validate_image(_upload(b"i am not a picture", "p.png", "image/png"))
    assert not ok and reason == "notimage"


def test_validate_stl_accepts_binary():
    ok, reason = safety.validate_stl(_upload(_binary_stl_bytes(3), "m.stl", "application/octet-stream"))
    assert ok and reason == ""


def test_validate_stl_accepts_ascii():
    ok, _ = safety.validate_stl(_upload(ASCII_STL, "m.stl", "application/octet-stream"))
    assert ok


def test_validate_stl_rejects_garbage_named_stl():
    ok, _ = safety.validate_stl(_upload(b"definitely not a mesh, just text" * 5, "fake.stl", "model/stl"))
    assert not ok


def test_validate_stl_rejects_empty():
    ok, reason = safety.validate_stl(_upload(b"", "empty.stl", "model/stl"))
    assert not ok and reason == "emptystl"


# --------------------------------------------------------------------------- #
# 2. image safety moderation
# --------------------------------------------------------------------------- #

def test_image_is_safe_passes_clean_in_stub_mode():
    # No API key -> moderation stub returns "not flagged".
    ok, reason = safety.image_is_safe(_upload(_png_bytes(), "p.png", "image/png"))
    assert ok and reason == ""


def test_image_is_safe_rejects_non_image():
    ok, reason = safety.image_is_safe(_upload(b"nope", "p.png", "image/png"))
    assert not ok and reason == "notimage"


def test_image_is_safe_blocks_flagged(monkeypatch):
    import app.ai_chat as ai
    monkeypatch.setattr(ai, "check_image_moderation",
                        lambda *a, **k: (False, {"sexual": True}))
    ok, reason = safety.image_is_safe(_upload(_png_bytes(), "p.png", "image/png"))
    assert not ok and reason == "flagged"


def test_image_is_safe_fails_open_on_error(monkeypatch):
    import app.ai_chat as ai

    def boom(*a, **k):
        raise RuntimeError("moderation down")

    monkeypatch.setattr(ai, "check_image_moderation", boom)
    ok, _ = safety.image_is_safe(_upload(_png_bytes(), "p.png", "image/png"))
    assert ok  # never block the site when the filter is broken


# --------------------------------------------------------------------------- #
# 3. text relevance (political / off-topic)
# --------------------------------------------------------------------------- #

def test_relevance_blocks_offtopic(monkeypatch):
    import app.ai_chat as ai
    monkeypatch.setattr(ai, "classify_relevance",
                        lambda text, ctx="": {"allowed": False,
                                              "categories": ["off_topic"], "reason": "recipe"})
    ok, _ = safety.text_relevance_ok("how do I make pizza dough", context_label="relv-block-1")
    assert ok is False


def test_relevance_fails_open_on_error(monkeypatch):
    import app.ai_chat as ai

    def boom(text, ctx=""):
        raise RuntimeError("classifier down")

    monkeypatch.setattr(ai, "classify_relevance", boom)
    ok, _ = safety.text_relevance_ok("unique fail-open message 42", context_label="relv-open-1")
    assert ok is True


def test_relevance_is_cached(monkeypatch):
    import app.ai_chat as ai
    calls = {"n": 0}

    def fake(text, ctx=""):
        calls["n"] += 1
        return {"allowed": True, "categories": [], "reason": "ok"}

    monkeypatch.setattr(ai, "classify_relevance", fake)
    msg = "cache this exact message please uniq-99"
    safety.text_relevance_ok(msg, context_label="relv-cache-1")
    safety.text_relevance_ok(msg, context_label="relv-cache-1")
    assert calls["n"] == 1  # second call served from cache


def test_relevance_respects_kill_switch(settings, monkeypatch):
    settings.CONTENT_RELEVANCE_ENABLED = False
    import app.ai_chat as ai
    monkeypatch.setattr(ai, "classify_relevance",
                        lambda text, ctx="": {"allowed": False, "categories": ["political"]})
    ok, _ = safety.text_relevance_ok("anything at all", context_label="relv-off-1")
    assert ok is True  # disabled -> always allowed, no classifier call


# --------------------------------------------------------------------------- #
# end-to-end wiring through real views
# --------------------------------------------------------------------------- #

def test_stl_upload_rejects_fake_stl():
    c = Course.objects.create(title="3D", slug="pytest-safety-3d", is_published=True)
    v = Video.objects.create(course=c, lesson_order=1, title="L1")
    u = User.objects.create_user("stlsafe", password="pass12345")
    cl = Client()
    cl.force_login(u)
    cl.post(f"/courses/{c.slug}/lesson/1/submit-model/",
            {"model": _upload(b"this is not really an stl mesh" * 3, "model.stl", "model/stl")})
    assert not LessonModelSubmission.objects.filter(user=u, video=v).exists()


def test_stl_upload_accepts_real_stl():
    c = Course.objects.create(title="3D", slug="pytest-safety-3d-ok", is_published=True)
    v = Video.objects.create(course=c, lesson_order=1, title="L1")
    u = User.objects.create_user("stlsafe2", password="pass12345")
    cl = Client()
    cl.force_login(u)
    cl.post(f"/courses/{c.slug}/lesson/1/submit-model/",
            {"model": _upload(_binary_stl_bytes(4), "model.stl", "application/octet-stream")})
    sub = LessonModelSubmission.objects.filter(user=u, video=v).first()
    assert sub is not None and bool(sub.model_file)


def test_avatar_upload_blocked_when_image_flagged(monkeypatch):
    import app.ai_chat as ai
    monkeypatch.setattr(ai, "check_image_moderation",
                        lambda *a, **k: (False, {"sexual": True}))
    u = User.objects.create_user("avsafe", password="pass12345")
    cl = Client()
    cl.force_login(u)
    cl.post("/community/settings/",
            {"is_public": "on",
             "avatar": _upload(_png_bytes(), "a.png", "image/png")})
    u.profile.refresh_from_db()
    assert not u.profile.avatar  # flagged -> nothing saved


# --------------------------------------------------------------------------- #
# priority-2 correctness grader (advisory) + management-panel switch
# --------------------------------------------------------------------------- #

from app.models import AIGraderConfig, CourseProjectSubmission  # noqa: E402


def _img_course(slug="grader-course"):
    c = Course.objects.create(title="Web", slug=slug, is_published=True,
                              requires_project=True,
                              project_upload_type=Course.PROJECT_IMAGE)
    Video.objects.create(course=c, lesson_order=1, title="L1", is_final_lesson=True)
    return c


def test_grader_config_singleton_defaults_to_best_model():
    cfg = AIGraderConfig.load()
    assert cfg.pk == 1 and cfg.enabled and cfg.model == "gpt-4o"
    assert AIGraderConfig.load().pk == 1  # same row, not a second one
    assert AIGraderConfig.objects.count() == 1


def test_grader_writes_verdict_and_logs_cost(monkeypatch):
    import app.ai_chat as ai
    monkeypatch.setattr(ai, "grade_image_submission",
                        lambda *a, **k: {"ok": True, "score": 88, "reason": "looks done",
                                         "model": "gpt-4o", "prompt_tokens": 800,
                                         "completion_tokens": 20})
    c = _img_course()
    u = User.objects.create_user("grada", password="pass12345")
    cl = Client()
    cl.force_login(u)
    cl.post(f"/courses/{c.slug}/submit-project/",
            {"image": _upload(_png_bytes(), "site.png", "image/png")})
    sub = CourseProjectSubmission.objects.get(user=u, course=c)
    assert sub.grade_ok is True and sub.grade_score == 88
    assert sub.graded_model == "gpt-4o" and sub.graded_hash
    # spend recorded in UsageLog (session-less) for the cost dashboard
    from app.models import UsageLog
    assert UsageLog.objects.filter(user=u, session__isnull=True, model="gpt-4o").exists()


def test_grader_skipped_when_disabled(monkeypatch):
    import app.ai_chat as ai
    called = {"n": 0}

    def spy(*a, **k):
        called["n"] += 1
        return {"ok": True, "score": 1, "reason": "x", "model": "gpt-4o",
                "prompt_tokens": 1, "completion_tokens": 1}

    monkeypatch.setattr(ai, "grade_image_submission", spy)
    cfg = AIGraderConfig.load()
    cfg.enabled = False
    cfg.save()
    c = _img_course(slug="grader-off")
    u = User.objects.create_user("gradb", password="pass12345")
    cl = Client()
    cl.force_login(u)
    cl.post(f"/courses/{c.slug}/submit-project/",
            {"image": _upload(_png_bytes(), "s.png", "image/png")})
    assert called["n"] == 0  # grader never invoked
    sub = CourseProjectSubmission.objects.get(user=u, course=c)
    assert sub.grade_ok is None  # ungraded, but upload still succeeded


def test_grader_fails_open(monkeypatch):
    import app.ai_chat as ai

    def boom(*a, **k):
        raise RuntimeError("grader down")

    monkeypatch.setattr(ai, "grade_image_submission", boom)
    AIGraderConfig.load()  # enabled by default
    c = _img_course(slug="grader-open")
    u = User.objects.create_user("gradc", password="pass12345")
    cl = Client()
    cl.force_login(u)
    r = cl.post(f"/courses/{c.slug}/submit-project/",
                {"image": _upload(_png_bytes(), "s.png", "image/png")})
    # upload still succeeds (redirect), submission saved but ungraded
    assert r.status_code in (302, 200)
    sub = CourseProjectSubmission.objects.get(user=u, course=c)
    assert sub.grade_ok is None and bool(sub.image)


def test_management_panel_switches_model():
    su = User.objects.create_superuser("boss", "boss@x.com", "pass12345")
    cl = Client()
    cl.force_login(su)
    r = cl.post("/admin-dashboard/grader/config/",
                {"enabled": "on", "model": "gpt-4o-mini", "image_detail": "low"})
    assert r.status_code == 302
    cfg = AIGraderConfig.load()
    assert cfg.model == "gpt-4o-mini" and cfg.image_detail == "low" and cfg.enabled

    # turning it off (checkbox absent) disables the grader
    cl.post("/admin-dashboard/grader/config/", {"model": "gpt-4o", "image_detail": "high"})
    assert AIGraderConfig.load().enabled is False
