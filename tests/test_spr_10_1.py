"""Chapter 10 / SPR-10.1 - the מט״צים program space: shell, gate, track, record.

The tests that matter here are the ones that pin down the chapter's laws, not
the ones that check a page returns 200:

  * the member gate (REQ-10.1) - public pages public, personal area not
  * the record is *derived* (DEC-71 / REQ-10.13) - it moves when babook
    progress moves, and the program space writes no learning state
  * retroactive credit (REQ-10.12) - activity from before certification counts,
    with no backfill step
  * certification is a **status, not a permission** (DEC-69) - it must not
    change what anyone can do on babook
"""
import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from app.matazim_models import Program, ProgramMembership, School
from app.models import Course, Enrollment, UserVideoProgress, Video

pytestmark = pytest.mark.django_db


def _program():
    return Program.objects.create(
        slug="matazim", name="מט״צים", tagline="מובילים טכנולוגיים צעירים")


def _user(username="kid"):
    return User.objects.create_user(username, password="pass12345",
                                    email=f"{username}@ex.com")


def _course(slug="tinkercad", lessons=4):
    c = Course.objects.create(slug=slug, title=f"course {slug}",
                              domain="matazim", is_published=True)
    for i in range(1, lessons + 1):
        Video.objects.create(course=c, title=f"lesson {i}", lesson_order=i)
    return c


def _watch(user, course, n):
    """Mark the first n lessons watched - i.e. real babook activity."""
    for v in Video.objects.filter(course=course).order_by("lesson_order")[:n]:
        UserVideoProgress.objects.update_or_create(
            user=user, video=v,
            defaults={"percent_watched": 100.0, "quiz_passed": True,
                      "completed_at": timezone.now()})


# --- REQ-10.3: the public pages are public -------------------------------

@pytest.mark.parametrize("path", ["/matazim/", "/matazim/track/", "/matazim/schools/"])
def test_public_pages_open_to_anonymous(client, path):
    _program()
    assert client.get(path).status_code == 200


def test_public_pages_show_no_member_data(client):
    program = _program()
    school = School.objects.create(program=program, name="תיכון בדיקה", city="חיפה")
    ProgramMembership.objects.create(user=_user("secret_kid"), program=program, school=school)
    body = client.get("/matazim/schools/").content.decode()
    assert "תיכון בדיקה" in body
    assert "secret_kid" not in body


# --- REQ-10.1: the member gate -------------------------------------------

def test_personal_area_sends_anonymous_to_the_join_wall(client):
    _program()
    r = client.get("/matazim/me/")
    assert r.status_code == 302 and "/join/" in r["Location"]
    assert "next=/matazim/me/" in r["Location"]


def test_personal_area_closed_to_a_logged_in_non_member(client):
    _program()
    client.force_login(_user("outsider"))
    assert client.get("/matazim/me/").status_code == 404


def test_personal_area_open_to_a_member(client):
    program = _program()
    user = _user("member")
    ProgramMembership.objects.create(user=user, program=program)
    client.force_login(user)
    assert client.get("/matazim/me/").status_code == 200


# --- REQ-10.4: the five-stage track is the status field ------------------

def test_track_marks_done_current_and_ahead():
    program = _program()
    m = ProgramMembership.objects.create(
        user=_user("mid"), program=program, status=ProgramMembership.PROJECT_SUBMITTED)
    steps = m.track_steps()
    assert [s["label"] for s in steps] == ["מתמיינים", "לומדים", "יוצרים", "מדריכים"]
    assert [s["done"] for s in steps] == [True, True, False, False]
    assert [s["current"] for s in steps] == [False, False, True, False]


def test_terminal_states_are_not_positions_on_the_track():
    program = _program()
    for status in (ProgramMembership.ALUMNUS, ProgramMembership.REVOKED,
                   ProgramMembership.REJECTED):
        m = ProgramMembership(user=_user(f"u_{status}"), program=program, status=status)
        assert m.stage_index == -1
        assert not any(s["current"] for s in m.track_steps())


def test_only_certified_counts_as_a_current_matatz():
    program = _program()
    certified = ProgramMembership(user=_user("a"), program=program,
                                  status=ProgramMembership.CERTIFIED)
    alumnus = ProgramMembership(user=_user("b"), program=program,
                                status=ProgramMembership.ALUMNUS)
    revoked = ProgramMembership(user=_user("c"), program=program,
                                status=ProgramMembership.REVOKED)
    assert certified.is_certified
    assert not alumnus.is_certified and not revoked.is_certified


# --- DEC-71 / REQ-10.13: the record is derived, never stored -------------

def test_record_is_computed_from_babook_progress():
    from app.matazim_views import training_record

    program = _program()
    user = _user("learner")
    course = _course(lessons=4)

    before = training_record(user, program)
    assert before["started"] == 0 and before["completed"] == 0

    _watch(user, course, 2)
    mid = training_record(user, program)
    assert mid["started"] == 1 and mid["completed"] == 0
    assert mid["rows"][0]["p"]["done"] == 2

    _watch(user, course, 4)
    Enrollment.objects.create(user=user, course=course, completed_at=timezone.now())
    after = training_record(user, program)
    assert after["completed"] == 1

    # Nothing about that learning was written into the program space.
    assert ProgramMembership.objects.filter(user=user).count() == 0


def test_credit_is_retroactive_with_no_backfill():
    """REQ-10.12: learning done *before* certification counts the moment the
    membership is created, because nothing was ever copied."""
    from app.matazim_views import training_record

    program = _program()
    user = _user("early")
    course = _course(lessons=4)
    _watch(user, course, 4)
    Enrollment.objects.create(user=user, course=course, completed_at=timezone.now())

    # Certified only now, long after the learning happened.
    ProgramMembership.objects.create(
        user=user, program=program, status=ProgramMembership.CERTIFIED,
        certified_at=timezone.now())

    assert training_record(user, program)["completed"] == 1


def test_personal_area_renders_the_derived_numbers(client):
    program = _program()
    user = _user("shown")
    course = _course(lessons=4)
    _watch(user, course, 4)
    Enrollment.objects.create(user=user, course=course, completed_at=timezone.now())
    ProgramMembership.objects.create(user=user, program=program,
                                     status=ProgramMembership.IN_TRAINING)
    client.force_login(user)
    body = client.get("/matazim/me/").content.decode()
    assert course.title in body
    assert "4 / 4" in body


# --- DEC-69: certification is a status, not a permission -----------------

def test_certification_grants_no_babook_permission():
    """The whole cost model of Chapter 10 rests on this: certifying somebody
    must not touch what they can do on babook."""
    program = _program()
    user = _user("newly_certified")
    assert user.profile.is_teacher is False

    m = ProgramMembership.objects.create(user=user, program=program)
    m.status = ProgramMembership.CERTIFIED
    m.certified_at = timezone.now()
    m.save()

    user.profile.refresh_from_db()
    assert user.profile.is_teacher is False, "certification must not grant teaching rights"
    assert user.is_staff is False and user.is_superuser is False


def test_only_program_staff_is_recognised_as_staff():
    """REQ-10.7 - two authorities and only two: Program.staff and School.leaders.
    A cohort member is neither."""
    from app.matazim_views import is_program_staff

    program = _program()
    school = School.objects.create(program=program, name="s1")
    member, leader, staff = _user("m"), _user("l"), _user("s")
    ProgramMembership.objects.create(user=member, program=program, school=school)
    school.leaders.add(leader)
    program.staff.add(staff)

    assert not is_program_staff(member, program)
    assert not is_program_staff(leader, program), "a leader is not an admin"
    assert is_program_staff(staff, program)


# --- REQ-10.1: the nav entry ---------------------------------------------
# Superseded: the entry used to be members-only. Avi asked on 2026-08-08 for it
# in the main menu and the drawer for everyone, since the program space is
# public. See test_matazim_is_in_the_site_menu_for_everyone below.

def test_nav_entry_is_highlighted_for_members(client):
    program = _program()
    outsider = _user("no_badge")
    client.force_login(outsider)
    assert "nav-link-active" not in client.get("/").content.decode()

    ProgramMembership.objects.create(user=outsider, program=program)
    body = client.get("/").content.decode()
    assert "/matazim/" in body and "nav-link-active" in body


# ---------------------------------------------------------------------------
# Schools, leaders, and the two consoles (Avi, 2026-08-08)
#
# The load-bearing test here is the cross-school one. Leaking one school's
# teenagers to a different school's teacher is the worst defect this system can
# have, and it is a defect of omission, so it is asserted from both directions:
# the roster a leader should see, and the roster they must not reach.
# ---------------------------------------------------------------------------

def _school(program, name, city=""):
    return School.objects.create(program=program, name=name, city=city)


def _member(program, school, username, status=ProgramMembership.IN_TRAINING):
    return ProgramMembership.objects.create(
        user=_user(username), program=program, school=school, status=status,
        school_join_status=ProgramMembership.SCHOOL_CONFIRMED)


def test_only_staff_may_open_a_school(client):
    program = _program()
    leader = _user("teacher")
    _school(program, "existing").leaders.add(leader)

    client.force_login(leader)
    assert client.post("/matazim/school/new/", {"name": "sneaky"}).status_code == 404
    assert not School.objects.filter(name="sneaky").exists()

    staff = _user("admin")
    program.staff.add(staff)
    client.force_login(staff)
    client.post("/matazim/school/new/", {"name": "properly opened", "city": "חיפה"})
    assert School.objects.filter(program=program, name="properly opened").exists()


def test_only_staff_may_assign_a_leader(client):
    program = _program()
    school = _school(program, "school a")
    leader, teacher2 = _user("leader1"), _user("teacher2")
    school.leaders.add(leader)

    client.force_login(leader)
    client.post(f"/matazim/school/{school.pk}/leader/", {"identifier": "teacher2"})
    assert not school.leaders.filter(pk=teacher2.pk).exists(), "a leader cannot recruit peers"

    staff = _user("admin2")
    program.staff.add(staff)
    client.force_login(staff)
    client.post(f"/matazim/school/{school.pk}/leader/", {"identifier": "teacher2"})
    assert school.leaders.filter(pk=teacher2.pk).exists()


def test_no_template_comment_leaks_into_any_page(client):
    """Django's {# #} is single-line only: a multi-line one renders as page text
    and can swallow the markup after it. That has bitten this chapter twice, so
    every מט״צים surface is checked for the tell-tale delimiters."""
    program = _program()
    school = _school(program, "s")
    staff = _user("leak_admin")
    program.staff.add(staff)
    m = _member(program, school, "someone_here")
    client.force_login(staff)

    for path in ["/matazim/", "/matazim/track/", "/matazim/schools/",
                 "/matazim/admin/", f"/matazim/school/{school.pk}/"]:
        body = client.get(path).content.decode()
        assert "{#" not in body and "#}" not in body, f"template comment leaked on {path}"
        assert "{% comment" not in body and "REQ-10" not in body, \
            f"template comment leaked on {path}"
    client.force_login(m.user)
    body = client.get("/matazim/me/").content.decode()
    assert "{#" not in body and "#}" not in body


# --- the user picker: find anyone, without the Django admin ---------------

def test_user_search_is_program_staff_only(client):
    program = _program()
    school = _school(program, "s")
    leader, member = _user("searching_leader"), _user("searching_member")
    school.leaders.add(leader)
    ProgramMembership.objects.create(user=member, program=program, school=school)

    assert client.get("/matazim/users/search/?q=sea").status_code in (302, 404)
    client.force_login(member)
    assert client.get("/matazim/users/search/?q=sea").status_code == 404
    client.force_login(leader)
    assert client.get("/matazim/users/search/?q=sea").status_code == 404, \
        "a school leader has no business browsing the whole user base"

    staff = _user("searching_admin")
    program.staff.add(staff)
    client.force_login(staff)
    assert client.get("/matazim/users/search/?q=sea").status_code == 200


def test_user_search_finds_by_name_username_and_email(client):
    program = _program()
    staff = _user("picker_admin")
    program.staff.add(staff)
    target = _user("ronit_levi")
    target.profile.display_name = "רונית לוי"
    target.profile.save()
    client.force_login(staff)

    for q in ("ronit", "רונית", target.email):
        names = [r["username"] for r in
                 client.get(f"/matazim/users/search/?q={q}").json()["results"]]
        assert target.username in names, f"search failed for {q!r}"


def test_user_search_never_returns_an_email(client):
    """It matches on email so a teacher can hand over their address, but it must
    not echo one back: otherwise the picker is an export of the site's mailing
    list to anyone with program-staff rights."""
    program = _program()
    staff = _user("privacy_admin")
    program.staff.add(staff)
    target = _user("someone")
    client.force_login(staff)

    payload = client.get(f"/matazim/users/search/?q={target.email}").content.decode()
    assert target.username in payload
    assert target.email not in payload
    assert "@" not in payload


def test_user_search_needs_two_characters(client):
    program = _program()
    staff = _user("short_admin")
    program.staff.add(staff)
    client.force_login(staff)
    assert client.get("/matazim/users/search/?q=a").json()["results"] == []


def test_staff_assign_a_leader_by_picking_them(client):
    """The picker posts a user_id; the typed field stays as the no-JS fallback."""
    program = _program()
    school = _school(program, "target school")
    staff = _user("assigning_admin")
    program.staff.add(staff)
    teacher = _user("picked_teacher")

    client.force_login(staff)
    client.post(f"/matazim/school/{school.pk}/leader/", {"user_id": teacher.pk})
    assert school.leaders.filter(pk=teacher.pk).exists()


def test_a_leader_sees_their_own_roster_and_never_anothers(client):
    """REQ-10.17, asserted from both sides on purpose.

    Anyone may *open* any school (Avi, 2026-08-08) — so the boundary is no
    longer the page, it is the people on it. A leader looking at somebody
    else's school gets the numbers and nothing else.
    """
    program = _program()
    mine, theirs = _school(program, "my school"), _school(program, "other school")
    leader = _user("my_leader")
    mine.leaders.add(leader)
    _member(program, mine, "my_kid")
    _member(program, theirs, "their_kid")

    client.force_login(leader)
    body = client.get(f"/matazim/school/{mine.pk}/").content.decode()
    assert "my_kid" in body
    assert "their_kid" not in body

    other = client.get(f"/matazim/school/{theirs.pk}/")
    assert other.status_code == 200, "any school is viewable"
    other_body = other.content.decode()
    assert "their_kid" not in other_body, "but never its people"
    assert "להמליץ להסמכה" not in other_body, "and never its controls"


def test_anyone_sees_a_schools_numbers_but_none_of_its_people(client):
    """The public school view: counts, no names, no statuses, no controls."""
    program = _program()
    school = _school(program, "open school")
    _member(program, school, "hidden_kid", ProgramMembership.CERTIFIED)
    _member(program, school, "other_hidden_kid")
    course = _course(lessons=2)
    outsider = _user("passer_by")

    for who in (None, outsider):
        if who:
            client.force_login(who)
        r = client.get(f"/matazim/school/{school.pk}/")
        assert r.status_code == 200
        body = r.content.decode()
        assert "hidden_kid" not in body and "other_hidden_kid" not in body
        assert "בקשות הצטרפות" not in body
        assert "להמליץ להסמכה" not in body
        assert "להקצות" not in body
        assert ">2<" in body, "the member count is shown"
    assert course  # the program has courses, so the stats query has something to sum


def test_public_school_view_grants_no_write_access(client):
    """Widening the *view* must not widen the actions."""
    program = _program()
    school = _school(program, "s")
    m = ProgramMembership.objects.create(
        user=_user("pending_kid"), program=program, school=school,
        school_join_status=ProgramMembership.SCHOOL_PENDING)
    outsider = _user("nosy")
    client.force_login(outsider)

    assert client.get(f"/matazim/school/{school.pk}/").status_code == 200
    assert client.post(f"/matazim/member/{m.pk}/confirm/").status_code == 404
    assert client.post(f"/matazim/member/{m.pk}/accept/").status_code == 404
    assert client.post(f"/matazim/member/{m.pk}/certify/",
                       {"note": "x"}).status_code == 404
    assert client.post(f"/matazim/school/{school.pk}/leader/",
                       {"user_id": outsider.pk}).status_code == 404
    m.refresh_from_db()
    assert m.school_join_status == ProgramMembership.SCHOOL_PENDING
    assert not school.leaders.exists()


def test_staff_can_act_as_the_teacher_in_any_school(client):
    """Litala runs every school when she needs to: same roster, same controls."""
    program = _program()
    school = _school(program, "someone elses school")
    School.objects.filter(pk=school.pk).first().leaders.add(_user("their_own_leader"))
    staff = _user("litala")
    program.staff.add(staff)
    pending = ProgramMembership.objects.create(
        user=_user("waiting_kid"), program=program, school=school,
        school_join_status=ProgramMembership.SCHOOL_PENDING)
    candidate = _member(program, school, "ready_kid", ProgramMembership.PROJECT_SUBMITTED)

    client.force_login(staff)
    body = client.get(f"/matazim/school/{school.pk}/").content.decode()
    assert "waiting_kid" in body and "ready_kid" in body

    client.post(f"/matazim/member/{pending.pk}/confirm/")
    pending.refresh_from_db()
    assert pending.school_join_status == ProgramMembership.SCHOOL_CONFIRMED

    client.post(f"/matazim/member/{candidate.pk}/certify/", {"note": "מוכן"})
    candidate.refresh_from_db()
    assert candidate.is_certified and candidate.certified_by == staff


def test_schools_list_links_into_each_school(client):
    program = _program()
    a, b = _school(program, "alpha"), _school(program, "beta")
    body = client.get("/matazim/schools/").content.decode()
    assert f"/matazim/school/{a.pk}/" in body
    assert f"/matazim/school/{b.pk}/" in body


def test_leaders_own_school_is_marked_in_the_list(client):
    program = _program()
    mine, theirs = _school(program, "mine"), _school(program, "theirs")
    leader = _user("marked_leader")
    mine.leaders.add(leader)
    client.force_login(leader)
    body = client.get("/matazim/schools/").content.decode()
    assert "בית הספר שלי" in body
    assert body.count("בית הספר שלי") == 1, "only her own school is marked"
    assert theirs  # the other school is listed too, just unmarked


# ---------------------------------------------------------------------------
# Applying (REQ-10.4): the school's invite link, and the open form
# ---------------------------------------------------------------------------

def test_the_invite_link_lands_a_logged_out_visitor_on_a_landing_page(client):
    """Not a bounce to the login form: the link gets pasted into WhatsApp and a
    kid who lands on a bare sign-in has no idea what they are signing into."""
    program = _program()
    school = _school(program, "תיכון ההזמנה", "חיפה")

    r = client.get(f"/matazim/join/{school.join_code}/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "תיכון ההזמנה" in body
    assert f"next=/matazim/join/{school.join_code}/" in body, \
        "the wall must return them to this exact page (REQ-5.4)"


def test_applying_through_the_link_attaches_the_school_with_no_extra_step(client):
    """DEC-84: the teacher handed out the link, so the school assignment is
    already their decision. What still needs granting is level 1."""
    program = _program()
    school = _school(program, "s")
    kid = _user("linked_kid")

    client.force_login(kid)
    client.post(f"/matazim/join/{school.join_code}/",
                {"grade": "ט'2", "motivation": "רוצה ללמד", "built_before": "רובוט"})

    m = ProgramMembership.objects.get(user=kid, program=program)
    assert m.school == school
    assert m.school_join_status == ProgramMembership.SCHOOL_CONFIRMED
    assert m.status == ProgramMembership.APPLIED, "still needs level 1"
    assert m.application.grade == "ט'2"
    assert m.application.via_invite_link is True


def test_applying_without_a_link_needs_the_leader_to_confirm(client):
    """DEC-77: they chose the school themselves, so its leader confirms."""
    program = _program()
    school = _school(program, "chosen school")
    kid = _user("self_selecting_kid")

    client.force_login(kid)
    client.post("/matazim/apply/", {"school_id": school.pk, "grade": "י'1"})

    m = ProgramMembership.objects.get(user=kid, program=program)
    assert m.school == school
    assert m.school_join_status == ProgramMembership.SCHOOL_PENDING
    assert m.application.via_invite_link is False


def test_an_existing_member_cannot_apply_twice(client):
    program = _program()
    school = _school(program, "s")
    kid = _user("already_in")
    ProgramMembership.objects.create(user=kid, program=program, school=school)

    client.force_login(kid)
    r = client.get(f"/matazim/join/{school.join_code}/")
    assert r.status_code == 302 and "/matazim/me/" in r["Location"]
    assert client.post("/matazim/apply/", {"school_id": school.pk}).status_code == 302
    assert ProgramMembership.objects.filter(user=kid, program=program).count() == 1


def test_a_closed_school_takes_no_applications(client):
    program = _program()
    school = _school(program, "closed")
    school.is_open = False
    school.save()
    kid = _user("late_kid")

    client.force_login(kid)
    client.post(f"/matazim/join/{school.join_code}/", {"grade": "ט'"})
    assert not ProgramMembership.objects.filter(user=kid).exists()


def test_rotating_the_code_kills_the_old_link(client):
    program = _program()
    school = _school(program, "s")
    old_code = school.join_code
    staff = _user("rotating_admin")
    program.staff.add(staff)

    client.force_login(staff)
    client.post(f"/matazim/school/{school.pk}/rotate/")
    school.refresh_from_db()
    assert school.join_code != old_code
    assert client.get(f"/matazim/join/{old_code}/").status_code == 404
    assert client.get(f"/matazim/join/{school.join_code}/").status_code in (200, 302)


def test_only_staff_may_rotate_the_code(client):
    program = _program()
    school = _school(program, "s")
    leader = _user("code_leader")
    school.leaders.add(leader)
    old_code = school.join_code

    client.force_login(leader)
    assert client.post(f"/matazim/school/{school.pk}/rotate/").status_code == 404
    school.refresh_from_db()
    assert school.join_code == old_code


def test_the_leader_sees_the_invite_link_and_an_outsider_does_not(client):
    program = _program()
    school = _school(program, "s")
    leader, outsider = _user("link_leader"), _user("link_outsider")
    school.leaders.add(leader)

    client.force_login(leader)
    body = client.get(f"/matazim/school/{school.pk}/").content.decode()
    assert school.join_code in body
    assert f"/matazim/school/{school.pk}/qr/" in body

    client.force_login(outsider)
    assert school.join_code not in client.get(f"/matazim/school/{school.pk}/").content.decode()
    assert client.get(f"/matazim/school/{school.pk}/qr/").status_code == 404


def test_every_school_gets_its_own_join_code():
    program = _program()
    codes = {_school(program, f"school {i}").join_code for i in range(5)}
    assert len(codes) == 5, "a shared default would make the link meaningless"


# --- REQ-10.20a: the help page -------------------------------------------

def test_help_page_is_public_and_covers_both_audiences(client):
    _program()
    r = client.get("/matazim/help/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "לתלמידים" in body
    assert "למובילי בתי הספר" in body


def test_matazim_is_in_the_site_menu_for_everyone(client):
    """Avi, 2026-08-08: the program is public, so the entry is not members-only."""
    _program()
    body = client.get("/").content.decode()
    assert "/matazim/" in body, "logged-out visitors get the entry too"

    client.force_login(_user("any_member"))
    assert "/matazim/" in client.get("/").content.decode()


def test_staff_reach_every_school(client):
    program = _program()
    a, b = _school(program, "a"), _school(program, "b")
    staff = _user("admin3")
    program.staff.add(staff)
    client.force_login(staff)
    assert client.get(f"/matazim/school/{a.pk}/").status_code == 200
    assert client.get(f"/matazim/school/{b.pk}/").status_code == 200


def test_admin_console_is_staff_only(client):
    program = _program()
    school = _school(program, "s")
    leader, member = _user("lead_only"), _user("kid_only")
    school.leaders.add(leader)
    ProgramMembership.objects.create(user=member, program=program, school=school)

    client.force_login(member)
    assert client.get("/matazim/admin/").status_code == 404
    client.force_login(leader)
    assert client.get("/matazim/admin/").status_code == 404, "a leader is not an admin"

    staff = _user("admin4")
    program.staff.add(staff)
    client.force_login(staff)
    assert client.get("/matazim/admin/").status_code == 200


# --- member picks, leader confirms (closes ACT-33) ------------------------

def test_leader_confirms_a_member_onto_the_roster(client):
    program = _program()
    school = _school(program, "s")
    leader = _user("confirming_leader")
    school.leaders.add(leader)
    m = ProgramMembership.objects.create(
        user=_user("applicant"), program=program, school=school,
        school_join_status=ProgramMembership.SCHOOL_PENDING)

    client.force_login(leader)
    body = client.get(f"/matazim/school/{school.pk}/").content.decode()
    assert "בקשות הצטרפות" in body

    client.post(f"/matazim/member/{m.pk}/confirm/")
    m.refresh_from_db()
    assert m.school_join_status == ProgramMembership.SCHOOL_CONFIRMED
    assert m.is_on_roster


def test_another_schools_leader_cannot_confirm_a_member(client):
    program = _program()
    mine, theirs = _school(program, "mine"), _school(program, "theirs")
    outsider = _user("outside_leader")
    theirs.leaders.add(outsider)
    m = ProgramMembership.objects.create(
        user=_user("not_yours"), program=program, school=mine,
        school_join_status=ProgramMembership.SCHOOL_PENDING)

    client.force_login(outsider)
    assert client.post(f"/matazim/member/{m.pk}/confirm/").status_code == 404
    m.refresh_from_db()
    assert m.school_join_status == ProgramMembership.SCHOOL_PENDING


# --- the two grants, both the school owner's (DEC-83) --------------------
#
# This supersedes the earlier "leaders endorse, never certify" rule (DEC-78).
# Avi reversed it on 2026-08-08: the school owner grants level 1 (acceptance,
# which the entrance test will gate) and level 2 (the מט״צ certification).
# What stays with program staff is opening schools, assigning leaders, and
# revoking a grant.

def test_the_school_owner_grants_level_1_acceptance(client):
    program = _program()
    school = _school(program, "s")
    leader = _user("accepting_leader")
    school.leaders.add(leader)
    m = _member(program, school, "applicant_kid", ProgramMembership.APPLIED)
    assert m.can_be_accepted and not m.is_accepted

    client.force_login(leader)
    client.post(f"/matazim/member/{m.pk}/accept/", {"note": "עבר את המבחן"})
    m.refresh_from_db()
    assert m.status == ProgramMembership.IN_TRAINING
    assert m.is_accepted
    assert m.accepted_by == leader and m.accepted_at is not None
    assert m.acceptance_note == "עבר את המבחן"


def test_the_school_owner_grants_level_2_certification(client):
    from app.matazim_models import ProgramStatusLog

    program = _program()
    school = _school(program, "s")
    leader = _user("certifying_leader")
    school.leaders.add(leader)
    m = _member(program, school, "ready_candidate", ProgramMembership.IN_TRAINING)

    client.force_login(leader)
    # Still no grant without a reason, whoever is giving it.
    client.post(f"/matazim/member/{m.pk}/certify/", {"note": ""})
    m.refresh_from_db()
    assert m.status != ProgramMembership.CERTIFIED

    client.post(f"/matazim/member/{m.pk}/certify/", {"note": "מוכן להדריך"})
    m.refresh_from_db()
    assert m.status == ProgramMembership.CERTIFIED
    assert m.certified_by == leader, "the school owner is recorded as the grantor"

    log = ProgramStatusLog.objects.get(membership=m,
                                       to_status=ProgramMembership.CERTIFIED)
    assert log.actor == leader and log.note == "מוכן להדריך"


def test_the_two_levels_run_in_order(client):
    """You cannot certify an applicant who was never accepted, and you cannot
    re-accept somebody already in the program."""
    program = _program()
    school = _school(program, "s")
    leader = _user("ordering_leader")
    school.leaders.add(leader)
    m = _member(program, school, "sequenced", ProgramMembership.APPLIED)
    client.force_login(leader)

    client.post(f"/matazim/member/{m.pk}/certify/", {"note": "לדלג על שלב"})
    m.refresh_from_db()
    assert m.status == ProgramMembership.APPLIED, "level 2 needs level 1 first"

    client.post(f"/matazim/member/{m.pk}/accept/", {"note": ""})
    m.refresh_from_db()
    assert m.status == ProgramMembership.IN_TRAINING

    client.post(f"/matazim/member/{m.pk}/accept/", {"note": "שוב"})
    m.refresh_from_db()
    assert m.status == ProgramMembership.IN_TRAINING, "accepting twice is a no-op"

    client.post(f"/matazim/member/{m.pk}/certify/", {"note": "עכשיו כן"})
    m.refresh_from_db()
    assert m.status == ProgramMembership.CERTIFIED


def test_an_owner_can_reject_an_applicant(client):
    program = _program()
    school = _school(program, "s")
    leader = _user("rejecting_leader")
    school.leaders.add(leader)
    m = _member(program, school, "turned_down", ProgramMembership.APPLIED)

    client.force_login(leader)
    client.post(f"/matazim/member/{m.pk}/accept/", {"reject": "1", "note": "לא הגיש"})
    m.refresh_from_db()
    assert m.status == ProgramMembership.REJECTED
    assert not m.is_accepted


def test_an_owner_cannot_grant_outside_their_own_school(client):
    """The scope check is on the *member's* school, so posting another school's
    member id directly gets nowhere."""
    program = _program()
    mine, theirs = _school(program, "mine"), _school(program, "theirs")
    leader = _user("scoped_leader")
    mine.leaders.add(leader)
    outsider_member = _member(program, theirs, "not_mine", ProgramMembership.APPLIED)

    client.force_login(leader)
    assert client.post(f"/matazim/member/{outsider_member.pk}/accept/").status_code == 404
    assert client.post(f"/matazim/member/{outsider_member.pk}/certify/",
                       {"note": "x"}).status_code == 404
    outsider_member.refresh_from_db()
    assert outsider_member.status == ProgramMembership.APPLIED


def test_revoking_stays_with_program_staff(client):
    """The grants moved to the schools; undoing one did not."""
    program = _program()
    school = _school(program, "s")
    leader = _user("revoke_wanting_leader")
    school.leaders.add(leader)
    m = _member(program, school, "certified_kid", ProgramMembership.CERTIFIED)

    client.force_login(leader)
    assert client.post(f"/matazim/member/{m.pk}/revoke/",
                       {"note": "התחרטתי"}).status_code == 404
    m.refresh_from_db()
    assert m.status == ProgramMembership.CERTIFIED

    staff = _user("overseeing_admin")
    program.staff.add(staff)
    client.force_login(staff)
    client.post(f"/matazim/member/{m.pk}/revoke/", {"note": "עזב את התוכנית"})
    m.refresh_from_db()
    assert m.status == ProgramMembership.REVOKED


def test_staff_certify_with_a_note_and_it_is_audited(client):
    from app.matazim_models import ProgramStatusLog

    program = _program()
    school = _school(program, "s")
    staff = _user("granting_admin")
    program.staff.add(staff)
    m = _member(program, school, "worthy", ProgramMembership.PROJECT_SUBMITTED)

    client.force_login(staff)
    # A grant with no reason is refused: that is part of keeping it scarce.
    client.post(f"/matazim/member/{m.pk}/certify/", {"note": ""})
    m.refresh_from_db()
    assert m.status != ProgramMembership.CERTIFIED

    client.post(f"/matazim/member/{m.pk}/certify/", {"note": "סיים הכל והדריך יפה"})
    m.refresh_from_db()
    assert m.status == ProgramMembership.CERTIFIED
    assert m.certified_by == staff and m.certified_at is not None

    log = ProgramStatusLog.objects.get(membership=m,
                                       to_status=ProgramMembership.CERTIFIED)
    assert log.actor == staff and log.note


def test_revoking_keeps_the_history(client):
    from app.matazim_models import ProgramStatusLog

    program = _program()
    school = _school(program, "s")
    staff = _user("revoking_admin")
    program.staff.add(staff)
    m = _member(program, school, "lapsed", ProgramMembership.CERTIFIED)
    m.certified_at = timezone.now()
    m.certified_by = staff
    m.save()

    client.force_login(staff)
    client.post(f"/matazim/member/{m.pk}/revoke/", {"note": "עזב את התוכנית"})
    m.refresh_from_db()
    assert m.status == ProgramMembership.REVOKED
    assert not m.is_certified
    # The grant itself is not erased, the trail survives (REQ-10.9).
    assert m.certified_at is not None and m.certified_by == staff
    assert ProgramStatusLog.objects.filter(
        membership=m, to_status=ProgramMembership.REVOKED).exists()


def test_certifying_still_grants_no_babook_permission(client):
    """DEC-69 again, this time through the real endpoint rather than the model."""
    program = _program()
    school = _school(program, "s")
    staff = _user("admin5")
    program.staff.add(staff)
    m = _member(program, school, "promoted", ProgramMembership.PROJECT_SUBMITTED)

    client.force_login(staff)
    client.post(f"/matazim/member/{m.pk}/certify/", {"note": "ראוי"})
    m.user.profile.refresh_from_db()
    m.user.refresh_from_db()
    assert m.user.profile.is_teacher is False
    assert m.user.is_staff is False and m.user.is_superuser is False
