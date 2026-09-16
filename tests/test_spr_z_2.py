"""SPR-Z.2 — memz: the engine, and the first front door
(docs/memz/backlog.md). A meme can be made, seen, shared, downloaded, and
expires. Spec references are docs/memz/spec.md rule numbers.
"""

import io
import json

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.utils import timezone
from PIL import Image

pytestmark = [pytest.mark.sprz2, pytest.mark.django_db]

PASSWORD = "memz-test-passw0rd"


def _png_bytes(size=(64, 48), color=(30, 90, 160)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _user(name):
    return User.objects.create_user(name, email=f"{name}@example.com", password=PASSWORD)


@pytest.fixture
def media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    return tmp_path / "media"


@pytest.fixture
def public_image(media_tmp):
    from memz.models import MemeImage

    img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED, title="ציבורית")
    img.file.save("public.png", ContentFile(_png_bytes()), save=True)
    return img


@pytest.fixture
def private_image(media_tmp):
    from memz.models import MemeImage

    owner = _user("owner")
    img = MemeImage(owner=owner, visibility=MemeImage.PRIVATE, moderation_status=MemeImage.APPROVED, title="פרטית")
    img.file.save("private.png", ContentFile(_png_bytes()), save=True)
    return owner, img


# ---------------------------------------------------------- F-Z.2.1 render


def test_wrap_caption_breaks_on_words_not_characters():
    from memz.render import _font, wrap_caption

    font = _font(40)
    lines = wrap_caption("שלום עולם זה משפט ארוך שאמור להישבר לכמה שורות", font, max_width=260)
    assert len(lines) > 1
    assert "".join(lines).replace(" ", "") == "שלוםעולםזהמשפטארוךשאמורלהישברלכמהשורות"


def test_fit_caption_shrinks_until_it_fits_the_line_limit():
    from memz import conf
    from memz.render import fit_caption

    size, lines = fit_caption("מילה " * 40, max_width=900, max_lines=3)
    assert len(lines) <= 3
    assert conf.get("RENDER_FONT_MIN") <= size <= conf.get("RENDER_FONT_MAX")


def test_fit_caption_never_exceeds_max_lines_even_for_one_giant_word():
    from memz.render import fit_caption

    size, lines = fit_caption("א" * 200, max_width=400, max_lines=3)
    assert len(lines) <= 3
    assert lines[-1].endswith("…")


def test_render_produces_a_jpeg_with_the_caption_bar_above_the_image(public_image):
    from memz import conf, render

    data, width, height = render.render(public_image.file, "שלום, בדיקה", watermark=False)
    assert data[:2] == b"\xff\xd8"          # JPEG magic
    assert width == conf.get("RENDER_WIDTH")
    assert height > width * 0.5             # bar + image, taller than the image alone would be at 4:3


def test_render_applies_watermark_only_when_asked(public_image):
    from memz import render

    plain, _w1, _h1 = render.render(public_image.file, "בלי סימן מים", watermark=False)
    marked, _w2, _h2 = render.render(public_image.file, "עם סימן מים", watermark=True)
    assert plain != marked


def test_render_handles_mixed_hebrew_latin_and_digits_without_crashing(public_image):
    from memz import render

    data, _w, _h = render.render(public_image.file, "יש לי 3 חתולים ו-2 כלבים, cool!", watermark=False)
    assert data[:2] == b"\xff\xd8"


def test_shape_for_draw_keeps_hebrew_first_even_when_the_caption_opens_in_latin():
    """2026-09-16 QA fix (Avi, live-testing the real game): a caption
    starting with an English word, a digit, an emoji or a quote mark used
    to come out backwards on the actual rendered meme, because
    `get_display`'s own auto-detection picks the paragraph's base
    direction from its *first strong character* -- so "WOW זה מטורף"
    (an entirely ordinary thing to type) got treated as an LTR paragraph
    and reordered as if it read "זה מטורף WOW". `shape_for_draw` pins
    `base_dir="R"` so this can never happen: memz captions are always a
    Hebrew-first RTL paragraph, never guessed at.

    PIL draws a string strictly left to right, so the *last* character of
    the shaped string is what lands visually rightmost -- where a Hebrew
    reader starts. For "WOW זה מטורף", "WOW" (the first thing actually
    typed) must be what ends up rightmost, i.e. last in the shaped
    string."""
    from memz.render import shape_for_draw

    shaped = shape_for_draw("WOW זה מטורף")
    assert shaped.endswith("WOW"), f"WOW should land rightmost (last in the LTR-drawn string), got {shaped!r}"

    # Un-prefixed Hebrew, and digit-then-Hebrew, must both still read
    # correctly too -- this fix must not just move the bug around. Each
    # RTL *run* is itself spelled backwards in the shaped string (that is
    # what makes PIL's left-to-right glyph drawing come out looking right
    # again) -- so the word typed first ("אחד") shows up run-reversed
    # ("דחא") at the very end, not literally as "אחד".
    shaped_plain = shape_for_draw("אחד שתיים שלוש")
    assert shaped_plain.endswith("אחד"[::-1]), f"אחד (typed first) should land rightmost, got {shaped_plain!r}"

    shaped_digit_first = shape_for_draw("5 דברים שכל הורה מכיר")
    assert shaped_digit_first.endswith("5"), f"the digit (typed first) should land rightmost, got {shaped_digit_first!r}"


def test_shape_for_draw_handles_punctuation_after_the_first_word():
    """2026-09-16 QA fix, round 4 (Avi, a real screenshot from the live
    game: "רגע... מה קורה פה?!" came out with "רגע" spelled backwards on
    the actual rendered meme). This did not reproduce against any
    `python-bidi` build installed locally, in any of several variations
    tried (an ellipsis of three periods, a real "…" character, with or
    without a trailing "?!", with or without a watermark) -- the
    behaviour turned out to depend on which exact `python-bidi` build is
    installed, and `requirements.txt` only pinned a range
    (">=0.6,<1"), so dev and production had silently drifted onto
    different resolved versions. Pinned to an exact version afterward;
    this test locks in the two exact strings from the real report
    against whatever's actually installed, so a future drift back to a
    version that gets this wrong fails a test instead of shipping."""
    from memz.render import shape_for_draw

    for text in ("רגע... מה קורה פה?!", "רגע… מה קורה פה?!"):
        shaped = shape_for_draw(text)
        assert shaped.endswith("רגע"[::-1]), (
            f"רגע (typed first) should land rightmost even with trailing punctuation, got {shaped!r} for {text!r}"
        )


def test_shape_for_draw_leaves_the_line_alone_when_pil_can_reorder_it_itself(monkeypatch):
    """2026-09-16 QA fix, round 4 continued (ACT-Z.11) -- the REAL root
    cause, after ACT-Z.10's version pin was deployed and shown NOT to fix
    it. The reversal wasn't about which `python-bidi` version was
    installed at all: it was that most Linux/macOS Pillow wheels (what
    Render actually runs) bundle `libraqm`, which gives PIL's own
    `ImageDraw.text` real Unicode-bidi awareness -- so production was
    reordering `shape_for_draw`'s already-reordered output a SECOND time,
    unreversing it right back to wrong. This reproduced for every
    pure-Hebrew multi-word caption, not just ones with punctuation, which
    is why ACT-Z.10's narrower fix never touched it. `PIL_HAS_RAQM` picks
    the right path at import time; this test pins that when it's true,
    `shape_for_draw` must hand PIL the line UNCHANGED, trusting PIL's own
    raqm layout (given `direction="rtl"`, checked in the next test) to do
    the reordering -- exactly the same fix shape as creator.js's
    `ctx.direction = "rtl"` (ACT-Z.8.2), just on the server."""
    from memz import render

    monkeypatch.setattr(render, "PIL_HAS_RAQM", True)
    line = "רגע מה קורה פה"
    assert render.shape_for_draw(line) == line, "raqm-backed PIL must get the logical line, not a pre-reordered one"

    monkeypatch.setattr(render, "PIL_HAS_RAQM", False)
    assert render.shape_for_draw(line) != line, "without raqm, PIL still needs the line reordered by hand"


def test_draw_caption_bar_tells_raqm_backed_pil_the_paragraph_is_rtl(monkeypatch):
    """The other half of the ACT-Z.11 fix: raqm only reorders correctly if
    it's told the base direction, the same way `base_dir="R"` pins it on
    the non-raqm path. Real raqm isn't installed on this dev machine
    (Windows Pillow wheels don't bundle it -- confirmed via
    `PIL.features.check_feature("raqm")`, which is exactly why this bug
    never reproduced locally), so `ImageDraw.text` itself is stubbed out
    here rather than actually exercised with `direction="rtl"`, which
    would raise on a non-raqm build."""
    from PIL import ImageDraw

    from memz import render

    monkeypatch.setattr(render, "PIL_HAS_RAQM", True)
    calls = []
    monkeypatch.setattr(
        ImageDraw.ImageDraw, "text",
        lambda self, xy, text, **kw: calls.append((text, kw)),
    )

    render._draw_caption_bar(600, "רגע מה קורה פה")

    assert calls, "no draw call happened"
    text, kw = calls[0]
    assert text == "רגע מה קורה פה", f"raqm path must draw the logical line unchanged, got {text!r}"
    assert kw.get("direction") == "rtl", f"raqm path must tell PIL the base direction, got kwargs {kw!r}"


def test_render_handles_empty_caption(public_image):
    from memz import render

    data, _w, _h = render.render(public_image.file, "", watermark=False)
    assert data[:2] == b"\xff\xd8"


# ------------------------------------------------------------ F-Z.2.4/.7 make_meme


def test_make_meme_for_a_guest_is_watermarked_owner_none_and_expires(public_image):
    from memz.memes import make_meme
    from memz.models import Meme

    meme = make_meme(image=public_image, caption_text="בדיקה", source=Meme.SOLO, user=None)
    assert meme.created_by_user is None
    assert meme.expires_at is not None
    assert meme.source == Meme.SOLO
    assert meme.rendered.name.endswith(".jpg")
    assert len(meme.share_slug) >= 16


def test_make_meme_for_a_logged_in_user_has_no_watermark_no_expiry_and_the_owner(public_image):
    from memz.memes import make_meme
    from memz.models import Meme

    user = _user("dana")
    guest_meme = make_meme(image=public_image, caption_text="בלי חשבון", source=Meme.SOLO, user=None)
    user_meme = make_meme(image=public_image, caption_text="עם חשבון", source=Meme.SOLO, user=user)
    assert user_meme.created_by_user == user
    assert user_meme.expires_at is None
    guest_meme.rendered.open("rb")
    user_meme.rendered.open("rb")
    assert guest_meme.rendered.read() != user_meme.rendered.read()   # the watermark differs the bytes


# --------------------------------------------------------------- F-Z.2.3 page


def test_creator_page_lists_only_images_the_visitor_may_use(client, public_image, private_image):
    owner, priv = private_image
    response = client.get("/memz/create/")
    assert response.status_code == 200
    ids = {img.pk for img in response.context["images"]}
    assert public_image.pk in ids
    assert priv.pk not in ids

    client.force_login(owner)
    response = client.get("/memz/create/")
    ids = {img.pk for img in response.context["images"]}
    assert public_image.pk in ids and priv.pk in ids


def test_a_guest_can_make_a_meme_through_the_page_with_no_account(client, public_image):
    from memz.models import Meme

    response = client.post("/memz/create/", {"image": public_image.pk, "caption_text": "בלי חשבון בכלל"})
    assert response.status_code == 302
    meme = Meme.objects.get()
    assert response.url == f"/memz/create/{meme.share_slug}/"
    assert meme.created_by_user is None


def test_the_creator_page_refuses_an_image_outside_the_visible_bank(client, public_image, private_image):
    owner, priv = private_image
    stranger = _user("stranger")
    client.force_login(stranger)
    response = client.post("/memz/create/", {"image": priv.pk, "caption_text": "ניסיון"})
    assert response.status_code == 200         # re-renders the form with an error, no redirect
    assert "data-screen=\"creator\"" in response.content.decode()
    from memz.models import Meme

    assert not Meme.objects.exists()


def test_the_creator_page_refuses_an_empty_caption(client, public_image):
    from memz.models import Meme

    response = client.post("/memz/create/", {"image": public_image.pk, "caption_text": "   "})
    assert response.status_code == 200
    assert not Meme.objects.exists()


def test_the_creator_result_page_shows_the_rendered_meme(client, public_image):
    from memz.memes import make_meme
    from memz.models import Meme

    meme = make_meme(image=public_image, caption_text="מוכן", source=Meme.SOLO, user=None)
    response = client.get(f"/memz/create/{meme.share_slug}/")
    assert response.status_code == 200
    assert meme.rendered.url in response.content.decode()


def test_creator_page_and_result_page_link_nowhere_outside_memz(client, public_image):
    from memz.memes import make_meme
    from memz.models import Meme

    meme = make_meme(image=public_image, caption_text="שום קשר לבבוק", source=Meme.SOLO, user=None)
    import re

    for path in (f"/memz/create/", f"/memz/create/{meme.share_slug}/"):
        html = client.get(path).content.decode()
        hrefs = re.findall(r'href="([^"]+)"', html)
        outside = [h for h in hrefs if not (h.startswith("/memz/") or h.startswith("/static/") or h.startswith("/media/")
                                            or h.startswith("#") or "fonts.googleapis.com" in h)]
        assert not outside, f"{path} links outside memz: {outside}"
        assert "babook" not in html.lower()


# --------------------------------------------------------------- F-Z.2.4 API


def test_anonymous_can_create_a_meme_through_the_api(client, public_image):
    from memz.models import Meme

    response = client.post("/memz/api/memes/", json.dumps({"image": public_image.pk, "caption_text": "מהאייפיאי"}),
                           content_type="application/json")
    assert response.status_code == 201, response.content
    meme = Meme.objects.get()
    assert meme.created_by_user is None
    assert response.json()["share_slug"] == meme.share_slug


def test_the_api_refuses_an_image_outside_the_callers_bank(client, private_image):
    owner, priv = private_image
    stranger = _user("stranger2")
    client.force_login(stranger)
    response = client.post("/memz/api/memes/", json.dumps({"image": priv.pk, "caption_text": "ניסיון"}),
                           content_type="application/json")
    assert response.status_code == 400
    from memz.models import Meme

    assert not Meme.objects.exists()


def test_the_api_never_takes_owner_source_or_expiry_from_the_body(client, public_image):
    from memz.models import Meme

    user = _user("erez")
    client.force_login(user)
    stranger = _user("someone_else")
    response = client.post("/memz/api/memes/", json.dumps({
        "image": public_image.pk, "caption_text": "לא משנה מה שולחים",
        "created_by_user": stranger.pk, "source": "game", "share_slug": "hacked", "expires_at": "2020-01-01T00:00:00Z",
    }), content_type="application/json")
    assert response.status_code == 201, response.content
    meme = Meme.objects.get()
    assert meme.created_by_user == user
    assert meme.source == Meme.SOLO
    assert meme.share_slug != "hacked"
    assert meme.expires_at is None


def test_listing_and_reading_memes_through_the_api_is_owner_only(client, public_image):
    from memz.memes import make_meme
    from memz.models import Meme

    a, b = _user("meme_a"), _user("meme_b")
    mine = make_meme(image=public_image, caption_text="שלי", source=Meme.SOLO, user=a)
    theirs = make_meme(image=public_image, caption_text="שלהם", source=Meme.SOLO, user=b)

    assert client.get("/memz/api/memes/").status_code in (401, 403)

    client.force_login(a)
    ids = {row["id"] for row in client.get("/memz/api/memes/").json()}
    assert mine.pk in ids and theirs.pk not in ids
    assert client.get(f"/memz/api/memes/{theirs.pk}/").status_code == 404
    assert client.delete(f"/memz/api/memes/{theirs.pk}/").status_code == 404
    assert client.delete(f"/memz/api/memes/{mine.pk}/").status_code == 204
    assert not Meme.objects.filter(pk=mine.pk).exists()


def test_meme_creation_is_throttled(client, public_image, settings):
    from django.core.cache import cache as django_cache

    django_cache.clear()   # a scope's request history outlives a rate change; start clean
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {
        **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}), "memz_meme_create_anon": "2/hour",
    }}
    for _ in range(2):
        response = client.post("/memz/api/memes/", json.dumps({"image": public_image.pk, "caption_text": "x"}),
                               content_type="application/json")
        assert response.status_code == 201
    response = client.post("/memz/api/memes/", json.dumps({"image": public_image.pk, "caption_text": "x"}),
                           content_type="application/json")
    assert response.status_code == 429


# ------------------------------------------------------------- F-Z.2.5 share


def test_the_share_page_shows_a_live_meme(client, public_image):
    from memz.memes import make_meme
    from memz.models import Meme

    meme = make_meme(image=public_image, caption_text="חי וקיים", source=Meme.SOLO, user=None)
    response = client.get(f"/memz/m/{meme.share_slug}/")
    assert response.status_code == 200
    html = response.content.decode()
    assert meme.rendered.url in html
    assert 'data-screen="share"' in html


def test_an_expired_meme_says_so_plainly_not_a_404(client, public_image):
    from memz.memes import make_meme
    from memz.models import Meme

    meme = make_meme(image=public_image, caption_text="פג תוקף", source=Meme.SOLO, user=None)
    Meme.objects.filter(pk=meme.pk).update(expires_at=timezone.now() - timezone.timedelta(hours=1))
    response = client.get(f"/memz/m/{meme.share_slug}/")
    assert response.status_code == 200
    assert 'data-screen="share-expired"' in response.content.decode()


def test_a_slug_that_never_existed_gets_the_same_friendly_page(client):
    response = client.get("/memz/m/this-was-never-a-real-slug/")
    assert response.status_code == 200
    assert 'data-screen="share-expired"' in response.content.decode()


def test_a_saved_looking_meme_with_no_expiry_never_shows_as_expired(client, public_image):
    from memz.memes import make_meme
    from memz.models import Meme

    user = _user("saver")
    meme = make_meme(image=public_image, caption_text="לא פג", source=Meme.SOLO, user=user)
    assert meme.expires_at is None
    response = client.get(f"/memz/m/{meme.share_slug}/")
    assert 'data-screen="share"' in response.content.decode()


# ------------------------------------------------------------- report link


def test_reporting_a_real_meme_mails_the_admin(client, public_image, settings):
    from memz.memes import make_meme
    from memz.models import Meme

    meme = make_meme(image=public_image, caption_text="דיווח עליי", source=Meme.SOLO, user=None)
    response = client.post("/memz/api/report/", json.dumps({"slug": meme.share_slug}), content_type="application/json")
    assert response.status_code == 200
    assert len(mail.outbox) == 1
    assert meme.share_slug in mail.outbox[0].body


def test_reporting_a_fake_slug_sends_no_mail_but_still_answers_ok(client):
    response = client.post("/memz/api/report/", json.dumps({"slug": "not-a-real-slug"}), content_type="application/json")
    assert response.status_code == 200
    assert len(mail.outbox) == 0


def test_report_is_throttled(client, public_image, settings):
    from memz.memes import make_meme
    from memz.models import Meme

    meme = make_meme(image=public_image, caption_text="x", source=Meme.SOLO, user=None)
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {
        **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}), "memz_report": "1/hour",
    }}
    assert client.post("/memz/api/report/", json.dumps({"slug": meme.share_slug}), content_type="application/json").status_code == 200
    assert client.post("/memz/api/report/", json.dumps({"slug": meme.share_slug}), content_type="application/json").status_code == 429


# ------------------------------------------------------------ F-Z.2.7 cleanup


def test_cleanup_deletes_expired_sessions_and_unsaved_expired_memes_only(public_image):
    from memz.memes import make_meme
    from memz.models import Meme, SavedMeme, Session

    now = timezone.now()
    gone_session = Session.objects.create(code="GONE", status="finished", expires_at=now - timezone.timedelta(hours=1))
    live_session = Session.objects.create(code="LIVE", status="lobby", expires_at=now + timezone.timedelta(hours=1))
    remembered_session = Session.objects.create(code="REMB", status="finished", remembered=True, expires_at=None)

    expired_unsaved = make_meme(image=public_image, caption_text="פג ולא נשמר", source=Meme.SOLO, user=None)
    Meme.objects.filter(pk=expired_unsaved.pk).update(expires_at=now - timezone.timedelta(hours=1))

    saver = _user("keeper")
    expired_but_saved = make_meme(image=public_image, caption_text="פג אבל נשמר", source=Meme.SOLO, user=None)
    Meme.objects.filter(pk=expired_but_saved.pk).update(expires_at=None)   # saving clears expiry (spec §8.4)
    SavedMeme.objects.create(user=saver, meme=expired_but_saved)

    not_yet_expired = make_meme(image=public_image, caption_text="עוד לא", source=Meme.SOLO, user=None)
    Meme.objects.filter(pk=not_yet_expired.pk).update(expires_at=now + timezone.timedelta(hours=1))

    call_command("memz_cleanup")

    assert not Session.objects.filter(pk=gone_session.pk).exists()
    assert Session.objects.filter(pk=live_session.pk).exists()
    assert Session.objects.filter(pk=remembered_session.pk).exists()
    assert not Meme.objects.filter(pk=expired_unsaved.pk).exists()
    assert Meme.objects.filter(pk=expired_but_saved.pk).exists()
    assert Meme.objects.filter(pk=not_yet_expired.pk).exists()


def test_cleanup_dry_run_changes_nothing(public_image):
    from memz.memes import make_meme
    from memz.models import Meme

    meme = make_meme(image=public_image, caption_text="פג תוקף", source=Meme.SOLO, user=None)
    Meme.objects.filter(pk=meme.pk).update(expires_at=timezone.now() - timezone.timedelta(hours=1))
    call_command("memz_cleanup", "--dry-run")
    assert Meme.objects.filter(pk=meme.pk).exists()


def test_cleanup_is_idempotent(public_image):
    from memz.memes import make_meme
    from memz.models import Meme

    meme = make_meme(image=public_image, caption_text="פג תוקף", source=Meme.SOLO, user=None)
    Meme.objects.filter(pk=meme.pk).update(expires_at=timezone.now() - timezone.timedelta(hours=1))
    call_command("memz_cleanup")
    call_command("memz_cleanup")   # must not error on an already-clean database
