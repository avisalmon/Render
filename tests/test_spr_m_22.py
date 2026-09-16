"""SPR-M.22 — the student detail page, for a leader.

Parked since SPR-M.15 with "we will define it later". Avi, 2026-09-16, handed
the definition over: "You define leader detail page."

**What the page is for.** It is the screen a leader opens when one teenager is
the subject, rather than a queue or a roster. It answers, in order: where are
they and what is outstanding, what have they actually made and what did I say
about it, what have they taught, and who moved them.

Every one of those existed except the second, which is the one the programme is
actually about. A leader's only route to a submission was the queue on האזור
שלי, and `waiting_for` holds `status=WAITING`, so answering a piece of work
removed it from every screen a leader has. The person who signs the certificate
could not look back over the body of work they were certifying without typing a
URL from memory. That is what this sprint adds.

**And the visibility rule it inherits.** Avi, the same day: "מוביל רואה את כל
התלמידים הקשורים אליו. לא לפי בית ספר." That closes Litala's צפייה בכל תלמידי
בית הספר, open since SPR-M.37 and recorded there as never accepted and never
refused. It is refused. Two leaders at one school do not see each other's
students, and this page is scoped through `visible_submissions` so it inherits
that rather than restating it.

Traces: REQ-M.19, M.22, M.23, M.123, M.125.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm22

PASSWORD = "sprm22-pass-4460"


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _institution(name="רשת אחת"):
    from matazim.models import Institution

    manager = _user(f"pm{name}@example.com", "נעמי")
    inst = Institution.objects.create(name=name)
    inst.managers.add(manager)
    return inst


def _leader(email, name, institution):
    from matazim.models import Leader

    return Leader.objects.create(
        user=_user(email, name), institution=institution, approved_at=timezone.now()
    )


def _student(email, name, leader):
    from matazim.models import MemberProfile, Student

    user = _user(email, name)
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now(),
            "birth_year": timezone.now().year - 14,
            "guardian_consent_at": timezone.now(),
            "welcome_accepted_at": timezone.now(),
        },
    )
    return Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)


def _work(student, title, status, said=None):
    from matazim.models import Feedback, Submission

    sub = Submission.objects.create(
        student=student, leader=student.leader, title=title,
        link="https://scratch.mit.edu/projects/1", status=status,
    )
    if said:
        Feedback.objects.create(
            submission=sub, author=student.leader.user, body=said, outcome=status
        )
    return sub


@pytest.fixture
def world(db):
    """One school, two leaders, one student each. The shape Litala's request
    was about: same building, different teacher."""
    from matazim.models import StudyClass

    inst = _institution()
    mine = _leader("ronit@example.com", "רונית", inst)
    theirs = _leader("yossi@example.com", "יוסי", inst)
    StudyClass.objects.create(leader=mine, name="ט1", school_name="עתיד רמלה")
    StudyClass.objects.create(leader=theirs, name="ט2", school_name="עתיד רמלה")
    return {
        "mine": mine,
        "theirs": theirs,
        "my_student": _student("kid1@example.com", "יובל", mine),
        "their_student": _student("kid2@example.com", "נועה", theirs),
    }


# --------------------------------------- the visibility decision, 2026-09-16


def test_a_leader_sees_their_own_students_and_not_the_schools(world):
    """Avi: "מוביל רואה את כל התלמידים הקשורים אליו. לא לפי בית ספר."

    Both students are at עתיד רמלה. The existing tenancy tests put the two
    leaders in different institutions, which is a different seam: this is the
    one Litala actually asked to open, and it stays shut.
    """
    from matazim.access import visible_students

    mine = set(visible_students(world["mine"].user))
    assert world["my_student"] in mine
    assert world["their_student"] not in mine, "a leader read another teacher's student"


def test_the_detail_page_refuses_another_leaders_student(client, world):
    """The same rule where somebody would actually try it: by URL."""
    client.force_login(world["mine"].user)
    resp = client.get(reverse("matazim:student", args=[world["their_student"].pk]))
    assert resp.status_code == 404


def test_work_from_another_leaders_student_is_never_listed(client, world):
    """The new section inherits the rule rather than restating it."""
    _work(world["their_student"], "המשחק של נועה", "waiting", said="יפה מאוד")
    client.force_login(world["mine"].user)
    html = client.get(reverse("matazim:student", args=[world["my_student"].pk])).content.decode()
    assert "המשחק של נועה" not in html


# --------------------------------------- the section the page was missing


def test_the_page_shows_the_work_and_what_was_said(client, world):
    """REQ-M.19, REQ-M.123. The words are on the page, not behind a click."""
    _work(world["my_student"], "המבוך שלי", "returned", said="הבסיס צריך להיות רחב יותר")
    client.force_login(world["mine"].user)
    html = client.get(reverse("matazim:student", args=[world["my_student"].pk])).content.decode()

    assert "העבודות שלהם" in html
    assert "המבוך שלי" in html
    assert "הבסיס צריך להיות רחב יותר" in html


def test_answered_work_stays_on_the_page(client, world):
    """The defect this sprint exists for.

    `waiting_for` holds WAITING only, so before this an approved submission was
    reachable from nowhere. A leader about to certify somebody has to be able
    to look at what they are certifying.
    """
    _work(world["my_student"], "עבודה שאושרה", "approved", said="מצוין")
    client.force_login(world["mine"].user)
    html = client.get(reverse("matazim:student", args=[world["my_student"].pk])).content.decode()
    assert "עבודה שאושרה" in html


def test_every_attempt_is_listed_not_only_the_last(client, world):
    """REQ-M.125. A returned piece and the one answering it are two rows, and
    reading them in order is how somebody sees a teenager get better."""
    _work(world["my_student"], "ניסיון ראשון", "returned", said="עוד קצת")
    _work(world["my_student"], "ניסיון שני", "approved", said="זהו, יפה")
    client.force_login(world["mine"].user)
    html = client.get(reverse("matazim:student", args=[world["my_student"].pk])).content.decode()

    assert "ניסיון ראשון" in html
    assert "ניסיון שני" in html


def test_a_student_with_no_work_says_so_rather_than_showing_nothing(client, world):
    """An empty panel reads as a page that failed to load."""
    client.force_login(world["mine"].user)
    html = client.get(reverse("matazim:student", args=[world["my_student"].pk])).content.decode()
    assert "עוד לא הגישו עבודה" in html
