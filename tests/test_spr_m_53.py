"""SPR-M.53 — נעמי and ליטל see the programme the way Avi does.

Avi, 2026-10-08:

> "אני צריך שתעשה שליטל ונעמי יראו את כל היכולות כמו שאני רואה. הם לא במעמד
> תלמיד ולא צריכות לעשות את המבחן... הכי חשוב בשלב הזה שהן יראו בברור בכניסה
> למערכת: את כל הקורסים, את כל המובילים והסטטוס התקדמות שלהם ואם עשו את המבחן."

Both answers were already in the database and neither had a screen: the leaders
list printed a name, a school and a dot, and the only screen showing the whole
catalogue was root's control panel for setting the pool.

**The tests that matter are the tenancy ones.** This sprint adds two screens
that read across the programme, which is exactly the shape of change that
quietly widens what a program manager can see. So a second institution exists
in the fixture for no other reason than to be invisible, and
`test_one_programmes_report_is_not_anothers` is the guard.

The second thing worth holding is the query count. Both readers are built for a
list page and both are one pass; the version that is one query per leader looks
identical until there are forty of them.

Traces: REQ-M.88, REQ-M.148, REQ-M.149, REQ-M.76, §4.3, §4.9, RULE-3.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

pytestmark = pytest.mark.sprm53

PASSWORD = "sprm53-pass-4417"


def _course(slug, title="הדרכה", published=True):
    from app.models import Course, Video

    course = Course.objects.create(slug=slug, title=title, is_published=published)
    Video.objects.create(course=course, title="שיעור 1", lesson_order=1,
                         bunny_video_id=f"v-{slug}")
    return course


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


@pytest.fixture
def world(db):
    """One programme, one foreign programme, and people in both."""
    from matazim.models import Institution, Leader, MemberProfile, Student, StudyClass

    for slug in ("scratch", "scratch-advanced"):
        _course(slug, "סקראץ׳")
    _course("arduino", "ארדואינו")
    _course("fpga", "FPGA")
    _course("secret", "טיוטה", published=False)

    root = User.objects.create_superuser("avi@example.com", "avi@example.com", PASSWORD)

    ours = Institution.objects.create(name="הרשת שלנו")
    theirs = Institution.objects.create(name="רשת אחרת")
    naomi = _user("naomi@example.com", "נעמי")
    ours.managers.add(naomi)
    other_pm = _user("pm2@example.com", "מנהלת אחרת")
    theirs.managers.add(other_pm)

    # One leader who took the entrance test, one who never met it, one waiting.
    taught = Leader.objects.create(
        user=_user("teacher@example.com", "מוביל שעבר"), institution=ours,
        approved_at=timezone.now(),
    )
    MemberProfile.objects.create(user=taught.user,
                                 entrance_test_passed_at=timezone.now())
    plain = Leader.objects.create(
        user=_user("plain@example.com", "מוביל רגיל"), institution=ours,
        approved_at=timezone.now(),
    )
    waiting = Leader.objects.create(
        user=_user("waiting@example.com", "ממתין"), institution=ours,
    )
    foreign = Leader.objects.create(
        user=_user("foreign@example.com", "מוביל זר"), institution=theirs,
        approved_at=timezone.now(),
    )
    StudyClass.objects.create(leader=taught, name="ט1", school_name="תיכון א")

    kid = Student.objects.create(user=_user("kid@example.com", "מט״צ"),
                                 leader=taught, status=Student.IN_TRAINING)
    their_kid = Student.objects.create(user=_user("kid2@example.com", "מט״צ זר"),
                                       leader=foreign, status=Student.IN_TRAINING)
    return {"root": root, "naomi": naomi, "other_pm": other_pm,
            "taught": taught, "plain": plain, "waiting": waiting,
            "foreign": foreign, "kid": kid, "their_kid": their_kid}


def _login(client, email):
    assert client.login(username=email, password=PASSWORD)
    return client


# ----------------------------------------------------- the tenancy guards


def test_one_programmes_report_is_not_anothers(client, world):
    """The load-bearing one. Two screens that read across the programme are
    exactly where a program manager quietly acquires another's people."""
    from matazim.overview import leader_rows

    rows = leader_rows(world["naomi"])
    names = {row["email"] for row in rows}
    assert "teacher@example.com" in names
    assert "foreign@example.com" not in names, "another programme's leader is showing"

    body = _login(client, "naomi@example.com").get("/matazim/staff/people/").content.decode()
    assert "מוביל שעבר" in body
    assert "מוביל זר" not in body


def test_root_crosses_every_programme(client, world):
    """REQ-M.88 — root is the only role that does, and ליטל is root."""
    from matazim.overview import leader_rows

    emails = {row["email"] for row in leader_rows(world["root"])}
    assert {"teacher@example.com", "foreign@example.com"} <= emails


def test_the_course_counts_are_scoped_too(world):
    """The catalogue is the same list for everybody; how many of *our* people
    are doing each one is not."""
    from app.models import Course, Enrollment
    from matazim.overview import course_rows

    arduino = Course.objects.get(slug="arduino")
    Enrollment.objects.create(user=world["kid"].user, course=arduino)
    Enrollment.objects.create(user=world["their_kid"].user, course=arduino)

    def started(user):
        return next(r["started"] for r in course_rows(user) if r["slug"] == "arduino")

    assert started(world["naomi"]) == 1, "she is counting another programme's member"
    assert started(world["root"]) == 2


def test_a_member_and_a_leader_cannot_open_either_report(client, world):
    """Hiding a link has never been access control, so both views refuse on
    their own."""
    for email in ("kid@example.com", "teacher@example.com"):
        session = _login(client, email)
        for path in ("/matazim/staff/people/", "/matazim/staff/courses/"):
            assert session.get(path).status_code == 403, f"{email} {path}"
        session.logout()


def test_a_stranger_is_sent_to_sign_in(client, world):
    for path in ("/matazim/staff/people/", "/matazim/staff/courses/"):
        response = client.get(path)
        assert response.status_code == 302
        assert "/matazim/login/" in response["Location"]


# ----------------------------------------------------- what Avi asked for


def test_every_course_on_the_site_is_on_the_page(client, world):
    """"את כל הקורסים" — the whole catalogue, not the offered pool."""
    body = _login(client, "naomi@example.com").get("/matazim/staff/courses/").content.decode()
    for title in ("סקראץ׳", "ארדואינו", "FPGA"):
        assert title in body, title
    assert "טיוטה" not in body, "an unpublished course is not part of the site yet"


def test_the_catalogue_says_what_each_course_is_to_the_programme(world):
    from matazim.models import OfferedCourse
    from matazim.overview import course_rows

    OfferedCourse.objects.create(slug="arduino", added_by=world["root"])
    OfferedCourse.objects.create(slug="fpga", added_by=world["root"], is_active=False)

    rows = {r["slug"]: r for r in course_rows(world["naomi"])}
    assert rows["scratch"]["required"] is True
    assert rows["scratch"]["offered"] is True
    assert rows["arduino"]["offered"] is True
    assert rows["fpga"]["withdrawn"] is True
    assert rows["fpga"]["offered"] is False


def test_the_programmes_own_two_read_as_open_even_with_no_pool_row(world):
    """REQ-M.76 — the track is not withdrawable, so the report must not show it
    as shut just because nobody added a pool row for it."""
    from matazim.overview import course_rows

    rows = {r["slug"]: r for r in course_rows(world["root"])}
    assert rows["scratch-advanced"]["offered"] is True
    assert rows["scratch-advanced"]["withdrawn"] is False


def test_the_leaders_page_shows_progress_and_the_test(client, world):
    """"את כל המובילים והסטטוס התקדמות שלהם ואם עשו את המבחן"."""
    body = _login(client, "naomi@example.com").get("/matazim/staff/people/").content.decode()
    assert "מוביל שעבר" in body
    assert "עבר/ה את המבחן" in body
    assert "במסלול" in body, "no progress against the required track"
    assert "תיכון א" in body


def test_never_sitting_the_test_is_not_the_same_as_failing_it(world):
    """Most leaders are adults nobody asked. Printing that as a failure would
    report something that never happened."""
    from matazim.overview import leader_rows

    rows = {row["email"]: row for row in leader_rows(world["naomi"])}
    assert rows["teacher@example.com"]["took_test"] is True
    assert rows["plain@example.com"]["took_test"] is None


def test_somebody_who_sat_it_and_did_not_pass_reads_as_not_yet(world):
    """An attempt is what makes it False. Found in the dev data: every leader
    has a MemberProfile the moment they accept the welcome notice, so reading
    the profile printed טרם עבר/ה against four teachers who had never been
    near the test."""
    from matazim.models import EntranceAttempt, MemberProfile
    from matazim.overview import leader_rows

    profile = MemberProfile.objects.create(user=world["plain"].user)
    rows = {row["email"]: row for row in leader_rows(world["naomi"])}
    assert rows["plain@example.com"]["took_test"] is None, (
        "merely having a profile is not having sat the test")

    EntranceAttempt.objects.create(member=profile, target_id="t1", number=1)
    rows = {row["email"]: row for row in leader_rows(world["naomi"])}
    assert rows["plain@example.com"]["took_test"] is False


def test_the_waiting_are_separated_from_the_working(client, world):
    """A candidate is the one state in this product that stays stuck until a
    person presses something, so it is not mixed into the list of everybody."""
    response = _login(client, "naomi@example.com").get("/matazim/staff/people/")
    approved = {row["email"] for row in response.context["rows"]}
    waiting = {row["email"] for row in response.context["candidates"]}
    assert "teacher@example.com" in approved
    assert "waiting@example.com" in waiting
    assert "waiting@example.com" not in approved
    assert "ממתינים לאישור" in response.content.decode()


def test_progress_is_read_from_the_shared_tables(world):
    """RULE-3 — the same reader the member's own screen uses, so a leader's row
    here and their own המסלול שלי can never disagree."""
    from app.models import Course, UserVideoProgress, Video
    from matazim.overview import leader_rows

    scratch = Course.objects.get(slug="scratch")
    UserVideoProgress.objects.create(
        user=world["taught"].user, video=Video.objects.get(course=scratch),
        completed_at=timezone.now(), quiz_passed=True, percent_watched=100.0,
    )
    rows = {row["email"]: row for row in leader_rows(world["naomi"])}
    assert rows["teacher@example.com"]["progress"]["pct"] > 0
    assert rows["plain@example.com"]["progress"]["pct"] == 0


# ----------------------------------------------------- the entry screen


def test_the_entry_screen_leads_to_both_reports(client, world):
    """"שהן יראו בברור בכניסה למערכת" — from the staff door, without hunting."""
    body = _login(client, "naomi@example.com").get("/matazim/staff/").content.decode()
    assert "/matazim/staff/people/" in body
    assert "/matazim/staff/courses/" in body
    assert "/matazim/staff/cohort/" in body, "the cohort funnel"
    assert "/matazim/requests/new/" in body, "the improvement loop"
    assert "/matazim/my-path/" in body, "the member's own screens, to look at"


def test_signing_in_as_staff_lands_on_the_reports(client, world):
    """בכניסה למערכת, literally. דף הבית is recruitment copy written for
    somebody deciding whether to join, which is the wrong page for the person
    running the programme."""
    response = client.post("/matazim/login/",
                           {"email": "naomi@example.com", "password": PASSWORD})
    assert response.status_code == 302
    assert response["Location"] == "/matazim/staff/"


def test_everybody_else_still_lands_where_they_did(client, world):
    for email in ("kid@example.com", "teacher@example.com"):
        response = client.post("/matazim/login/",
                               {"email": email, "password": PASSWORD})
        assert response["Location"] == "/matazim/", email
        client.logout()


def test_an_explicit_destination_still_wins(client, world):
    response = client.post("/matazim/login/",
                           {"email": "naomi@example.com", "password": PASSWORD,
                            "next": "/matazim/staff/cohort/"})
    assert response["Location"] == "/matazim/staff/cohort/"


def test_the_menu_does_not_grow_for_the_reports(client, world):
    """REQ-M.101 caps a signed-in role at seven items, and that rule took these
    two back out of the menu an hour after they went in. The ניהול door is
    where they live."""
    import re

    body = _login(client, "naomi@example.com").get("/matazim/profile/").content.decode()
    nav = body.split('<nav class="mz-nav"')[1].split("</nav>")[0]
    assert len(re.findall(r"<a\s", nav)) <= 7
    assert "/matazim/staff/people/" not in nav


def test_staff_are_never_treated_as_pupils(client, world):
    """"הם לא במעמד תלמיד ולא צריכות לעשות את המבחן". A program manager is not
    a fourteen-year-old and the menu must not invite her to sit an exam."""
    from matazim.views import _is_member

    assert _is_member(world["naomi"]) is False
    assert _is_member(world["root"]) is False

    body = _login(client, "naomi@example.com").get("/matazim/").content.decode()
    assert "המסלול שלי" not in body, "a pupil's menu item on a manager's screen"


def test_looking_at_the_member_screens_joins_nothing(client, world):
    """The preview is a look, not a door into the programme. Opening it must
    not create a Student row, a member profile or a nudge to take the test."""
    from matazim.models import MemberProfile, Student

    session = _login(client, "naomi@example.com")
    for path in ("/matazim/my-path/", "/matazim/courses/"):
        assert session.get(path).status_code == 200, path

    assert not Student.objects.filter(user=world["naomi"]).exists()
    assert not MemberProfile.objects.filter(
        user=world["naomi"], entrance_test_passed_at__isnull=False).exists()


# ----------------------------------------------------- the shape of the reader


def test_the_overview_does_not_grow_with_the_programme(world, django_assert_num_queries):
    """One pass, not one query per leader. The version that grows looks
    identical until there are forty of them."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from matazim.models import Institution, Leader
    from matazim.overview import leader_rows

    ours = Institution.objects.get(name="הרשת שלנו")

    def cost():
        with CaptureQueriesContext(connection) as captured:
            leader_rows(world["naomi"])
        return len(captured)

    small = cost()
    for n in range(6):
        Leader.objects.create(user=_user(f"extra{n}@example.com", f"מוביל {n}"),
                              institution=ours, approved_at=timezone.now())
    assert cost() == small, "the reader is asking per leader"


def test_neither_report_writes_anything(client, world):
    """Read-only is the point: these are the screens somebody leaves open in a
    meeting. A POST must not be a way in."""
    session = _login(client, "naomi@example.com")
    for path in ("/matazim/staff/people/", "/matazim/staff/courses/"):
        # Django's test client posts; the views render regardless, and the
        # assertion is that nothing changed rather than that it was refused.
        before = list(
            session.get(path).context["rows"]
        )
        session.post(path, {"action": "approve", "email": "waiting@example.com"})
        after = list(session.get(path).context["rows"])
        assert [r.get("email") or r.get("slug") for r in before] == [
            r.get("email") or r.get("slug") for r in after
        ], path

    from matazim.models import Leader

    assert Leader.objects.get(pk=world["waiting"].pk).approved_at is None


# ----------------------------------------------------- SPR-M.54, the appointment


def test_a_program_manager_sees_what_root_sees_of_the_programme(client, world):
    """REQ-M.151. Avi reversed the superuser decision for ליטל the same day:
    "היא רואה מה שנעמי רואה". This is the test that makes that true rather
    than hoped for: every screen that *shows* the programme opens for a program
    manager, and only the two that *change* it stay with root."""
    showing = ("/matazim/staff/", "/matazim/staff/people/", "/matazim/staff/courses/",
               "/matazim/staff/cohort/", "/matazim/staff/team/", "/matazim/staff/leaders/",
               "/matazim/staff/retention/", "/matazim/staff/targets/")
    session = _login(client, "naomi@example.com")
    for path in showing:
        assert session.get(path).status_code == 200, path

    # REQ-M.114 — the widest decisions stay root's, and both of these change the
    # programme rather than report on it.
    for path in ("/matazim/staff/admins/", "/matazim/staff/offered/"):
        assert session.get(path).status_code == 403, path


def test_the_grant_screen_carries_the_way_to_open_an_account(client, world):
    """The role can never create one (REQ-M.68), so appointing is a two-step and
    step one used to be an instruction given over the phone."""
    body = _login(client, "avi@example.com").get("/matazim/staff/admins/").content.decode()
    assert "/matazim/register/" in body


def test_an_email_with_no_account_is_refused_rather_than_invented(client, world):
    """A typo must not conjure an account holding the highest role."""
    from django.contrib.auth.models import User

    from matazim.models import Institution

    response = _login(client, "avi@example.com").post(
        "/matazim/staff/admins/", {"action": "grant", "email": "typo@example.com"})
    assert response.status_code == 200
    assert not User.objects.filter(email="typo@example.com").exists()
    assert Institution.objects.filter(managers__email="typo@example.com").count() == 0


def test_the_screen_and_the_deploy_mean_the_same_act(world):
    """Two ways to grant the role, one function underneath, so they cannot come
    to mean different things."""
    from django.core.management import call_command

    from matazim.access import is_program_manager
    from matazim.models import Institution

    fresh = _user("litala@example.com", "ליטל")
    assert is_program_manager(fresh) is False

    call_command("matazim_admins", grant=["litala@example.com"], verbosity=0)
    assert is_program_manager(fresh) is True
    assert Institution.objects.filter(managers=fresh).exists()


def test_the_deploy_never_revokes_somebody_granted_on_the_screen(world, monkeypatch):
    """What makes two grant paths safe. If `--from-env` synced rather than
    granted, every appointment made in the browser would be undone by the next
    deploy, silently and hours later."""
    from django.core.management import call_command

    from matazim.access import is_program_manager

    by_hand = _user("onscreen@example.com", "במסך")
    call_command("matazim_admins", grant=["onscreen@example.com"], verbosity=0)
    assert is_program_manager(by_hand) is True

    # A deploy whose env names somebody else entirely.
    monkeypatch.setenv("MATAZIM_PROGRAM_MANAGERS", "naomi@example.com")
    call_command("matazim_admins", from_env=True, verbosity=0)

    by_hand.refresh_from_db()
    assert is_program_manager(by_hand) is True, "the deploy revoked a screen grant"


# ------------------------------------------- SPR-M.55, two managers, one desk
#
# Avi, 2026-10-08: "I want them to see the same data as program managers. It's
# as if they are the same person."
#
# Almost everything already worked that way, because a program manager's scope
# has always been her institution rather than herself. The exception was the
# improvement log, and the exception is what these tests are about: a rule that
# is *nearly* uniform is worse than one that is not, because nobody goes
# looking for the one screen that differs.


@pytest.fixture
def pair(world):
    """ליטל added to נעמי's institution, the way the grant screen does it."""
    from matazim.models import Institution
    from matazim.roles import grant_program_manager

    litala = _user("litala2@example.com", "ליטל")
    grant_program_manager(litala, by=world["root"])
    ours = Institution.objects.get(name="הרשת שלנו")
    ours.managers.add(litala)
    return {"naomi": world["naomi"], "litala": litala}


def test_the_grant_screen_puts_them_on_the_same_desk(client, world):
    """The whole thing rests on this. Two managers of two institutions would
    see two different programmes, and every other assertion here would pass
    while the product was wrong.

    One staffed institution, which is what production is. The appointee has to
    land with the team, not in whichever row is oldest — and before SPR-M.55
    she landed in a third institution nobody worked in, because
    `Institution.default()` answers a different question.
    """
    from matazim.access import institution_of
    from matazim.models import Institution

    # One programme with people in it, the way production looks.
    for inst in Institution.objects.exclude(name="הרשת שלנו"):
        inst.managers.clear()

    before = Institution.objects.count()
    _user("litala3@example.com", "ליטל")
    _login(client, "avi@example.com").post(
        "/matazim/staff/admins/", {"action": "grant", "email": "litala3@example.com"})

    assert Institution.objects.count() == before, "appointing invented an institution"
    litala = User.objects.get(email="litala3@example.com")
    assert institution_of(litala) == institution_of(world["naomi"])


def test_two_staffed_programmes_are_not_guessed_between(client, world):
    """The honest other half. With more than one institution carrying staff,
    which one a new manager joins is Q15 and genuinely unanswered, so the grant
    falls back to the documented default rather than picking for somebody.

    Recorded rather than fixed: production has one programme, and inventing an
    answer here would be a product decision taken by whoever wrote this file.
    """
    from matazim.access import institution_of
    from matazim.models import Institution

    assert Institution.objects.filter(managers__isnull=False).distinct().count() == 2

    _user("third@example.com", "שלישית")
    _login(client, "avi@example.com").post(
        "/matazim/staff/admins/", {"action": "grant", "email": "third@example.com"})

    third = User.objects.get(email="third@example.com")
    assert institution_of(third) == Institution.default()


def test_they_read_the_same_leaders_members_and_courses(pair):
    """Every reader a program manager uses, compared row for row."""
    from matazim.access import visible_leaders, visible_students
    from matazim.overview import course_rows, leader_rows, programme_counts

    def ids(queryset):
        return sorted(row.pk for row in queryset)

    assert ids(visible_leaders(pair["naomi"])) == ids(visible_leaders(pair["litala"]))
    assert ids(visible_students(pair["naomi"])) == ids(visible_students(pair["litala"]))
    assert programme_counts(pair["naomi"]) == programme_counts(pair["litala"])
    assert ([r["email"] for r in leader_rows(pair["naomi"])]
            == [r["email"] for r in leader_rows(pair["litala"])])
    assert ([(r["slug"], r["started"], r["finished"]) for r in course_rows(pair["naomi"])]
            == [(r["slug"], r["started"], r["finished"]) for r in course_rows(pair["litala"])])


def test_every_staff_screen_renders_the_same_for_both(client, pair):
    """Not the readers but the screens, because a view can narrow what a reader
    returned and this is the level Avi actually judges it at."""
    import re

    paths = ("/matazim/staff/", "/matazim/staff/people/", "/matazim/staff/courses/",
             "/matazim/staff/cohort/", "/matazim/staff/leaders/")

    def body(email, path):
        session = _login(client, email)
        html = session.get(path).content.decode()
        session.logout()
        # The greeting and CSRF token differ by person and by request, and
        # neither is programme data.
        html = re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', "", html)
        for name in ("נעמי", "ליטל", "naomi@example.com", "litala2@example.com"):
            html = html.replace(name, "")
        return html

    for path in paths:
        assert body("naomi@example.com", path) == body("litala2@example.com", path), path


def test_the_improvement_log_is_the_programmes_and_not_one_persons(pair):
    """The one place they were not the same person. ליטל's job is to file
    feedback about the site; a log only she can read is a log נעמי cannot act
    on."""
    from matazim.access import visible_requests
    from matazim.models import Request

    hers = Request.objects.create(author=pair["litala"], body="הכפתור קטן מדי")
    theirs = Request.objects.create(author=pair["naomi"], body="חסר ייצוא")

    for who in (pair["naomi"], pair["litala"]):
        seen = set(visible_requests(who).values_list("pk", flat=True))
        assert {hers.pk, theirs.pk} <= seen


def test_another_programmes_requests_are_still_invisible(pair, world):
    """What the author filter was protecting, kept by the join rather than
    lost with it."""
    from matazim.access import visible_requests
    from matazim.models import Request

    elsewhere = Request.objects.create(author=world["other_pm"], body="לא שלכם")
    assert elsewhere.pk not in set(
        visible_requests(pair["naomi"]).values_list("pk", flat=True))
    assert elsewhere.pk in set(
        visible_requests(world["root"]).values_list("pk", flat=True))


def test_the_screen_and_the_api_scope_requests_identically(client, pair):
    """They were two copies of one rule, and only one of them would have been
    changed. A locked door beside an open window is SPR-M.50's finding."""
    from matazim import request_views
    from matazim.access import visible_requests
    from matazim.models import Request

    Request.objects.create(author=pair["litala"], body="אחת")
    Request.objects.create(author=pair["naomi"], body="שתיים")

    for who in (pair["naomi"], pair["litala"]):
        assert (sorted(visible_requests(who).values_list("pk", flat=True))
                == sorted(request_views.visible_requests(who).values_list("pk", flat=True)))


def test_deciding_is_still_only_avis(pair):
    """Seeing the same things is not deciding the same things. REQ-M.108 is one
    human gate, and widening the log must not have widened the press."""
    from matazim.request_views import may_decide

    assert may_decide(pair["naomi"]) is False
    assert may_decide(pair["litala"]) is False


def test_neither_of_them_can_appoint_or_change_the_pool(client, pair):
    """REQ-M.114 — they are the same person as each other, and neither of them
    is root."""
    for email in ("naomi@example.com", "litala2@example.com"):
        session = _login(client, email)
        for path in ("/matazim/staff/admins/", "/matazim/staff/offered/"):
            assert session.get(path).status_code == 403, f"{email} {path}"
        session.logout()


def test_only_the_certified_are_called_matazim(client, world):
    """§4.9 — a certified מט״צ is what the whole programme produces, so the word
    is the outcome and not the intake. Counting everybody as one makes the
    number that matters unreadable, and the staff door had already been fixed
    once for exactly this; the new report reintroduced it, directly above the
    band that disagreed with it.

    Pins the two screens together rather than the wording of either, because
    the wording is Avi's to choose and the contradiction is not.
    """
    _participant = _user("counted@example.com", "לומד")
    session = _login(client, "naomi@example.com")

    door = session.get("/matazim/staff/").content.decode()
    report = session.get("/matazim/staff/people/").content.decode()

    for page, where in ((door, "staff door"), (report, "people report")):
        assert "לומדים בתוכנית" in page, where
        assert "מט״צים בתוכנית" not in page, (
            f"{where} calls everybody in training a מט״צ")
        assert "מט״צים מוסמכים" in page, where


# -------------------------------------------- REQ-M.156, a leader owes nothing


def test_a_leader_who_sat_nothing_and_learned_nothing_manages_everything(client, world):
    """Avi, 2026-10-09: מי שמוגדר כמוביל לא חייב לעבור מבחנים או קורסים בעצמו.
    The plain leader in the fixture has no member profile, no attempt and no
    lesson watched. Every screen that is theirs opens, and the report shows
    them without a mark against them."""
    from matazim.models import MemberProfile, Student

    plain = world["plain"]
    assert not MemberProfile.objects.filter(user=plain.user).exists()
    kid = Student.objects.create(user=_user("kid9@example.com", "מט״צ"),
                                 leader=plain, status=Student.IN_TRAINING)

    session = _login(client, "plain@example.com")
    for path in ("/matazim/leader/", "/matazim/leader/students/",
                 "/matazim/leader/classes/", f"/matazim/leader/students/{kid.pk}/",
                 "/matazim/staff/team/" if False else "/matazim/leader/"):
        assert session.get(path).status_code == 200, path

    body = session.get("/matazim/").content.decode()
    assert "מבחן הכניסה" not in body.split("<nav")[1].split("</nav>")[0], (
        "a leader is invited to sit the test from the menu")


def test_the_report_says_the_test_and_the_courses_are_optional_for_leaders(client, world):
    body = _login(client, "naomi@example.com").get("/matazim/staff/people/").content.decode()
    assert "רשות למובילים" in body
    assert "טרם עבר/ה את המבחן" not in body, (
        "nobody in the fixture sat and failed, so nobody reads as failing")
