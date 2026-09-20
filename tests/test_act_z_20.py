"""ACT-Z.20 — memz: the creator's picture and words come before its
picture library.

Avi: "באופציה של יצירת מם משלך... הטקסט נמצא מתחת לכל התמונות. עדיף
שלמעלה תהיה תמונה ממש מתחתיה הטקסט לכתוב, מתחת לזה כפתורי שיתוף וכאלה,
רק בסוף כל התמונות. וגם כשהוא בוחר תמונה, שזה יקפוץ חזרה למעלה. כי
התמונות נורא נורא מפריעות."

The thumbnail grid sat between the live preview and the caption field, so
every image added to the public bank pushed the two things a person came
to do further down the page. Order is the fix; the scroll-back is what
makes a grid at the bottom usable at all, since the preview it changes is
then off screen.
"""

import io

import pytest
from django.core.files.base import ContentFile
from PIL import Image

pytestmark = [pytest.mark.actz20, pytest.mark.django_db]

URL = "/memz/create/"


@pytest.fixture(autouse=True)
def _test_setup(settings, tmp_path):
    from django.core.cache import cache as django_cache

    django_cache.clear()
    settings.MEDIA_ROOT = str(tmp_path / "media")
    yield


@pytest.fixture
def bank():
    from memz.models import MemeImage

    out = []
    for i in range(5):
        buf = io.BytesIO()
        Image.new("RGB", (300, 220), (30 * i, 90, 150)).save(buf, format="PNG")
        img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
        img.file.save(f"c{i}.png", ContentFile(buf.getvalue()), save=True)
        out.append(img)
    return out


def _order(body, *needles):
    """Where each marker sits in the document, in reading order."""
    return [body.index(n) for n in needles]


def test_the_caption_and_the_button_come_before_the_thumbnails(client, bank):
    """The whole complaint: "the text is underneath all the images"."""
    body = client.get(URL).content.decode()
    preview, caption, submit, grid = _order(
        body, "data-creator-preview", "name=\"caption_text\"", "data-creator-submit", "memz-thumb-grid",
    )
    assert preview < caption < submit < grid, (
        "expected preview -> caption -> button -> thumbnails, got "
        f"{sorted([('preview', preview), ('caption', caption), ('button', submit), ('grid', grid)], key=lambda p: p[1])}"
    )


def test_the_classic_template_panel_is_ordered_the_same_way(client, bank):
    """Both tabs on this screen, or the fix only half-lands."""
    body = client.get(URL).content.decode()
    panel = body[body.index('data-creator-source-panel="imgflip"'):]
    top, bottom, submit, grid = _order(
        panel, "data-imgflip-top", "data-imgflip-bottom", "data-imgflip-submit", "data-imgflip-thumb-grid",
    )
    assert top < bottom < submit < grid, "the template grid is still above the fields it feeds"


def test_the_picture_is_still_the_first_thing_on_the_screen(client, bank):
    """Moving the grid must not have cost the preview its place: the
    point of the order is picture, then words, then button."""
    body = client.get(URL).content.decode()
    form_at = body.index("data-creator-form")
    preview_at = body.index("data-creator-preview")
    caption_at = body.index('name="caption_text"')
    assert form_at < preview_at < caption_at


def test_there_is_somewhere_to_scroll_back_to(client, bank):
    """`data-creator-top` is what the thumbnail handlers scroll to. If the
    markup loses it, the scroll silently stops happening and the grid at
    the bottom becomes a dead end again."""
    body = client.get(URL).content.decode()
    assert body.count("data-creator-top") == 2, "each panel needs its own anchor to scroll back to"


def test_both_pickers_scroll_back_up_when_something_is_chosen(client, bank):
    """Checked against the shipped scripts rather than a reimplementation
    of them, the way ACT-Z.8's own bidi test does."""
    from pathlib import Path

    for name in ("creator.js", "creator_imgflip.js"):
        source = Path("static/memz") .joinpath(name).read_text(encoding="utf-8")
        assert "scrollIntoView" in source, f"{name} never scrolls back to the preview"
        assert "prefers-reduced-motion" in source, f"{name} animates the scroll regardless of the setting"


def test_choosing_a_classic_template_shows_it_at_the_top(client, bank):
    """That panel has no live canvas, so without this there would be
    nothing up there worth scrolling back to."""
    body = client.get(URL).content.decode()
    panel = body[body.index('data-creator-source-panel="imgflip"'):]
    assert "data-imgflip-chosen-image" in panel
    assert panel.index("data-imgflip-chosen") < panel.index("data-imgflip-top")

    from pathlib import Path

    source = Path("static/memz/creator_imgflip.js").read_text(encoding="utf-8")
    assert "chosenWrap.hidden = false" in source, "the chosen template is never revealed"


def test_making_a_meme_still_works_after_the_reshuffle(client, bank):
    """The order changed, not the form."""
    from memz.models import Meme

    r = client.post(URL, {"image": bank[1].pk, "caption_text": "כשמבינים שזה כבר יום שלישי"})
    assert r.status_code == 302, r.content
    meme = Meme.objects.get()
    assert meme.caption_text == "כשמבינים שזה כבר יום שלישי"
    assert r["Location"].endswith(f"/memz/create/{meme.share_slug}/")
