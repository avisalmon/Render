"""SPR-M.56 — Litala's three screens, as drawn.

Avi, 2026-10-08: "עד כמה שניתן לדבוק בעיצוב שלה. ותעבור על האתר ותשפר אותו
להיות מהמם, אינטואיטיבי ודבק ברצון הלקוחה."

Her three prototype screens (docs/matazim/prototype/) are all the member's
site: דף הבית, ההדרכות, המסלול שלי. This sprint rebuilds the two member screens
to her drawings and puts the home page back in her order, with one rule over
all of it: nothing is drawn to fill a slot. Her picture has fourteen
milestones with dates because it is a picture; a member on day one has one,
and the number of nodes on the screen is the number of true things.

**The tests that matter are the ones about truth, not layout.** A milestone
carries a date only when something happened; a status card appears only when
there is something behind it; the ring on a card and the ring in the sidebar
are counted off the same rows. Layout is the screen contract's job and both
screens were already in its catalogue.

Traces: REQ-M.5a, REQ-M.5f, REQ-M.12, REQ-M.12b, REQ-M.59, REQ-M.76, §4.9, RULE-3.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

pytestmark = pytest.mark.sprm56

PASSWORD = "sprm56-pass-3391"


def _course(slug, title, lessons=3, thumbnail=""):
    from app.models import Course, Video

    course = Course.objects.create(slug=slug, title=title, is_published=True,
                                   thumbnail=thumbnail, description=f"על {title}")
    for n in range(1, lessons + 1):
        Video.objects.create(course=course, title=f"שיעור {n}", lesson_order=n,
                             bunny_video_id=f"{slug}-{n}")
    return course


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _watch(user, course, upto):
    """Finish the first `upto` lessons of a course, the way babook records it."""
    from app.models import UserVideoProgress, Video

    for video in Video.objects.filter(course=course, lesson_order__lte=upto):
        UserVideoProgress.objects.update_or_create(
            user=user, video=video,
            defaults={"completed_at": timezone.now(), "quiz_passed": True, "percent_watched": 100.0},
        )


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, MemberProfile, Student

    scratch = _course("scratch", "סקראץ׳ 1", lessons=8, thumbnail="matazim/img/hero.webp")
    advanced = _course("scratch-advanced", "סקראץ׳ 2", lessons=4)

    inst = Institution.objects.create(name="רשת")
    leader = Leader.objects.create(user=_user("l@example.com", "מוביל"), institution=inst,
                                   approved_at=timezone.now())

    # Somebody in the middle: passed the test, has a leader, half way through.
    mid = _user("mid@example.com", "מאיה")
    MemberProfile.objects.create(user=mid, entrance_test_passed_at=timezone.now(),
                                 welcome_accepted_at=timezone.now())
    Student.objects.create(user=mid, leader=leader, status=Student.IN_TRAINING)
    _watch(mid, scratch, 3)

    # Somebody on day one: signed in, nothing else.
    fresh = _user("fresh@example.com", "נועה")
    MemberProfile.objects.create(user=fresh, welcome_accepted_at=timezone.now())

    return {"scratch": scratch, "advanced": advanced, "leader": leader,
            "mid": mid, "fresh": fresh}


def _login(client, email):
    assert client.login(username=email, password=PASSWORD)
    return client


# ------------------------------------------------------ המסלול שלי, screen 3


def test_a_milestone_carries_a_date_only_when_something_happened(world):
    """The rule over the whole screen. Her drawing dates everything; a member
    on day one has done nothing and must not be shown a date for it."""
    from matazim.certification import eligibility_for_user
    from matazim.content import REQUIRED_COURSE_SLUGS
    from matazim.progress import JustAUser, cohort_progress
    from matazim.track import DONE, TODO, milestones

    user = world["fresh"]
    per_course = cohort_progress([JustAUser(user.id)], REQUIRED_COURSE_SLUGS).get(user.id, {})
    nodes = milestones(user, user.matazim_profile, None, eligibility_for_user(user), per_course)

    assert nodes, "a member on day one still has a path in front of them"
    assert all(n["when"] is None for n in nodes)
    assert all(n["status"] != DONE for n in nodes)
    assert nodes[0]["key"] == "test" and nodes[0]["status"] == TODO
    assert nodes[0]["is_current"] is True


def test_the_path_reads_the_same_tables_the_leader_reads(world):
    """RULE-3 — three lessons watched is a node in progress at the percentage
    the roster shows, not a copy kept here."""
    from matazim.certification import eligibility
    from matazim.content import REQUIRED_COURSE_SLUGS
    from matazim.models import Student
    from matazim.progress import cohort_progress
    from matazim.track import DOING, DONE, milestones

    user = world["mid"]
    student = Student.objects.get(user=user)
    per_course = cohort_progress([student], REQUIRED_COURSE_SLUGS).get(user.id, {})
    nodes = {n["key"]: n for n in milestones(user, user.matazim_profile, student,
                                            eligibility(student), per_course)}

    assert nodes["test"]["status"] == DONE and nodes["test"]["when"] is not None
    assert nodes["join"]["status"] == DONE
    assert nodes["course-scratch"]["status"] == DOING
    assert nodes["course-scratch"]["pct"] == per_course["scratch"]["pct"] == 37
    assert nodes["course-scratch"]["is_current"] is True
    assert nodes["cert-scratch"]["status"] != DONE


def test_the_current_node_is_the_first_unfinished_one_and_only_one(world):
    from matazim.certification import eligibility
    from matazim.content import REQUIRED_COURSE_SLUGS
    from matazim.models import Student
    from matazim.progress import cohort_progress
    from matazim.track import milestones

    user = world["mid"]
    student = Student.objects.get(user=user)
    per_course = cohort_progress([student], REQUIRED_COURSE_SLUGS).get(user.id, {})
    nodes = milestones(user, user.matazim_profile, student, eligibility(student), per_course)
    assert sum(1 for n in nodes if n["is_current"]) == 1


def test_a_status_card_exists_only_when_there_is_something_behind_it(world):
    """Her row has five cards because it is a drawing. Three cards saying
    "nothing" teach people to stop reading the row."""
    from matazim.track import status_cards

    cards = status_cards(summary={"pct": 0}, next_step={"text": "x", "where": None},
                         student=None, work_waiting=False, work_answered=False,
                         next_events=[], unread=0)
    assert [c["key"] for c in cards] == ["progress", "next"]

    class E:
        title = "יום שיא"
        starts_at = timezone.now()

    cards = status_cards(summary={"pct": 62}, next_step={"text": "x", "where": None},
                         student=None, work_waiting=False, work_answered=True,
                         next_events=[E()], unread=0)
    assert [c["key"] for c in cards] == ["progress", "next", "event", "feedback"]
    assert cards[0]["figure"] == "62%"


def test_the_lesson_checklist_is_a_window_around_the_current_lesson(world):
    """Her panel shows five. A nineteen-lesson list is the course page."""
    from matazim.content import REQUIRED_COURSE_SLUGS
    from matazim.progress import JustAUser, cohort_progress
    from matazim.track import current_course

    user = world["mid"]
    per_course = cohort_progress([JustAUser(user.id)], REQUIRED_COURSE_SLUGS).get(user.id, {})
    now = current_course(user, per_course)

    assert now["slug"] == "scratch"
    assert now["resume_order"] == 4
    assert len(now["lessons"]) == 6
    assert now["hidden"] == 2
    assert sum(1 for row in now["lessons"] if row["is_current"]) == 1
    # Two finished lessons for context, then the current one, then what comes.
    assert [row["order"] for row in now["lessons"]] == [2, 3, 4, 5, 6, 7]
    assert [row["done"] for row in now["lessons"]][:3] == [True, True, False]
    assert now["lessons"][2]["is_current"] is True


def test_the_track_page_renders_her_three_bands(client, world):
    body = _login(client, "mid@example.com").get("/matazim/my-path/").content.decode()
    assert "התקדמות כללית" in body
    assert "המשימה הבאה" in body
    assert "המסלול שלי בתכנית" in body
    assert "המשימה הנוכחית" in body
    assert "ההדרכות שלי עכשיו" in body
    assert "תוצרים והגשות" in body
    assert "אירועים קרובים" in body
    # Status is a word plus a colour: every legend entry is text.
    for word in ("הושלם", "בתהליך", "דורש תיקון", "טרם התחיל"):
        assert word in body, word


def test_the_track_page_holds_for_somebody_who_has_done_nothing(client, world):
    response = _login(client, "fresh@example.com").get("/matazim/my-path/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "המסלול שלי בתכנית" in body
    assert "ההדרכות ייפתחו כאן" not in body, "there is a required track, so there is a current course"


# ------------------------------------------------------- ההדרכות, screen 2


def test_the_sidebar_ring_is_counted_off_the_cards_on_the_page(client, world):
    """One ring for everything, broken into finished / in progress / not
    started, and it cannot disagree with the cards because it is counted from
    them."""
    response = _login(client, "mid@example.com").get("/matazim/courses/")
    overview = response.context["overview"]
    cards = response.context["cards"] + response.context["started"] + response.context["offered"]

    assert overview["total"] == len(cards) == 2
    assert overview["done"] == 0
    assert overview["doing"] == 1
    assert overview["todo"] == 1
    assert overview["pct"] == int((37 + 0) / 2)


def test_each_card_carries_a_cover_a_line_and_the_word_for_its_state(client, world):
    response = _login(client, "mid@example.com").get("/matazim/courses/")
    body = response.content.decode()
    by_slug = {c["slug"]: c for c in response.context["cards"]}

    assert by_slug["scratch"]["thumbnail"] == "matazim/img/hero.webp"
    assert by_slug["scratch"]["about"].startswith("על ")
    assert by_slug["scratch"]["word"] == "באמצע"
    assert by_slug["scratch"]["action"] == "להמשיך"
    assert by_slug["scratch-advanced"]["action"] == "להתחיל"
    assert "matazim/img/hero.webp" in body
    assert 'class="mz-ring mz-ring-sm"' in body


def test_the_stage_panel_names_the_stage_and_what_opens_the_next(client, world):
    response = _login(client, "mid@example.com").get("/matazim/courses/")
    stage = response.context["stage"]
    assert stage["title"] == "לומדים"
    assert "2 הדרכות" in stage["hint"]


def test_the_chips_cover_exactly_the_groups_on_the_page(client, world):
    """A chip for a group with nothing in it is a filter over an empty list."""
    body = _login(client, "mid@example.com").get("/matazim/courses/").content.decode()
    assert 'data-chip="all"' in body
    assert 'data-chip="required"' in body
    assert 'data-chip="started"' not in body
    assert 'data-chip="offered"' not in body


def test_a_visitor_still_gets_the_visitor_page(client, world):
    body = client.get("/matazim/courses/").content.decode()
    assert "מה לומדים בתוכנית" in body
    assert "mz-chip" not in body


# ------------------------------------------------------- דף הבית, screen 1


def test_the_home_reads_in_her_order(client, world):
    """Hero, איך זה עובד, the band, then everything else. The partners sat
    between the hero and the four stages, where she put the programme."""
    body = client.get("/matazim/").content.decode()
    assert body.index("mzHow") < body.index("mzPartners")
    assert body.index("mzHow") < body.index('class="mz-band')


def test_the_band_is_her_gradient_with_a_pictogram_per_figure(client, world):
    from matazim.public import counters

    rows = counters()
    assert rows, "the fixture has a leader, so there is a figure"
    assert all(row.get("icon") for row in rows)

    body = client.get("/matazim/").content.decode()
    assert "mz-band-gradient" in body


def test_the_band_uses_the_earned_word(world):
    """§4.9 — לומדים for everybody in the programme, מוסמכים only for those who
    finished; her own band says תלמידים."""
    from matazim.models import Student
    from matazim.public import counters

    Student.objects.filter(user=world["mid"]).update(status=Student.CERTIFIED)
    labels = {row["label"] for row in counters()}
    assert not any(label.startswith("מט״צים בתוכנית") for label in labels)
    assert "מט״צ מוסמך/ת" in labels


def test_nothing_on_any_of_the_three_screens_is_invented(client, world):
    """The numbers her drawing shows (1,250 pupils, 28 schools) must never
    appear unless they are counted. The band drops zeros; the showcase is
    absent until somebody consents; the path has as many nodes as true steps."""
    body = client.get("/matazim/").content.decode()
    assert "1,250" not in body and "4,300" not in body
    assert "תוצרים נבחרים" not in body

    member = _login(client, "fresh@example.com").get("/matazim/my-path/").content.decode()
    # The test, joining, two courses, two certificates, and certification
    # itself. No first submission (nobody to hand it to yet) and no first
    # teaching session (not certified), because neither is a step they have.
    assert member.count('class="mz-path-node') == 7
