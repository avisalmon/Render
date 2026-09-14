"""SPR-M.35 — פרקטיקום: the teaching itself.

REQ-M.32. The stage the whole programme exists to produce, and the last one
with no model behind it. Before this a leader could read a roster, approve work
and sign a certificate without ever seeing what that teenager had taught.

The test that carries the most weight here is
`test_nothing_about_a_session_is_a_record_about_a_child`. REQ-M.29 says nothing
in this product creates, stores or infers a record about one of the children a
מט״צ teaches, and this is the first model in the app where somebody would
reasonably expect otherwise: it is literally about a class of ten-year-olds. It
records a count and there is no field beside it a name could go into instead.

Traces: REQ-M.32, M.29, M.23, M.78, §4.4.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm35

PASSWORD = "sprm35-pass-3318"


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _manager(email="naomi@example.com"):
    from matazim.models import MemberProfile

    user = _user(email, "נעמי")
    _make_manager(user)
    return user


def _leader(email, name, manager):
    from matazim.models import Leader

    return Leader.objects.create(
        user=_user(email, name), institution=_inst(manager), approved_at=timezone.now()
    )


def _student(email, leader, name="יובל כהן"):
    from matazim.models import MemberProfile, Student

    user = _user(email, name)
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now(),
            "birth_year": timezone.now().year - 14,
            "welcome_accepted_at": timezone.now(),
        },
    )
    return Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)


def _session(student, days_ago=1, **extra):
    from matazim.models import TeachingSession

    fields = {
        "student": student,
        "title": "לולאות בסקראץ׳",
        "happened_on": timezone.localdate() - timezone.timedelta(days=days_ago),
        "minutes": 45,
        "learners": 12,
    }
    fields.update(extra)
    return TeachingSession.objects.create(**fields)


# ------------------------------------------------ the privacy rule, first


def test_nothing_about_a_session_is_a_record_about_a_child(db):
    """T-F-M.35.1-1: REQ-M.29.

    The first model in this app that is literally about a class of ten-year-olds,
    and the one where somebody would most reasonably expect a list of names.
    There is a count and there is no field beside it a name could go into.
    """
    from matazim.models import TeachingSession

    names = {f.name for f in TeachingSession._meta.get_fields()}
    forbidden = {"learner_names", "children", "pupils", "attendees", "roster", "names"}

    assert not (names & forbidden), f"a session records a child: {names & forbidden}"
    assert "learners" in names

    field = TeachingSession._meta.get_field("learners")
    assert field.get_internal_type() == "PositiveIntegerField", (
        "the number of children became something that can hold a name"
    )

    relations = {
        f.name
        for f in TeachingSession._meta.get_fields()
        if f.is_relation and f.related_model is not None
    }
    assert relations == {"student"}, (
        f"a session points at somebody other than the מט״צ who ran it: {relations}"
    )


def test_the_form_says_not_to_name_a_child(client, db):
    """T-F-M.35.1-2: REQ-M.29, and the honest limit of it.

    `place`, `went_well` and `was_hard` are prose, so the schema cannot enforce
    this and the screen has to ask. Same approach as the request box in §4.11.
    """
    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))

    client.force_login(student.user)
    html = client.get(reverse("matazim:my_teaching")).content.decode()

    assert "לא שומרים שום דבר על התלמידים" in html
    assert "בלי שמות של תלמידים" in html


# ------------------------------------------------ a member writes one down


def test_a_member_logs_what_they_taught(client, db):
    """T-F-M.35.2-1: REQ-M.32."""
    from matazim.models import TeachingSession

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))

    client.force_login(student.user)
    client.post(
        reverse("matazim:my_teaching"),
        {
            "title": "לולאות בסקראץ׳",
            "happened_on": timezone.localdate().isoformat(),
            "minutes": "45",
            "learners": "12",
            "place": "כיתה ד׳2, עתיד רמלה",
            "went_well": "הם בנו משחק",
            "was_hard": "איבדתי אותם בהתחלה",
        },
    )

    row = TeachingSession.objects.get()
    assert row.student_id == student.pk
    assert row.learners == 12
    assert row.was_hard == "איבדתי אותם בהתחלה"


def test_a_session_with_no_title_or_date_is_refused(client, db):
    """T-F-M.35.2-2: a row saying nothing happened is not a record."""
    from matazim.models import TeachingSession

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    client.force_login(student.user)

    client.post(reverse("matazim:my_teaching"), {"title": "  ", "happened_on": ""})
    client.post(reverse("matazim:my_teaching"), {"title": "משהו", "happened_on": ""})

    assert not TeachingSession.objects.exists()


def test_a_member_with_no_leader_is_told_what_opens_it(client, db):
    """T-F-M.35.2-3: REQ-M.65, REQ-M.102.

    Having no leader is a normal state. The screen says what opens the stage
    rather than showing an empty form that would save nowhere.
    """
    from matazim.models import MemberProfile, Student

    user = _user("loose@example.com", "איתי")
    MemberProfile.objects.update_or_create(user=user, defaults={"birth_year": 2012})
    assert not Student.objects.filter(user=user).exists()

    client.force_login(user)
    html = client.get(reverse("matazim:my_teaching")).content.decode()

    assert "כשמצטרפים למוביל" in html
    assert "מפגש חדש" not in html, "a form was offered with nowhere to save"


# ------------------------------------------------ what it adds up to


def test_the_totals_count_what_happened_and_not_what_did_not(client, db):
    """T-F-M.35.3-1: REQ-M.32.

    A cancelled session keeps its row and stops counting. A planned one has not
    happened yet, so it is not an hour taught either.
    """
    from matazim.teaching_views import summary_for

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))

    _session(student, days_ago=7, minutes=60, learners=10)
    _session(student, days_ago=3, minutes=30, learners=8)
    _session(student, days_ago=1, minutes=45, learners=99, cancelled_at=timezone.now())
    _session(student, days_ago=-5, minutes=45, learners=99)  # planned

    totals = summary_for(student)

    assert totals["sessions"] == 2
    assert totals["minutes"] == 90
    assert totals["hours"] == 1.5
    assert totals["learners"] == 18, "a session that did not happen was counted"
    assert totals["planned"] == 1


def test_the_count_is_on_the_screen_they_already_open(client, db):
    """T-F-M.35.3-2: REQ-M.32.

    A total that only shows on a page you have to remember to visit is a total
    nobody sees, and this one is the thing the whole programme is for.
    """
    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    _session(student, minutes=60, learners=10)

    client.force_login(student.user)
    html = client.get(reverse("matazim:my_path")).content.decode()

    assert "פרקטיקום" in html
    assert reverse("matazim:my_teaching") in html


def test_a_session_is_cancelled_rather_than_deleted(client, db):
    """T-F-M.35.3-3: the same rule as an event and a post.

    A session that was planned and fell through is worth more to a leader than
    a gap in a list.
    """
    from matazim.models import TeachingSession

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    row = _session(student, days_ago=-2)

    client.force_login(student.user)
    client.post(reverse("matazim:cancel_session", args=[row.pk]))

    assert TeachingSession.objects.filter(pk=row.pk).exists(), "the row was destroyed"
    row.refresh_from_db()
    assert row.is_cancelled


def test_nobody_cancels_somebody_elses_session(client, db):
    """T-F-M.35.3-4: §4.4, and it is their own account of their own year."""
    from matazim.models import TeachingSession

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    mine = _student("kid1@example.com", noa)
    other = _student("kid2@example.com", noa, name="דנה לוי")
    row = _session(mine)

    client.force_login(other.user)
    assert client.post(reverse("matazim:cancel_session", args=[row.pk])).status_code == 404

    row.refresh_from_db()
    assert not row.is_cancelled


# ------------------------------------------------ the leader reads it


def test_the_leader_sees_the_teaching_they_are_certifying(client, db):
    """T-F-M.35.4-1: REQ-M.23, REQ-M.32.

    The half that makes this mentorship rather than bookkeeping. A leader who
    can approve work and sign a certificate should be able to see the teaching
    being certified, and the reflection is the part worth reading.
    """
    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    student = _student("kid@example.com", noa)
    _session(student, went_well="הם בנו משחק", was_hard="איבדתי אותם בהתחלה")

    client.force_login(noa.user)
    html = client.get(reverse("matazim:student", args=[student.pk])).content.decode()

    assert "פרקטיקום" in html
    assert "לולאות בסקראץ׳" in html
    assert "איבדתי אותם בהתחלה" in html, "the reflection, which is the point, is missing"


def test_another_leaders_student_teaching_is_unreachable(client, db):
    """T-F-M.35.4-2: §4.4 — never in the queryset."""
    from matazim.access import visible_sessions

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    dana = _leader("dana@example.com", "דנה", naomi)

    hers = _student("kid1@example.com", noa)
    theirs = _student("kid2@example.com", dana, name="רות")
    _session(hers, title="של נעה")
    _session(theirs, title="של דנה")

    titles = set(visible_sessions(noa.user).values_list("title", flat=True))
    assert titles == {"של נעה"}


def test_a_members_teaching_is_their_own(client, db):
    """T-F-M.35.4-3: a session includes what they found hard, which is not
    something one teenager shows another."""
    from matazim.access import visible_sessions

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    mine = _student("kid1@example.com", noa)
    other = _student("kid2@example.com", noa, name="דנה לוי")
    _session(mine, title="שלי")

    assert not visible_sessions(other.user).exists()


# ------------------------------------------------ the API (Rule 6)


def test_the_api_writes_a_session_as_its_author(client, db):
    """T-F-M.35.5-1: REQ-M.139 — the student is stamped, never client-supplied."""
    from matazim.models import TeachingSession

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    mine = _student("kid1@example.com", noa)
    victim = _student("kid2@example.com", noa, name="דנה לוי")

    client.force_login(mine.user)
    response = client.post(
        "/matazim/api/teaching/",
        {
            "title": "רובוטיקה",
            "happened_on": timezone.localdate().isoformat(),
            "minutes": 45,
            "learners": 9,
            "student": victim.pk,
        },
        content_type="application/json",
    )

    assert response.status_code == 201, response.content
    assert TeachingSession.objects.get().student_id == mine.pk


def test_the_api_lets_a_member_fix_their_own_and_not_anothers(client, db):
    """T-F-M.35.5-2: Rule 6's question — can somebody fix a mistake without
    going to /admin/. Getting the number of learners wrong should be fixable."""
    from matazim.models import TeachingSession

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    mine = _student("kid1@example.com", noa)
    other = _student("kid2@example.com", noa, name="דנה לוי")
    row = _session(mine)

    client.force_login(mine.user)
    assert client.patch(
        f"/matazim/api/teaching/{row.pk}/", {"learners": 14},
        content_type="application/json",
    ).status_code == 200
    row.refresh_from_db()
    assert row.learners == 14

    client.force_login(other.user)
    assert client.patch(
        f"/matazim/api/teaching/{row.pk}/", {"learners": 99},
        content_type="application/json",
    ).status_code == 404

    row.refresh_from_db()
    assert row.learners == 14


def test_the_api_cannot_quietly_set_cancelled(client, db):
    """T-F-M.35.5-3: cancelled is always something somebody marked."""
    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    row = _session(student)

    client.force_login(student.user)
    client.patch(
        f"/matazim/api/teaching/{row.pk}/",
        {"cancelled_at": timezone.now().isoformat()},
        content_type="application/json",
    )

    row.refresh_from_db()
    assert not row.is_cancelled

    assert client.post(f"/matazim/api/teaching/{row.pk}/cancel/").status_code == 200
    row.refresh_from_db()
    assert row.is_cancelled


# --- SPR-M.40: the role is Institution.managers, the FKs are `institution` ---

def _make_manager(user):
    """One institution per test manager, so two managers are two worlds."""
    from matazim.models import Institution

    Institution.objects.create(name=f"מוסד {user.pk}").managers.add(user)


def _inst(user):
    from matazim.access import institution_of

    return institution_of(user)


def _is_pm(user):
    from matazim.access import is_program_manager

    return is_program_manager(user)
