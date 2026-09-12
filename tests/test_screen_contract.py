"""The screen contract: what every מט״צים page must be true of, rendered.

Written 2026-09-11 after eleven sprints in which **every single screen that got
rendered turned out to have a defect no test had caught**, and not one exception.
A badge 1018px wide. A class-name collision silently inheriting another page's
card styling. "Continue" said to somebody at 0 of 19. Raw database keys in a
teenager's audit trail. A school name printed twice. Course slugs in Hebrew
prose.

Two things are true about all of them and they point the same way.

**They were invisible to a test that reads a template.** Nothing was wrong in
the markup; the wrongness only existed once a browser had applied the
stylesheet and the data. The one check that did catch things repeatedly was the
phone guard, which is the only test in this suite that renders in a real
browser and measures.

**Every one lived in a state nobody had rendered.** Zero progress. Two classes
in one school. No class at all. A history with one line. The happy path was
tested and looked at; the other states were tested and never seen.

So this is not more tests of the same kind. It is a catalogue of screens *by
state*, rendered, asserting the handful of properties that only exist after
layout. Adding a screen means adding it here, and adding a state it can be in
means adding that too. That is the cost, and it is smaller than the cost of
finding these one at a time by accident.

What it does **not** replace: the per-sprint tests, which check that the rules
hold. This checks that the result is fit to put in front of a fourteen-year-old.
"""

import os
import re

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.screens, pytest.mark.django_db]

PASSWORD = "screen-contract-7781"
DESKTOP = {"width": 1280, "height": 900}

# Raw values that must never reach a reader. These are database keys and code
# identifiers; the product has Hebrew for every one of them, and a page showing
# the key is a page that forgot to ask for the label.
RAW_KEYS = [
    "in_training",
    "project_submitted",
    "scratch-advanced",
]

# Words that mean something went wrong. A screen in a *normal* empty state must
# never use them: having no students yet, or no leader yet, is a beginning
# rather than a fault (REQ-M.65).
ALARM_WORDS = ["שגיאה", "Traceback", "None", "null"]


# --------------------------------------------------------------- the world


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _courses():
    from app.models import Course, Video

    made = {}
    for slug, title, n in (
        ("scratch", "סקראץ׳ למתחילים", 6),
        ("scratch-advanced", "סקראץ׳ מתקדם", 4),
    ):
        course = Course.objects.create(slug=slug, title=title, is_published=True)
        for i in range(n):
            Video.objects.create(course=course, title=f"{title} {i}", lesson_order=i + 1)
        made[slug] = course
    return made


def build_world(*, students="mixed", classes="one"):
    """One institution, dialled to the state under test.

    `students`: none | mixed  — an empty roster is its own screen.
    `classes`:  none | one | two_same_school — the last one is the shape that
                printed "עתיד רמלה · עתיד רמלה" and would otherwise never occur
                in a fixture, because nobody writes that case by hand.
    """
    from app.models import CourseCertificate, UserVideoProgress
    from matazim.history import record_arrival, set_status
    from matazim.models import Leader, MemberProfile, Student, StudyClass

    courses = _courses()
    now = timezone.now()

    manager = _user("pm@example.com", "נעמי")
    MemberProfile.objects.update_or_create(user=manager, defaults={"is_program_manager": True})

    leader = Leader.objects.create(
        user=_user("leader@example.com", "נעה מורה"),
        program_manager=manager,
        approved_at=now,
    )

    rooms = []
    if classes == "one":
        rooms = [StudyClass.objects.create(leader=leader, name="ט1", school_name="עתיד רמלה")]
    elif classes == "two_same_school":
        rooms = [
            StudyClass.objects.create(leader=leader, name=n, school_name="עתיד רמלה")
            for n in ("ט1", "ט3")
        ]

    people = {}
    if students == "mixed":
        # Deliberately across the whole range, including the two ends. Nothing
        # started and everything finished are where the copy goes wrong.
        spec = [
            ("fresh@example.com", "יובל כהן", 0, 0, [], "in_training"),
            ("mid@example.com", "מאיה לוי", 4, 1, ["scratch"], "in_training"),
            (
                "ready@example.com",
                "עומר שלום",
                6,
                4,
                ["scratch", "scratch-advanced"],
                "in_training",
            ),
            (
                "done@example.com",
                "דניאל אזולאי",
                6,
                4,
                ["scratch", "scratch-advanced"],
                "certified",
            ),
        ]
        for email, name, n_a, n_b, certs, status in spec:
            user = _user(email, name)
            MemberProfile.objects.update_or_create(
                user=user,
                defaults={
                    "entrance_test_passed_at": now,
                    "birth_year": now.year - 14,
                    "guardian_consent_at": now,
                    "welcome_accepted_at": now,
                },
            )
            student = Student.objects.create(user=user, leader=leader)
            record_arrival(student, by=user, note="הצטרפות")
            set_status(student, status, by=leader.user, note="אישור מוביל/ה")
            if rooms:
                student.classes.set(rooms)

            for slug, count in (("scratch", n_a), ("scratch-advanced", n_b)):
                for video in courses[slug].videos.order_by("lesson_order")[:count]:
                    UserVideoProgress.objects.update_or_create(
                        user=user,
                        video=video,
                        defaults={
                            "percent_watched": 100.0,
                            "quiz_passed": True,
                            "completed_at": now,
                        },
                    )
            for slug in certs:
                CourseCertificate.objects.get_or_create(user=user, course=courses[slug])
            people[email] = student

    return {"manager": manager, "leader": leader, "students": people}


# --------------------------------------------------------- the catalogue
#
# Every screen, in every state it can meaningfully be in. A screen missing from
# here is a screen nobody is looking at.

SCREENS = [
    # (label, path, who signs in, how to build the world)
    ("member/fresh", "/matazim/my-path/", "fresh@example.com", dict(students="mixed")),
    ("member/mid", "/matazim/my-path/", "mid@example.com", dict(students="mixed")),
    ("member/ready", "/matazim/my-path/", "ready@example.com", dict(students="mixed")),
    ("member/certified", "/matazim/my-path/", "done@example.com", dict(students="mixed")),
    ("member/no-class", "/matazim/my-path/", "fresh@example.com", dict(classes="none")),
    ("leader/roster", "/matazim/leader/students/", "leader@example.com", dict(students="mixed")),
    (
        "leader/roster-empty",
        "/matazim/leader/students/",
        "leader@example.com",
        dict(students="none"),
    ),
    ("leader/classes", "/matazim/leader/classes/", "leader@example.com", dict(students="mixed")),
    ("leader/home", "/matazim/leader/", "leader@example.com", dict(students="mixed")),
    ("pm/leaders", "/matazim/staff/team/", "pm@example.com", dict(students="mixed")),
    (
        "pm/leaders-two-classes",
        "/matazim/staff/team/",
        "pm@example.com",
        dict(classes="two_same_school"),
    ),
    ("pm/cohort", "/matazim/staff/cohort/", "pm@example.com", dict(students="mixed")),
    ("pm/cohort-empty", "/matazim/staff/cohort/", "pm@example.com", dict(students="none")),
    # SPR-M.19: the track, which a member reads more than any staff screen.
    ("learn/course-fresh", "/matazim/learn/scratch/", "fresh@example.com", dict(students="mixed")),
    ("learn/course-part", "/matazim/learn/scratch/", "mid@example.com", dict(students="mixed")),
    ("learn/course-done", "/matazim/learn/scratch/", "done@example.com", dict(students="mixed")),
    ("learn/lesson", "/matazim/learn/scratch/1/", "mid@example.com", dict(students="mixed")),
]


# ------------------------------------------------------------ the checks
#
# Each returns a list of complaints. Written as JS because every one of them is
# a question about the rendered result, not about the source.

VISIBLE_TEXT_JS = "() => document.body.innerText"

STRETCHED_JS = """() => {
    // A pill that is nearly as wide as its container is not a label any more.
    // `.mz-tag` sets `flex: none`, which governs the main axis only, so inside
    // a column flex it still stretches: that is how a badge became a banner.
    const bad = [];
    document.querySelectorAll('.mz-tag').forEach(el => {
        const w = el.getBoundingClientRect().width;
        const parent = el.parentElement
            ? el.parentElement.getBoundingClientRect().width : 0;
        if (parent > 0 && w > parent * 0.6 && w > 220) {
            bad.push((el.textContent || '').trim().slice(0, 20) + ' ' +
                     Math.round(w) + 'px of ' + Math.round(parent));
        }
    });
    return bad;
}"""

REPEATED_JS = """() => {
    // "עתיד רמלה · עתיד רמלה": a list built by looping the wrong thing. On a
    // page meant to be scanned a repeated word reads as two different things.
    const bad = [];
    document.querySelectorAll('span, li, p').forEach(el => {
        if (el.querySelector('span, li, p')) return;   // leaves only
        const text = (el.textContent || '').trim();
        if (text.length < 4 || !text.includes('\\u00b7')) return;
        const parts = text.split('\\u00b7').map(s => s.trim()).filter(Boolean);
        const seen = new Set();
        for (const part of parts) {
            if (part.length > 2 && seen.has(part)) { bad.push(text.slice(0, 50)); break; }
            seen.add(part);
        }
    });
    return [...new Set(bad)];
}"""


@pytest.fixture(scope="module")
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            b = pw.chromium.launch()
            yield b
            b.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


def _open(browser, live_server, email, path):
    context = browser.new_context(viewport=DESKTOP)
    page = context.new_page()
    page.goto(f"{live_server.url}/matazim/login/", wait_until="domcontentloaded")
    page.wait_for_timeout(200)
    welcome = page.locator(".mz-welcome button[type=submit]")
    if welcome.count():
        welcome.click()
        page.wait_for_timeout(250)
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', PASSWORD)
    page.click('form:has(input[name="password"]) button[type="submit"]')
    page.wait_for_timeout(500)
    assert "/login/" not in page.url, f"could not sign in as {email}"

    page.goto(live_server.url + path, wait_until="domcontentloaded")
    page.wait_for_timeout(350)
    return context, page


@pytest.mark.parametrize("label,path,who,world", SCREENS, ids=[s[0] for s in SCREENS])
def test_screen_contract(browser, live_server, db, label, path, who, world):
    """Every screen, in every state, must hold all of these at once.

    One test per screen-state rather than one per property, because a failure
    should name the screen you broke, which is the thing you are about to go
    and look at.
    """
    build_world(**world)
    context, page = _open(browser, live_server, who, path)
    try:
        complaints = []

        text = page.evaluate(VISIBLE_TEXT_JS)
        for key in RAW_KEYS:
            if key in text:
                complaints.append(f"a database key or slug reached the reader: {key!r}")
        for word in ALARM_WORDS:
            if re.search(rf"(?<![\w/]){re.escape(word)}(?![\w/])", text):
                complaints.append(f"reads as a fault rather than a state: {word!r}")

        for entry in page.evaluate(STRETCHED_JS):
            complaints.append(f"a label is stretching to banner width: {entry}")
        for entry in page.evaluate(REPEATED_JS):
            complaints.append(f"something is listed twice: {entry}")

        assert not complaints, f"{label} ({path}):\n  " + "\n  ".join(complaints)
    finally:
        context.close()


def test_every_class_a_template_uses_actually_exists():
    """A class in the markup that the stylesheet has never heard of.

    This is the honest half of a problem I could not automate. Three times a new
    screen reused a class the stylesheet had already given to another component
    and silently inherited its look: `.mz-path-body`, `.mz-lessons`, and one
    before them. I tried to detect that statically and could not make it precise
    without flagging legitimate cases, and a guard that cries wolf is a guard
    that gets suppressed. So the collision rule stays a written discipline
    (the_manager.md, Step 4a: grep the stylesheet before naming a component).

    What *is* precise is the mirror image, and it is worth having: a class that
    appears in a template and nowhere in the stylesheet is a typo or a leftover,
    and it fails silently for ever because unstyled markup still renders.
    """
    import re
    from pathlib import Path

    css = Path("static/matazim/matazim.css").read_text(encoding="utf-8")
    defined = set(re.findall(r"\.(mz-[a-z0-9-]+)", css))

    # State hooks: classes that carry meaning rather than style. `mz-door-locked`
    # has no CSS and never needed any, because the locked look comes from
    # `.mz-btn.is-disabled`; what it does is let six tests assert the door is
    # shut. That is a legitimate thing for a class to be, so the allowlist names
    # them rather than the check pretending they are mistakes.
    STATE_ONLY = {"mz-door-locked", "mz-nav-done", "mz-tag-fix", "mz-tag-late"}

    unknown = {}
    for template in sorted(Path("templates/matazim").glob("*.html")):
        text = template.read_text(encoding="utf-8")
        for attr in re.findall(r'class="([^"]*)"', text):
            for name in attr.split():
                if not name.startswith("mz-") or "{" in name:
                    continue
                if name not in defined and name not in STATE_ONLY:
                    unknown.setdefault(name, template.name)

    listing = "\n  ".join(f"{name}  ({where})" for name, where in sorted(unknown.items()))
    assert not unknown, f"markup uses classes the stylesheet does not define:\n  {listing}"
