"""The fast gate. Does the site still stand?

Avi, 2026-09-10: everything goes to production for him to look at, so a
fifteen-minute suite before every push is the wrong shape. This is the cheap
half of a two-tier gate:

- **Every push:** this file plus the sprint's own tests. Seconds, not minutes.
- **Once a day, and before any version:** the whole suite.

The rule for what belongs here: it must be fast, it must never be flaky, and
it must fail if the site is actually broken for a visitor. It is deliberately
shallow. It is not a substitute for the full run, it is the thing that stops an
obviously broken deploy while the full run happens on its own schedule.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.smoke


@pytest.mark.parametrize(
    "path",
    [
        "/",  # babook home
        "/courses/",  # the catalogue
        "/join/",  # the wall every logged-out visitor meets
        "/matazim/",  # the מט״צים front door
        "/matazim/login/",
        "/matazim/register/",
        "/matazim/test/",
    ],
)
def test_the_page_serves(client, db, path):
    """A 500 here means the deploy is broken for a real visitor."""
    response = client.get(path)
    assert response.status_code == 200, f"{path} returned {response.status_code}"


def test_healthz_is_ok(client, db):
    """What the platform itself polls."""
    assert client.get("/healthz").status_code == 200


def test_the_two_products_stay_sealed(client, db):
    """The separation, checked through the running site rather than the source.

    Cheap enough to run on every push, and it is the rule most likely to be
    broken by accident: one convenient link is all it takes.
    """
    babook = client.get("/").content.decode()
    assert "/matazim" not in babook

    matazim = client.get(reverse("matazim:home")).content.decode()
    assert "babook" not in matazim


def test_a_member_page_asks_for_our_login(client, db):
    """Gating works and sends people to our door, not somebody else's."""
    response = client.get(reverse("matazim:profile"))
    assert response.status_code == 302
    assert response.url.startswith("/matazim/login/")


def test_every_css_variable_is_defined():
    """An undefined custom property fails silently, which is the worst kind.

    `var(--mz-accent)` in a rule is not an error: the declaration is simply
    dropped and the element keeps whatever it inherited, so a wrong colour or a
    missing border looks like a design choice rather than a typo. Two invented
    token names got into the stylesheet this way and were only caught by reading
    the paint by eye. This is a grep, it costs nothing, and it runs every push.
    """
    import re
    from pathlib import Path

    css = Path("static/matazim/matazim.css").read_text(encoding="utf-8")

    # A definition is `--name:` at the start of a declaration; a use is inside
    # `var()`. Fallbacks (`var(--a, #fff)`) still require --a to exist to be
    # anything other than luck, so they are checked the same way.
    defined = set(re.findall(r"(--mz-[\w-]+)\s*:", css))
    used = set(re.findall(r"var\(\s*(--mz-[\w-]+)", css))

    missing = sorted(used - defined)
    assert not missing, f"used in a rule but never defined, so the rule is dead: {missing}"


def test_no_template_comment_spans_a_line():
    """Django's `{# #}` is single-line only, so a wrapped one is not a comment.

    The half after the newline renders, as developer prose, in the middle of a
    page. The screen contract catches this only where a screen is rendered in
    the state that reaches the comment, and two of these were sitting in
    branches no fixture visits: a fallback for applications made before the
    table existed, and a history entry for a move. Two more were in babook, one
    of them at the top of a reusable gallery partial, which put an English
    paragraph about function arguments onto lesson pages.

    It is a static fault, so this is a static check, and it covers both products
    because the mistake is not specific to either.
    """
    import re
    from pathlib import Path

    bad = []
    for path in sorted(Path("templates").rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"\{#", text):
            rest = text[match.start():]
            end = rest.find("#}")
            if end == -1 or "\n" in rest[:end]:
                bad.append(f"{path}:{text[:match.start()].count(chr(10)) + 1}")

    assert not bad, (
        "a `{# #}` comment runs past its line, so the rest of it renders as "
        "text; use `{% comment %}`:\n  " + "\n  ".join(bad)
    )


def test_matazim_says_hadrachot():
    """Avi, 2026-09-13: מט״צים says הדרכות, not קורסים.

    Decided after the request assistant nearly had the opposite baked into its
    prompt. The rule is babook's brand term and מט״צים was using both: 14 uses
    of הדרכות against 6 of קורסים, including the nav item every member read on
    every page. Copy drifts back the moment nobody is looking, and a product
    that calls one thing two names teaches its own assistant to as well.

    UI text only. URLs, view names and model slugs stay `course`, which is
    babook's vocabulary for its own tables and is not something a reader sees.
    """
    import re
    from pathlib import Path

    offenders = []
    for template in sorted(Path("templates/matazim").rglob("*.html")):
        for n, line in enumerate(template.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"קורס", line):
                offenders.append(f"{template.name}:{n} {line.strip()[:70]}")

    assert not offenders, (
        "מט״צים says הדרכות, never קורסים, in anything a reader sees:\n  "
        + "\n  ".join(offenders)
    )


def test_the_matazim_track_has_nothing_it_cannot_render(db):
    """The trainings are babook's; the experience is מט״צים's (Avi, 2026-09-13).

    That holds only while מט״צים can render everything the completion rule
    depends on. It reads babook's content flags: a lesson needs `quiz_passed`
    if it carries a quiz marked `requires_correct`, or a reflection prompt on a
    course that issues certificates. מט״צים's lesson page renders the video and
    nothing else — no quiz, no reflection, no practice cell.

    Today the three courses in the track have neither, so a member who watches
    is credited and can be certified. The trap is that a babook author adding a
    quiz to `scratch` is a completely ordinary thing to do, and the day it
    happens every מט״צים member silently stops being able to finish the course
    while the screen shows them nothing to answer. Silent, because the progress
    bar simply stops moving.

    So this fails the moment the track gains something the player cannot show.
    The fix then is to render it in מט״צים's own chrome, not to relax the rule:
    the completion rule is babook's and RULE-3 says there is one of it.
    """
    from app.models import Course, LessonQuiz, Video

    from matazim.content import REQUIRED_COURSE_SLUGS

    blocked = []
    for slug in REQUIRED_COURSE_SLUGS:
        course = Course.objects.filter(slug=slug).first()
        if course is None:
            continue

        gating = LessonQuiz.objects.filter(video__course=course, requires_correct=True)
        for quiz in gating.select_related("video"):
            blocked.append(f"{slug}: lesson {quiz.video.lesson_order} has a gating quiz")

        if getattr(course, "issues_certificate", False):
            with_prompt = (
                Video.objects.filter(course=course)
                .exclude(reflection_prompt="")
                .exclude(reflection_prompt=None)
            )
            for video in with_prompt:
                blocked.append(f"{slug}: lesson {video.lesson_order} has a reflection prompt")

    assert not blocked, (
        "the מט״צים track now contains something its own lesson page cannot "
        "render, so members will stop completing it with nothing on screen to "
        "do about it:\n  " + "\n  ".join(blocked)
    )


def test_a_babook_test_never_holds_a_live_key():
    """The live-AI flag is מט״צים's, and reaches nothing else.

    Added 2026-09-14, after `MATAZIM_LIVE_AI=1` was found to hand a real key to
    all 1638 tests rather than to this product's own suites. babook's
    content-safety tests call the moderation and relevance endpoints on nearly
    every case, so the full regression went from minutes to twenty seconds a
    test. This file is not a מט״צים sprint suite, so the key must be blank here
    whatever the flag says, and this test says so from the only place that can
    prove it: inside a test that is not entitled to one.
    """
    from django.conf import settings

    assert settings.OPENAI_API_KEY == "", (
        "a test outside tests/test_spr_m_*.py was handed a live API key"
    )
