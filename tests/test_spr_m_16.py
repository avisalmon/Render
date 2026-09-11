"""SPR-M.16 — המסלול שלי, the member's own screen.

The only role in this system with nowhere to stand. A leader has five screens,
the program manager seven, and the teenager the whole thing exists for has four,
two of them privacy plumbing. Their leader can see their progress through both
Scratch courses; they cannot see it themselves.

REQ-M.5a is the acceptance test, in Litala's words: every member sees
immediately where they are, what they have completed, and what their next task
is. Most of what follows is that sentence, split into things that can fail.

The tests that matter most are the two about *agreement*. This screen and the
leader's roster answer the same question from opposite ends, and a member told
they have finished four lessons while their leader is told three is the failure
this sprint can actually cause. The only reliable defence is one source, so
those tests compare the two screens rather than checking either one is plausible.

Traces: REQ-M.5a, M.12, M.43, M.65, M.74, M.76.
"""

import os

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.sprm16

PASSWORD = "sprm16-pass-3358"


def make_user(email, name=""):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name or email})
    return user


def make_course(slug, title, lessons=6):
    from app.models import Course, Video

    course = Course.objects.create(slug=slug, title=title, is_published=True)
    for n in range(lessons):
        Video.objects.create(course=course, title=f"{slug} {n}", lesson_order=n + 1)
    return course


def make_track():
    return (
        make_course("scratch", "סקראץ׳ למתחילים"),
        make_course("scratch-advanced", "סקראץ׳ מתקדם"),
    )


def make_leader(email="noa@example.com", name="נעה מורה", school="עתיד רמלה"):
    from matazim.models import Leader, StudyClass

    leader = Leader.objects.create(user=make_user(email, name), approved_at=timezone.now())
    StudyClass.objects.create(leader=leader, name="ט1", school_name=school)
    return leader


def make_member(email="kid@example.com", name="יובל כהן", passed=True, leader=None):
    from matazim.models import MemberProfile, Student

    user = make_user(email, name)
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now() if passed else None,
            "birth_year": timezone.now().year - 14,
            "guardian_consent_at": timezone.now(),
            "welcome_accepted_at": timezone.now(),
        },
    )
    student = None
    if leader is not None:
        student = Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)
    return user, student


def watch(user, course, count):
    from app.models import UserVideoProgress

    for video in course.videos.order_by("lesson_order")[:count]:
        UserVideoProgress.objects.update_or_create(
            user=user,
            video=video,
            defaults={
                "percent_watched": 100.0,
                "quiz_passed": True,
                "completed_at": timezone.now(),
            },
        )


def certify(user, course):
    from app.models import CourseCertificate

    return CourseCertificate.objects.get_or_create(user=user, course=course)[0]


# ------------------------------------------------- F-M.16.1, F-M.16.2


def test_a_member_has_a_screen_of_their_own(client, db):
    """T-F-M.16.1-1: REQ-M.12. The hole this sprint exists to fill."""
    make_track()
    user, _ = make_member(leader=make_leader())
    client.force_login(user)

    response = client.get(reverse("matazim:my_path"))
    assert response.status_code == 200


def test_it_says_where_they_are_right_now(client, db):
    """T-F-M.16.1-2: REQ-M.5a, Litala's sentence.

    The current stage is marked, not merely listed among five. A path that does
    not say which step you are on is a diagram, not a screen.
    """
    make_track()
    user, _ = make_member(leader=make_leader())
    client.force_login(user)

    html = client.get(reverse("matazim:my_path")).content.decode()
    assert "לומדים" in html
    assert "is-current" in html, "the current stage must be marked"


def test_it_says_what_is_next(client, db):
    """T-F-M.16.2-1: REQ-M.5a.

    The other half of her sentence, and the half a member actually acts on.
    """
    scratch, _advanced = make_track()
    user, _ = make_member(leader=make_leader())
    watch(user, scratch, 2)
    client.force_login(user)

    html = client.get(reverse("matazim:my_path")).content.decode()
    assert "המשימה הנוכחית" in html or "הצעד הבא" in html


def test_someone_who_has_not_started_is_not_shown_an_error(client, db):
    """T-F-M.16.2-2: REQ-M.65's principle on the member's own screen.

    Nothing done yet is the normal state of a new member, and the page must read
    as a beginning rather than as something broken.
    """
    make_track()
    user, _ = make_member(leader=make_leader())
    client.force_login(user)

    html = client.get(reverse("matazim:my_path")).content.decode()
    assert "0/12" in html
    assert "שגיאה" not in html


# ------------------------------------------------- F-M.16.3: the track


def test_the_track_is_listed_lesson_by_lesson(client, db):
    """T-F-M.16.3-1: REQ-M.12.

    Named in Hebrew, because a slug is an identifier and this reader is
    fourteen.
    """
    scratch, _advanced = make_track()
    user, _ = make_member(leader=make_leader())
    watch(user, scratch, 4)
    client.force_login(user)

    html = client.get(reverse("matazim:my_path")).content.decode()
    assert "סקראץ׳ למתחילים" in html
    assert "סקראץ׳ מתקדם" in html
    assert "4/6" in html


def test_the_member_and_their_leader_are_told_the_same_number(client, db):
    """T-F-M.16.3-2: REQ-M.74, and the failure this sprint could cause.

    Two screens answering the same question from opposite ends. A member told
    they have finished four lessons while their leader is told three is not a
    cosmetic bug: it is the product lying to one of them, and neither would know.
    """
    import re

    scratch, advanced = make_track()
    leader = make_leader()
    user, student = make_member(leader=leader)
    watch(user, scratch, 5)
    watch(user, advanced, 2)

    client.force_login(user)
    mine = client.get(reverse("matazim:my_path")).content.decode()

    client.logout()
    client.force_login(leader.user)
    theirs = client.get(reverse("matazim:roster")).content.decode()

    def fraction(html):
        row = re.search(r"(\d+)/(\d+)", html)
        return row.group(0) if row else None

    assert "7/12" in mine, f"the member's own total is wrong: {fraction(mine)}"
    assert "7/12" in theirs, f"the leader is told something else: {fraction(theirs)}"


# ------------------------------------------------- F-M.16.4: the conditions


def test_the_three_conditions_are_shown_as_things_to_do(client, db):
    """T-F-M.16.4-1: REQ-M.76 from the other side.

    The leader's version of this panel is a decision aid. The member's version
    is the answer to "what do I have to do", which is the same three facts
    arranged for somebody who can act on them.
    """
    scratch, _advanced = make_track()
    user, _ = make_member(leader=make_leader())
    certify(user, scratch)
    client.force_login(user)

    html = client.get(reverse("matazim:my_path")).content.decode()
    assert "מבחן הכניסה" in html
    assert "סקראץ׳ מתקדם" in html


def test_a_member_who_is_ready_is_told_so(client, db):
    """T-F-M.16.4-2: REQ-M.76, REQ-M.78.

    Ready is not certified, and the page must not imply it is. What it can
    honestly say is that the part they control is finished and the decision is
    now somebody else's.
    """
    scratch, advanced = make_track()
    user, _ = make_member(leader=make_leader())
    certify(user, scratch)
    certify(user, advanced)
    client.force_login(user)

    html = client.get(reverse("matazim:my_path")).content.decode()
    assert "מוכנים" in html or "המוביל" in html

    # The badge, not the phrase. A bare substring catches the section heading
    # "כדי להיות מט״צ מוסמך", which is the page correctly describing the goal,
    # and asserting against it would be the test misreading its own screen.
    assert 'mz-tag-done">מט״צ מוסמך' not in html, "ready must not wear the certified badge"


def test_a_certified_member_sees_it_plainly(client, db):
    """T-F-M.16.4-3: REQ-M.28. The thing the whole programme is for."""
    from matazim.models import Student

    scratch, advanced = make_track()
    leader = make_leader()
    user, student = make_member(leader=leader)
    certify(user, scratch)
    certify(user, advanced)
    student.status = Student.CERTIFIED
    student.certified_at = timezone.now()
    student.certified_by = leader.user
    student.save()

    client.force_login(user)
    html = client.get(reverse("matazim:my_path")).content.decode()
    assert "מט״צ מוסמך" in html


# ------------------------------------------------- F-M.16.5: their leader


def test_a_member_sees_who_their_leader_is(client, db):
    """T-F-M.16.5-1: REQ-M.43.

    They can see the person who can see them. A one-way mirror would be a
    strange thing to build for minors.
    """
    make_track()
    user, _ = make_member(leader=make_leader(name="נעה מורה", school="עתיד רמלה"))
    client.force_login(user)

    html = client.get(reverse("matazim:my_path")).content.decode()
    assert "נעה מורה" in html
    assert "עתיד רמלה" in html


def test_a_member_with_no_leader_is_given_the_way_forward(client, db):
    """T-F-M.16.5-2: REQ-M.65.

    Having no leader is a normal state, not an error, and the page says what to
    do rather than reading as though something went wrong.
    """
    make_track()
    user, _ = make_member(leader=None)
    client.force_login(user)

    html = client.get(reverse("matazim:my_path")).content.decode()
    assert reverse("matazim:apply") in html
    assert "שגיאה" not in html


def test_a_member_sees_nobody_elses_data(client, db):
    """T-F-M.16.5-3: REQ-M.22 on the newest screen.

    Their own screen, built from `request.user` and nothing in the URL, so there
    is no identifier here to tamper with.
    """
    make_track()
    leader = make_leader()
    user, _ = make_member("mine@example.com", "יובל שלי", leader=leader)
    make_member("other@example.com", "דני זר", leader=leader)

    client.force_login(user)
    html = client.get(reverse("matazim:my_path")).content.decode()
    assert "דני זר" not in html


# ------------------------------------------------- F-M.16.6: reaching it


def test_a_member_can_find_the_screen(client, db):
    """T-F-M.16.6-1: REQ-M.5b.

    A screen you have to know the URL for is a screen nobody uses, which this
    product has now learned three times (REQ-M.62, REQ-M.89, and the roster).
    """
    make_track()
    user, _ = make_member(leader=make_leader())
    client.force_login(user)

    for page in ("matazim:home", "matazim:profile"):
        html = client.get(reverse(page)).content.decode()
        assert reverse("matazim:my_path") in html, f"unreachable from {page}"


def test_a_stranger_cannot_open_it(client, db):
    """T-F-M.16.6-2: it is somebody's own data."""
    make_track()
    assert client.get(reverse("matazim:my_path")).status_code in (302, 403)


def test_a_visitor_with_an_account_but_no_program_still_gets_a_useful_page(client, db):
    """T-F-M.16.6-3: REQ-M.11 as amended.

    A screen showing only your own data requires only an account. Somebody who
    registered and has not taken the entrance test is not an error either: they
    are at the beginning, and the page should say so and point at the test.
    """
    make_track()
    user, _ = make_member(passed=False, leader=None)
    client.force_login(user)

    response = client.get(reverse("matazim:my_path"))
    assert response.status_code == 200
    assert reverse("matazim:entrance_test") in response.content.decode()


def test_the_here_you_are_badge_is_a_label_not_a_banner(live_server, db):
    """T-F-M.16.1-3: found by rendering it and measuring.

    `.mz-tag` sets `flex: none`, which governs the main axis only. Inside a
    column flex container the cross axis is horizontal and still stretches, so
    the badge rendered as a pill the full width of the page. A test that reads
    the template cannot see this; only a browser can, so this measures.
    """
    playwright = pytest.importorskip("playwright.sync_api")

    make_track()
    user, _ = make_member(leader=make_leader())

    from django.contrib.auth import SESSION_KEY, get_user_model  # noqa: F401

    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        page.goto(f"{live_server.url}/matazim/login/", wait_until="domcontentloaded")
        page.wait_for_timeout(250)
        welcome = page.locator(".mz-welcome button[type=submit]")
        if welcome.count():
            welcome.click()
            page.wait_for_timeout(300)
        page.fill('input[name="email"]', user.email)
        page.fill('input[name="password"]', PASSWORD)
        page.click('form:has(input[name="password"]) button[type="submit"]')
        page.wait_for_timeout(600)
        page.goto(f"{live_server.url}/matazim/my-path/", wait_until="domcontentloaded")
        page.wait_for_timeout(400)

        width = page.evaluate(
            "() => { const t = document.querySelector('.mz-journey-body > .mz-tag');"
            " return t ? Math.round(t.getBoundingClientRect().width) : -1; }"
        )
        browser.close()

    assert width > 0, "the current-stage badge is missing"
    assert width < 200, f"the badge is {width}px wide: it is stretching, not hugging its text"


def test_the_screen_does_not_grow_a_query_per_lesson(django_assert_num_queries, db, client):
    """T-F-M.16.3-3: REQ-M.74's motivation, applied to the member's own page.

    The roster was rewritten so it would not cost a query per teenager. This
    page has the mirror risk: a query per course, or worse per lesson, because
    it renders a track lesson by lesson. Measured against a two-course track and
    then asserted to be unchanged, rather than pinned to a number that any
    unrelated refactor would break.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    scratch, advanced = make_track()
    user, _ = make_member(leader=make_leader())
    watch(user, scratch, 6)
    watch(user, advanced, 3)
    client.force_login(user)

    with CaptureQueriesContext(connection) as first:
        client.get(reverse("matazim:my_path"))

    # Triple the lessons. The page shows the same two courses, so the cost of
    # rendering it must not move.
    from app.models import Video

    for course in (scratch, advanced):
        for n in range(12):
            Video.objects.create(course=course, title=f"extra {n}", lesson_order=100 + n)
    watch(user, scratch, 18)

    with django_assert_num_queries(len(first)):
        client.get(reverse("matazim:my_path"))


def test_it_does_not_say_continue_to_someone_who_has_not_started(client, db):
    """T-F-M.16.2-3: found by reading the rendered page.

    A member at 0/19 was told "להמשיך" — continue. It is a small wrongness, and
    small wrongnesses are how a screen stops feeling like it is looking at you.
    """
    make_track()
    user, _ = make_member(leader=make_leader())
    client.force_login(user)

    html = client.get(reverse("matazim:my_path")).content.decode()
    assert "להתחיל" in html
    assert "להמשיך" not in html


def test_it_does_say_continue_to_someone_who_has(client, db):
    """T-F-M.16.2-4: and the other half, so the fix is not just a word swap."""
    scratch, _advanced = make_track()
    user, _ = make_member(leader=make_leader())
    watch(user, scratch, 3)
    client.force_login(user)

    html = client.get(reverse("matazim:my_path")).content.decode()
    assert "להמשיך" in html


# ---------------------------------- REQ-M.17, resolved rather than carried


def test_a_leader_can_open_the_attempt_that_let_their_student_in(client, db):
    """T-REQ-M.17-1: the human judgement, where it can actually happen.

    REQ-M.17 used to say a school leader reviews the entrance attempt and
    decides. That reviewer could not exist: REQ-M.36 requires the test to be
    passed *before* anyone can join a leader, so at review time the candidate
    has no leader. The gate is the automatic check, which never rejects.

    What is real is this: once a student joins, their leader can open the
    attempt and see how it measured, and is under no obligation to keep them or
    certify them. The judgement moved downstream rather than disappearing, so
    this pins the part that actually exists.
    """
    from django.core.files.uploadedfile import SimpleUploadedFile

    from matazim.models import EntranceAttempt, MemberProfile

    make_track()
    leader = make_leader()
    user, _student = make_member(leader=leader)

    profile = MemberProfile.objects.get(user=user)
    attempt = EntranceAttempt.objects.create(
        member=profile, target_id="t0000", number=1, passed=True, submitted_at=timezone.now()
    )
    attempt.model_file = SimpleUploadedFile("mine.stl", b"solid x\nendsolid x\n")
    attempt.save()

    client.force_login(leader.user)
    assert client.get(reverse("matazim:attempt_file", args=[attempt.pk])).status_code == 200
