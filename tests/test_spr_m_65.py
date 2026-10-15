"""SPR-M.65 - what changed, and the stages of the year (REQ-M.184, M.185, M.181, M.190).

Atid's list for the site: "עדכון שינויים באתר", "הוספת תכנים", and a site that is
easier to follow in its order. What these tests protect: a note posted by the
team rings the bell of the people it is for and nobody else's, only a program
manager writes, the list and the home banner carry the same words (the bell is
never the only telling), the team can say which stage each הדרכה is for, cards
are laid out in the year's order, and the schedule reads month by month.
"""

import importlib

import pytest
from django.apps import apps as real_apps
from django.contrib.auth.models import User
from django.utils import timezone

from tests.test_spr_m_51 import _course

pytestmark = pytest.mark.sprm65

PASSWORD = "sprm65-pass-8841"


def _user(name):
    return User.objects.create_user(username=f"{name}@example.com", email=f"{name}@example.com",
                                    password=PASSWORD)


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, MemberProfile, Student

    inst = Institution.objects.create(name="רשת עתיד")
    pm = _user("pm")
    inst.managers.add(pm)
    leader = Leader.objects.create(user=_user("leader"), institution=inst,
                                   approved_at=timezone.now())
    kid = _user("kid")
    MemberProfile.objects.update_or_create(user=kid, defaults={
        "birth_year": timezone.now().year - 14, "guardian_consent_at": timezone.now(),
        "welcome_accepted_at": timezone.now(), "entrance_test_passed_at": timezone.now()})
    Student.objects.create(user=kid, leader=leader, status="in_training")

    other = Institution.objects.create(name="רשת אחרת")
    other_leader = Leader.objects.create(user=_user("otherleader"), institution=other,
                                         approved_at=timezone.now())
    stranger = _user("stranger")
    MemberProfile.objects.update_or_create(user=stranger, defaults={
        "birth_year": timezone.now().year - 14, "guardian_consent_at": timezone.now(),
        "welcome_accepted_at": timezone.now(), "entrance_test_passed_at": timezone.now()})
    Student.objects.create(user=stranger, leader=other_leader, status="in_training")
    return {"inst": inst, "pm": pm, "leader": leader, "kid": kid, "stranger": stranger}


def _post(client, world, **extra):
    client.force_login(world["pm"])
    return client.post("/matazim/staff/updates/", {"title": "נוסף לוח השנה", "body": "ראו למעלה",
                                                   **extra})


# ---------------------------------------------------------------- updates


def test_posting_rings_the_bell_of_the_people_it_is_for_and_nobody_elses(client, world):
    from matazim.models import Notification, SiteUpdate

    assert _post(client, world).status_code == 302
    row = SiteUpdate.objects.get(title="נוסף לוח השנה")
    assert row.institution_id == world["inst"].pk and row.posted_by_id == world["pm"].pk

    rung = lambda user: Notification.objects.filter(user=user, kind=Notification.SITE_UPDATE)
    assert rung(world["kid"]).count() == 1 and rung(world["leader"].user).count() == 1
    assert rung(world["stranger"]).count() == 0   # another institution
    assert rung(world["pm"]).count() == 0         # telling somebody about their own act is noise
    assert rung(world["kid"]).get().url == "/matazim/updates/"


def test_only_a_program_manager_writes_a_note(client, world):
    from matazim.models import SiteUpdate

    for who in (world["leader"].user, world["kid"]):
        client.force_login(who)
        assert client.post("/matazim/staff/updates/", {"title": "x"}).status_code == 403
    assert not SiteUpdate.objects.exists()


def test_a_note_can_be_fixed_and_removed_by_its_own_manager_only(client, world):
    from matazim.models import Institution, SiteUpdate

    _post(client, world)
    row = SiteUpdate.objects.get()

    client.post(f"/matazim/staff/updates/{row.pk}/edit/", {"title": "תוקן", "body": "", "pinned": "on"})
    row.refresh_from_db()
    assert row.title == "תוקן" and row.pinned

    other = Institution.objects.create(name="עוד רשת")
    other_pm = _user("otherpm")
    other.managers.add(other_pm)
    client.force_login(other_pm)
    assert client.post(f"/matazim/staff/updates/{row.pk}/delete/").status_code == 404
    assert SiteUpdate.objects.filter(pk=row.pk).exists()

    client.force_login(world["pm"])
    client.post(f"/matazim/staff/updates/{row.pk}/delete/")
    assert not SiteUpdate.objects.filter(pk=row.pk).exists()


def test_the_list_and_the_banner_carry_the_same_words_as_the_bell(client, world):
    _post(client, world)
    client.force_login(world["kid"])

    listing = client.get("/matazim/updates/").content.decode()
    assert "נוסף לוח השנה" in listing and "ראו למעלה" in listing

    home = client.get("/matazim/").content.decode()
    start = home.index('class="mz-year-banner"')
    banner = home[start:home.index("</aside>", start)]
    assert "נוסף לוח השנה" in banner and 'href="/matazim/updates/"' in banner


def test_a_member_does_not_read_another_institutions_notes(client, world):
    _post(client, world)
    client.force_login(world["stranger"])
    assert "נוסף לוח השנה" not in client.get("/matazim/updates/").content.decode()


def test_the_api_writes_for_managers_only_and_posting_rings_the_bell(client, world):
    from matazim.models import Notification

    payload = {"title": "דרך ה-API"}
    client.force_login(world["kid"])
    assert client.post("/matazim/api/site-updates/", payload).status_code == 403

    client.force_login(world["pm"])
    resp = client.post("/matazim/api/site-updates/", {**payload, "institution": 999})
    assert resp.status_code == 201, resp.content
    assert Notification.objects.filter(user=world["kid"], kind=Notification.SITE_UPDATE).exists()


# ----------------------------------------------------------------- stages


def test_the_stage_order_is_scratch_then_3d_then_electives_then_unstaged(world):
    from matazim.models import OfferedCourse
    from matazim.stages import annotate

    OfferedCourse.objects.all().delete()
    OfferedCourse.objects.create(slug="python", stage="elective")
    OfferedCourse.objects.create(slug="tinkercad", stage="3d")
    OfferedCourse.objects.create(slug="arduino")  # no stage
    cards = [{"slug": s} for s in ("arduino", "python", "tinkercad", "scratch-advanced", "scratch")]

    ordered = annotate(cards)
    assert [c["slug"] for c in ordered] == [
        "scratch-advanced", "scratch", "tinkercad", "python", "arduino"]
    assert ordered[0]["stage_label"] == "Scratch"        # required means Scratch by definition
    assert ordered[2]["stage_label"] == "תלת־ממד"
    assert ordered[-1]["stage_label"] == ""


def test_the_team_sets_a_stage_and_only_root_may(client, world):
    from matazim.models import OfferedCourse

    _course("tinkercad")
    OfferedCourse.objects.update_or_create(slug="tinkercad", defaults={"is_active": True, "stage": ""})

    client.force_login(world["pm"])
    assert client.post("/matazim/staff/offered/", {
        "slug": "tinkercad", "action": "stage", "stage": "3d"}).status_code == 403

    root = User.objects.create_superuser("root@example.com", "root@example.com", PASSWORD)
    client.force_login(root)
    client.post("/matazim/staff/offered/", {"slug": "tinkercad", "action": "stage", "stage": "3d"})
    assert OfferedCourse.objects.get(slug="tinkercad").stage == "3d"

    client.post("/matazim/staff/offered/", {"slug": "tinkercad", "action": "stage", "stage": "bogus"})
    assert OfferedCourse.objects.get(slug="tinkercad").stage == "3d"   # a made-up stage is not stored


def test_a_course_card_says_its_stage(client, world):
    _course("scratch")
    client.force_login(world["kid"])
    html = client.get("/matazim/courses/").content.decode()
    start = html.index('class="mz-course')
    card = html[start:html.index("</li>", start)]
    assert 'class="mz-course-stage">Scratch<' in card


def test_the_migration_stages_what_it_knows_and_never_overwrites_a_choice(db):
    from matazim.models import OfferedCourse

    mod = importlib.import_module("matazim.migrations.0042_stages_and_site_updates")
    OfferedCourse.objects.all().delete()
    OfferedCourse.objects.create(slug="scratch")
    OfferedCourse.objects.create(slug="fusion360")
    OfferedCourse.objects.create(slug="tinkercad", stage="elective")  # the team chose
    OfferedCourse.objects.create(slug="python")

    mod.default_stages(real_apps, None)

    stages = dict(OfferedCourse.objects.values_list("slug", "stage"))
    assert stages == {"scratch": "scratch", "fusion360": "3d", "tinkercad": "elective", "python": ""}


# ------------------------------------------------------------ month by month


def test_the_schedule_reads_month_by_month(client, world):
    from tests.test_spr_m_63 import _seed

    _seed()
    client.force_login(world["kid"])
    html = client.get("/matazim/track/").content.decode()
    start = html.index('id="mzYear"')
    block = html[start:html.index("</section>", start)]
    months = block.count('class="mz-year-month"')
    assert months == 6           # Sep, Oct, Nov, Dec, Feb, May
    assert "מה קורה בכל חודש" in block
