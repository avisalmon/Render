"""SPR-M.45 — a lesson page reaches nobody until somebody presses play.

Found while walking the screens where a מט״צ actually spends their hours, which
no review had opened before. Measured on a real lesson page, simply opening it
reached ten third-party hosts: the Bunny player's scripts from
`assets.mediadelivery.net` and `iframe.mediadelivery.net`, video segments from
`vz-*.b-cdn.net` before anybody pressed play, `fonts.bunny.net`, performance
telemetry to `rum-metrics.bunny.net` and `metrics-bunny.net`, and edge latency
probes as far apart as Auckland and Kenya.

Every other screen in מט״צים contacts nobody at all, which is not an accident:
SPR-M.21 self-hosted Rubik rather than let a Google Fonts link send a
fourteen-year-old's IP address to Google "before they have agreed to anything
and with nothing on screen saying so".

And the privacy page says, in bold, **"אין כאן גוגל אנליטיקס, אין פיקסל של
פייסבוק, ואין שום סקריפט של חברה אחרת"**, then uses that to explain why the
site asks for no cookie consent. On the lesson screen that sentence was not
true.

`loading="lazy"` did not save it: the player sits at the top of the page, so it
is in the viewport and loads at once.

The fix is the ordinary one. A still frame and a play button, the iframe built
on the first click, and a line saying where the video comes from *before* it is
fetched rather than in a policy page nobody opens. Opening a lesson now reaches
nobody. Pressing play reaches Bunny, because that is where the video is, and by
then the reader has chosen it.

Traces: REQ-M.13, REQ-M.14, §4.10.
"""

import pathlib
import re

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm45

REPO = pathlib.Path(__file__).resolve().parent.parent
PASSWORD = "sprm45-pass-7712"

# Anything that is not us. Kept as a list of substrings rather than a strict
# hostname parse because the point is coarse: no other company's address should
# appear in the bytes we send a member before they ask for one.
STRANGERS = ("mediadelivery.net", "b-cdn.net", "bunny.net", "bunnyinfra.net",
             "googleapis.com", "gstatic.com", "facebook", "google-analytics")


@pytest.fixture
def member(db):
    from app.models import UserProfile
    from matazim.models import MemberProfile

    user = User.objects.create_user(
        username="kid@example.com", email="kid@example.com", password=PASSWORD
    )
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": "אלמה"})
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now(),
            "birth_year": timezone.now().year - 14,
            "guardian_consent_at": timezone.now(),
            "welcome_accepted_at": timezone.now(),
        },
    )
    return user


@pytest.fixture
def lesson(db):
    from app.models import Course, Video

    course = Course.objects.create(slug="scratch", title="סקראץ' 1")
    return Video.objects.create(
        course=course, title="מבוא", lesson_order=1,
        bunny_video_id="d5f2f7c1-7bd0-4a99-867c-e1107c794df2",
    )


def _page(client, member, lesson):
    client.force_login(member)
    resp = client.get(reverse("matazim:learn_lesson", args=[lesson.course.slug, 1]))
    assert resp.status_code == 200
    return resp.content.decode()


def _what_a_browser_acts_on(html):
    """The page minus the two places an address is allowed to appear.

    `<noscript>` is a deliberate exception: a member whose JavaScript did not
    run would otherwise see a button that does nothing and be unable to watch
    any lesson at all, and a privacy improvement that costs somebody the
    product is not one. A browser running scripts never fetches what is in
    there. `data-embed` is the address the page holds and does not call, which
    is the whole mechanism.
    """
    html = re.sub(r"<noscript>.*?</noscript>", "", html, flags=re.S)
    return re.sub(r'data-embed="[^"]*"', "", html)


def test_opening_a_lesson_sends_nobody_anywhere(client, member, lesson):
    """The bytes a member receives name no other company.

    The `data-embed` attribute is the one exception and is deliberate: it is an
    address the page holds and does not call, which is the whole mechanism.
    """
    for stranger in STRANGERS:
        assert stranger not in _what_a_browser_acts_on(_page(client, member, lesson)), (
            f"a lesson page reaches {stranger} before anybody asked it to"
        )


def test_there_is_no_iframe_until_somebody_clicks(client, member, lesson):
    """An iframe in the response is a request already made."""
    assert "<iframe" not in _what_a_browser_acts_on(_page(client, member, lesson))


def test_the_page_says_where_the_video_will_come_from(client, member, lesson):
    """Before it happens, on the screen, rather than in a policy page.

    §4.10's standard, applied to the one screen that was failing it."""
    html = _page(client, member, lesson)
    assert "הפעלת השיעור" in html
    assert "שרת חיצוני" in html
    assert "Bunny" in html


def test_the_address_is_held_so_the_click_can_use_it(client, member, lesson):
    """The mechanism has to still work, or this is just a broken player."""
    html = _page(client, member, lesson)
    assert 'data-embed="https://iframe.mediadelivery.net/embed/' in html
    assert "mz-player-start" in html


def test_the_still_is_a_real_target_not_a_small_triangle():
    """A play control at the size of a glyph is the tap-target defect SPR-M.41
    swept the product for. The whole frame is the button."""
    css = (REPO / "static" / "matazim" / "matazim.css").read_text(encoding="utf-8")
    block = re.search(r"\.mz-player-start \{(.*?)\}", css, re.S)
    assert block, "the play control lost its styles"
    assert "aspect-ratio" in block.group(1)
    assert "width: 100%" in block.group(1)


def test_a_member_without_javascript_can_still_watch(client, member, lesson):
    """The trade this sprint must not make.

    The click that buys the choice needs JavaScript. If it did not run, the
    old behaviour is better than a dead button: being able to watch the
    programme matters more than being asked first.
    """
    html = _page(client, member, lesson)
    fallback = re.search(r"<noscript>(.*?)</noscript>", html, re.S)
    assert fallback, "no JavaScript means no lessons at all"
    assert "<iframe" in fallback.group(1)
    assert "iframe.mediadelivery.net/embed/" in fallback.group(1)
