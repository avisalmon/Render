"""SPR-M.60 — open classes: anyone may open one, and the joiner always acts.

Avi, 2026-10-12: "כל משתמש יכול לפתוח כיתה ולהכניס משתמשים אחרים", and the line
that matters more, "הפעולה האקטיבית של ההצטרפות לכיתה תהיה על ידי משתמש". An
owner is a מורה on screen and nothing in the data: certifies nobody, sees no
email, reaches no roster. These tests hold the two ways it can go wrong quietly:
an owner who can put somebody in a class, and a lens that shows more than it
promised.

Traces: REQ-M.167 to REQ-M.176.
"""

import re

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm60

PASSWORD = "sprm60-pass-5512"


def _user(email, name="x"):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _member(email="kid@example.com", name="יובל"):
    from matazim.models import MemberProfile

    user = _user(email, name)
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "welcome_accepted_at": timezone.now(),
            "birth_year": 2011,
            "guardian_name": "רונית כהן",
            "guardian_email": "parent@example.com",
            "guardian_consent_at": timezone.now(),
        },
    )
    return user


def _leader(email="noa@example.com"):
    from matazim.models import Institution, Leader, StudyClass

    inst = Institution.objects.order_by("created_at").first() or Institution.objects.create(
        name="עתיד רמלה"
    )
    leader = Leader.objects.create(
        user=_user(email, "נעה"), institution=inst, approved_at=timezone.now()
    )
    StudyClass.objects.create(leader=leader, name="ט1", school_name="עתיד")
    return leader


def _open(owner, name="חוג רובוטיקה"):
    from matazim import open_class as oc

    return oc.create_class(owner, name)


def _join(cls, user):
    from matazim import open_class as oc

    return oc.join_class(cls, user)


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()
    yield
    cache.clear()


def _body(response):
    return response.content.decode().split("<main", 1)[1]


# --- opening a class (REQ-M.167) --------------------------------------------


def test_a_signed_out_visitor_cannot_open_a_class(client, db):
    from matazim.models import OpenClass

    response = client.get(reverse("matazim:open_new"))
    assert response.status_code == 302 and "/login/" in response["Location"]
    client.post(reverse("matazim:open_new"), {"name": "x", "terms": "1"})
    assert not OpenClass.objects.exists()


@pytest.mark.parametrize("who", ["member", "leader"])
def test_any_signed_in_account_can_open_a_class(client, db, who):
    from matazim.models import OpenClass

    user = _member() if who == "member" else _leader().user
    client.force_login(user)
    response = client.post(reverse("matazim:open_new"), {"name": "חוג", "terms": "1"})
    row = OpenClass.objects.get(owner=user)
    assert response.status_code == 302
    assert response["Location"] == reverse("matazim:open_class", args=[row.pk])
    assert row.terms_accepted_at is not None


def test_a_program_manager_can_open_one_too(client, db):
    from matazim.models import OpenClass

    root = User.objects.create_superuser("root", "root@example.com", PASSWORD)
    client.force_login(root)
    client.post(reverse("matazim:open_new"), {"name": "חוג", "terms": "1"})
    assert OpenClass.objects.filter(owner=root).count() == 1


def test_the_terms_must_be_ticked_and_a_name_given(client, db):
    from matazim.models import OpenClass

    client.force_login(_member())
    client.post(reverse("matazim:open_new"), {"name": "חוג"})
    client.post(reverse("matazim:open_new"), {"name": "  ", "terms": "1"})
    assert not OpenClass.objects.exists()


def test_the_new_class_page_states_the_terms(client, db):
    from matazim.open_class_views import TERMS

    client.force_login(_member())
    html = client.get(reverse("matazim:open_new")).content.decode()
    for line in TERMS:
        assert line in html


def test_an_eleventh_class_is_refused_and_archiving_frees_a_place(client, db):
    from matazim import open_class as oc
    from matazim.models import OpenClass

    user = _member()
    client.force_login(user)
    for i in range(oc.MAX_LIVE_CLASSES):
        client.post(reverse("matazim:open_new"), {"name": f"כיתה {i}", "terms": "1"})
    assert OpenClass.objects.filter(owner=user).count() == oc.MAX_LIVE_CLASSES
    client.post(reverse("matazim:open_new"), {"name": "אחת יותר", "terms": "1"})
    assert OpenClass.objects.filter(owner=user).count() == oc.MAX_LIVE_CLASSES

    first = OpenClass.objects.filter(owner=user).first()
    client.post(reverse("matazim:open_class", args=[first.pk]), {"action": "archive"})
    client.post(reverse("matazim:open_new"), {"name": "אחת יותר", "terms": "1"})
    assert OpenClass.objects.filter(owner=user, archived_at__isnull=True).count() == oc.MAX_LIVE_CLASSES


# --- codes ------------------------------------------------------------------


def test_a_thousand_class_codes_never_equal_a_leader_code(db):
    from matazim.models import new_class_code

    leader = _leader()
    codes = {new_class_code() for _ in range(1000)}
    assert leader.join_code not in codes
    assert len(codes) == 1000


def test_a_class_code_that_collides_with_a_leader_code_is_drawn_again(db, monkeypatch):
    from matazim import models

    leader = _leader()
    draws = iter([leader.join_code, "fresh-code-123456"])
    monkeypatch.setattr(models, "new_join_code", lambda: next(draws))
    assert models.new_class_code() == "fresh-code-123456"


# --- the joiner always acts (REQ-M.168) -------------------------------------


def test_a_signed_out_visitor_sees_the_join_page_and_a_way_to_register(client, db):
    cls = _open(_member("owner@example.com", "דנה"))
    response = client.get(reverse("matazim:open_join", args=[cls.code]))
    assert response.status_code == 200
    html = response.content.decode()
    assert cls.name in html and "דנה" in html
    assert f"{reverse('matazim:register')}?next=/matazim/class/{cls.code}/" in html


def test_the_join_page_lists_what_the_owner_sees_before_the_button(client, db):
    from matazim.open_class import LENS, NEVER

    cls = _open(_member("owner@example.com"))
    client.force_login(_member())
    html = _body(client.get(reverse("matazim:open_join", args=[cls.code])))
    button = html.index('value="join"')
    for line in LENS + NEVER:
        assert html.index(line) < button


def test_joining_inserts_exactly_one_row_for_the_requester(client, db):
    from matazim.models import OpenClassMember

    owner = _member("owner@example.com")
    cls = _open(owner)
    joiner = _member()
    bystander = _member("bystander@example.com")
    client.force_login(joiner)
    client.post(
        reverse("matazim:open_join", args=[cls.code]),
        {"action": "join", "user": bystander.pk, "user_id": bystander.pk, "email": bystander.email},
    )
    rows = OpenClassMember.objects.filter(open_class=cls)
    assert [r.user_id for r in rows] == [joiner.pk]


def test_an_owner_cannot_add_anybody_through_any_post(client, db):
    from matazim.models import OpenClassMember

    owner = _member("owner@example.com")
    cls = _open(owner)
    target = _member()
    client.force_login(owner)
    for action in ("add", "join", "invite", "member"):
        client.post(
            reverse("matazim:open_class", args=[cls.pk]),
            {"action": action, "user": target.pk, "member": target.pk, "email": target.email},
        )
        client.post(
            reverse("matazim:open_join", args=[cls.code]),
            {"action": action, "user": target.pk},
        )
    assert not OpenClassMember.objects.exists()


def test_nothing_but_join_class_creates_a_membership():
    """The structural half of the rule: one inserter, and it is the joiner's."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent / "matazim"
    offenders = []
    for path in root.rglob("*.py"):
        if "migrations" in path.parts or path.name == "open_class.py":
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"(?<!class )OpenClassMember\s*\(|OpenClassMember\.objects\.(create|get_or_create|update_or_create|bulk_create)", text):
            offenders.append(path.name)
        if re.search(r"\.members\.(create|add|get_or_create)", text):
            offenders.append(path.name)
    assert offenders == []


def test_no_serializer_field_names_a_user():
    from matazim.serializers import OpenClassMemberSerializer, OpenClassSerializer

    for serializer in (OpenClassMemberSerializer, OpenClassSerializer):
        names = set(serializer.Meta.fields)
        assert not names & {"user", "user_id", "owner", "email", "members"}


def test_rejoining_reuses_the_row(db):
    from matazim.models import OpenClassMember
    from matazim import open_class as oc

    owner = _member("owner@example.com")
    cls = _open(owner)
    joiner = _member()
    row, created = _join(cls, joiner)
    assert created
    oc.end_membership(row, by=joiner)
    again, created = _join(cls, joiner)
    assert created and again.pk == row.pk
    assert again.ended_at is None and again.ended_by is None
    assert OpenClassMember.objects.filter(open_class=cls, user=joiner).count() == 1
    same, created = _join(cls, joiner)
    assert not created and same.pk == row.pk


def test_the_class_is_full_at_the_cap(db, monkeypatch):
    from matazim import open_class as oc

    monkeypatch.setattr(oc, "MAX_MEMBERS", 2)
    cls = _open(_member("owner@example.com"))
    _join(cls, _member("a@example.com"))
    _join(cls, _member("b@example.com"))
    with pytest.raises(oc.ClassFull):
        _join(cls, _member("c@example.com"))


def test_a_full_class_says_so_on_the_page(client, db, monkeypatch):
    from matazim import open_class as oc
    from matazim.models import OpenClassMember

    monkeypatch.setattr(oc, "MAX_MEMBERS", 1)
    cls = _open(_member("owner@example.com"))
    _join(cls, _member("a@example.com"))
    client.force_login(_member("b@example.com"))
    response = client.post(reverse("matazim:open_join", args=[cls.code]), {"action": "join"})
    assert response.status_code == 200 and "מלאה" in response.content.decode()
    assert OpenClassMember.objects.filter(open_class=cls).count() == 1


@pytest.mark.parametrize("state", ["closed", "archived", "unknown"])
def test_a_closed_archived_or_unknown_code_is_one_and_the_same_404(client, db, state):
    from matazim import open_class as oc

    cls = _open(_member("owner@example.com"))
    if state == "closed":
        cls.is_open = False
        cls.save()
    elif state == "archived":
        oc.archive(cls)
    code = "no-such-code" if state == "unknown" else cls.code
    client.force_login(_member())
    response = client.post(reverse("matazim:open_join", args=[code]), {"action": "join"})
    assert response.status_code == 404


def test_the_owner_who_opens_their_own_link_just_goes_to_their_class(client, db):
    from matazim.models import OpenClassMember

    owner = _member("owner@example.com")
    cls = _open(owner)
    client.force_login(owner)
    client.post(reverse("matazim:open_join", args=[cls.code]), {"action": "join"})
    assert not OpenClassMember.objects.exists()


# --- the lens (REQ-M.169, REQ-M.170) ----------------------------------------


def _progress(user, slug, lessons=2, done=1):
    from app.models import Course, UserVideoProgress, Video

    course, _ = Course.objects.get_or_create(
        slug=slug, defaults={"title": f"הדרכה {slug}", "is_published": True}
    )
    videos = list(course.videos.order_by("lesson_order"))
    for i in range(len(videos), lessons):
        videos.append(
            Video.objects.create(
                course=course, title=f"שיעור {i + 1}", lesson_order=i + 1, bunny_video_id=f"{slug}{i}"
            )
        )
    for video in videos[:done]:
        UserVideoProgress.objects.update_or_create(
            user=user,
            video=video,
            defaults={"percent_watched": 100.0, "quiz_passed": True, "completed_at": timezone.now()},
        )
    return course


def test_the_owner_sees_the_lens_and_nothing_beyond_it(client, db):
    from matazim.models import Feedback  # noqa: F401  (kept to show what is not read)

    owner = _member("owner@example.com", "דנה")
    cls = _open(owner)
    kid = _member("kid@example.com", "יובל")
    _join(cls, kid)
    _progress(kid, "python", lessons=2, done=1)
    client.force_login(owner)
    html = client.get(reverse("matazim:open_class", args=[cls.pk])).content.decode()
    assert "יובל" in html and "50%" in html
    for secret in ("kid@example.com", "parent@example.com", "רונית כהן", "2011", "guardian"):
        assert secret not in html


def test_the_rest_payload_carries_the_lens_and_nothing_else(client, db):
    owner = _member("owner@example.com", "דנה")
    cls = _open(owner)
    kid = _member("kid@example.com", "יובל")
    _join(cls, kid)
    _progress(kid, "python")
    client.force_login(owner)
    response = client.get("/matazim/api/open-class-members/")
    assert response.status_code == 200
    rows = response.json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert len(rows) == 1
    assert set(rows[0]) == {
        "id", "open_class", "name", "joined_at", "ended_at",
        "started", "certificates", "last_active",
    }
    raw = response.content.decode()
    for secret in ("kid@example.com", "parent@example.com", "רונית כהן", "2011", "birth_year", "guardian"):
        assert secret not in raw


def test_progress_outside_the_open_courses_is_absent(client, db):
    owner = _member("owner@example.com")
    cls = _open(owner)
    kid = _member("kid@example.com", "יובל")
    _join(cls, kid)
    _progress(kid, "python", lessons=2, done=1)
    _progress(kid, "robotics-private", lessons=2, done=2)
    client.force_login(owner)
    html = client.get(reverse("matazim:open_class", args=[cls.pk])).content.decode()
    assert "robotics-private" not in html and "הדרכה robotics-private" not in html
    api = client.get("/matazim/api/open-class-members/").content.decode()
    assert "robotics-private" not in api


def test_a_certificate_for_a_non_open_course_is_absent_and_an_open_one_present(client, db):
    from app.models import Course, CourseCertificate

    owner = _member("owner@example.com")
    cls = _open(owner)
    kid = _member("kid@example.com", "יובל")
    _join(cls, kid)
    other = Course.objects.create(slug="robotics-private", title="רובוטיקה סגורה", is_published=True)
    CourseCertificate.objects.create(user=kid, course=other)
    python = _progress(kid, "python")
    CourseCertificate.objects.create(user=kid, course=python)
    client.force_login(owner)
    html = client.get(reverse("matazim:open_class", args=[cls.pk])).content.decode()
    assert "רובוטיקה סגורה" not in html
    assert python.title in html


def test_the_lens_reads_in_a_fixed_number_of_queries(db, django_assert_max_num_queries):
    from matazim import open_class as oc

    cls = _open(_member("owner@example.com"))
    for i in range(3):
        _join(cls, _member(f"k{i}@example.com", f"שם{i}"))
    with django_assert_max_num_queries(8):
        oc.lens_rows(cls)
    for i in range(3, 12):
        _join(cls, _member(f"k{i}@example.com", f"שם{i}"))
    with django_assert_max_num_queries(8):
        oc.lens_rows(cls)


def test_a_person_with_no_name_reads_as_a_placeholder_never_an_email(db):
    from matazim import open_class as oc

    user = User.objects.create_user("secret@example.com", "secret@example.com", PASSWORD)
    assert "secret@example.com" not in oc.display_name(user)


def test_a_member_sees_the_lens_and_cannot_see_other_members(client, db):
    owner = _member("owner@example.com", "דנה")
    cls = _open(owner)
    me = _member("me@example.com", "אני")
    other = _member("other@example.com", "מישהו אחר")
    _join(cls, me)
    _join(cls, other)
    client.force_login(me)
    html = client.get(reverse("matazim:open_class", args=[cls.pk])).content.decode()
    assert "דנה" in html and "מישהו אחר" not in html
    assert reverse("matazim:open_leave", args=[cls.pk]) in html
    rows = client.get("/matazim/api/open-class-members/").json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert [r["name"] for r in rows] == ["אני"]


# --- leaving and removal (REQ-M.170) -----------------------------------------


def test_a_member_can_leave_and_the_owner_stops_seeing_them(client, db):
    owner = _member("owner@example.com", "דנה")
    cls = _open(owner)
    kid = _member("kid@example.com", "יובל")
    row, _ = _join(cls, kid)
    client.force_login(kid)
    response = client.post(reverse("matazim:open_leave", args=[cls.pk]))
    assert response.status_code == 302
    row.refresh_from_db()
    assert row.ended_at is not None and row.ended_by_id == kid.pk
    client.force_login(owner)
    assert "יובל" not in client.get(reverse("matazim:open_class", args=[cls.pk])).content.decode()


def test_leaving_is_post_only(client, db):
    cls = _open(_member("owner@example.com"))
    kid = _member()
    _join(cls, kid)
    client.force_login(kid)
    assert client.get(reverse("matazim:open_leave", args=[cls.pk])).status_code == 405


def test_the_owner_can_remove_a_member_and_that_member_is_not_blocked_elsewhere(client, db):
    from matazim.models import Student

    owner = _member("owner@example.com")
    cls = _open(owner)
    other = _open(_member("owner2@example.com"))
    leader = _leader()
    kid = _member()
    row, _ = _join(cls, kid)
    client.force_login(owner)
    client.post(reverse("matazim:open_class", args=[cls.pk]), {"action": "remove", "member": row.pk})
    row.refresh_from_db()
    assert row.ended_at is not None and row.ended_by_id == owner.pk

    client.force_login(kid)
    client.post(reverse("matazim:open_join", args=[other.code]), {"action": "join"})
    client.post(reverse("matazim:join", args=[leader.join_code]), {"action": "join"})
    assert other.members.filter(user=kid, ended_at__isnull=True).exists()
    assert Student.objects.filter(user=kid, leader=leader).exists()


def test_an_owner_cannot_remove_a_member_of_somebody_elses_class(client, db):
    owner = _member("owner@example.com")
    mine = _open(owner)
    theirs = _open(_member("owner2@example.com"))
    kid = _member()
    row, _ = _join(theirs, kid)
    client.force_login(owner)
    client.post(reverse("matazim:open_class", args=[mine.pk]), {"action": "remove", "member": row.pk})
    row.refresh_from_db()
    assert row.ended_at is None


def test_archiving_ends_the_view_for_members_and_keeps_the_rows(client, db):
    from matazim import open_class as oc

    owner = _member("owner@example.com")
    cls = _open(owner)
    kid = _member()
    row, _ = _join(cls, kid)
    oc.archive(cls)
    client.force_login(kid)
    assert client.get(reverse("matazim:open_class", args=[cls.pk])).status_code == 404
    row.refresh_from_db()
    assert row.pk


def test_closing_stops_new_joiners_and_reopening_restores_it(client, db):
    owner = _member("owner@example.com")
    cls = _open(owner)
    client.force_login(owner)
    url = reverse("matazim:open_class", args=[cls.pk])
    client.post(url, {"action": "close"})
    cls.refresh_from_db()
    assert not cls.is_open
    client.force_login(_member())
    assert client.get(reverse("matazim:open_join", args=[cls.code])).status_code == 404
    client.force_login(owner)
    client.post(url, {"action": "reopen"})
    cls.refresh_from_db()
    assert cls.is_open


def test_replacing_the_code_kills_the_old_link(client, db):
    owner = _member("owner@example.com")
    cls = _open(owner)
    old = cls.code
    client.force_login(owner)
    client.post(reverse("matazim:open_class", args=[cls.pk]), {"action": "replace_code"})
    cls.refresh_from_db()
    assert cls.code != old
    assert client.get(reverse("matazim:open_join", args=[old])).status_code == 404
    assert client.get(reverse("matazim:open_join", args=[cls.code])).status_code == 200


# --- separate worlds (REQ-M.172) --------------------------------------------


def test_membership_creates_no_student_and_no_certificate_and_moves_no_count(client, db):
    from matazim.models import Leader, MatazCertificate, Student

    cls = _open(_member("owner@example.com"))
    kid = _member()
    before = (Student.objects.count(), MatazCertificate.objects.count(), Leader.objects.count())
    client.force_login(kid)
    client.post(reverse("matazim:open_join", args=[cls.code]), {"action": "join"})
    assert cls.members.filter(user=kid).exists()
    assert (Student.objects.count(), MatazCertificate.objects.count(), Leader.objects.count()) == before


def test_the_class_page_has_no_certify_approve_or_stage_control(client, db):
    owner = _member("owner@example.com")
    cls = _open(owner)
    _join(cls, _member())
    client.force_login(owner)
    html = client.get(reverse("matazim:open_class", args=[cls.pk])).content.decode()
    assert "לא מסמיך/ה אף אחד/ת למט״צ" in html
    assert "/certify/" not in html
    for word in ("להסמיך", "לאשר", "שלב"):
        assert word not in html.split("<main", 1)[1]


def test_the_open_tables_hold_no_key_to_the_roster_world():
    from matazim.models import OpenClass, OpenClassMember

    related = {
        f.related_model.__name__
        for model in (OpenClass, OpenClassMember)
        for f in model._meta.get_fields()
        if f.is_relation and f.related_model is not None
    }
    assert related <= {"User", "OpenClass", "OpenClassMember"}


# --- who can see what: 404, not 403 (REQ-M.173) ------------------------------


def test_a_stranger_gets_a_404_for_every_surface_of_a_class(client, db):
    owner = _member("owner@example.com")
    cls = _open(owner)
    kid = _member("kid@example.com")
    _join(cls, kid)
    leader = _leader()
    pm = _leader("pm@example.com").user
    from matazim.models import Institution

    Institution.objects.first().managers.add(pm)
    strangers = [_member("stranger@example.com"), leader.user, pm]
    for who in strangers:
        client.force_login(who)
        for url in (
            reverse("matazim:open_class", args=[cls.pk]),
            reverse("matazim:open_class_qr", args=[cls.pk]),
        ):
            assert client.get(url).status_code == 404, (who.email, url)
        assert client.post(reverse("matazim:open_class", args=[cls.pk]), {"action": "archive"}).status_code == 404
        assert client.post(reverse("matazim:open_leave", args=[cls.pk])).status_code == 404
        assert client.post(reverse("matazim:open_report", args=[cls.pk]), {"reason": "x"}).status_code == 404
        assert client.get(f"/matazim/api/open-classes/{cls.pk}/").status_code == 404
        assert client.get("/matazim/api/open-class-members/").json() in ([], {"count": 0, "next": None, "previous": None, "results": []})
    cls.refresh_from_db()
    assert cls.archived_at is None


def test_the_qr_needs_a_login_and_the_owner(client, db):
    owner = _member("owner@example.com")
    cls = _open(owner)
    kid = _member()
    _join(cls, kid)
    url = reverse("matazim:open_class_qr", args=[cls.pk])
    assert client.get(url).status_code == 302
    client.force_login(kid)
    assert client.get(url).status_code == 404
    client.force_login(owner)
    response = client.get(url)
    assert response.status_code == 200 and response["Content-Type"] == "image/png"


def test_root_can_read_a_class_but_gets_no_code_link_or_qr(client, db):
    cls = _open(_member("owner@example.com"))
    root = User.objects.create_superuser("root", "root@example.com", PASSWORD)
    client.force_login(root)
    response = client.get(reverse("matazim:open_class", args=[cls.pk]))
    assert response.status_code == 200
    assert cls.code not in response.content.decode()
    assert client.get(reverse("matazim:open_class_qr", args=[cls.pk])).status_code == 404


# --- one box (REQ-M.171) ------------------------------------------------------


def test_the_code_box_routes_a_class_code_to_the_class(client, db):
    cls = _open(_member("owner@example.com"))
    response = client.post(reverse("matazim:code"), {"code": cls.code})
    assert response.status_code == 302
    assert response["Location"] == reverse("matazim:open_join", args=[cls.code])


def test_the_code_box_still_routes_a_leaders_code(client, db):
    leader = _leader()
    response = client.post(reverse("matazim:code"), {"code": leader.join_code})
    assert response["Location"] == reverse("matazim:join", args=[leader.join_code])


def test_a_pasted_class_link_works_and_a_closed_class_does_not(client, db):
    cls = _open(_member("owner@example.com"))
    link = f"https://example.com/matazim/class/{cls.code}/"
    assert client.post(reverse("matazim:code"), {"code": link}).status_code == 302
    cls.is_open = False
    cls.save()
    response = client.post(reverse("matazim:code"), {"code": link})
    assert response.status_code == 200 and "לא מוכר" in response.content.decode()


def test_wrong_codes_rest_the_box_for_class_codes_too(client, db):
    cls = _open(_member("owner@example.com"))
    for _ in range(8):
        client.post(reverse("matazim:code"), {"code": "wrong"})
    response = client.post(reverse("matazim:code"), {"code": cls.code})
    assert response.status_code == 200 and "הרבה פעמים" in response.content.decode()


# --- consent, the bell, reports ---------------------------------------------


@override_settings(MATAZIM_REQUIRE_GUARDIAN_CONSENT=True)
def test_the_consent_gate_stops_a_minor_at_the_join_step_only(client, db):
    from matazim.models import MemberProfile

    cls = _open(_member("owner@example.com"))
    kid = _member()
    MemberProfile.objects.filter(user=kid).update(guardian_consent_at=None)
    client.force_login(kid)
    assert client.get(reverse("matazim:open_join", args=[cls.code])).status_code == 200
    response = client.post(reverse("matazim:open_join", args=[cls.code]), {"action": "join"})
    assert response.status_code == 302 and response["Location"] == reverse("matazim:profile")
    assert not cls.members.exists()
    assert client.get(reverse("matazim:my_classes")).status_code == 200
    assert client.get(reverse("matazim:courses")).status_code == 200


@override_settings(MATAZIM_REQUIRE_GUARDIAN_CONSENT=True)
def test_a_minor_with_consent_joins(client, db):
    cls = _open(_member("owner@example.com"))
    kid = _member()
    client.force_login(kid)
    client.post(reverse("matazim:open_join", args=[cls.code]), {"action": "join"})
    assert cls.members.filter(user=kid).exists()


def test_the_consent_wording_no_longer_assumes_a_leader():
    from matazim import consent

    text = consent.consent_blocker.__doc__ or ""
    import inspect

    assert "למוביל/ה" not in inspect.getsource(consent)
    assert text is not None


def test_the_owner_gets_a_bell_and_no_email_when_somebody_joins(client, db):
    from matazim.models import Notification

    owner = _member("owner@example.com")
    cls = _open(owner)
    kid = _member("kid@example.com", "יובל")
    client.force_login(kid)
    mail.outbox.clear()
    client.post(reverse("matazim:open_join", args=[cls.code]), {"action": "join"})
    notice = Notification.objects.get(user=owner, kind=Notification.OPEN_JOINED)
    assert "יובל" in notice.text and cls.name in notice.text
    assert notice.url.startswith("/matazim/")
    assert mail.outbox == []
    client.post(reverse("matazim:open_join", args=[cls.code]), {"action": "join"})
    assert Notification.objects.filter(user=owner, kind=Notification.OPEN_JOINED).count() == 1


def test_a_report_reaches_root_through_the_request_queue_without_the_code(client, db):
    from matazim.models import Request

    owner = _member("owner@example.com")
    cls = _open(owner)
    kid = _member()
    _join(cls, kid)
    client.force_login(kid)
    client.post(reverse("matazim:open_report", args=[cls.pk]), {"reason": "שמות לא הולמים"})
    row = Request.objects.get()
    assert row.author_id == kid.pk and row.status == Request.NEW and row.kind == Request.PROBLEM
    assert "שמות לא הולמים" in row.body and cls.name in row.body
    assert cls.code not in row.body


def test_a_visitor_to_the_join_page_can_report_it_too(client, db):
    from matazim.models import Request

    cls = _open(_member("owner@example.com"))
    client.force_login(_member())
    client.post(reverse("matazim:open_join", args=[cls.code]), {"action": "report", "reason": "ספאם"})
    assert Request.objects.count() == 1


# --- the hub, the nav, the guide (REQ-M.175, REQ-M.176) ----------------------


def test_the_learner_hub_lists_owned_and_joined_classes(client, db):
    owner = _member("owner@example.com", "דנה")
    mine = _open(owner, "הכיתה שלי")
    theirs = _open(_member("owner2@example.com"), "הכיתה של אחרים")
    _join(theirs, owner)
    client.force_login(owner)
    html = client.get(reverse("matazim:my_classes")).content.decode()
    assert "הכיתה שלי" in html and "הכיתה של אחרים" in html
    assert reverse("matazim:open_new") in html and reverse("matazim:open_guide") in html
    assert reverse("matazim:open_class", args=[mine.pk]) in html


def test_a_learner_with_no_leader_sees_open_classes_and_no_official_ones(client, db):
    client.force_login(_member())
    html = _body(client.get(reverse("matazim:my_classes")))
    assert "כיתות פתוחות" in html
    assert 'name="school_name"' not in html


def test_a_leader_hub_keeps_the_official_classes_and_lists_open_ones_apart(client, db):
    leader = _leader()
    _open(leader.user, "חוג פתוח")
    client.force_login(leader.user)
    html = _body(client.get(reverse("matazim:my_classes")))
    assert "ט1" in html and "חוג פתוח" in html
    assert 'name="school_name"' in html


def test_the_learner_menu_has_one_classes_entry_and_a_leaders_is_unchanged(client, db):
    client.force_login(_member())
    html = client.get(reverse("matazim:courses")).content.decode()
    assert reverse("matazim:my_classes") in html
    leader = _leader()
    client.force_login(leader.user)
    html = client.get(reverse("matazim:leader_home")).content.decode()
    nav = html.split('id="mzNav"', 1)[1].split("</nav>", 1)[0]
    assert reverse("matazim:my_classes") not in nav
    assert reverse("matazim:classes") in nav


def test_the_guide_is_public_and_states_the_limits(client, db):
    response = client.get(reverse("matazim:open_guide"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "10" in html and "100" in html
    assert "מוביל/ה" in html


def test_no_page_of_the_feature_links_outside_the_app(client, db):
    owner = _member("owner@example.com")
    cls = _open(owner)
    _join(cls, _member())
    client.force_login(owner)
    pages = [
        reverse("matazim:my_classes"),
        reverse("matazim:open_new"),
        reverse("matazim:open_guide"),
        reverse("matazim:open_class", args=[cls.pk]),
        reverse("matazim:open_join", args=[cls.code]),
    ]
    for url in pages:
        html = client.get(url).content.decode()
        for href in re.findall(r'href="(/[^"]*)"', html):
            assert href.startswith("/matazim/") or href.startswith("/static/"), (url, href)


# --- the REST API (REQ-M.139 stays true) --------------------------------------


def test_the_api_is_closed_to_the_signed_out(client, db):
    assert client.get("/matazim/api/open-classes/").status_code in (401, 403)
    assert client.get("/matazim/api/open-class-members/").status_code in (401, 403)


def test_creating_a_class_through_the_api_needs_the_terms_and_stamps_the_owner(client, db):
    from matazim.models import OpenClass

    me = _member()
    stranger = _member("stranger@example.com")
    client.force_login(me)
    refused = client.post("/matazim/api/open-classes/", {"name": "חוג"}, content_type="application/json")
    assert refused.status_code == 400 and not OpenClass.objects.exists()
    response = client.post(
        "/matazim/api/open-classes/",
        {"name": "חוג", "terms_accepted": True, "owner": stranger.pk, "code": "mine-now", "archived_at": None},
        content_type="application/json",
    )
    assert response.status_code == 201
    row = OpenClass.objects.get()
    assert row.owner_id == me.pk and row.code != "mine-now" and row.terms_accepted_at is not None
    assert response.json()["code"] == row.code


def test_the_code_is_shown_to_the_owner_alone(client, db):
    owner = _member("owner@example.com")
    cls = _open(owner)
    kid = _member()
    _join(cls, kid)
    client.force_login(owner)
    assert client.get(f"/matazim/api/open-classes/{cls.pk}/").json()["code"] == cls.code
    client.force_login(kid)
    body = client.get(f"/matazim/api/open-classes/{cls.pk}/")
    assert body.status_code == 200 and "code" not in body.json()


def test_only_the_owner_can_change_or_end_a_class_through_the_api(client, db):
    owner = _member("owner@example.com")
    cls = _open(owner)
    kid = _member()
    _join(cls, kid)
    client.force_login(kid)
    assert client.patch(f"/matazim/api/open-classes/{cls.pk}/", {"name": "x"}, content_type="application/json").status_code == 403
    assert client.delete(f"/matazim/api/open-classes/{cls.pk}/").status_code == 403
    client.force_login(owner)
    old = cls.code
    response = client.patch(
        f"/matazim/api/open-classes/{cls.pk}/",
        {"name": "שם חדש", "rotate_code": True, "is_open": False},
        content_type="application/json",
    )
    assert response.status_code == 200
    cls.refresh_from_db()
    assert cls.name == "שם חדש" and cls.code != old and not cls.is_open
    assert client.delete(f"/matazim/api/open-classes/{cls.pk}/").status_code == 204
    cls.refresh_from_db()
    assert cls.archived_at is not None


def test_joining_through_the_api_takes_a_code_and_joins_the_caller_only(client, db):
    owner = _member("owner@example.com")
    cls = _open(owner)
    kid = _member()
    other = _member("other@example.com")
    client.force_login(kid)
    response = client.post(
        "/matazim/api/open-class-members/",
        {"code": cls.code, "user": other.pk},
        content_type="application/json",
    )
    assert response.status_code == 201
    assert [m.user_id for m in cls.members.all()] == [kid.pk]


def test_the_api_gives_one_answer_for_wrong_closed_and_archived_codes(client, db):
    from matazim import open_class as oc

    closed = _open(_member("owner@example.com"))
    closed.is_open = False
    closed.save()
    gone = _open(_member("owner2@example.com"))
    oc.archive(gone)
    client.force_login(_member())
    answers = set()
    for code in ("nope", closed.code, gone.code):
        response = client.post("/matazim/api/open-class-members/", {"code": code}, content_type="application/json")
        assert response.status_code == 400
        answers.add(response.content)
    assert len(answers) == 1


def test_the_api_code_endpoint_rests_after_wrong_guesses(client, db):
    cls = _open(_member("owner@example.com"))
    client.force_login(_member())
    for _ in range(8):
        client.post("/matazim/api/open-class-members/", {"code": "wrong"}, content_type="application/json")
    response = client.post("/matazim/api/open-class-members/", {"code": cls.code}, content_type="application/json")
    assert response.status_code == 403
    assert not cls.members.exists()


def test_the_member_endpoint_has_no_browsable_form(client, db):
    client.force_login(_member())
    response = client.get("/matazim/api/open-class-members/", HTTP_ACCEPT="text/html")
    assert "application/json" in response["Content-Type"]


def test_leaving_or_removing_through_the_api(client, db):
    owner = _member("owner@example.com")
    cls = _open(owner)
    a, b = _member("a@example.com"), _member("b@example.com")
    ra, _ = _join(cls, a)
    rb, _ = _join(cls, b)
    client.force_login(a)
    assert client.delete(f"/matazim/api/open-class-members/{ra.pk}/").status_code == 204
    assert client.delete(f"/matazim/api/open-class-members/{rb.pk}/").status_code == 404
    client.force_login(owner)
    assert client.delete(f"/matazim/api/open-class-members/{rb.pk}/").status_code == 204
    ra.refresh_from_db()
    rb.refresh_from_db()
    assert ra.ended_at and rb.ended_at and rb.ended_by_id == owner.pk


def test_a_membership_is_not_editable_through_the_api(client, db):
    cls = _open(_member("owner@example.com"))
    kid = _member()
    row, _ = _join(cls, kid)
    client.force_login(kid)
    response = client.patch(
        f"/matazim/api/open-class-members/{row.pk}/", {"ended_at": None}, content_type="application/json"
    )
    assert response.status_code == 403


def test_the_two_new_models_are_routed():
    from matazim.api import ROUTES

    prefixes = {prefix for prefix, _view, _model in ROUTES}
    assert {"open-classes", "open-class-members"} <= prefixes


def test_a_person_on_a_leaders_roster_joins_an_open_class_and_the_roster_is_unchanged(client, db):
    from matazim.models import MatazCertificate, Student

    leader = _leader()
    kid = _member()
    client.force_login(kid)
    client.post(reverse("matazim:join", args=[leader.join_code]), {"action": "join"})
    student = Student.objects.get(user=kid, leader=leader)
    status, certified = student.status, MatazCertificate.objects.filter(student=student).count()
    roster = Student.objects.filter(leader=leader).count()

    cls = _open(_member("owner@example.com"))
    client.post(reverse("matazim:open_join", args=[cls.code]), {"action": "join"})

    student.refresh_from_db()
    assert cls.members.filter(user=kid).exists()
    assert student.status == status
    assert MatazCertificate.objects.filter(student=student).count() == certified
    assert Student.objects.filter(leader=leader).count() == roster
