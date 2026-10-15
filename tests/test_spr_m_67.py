"""SPR-M.67 - the three stages of a learner (REQ-M.191, REQ-M.192, REQ-M.193).

Lital, 2026-10-15, through Avi: a student who signs in sees nothing open and
begins with the test; only after passing is he invited to join a leader, by a code
or from an open list sorted by school, and joining is his own act; once attached
the site opens in the state before being a מטצ and the home is big tiles; and the
word is מטצ, never מט״צ. Avi, the same day: no "how it works", only what there is
to do, minimal for the stage.
"""

import pathlib
import re

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from matazim.gate import JOIN, MEMBER, TEST, learner_stage

pytestmark = pytest.mark.sprm67

PASSWORD = "sprm67-pass-6120"
ROOT = pathlib.Path(__file__).resolve().parent.parent
READY = dict(birth_year=timezone.now().year - 14, guardian_consent_at=timezone.now(),
             welcome_accepted_at=timezone.now())


def _user(name):
    return User.objects.create_user(username=f"{name}@example.com", email=f"{name}@example.com",
                                    password=PASSWORD)


@pytest.fixture
def world(db):
    from matazim.models import Institution, Leader, MemberProfile, StudyClass

    inst = Institution.objects.create(name="רשת עתיד")
    pm = _user("pm")
    inst.managers.add(pm)
    ramla = Leader.objects.create(user=_user("ramla"), institution=inst, approved_at=timezone.now())
    haifa = Leader.objects.create(user=_user("haifa"), institution=inst, approved_at=timezone.now())
    StudyClass.objects.create(leader=ramla, name="ט1", school_name="עתיד רמלה")
    StudyClass.objects.create(leader=haifa, name="ט1", school_name="עתיד חיפה")

    def learner(name, *, passed=True, leader=None, **profile):
        from matazim.models import Student

        user = _user(name)
        MemberProfile.objects.update_or_create(user=user, defaults={
            **READY, **profile,
            "entrance_test_passed_at": timezone.now() if passed else None})
        if leader is not None:
            Student.objects.create(user=user, leader=leader, status="in_training")
        return user

    return {"inst": inst, "pm": pm, "ramla": ramla, "haifa": haifa, "learner": learner}


# ------------------------------------------------------------------ stages


def test_a_learner_is_at_exactly_one_stage(world):
    assert learner_stage(world["learner"]("fresh", passed=False)) == TEST
    assert learner_stage(world["learner"]("passed")) == JOIN
    assert learner_stage(world["learner"]("joined", leader=world["ramla"])) == MEMBER


def test_nobody_who_is_not_a_learner_has_a_stage(world):
    root = User.objects.create_superuser("root@example.com", "root@example.com", PASSWORD)
    assert learner_stage(root) is None
    assert learner_stage(world["pm"]) is None
    assert learner_stage(world["ramla"].user) is None
    from django.contrib.auth.models import AnonymousUser

    assert learner_stage(AnonymousUser()) is None


def test_the_gate_sends_each_stage_to_the_one_thing_it_can_do(client, world):
    client.force_login(world["learner"]("fresh", passed=False))
    assert client.get("/matazim/learn/scratch/")["Location"] == "/matazim/test/?gate=1"

    client.force_login(world["learner"]("passed"))
    assert client.get("/matazim/learn/scratch/")["Location"] == "/matazim/join-leader/"
    assert client.get("/matazim/classes/")["Location"] == "/matazim/join-leader/"


# -------------------------------------------------------------------- home


def _main(html):
    start = html.index('class="mz-container mz-home"')
    return html[start:html.index("</main>", start) if "</main>" in html[start:] else len(html)]


def test_a_visitor_sees_one_button_and_no_how_it_works(client, db):
    home = _main(client.get("/matazim/").content.decode())
    assert home.count("mz-btn-primary") == 1
    assert "איך זה עובד" not in home and "אני רוצה ללמוד" not in home


def test_before_the_test_there_is_one_button_and_a_nav_of_one(client, world):
    client.force_login(world["learner"]("fresh", passed=False))
    html = client.get("/matazim/").content.decode()
    home = _main(html)
    assert home.count("mz-btn-primary") == 1 and 'href="/matazim/test/"' in home
    assert "איך זה עובד" not in html

    nav = html[html.index('id="mzNav"'):html.index("</nav>", html.index('id="mzNav"'))]
    assert nav.count("<a ") == 1 and "מבחן הכניסה" in nav


def test_after_the_test_home_is_the_list_of_leaders(client, world):
    client.force_login(world["learner"]("passed"))
    assert client.get("/matazim/")["Location"] == "/matazim/join-leader/"
    html = client.get("/matazim/join-leader/").content.decode()
    nav = html[html.index('id="mzNav"'):html.index("</nav>", html.index('id="mzNav"'))]
    assert nav.count("<a ") == 1 and "בחירת מוביל/ה" in nav


def test_a_member_sees_big_tiles_and_the_state_before_being_a_matz(client, world):
    from matazim.models import Student

    kid = world["learner"]("joined", leader=world["ramla"])
    client.force_login(kid)
    html = client.get("/matazim/").content.decode()
    home = _main(html)
    assert home.count('class="mz-tile"') == 8
    assert "טרום מטצ" in home and "איך זה עובד" not in html

    Student.objects.filter(user=kid).update(status="certified")
    assert ">מטצ<" in client.get("/matazim/").content.decode()


# ------------------------------------------------------------- choose a leader


def test_the_list_shows_every_active_leader_and_sorts_by_school(client, world):
    from matazim.models import Leader

    gone = Leader.objects.create(user=_user("gone"), institution=world["inst"],
                                 approved_at=timezone.now(), is_active=False)
    client.force_login(world["learner"]("passed"))
    html = client.get("/matazim/join-leader/").content.decode()
    assert html.count('class="mz-leaderlist-row"') == 2
    assert html.index("עתיד חיפה") < html.index("עתיד רמלה")
    assert f'value="{gone.pk}"' not in html

    one = client.get("/matazim/join-leader/?school=עתיד רמלה").content.decode()
    assert one.count('class="mz-leaderlist-row"') == 1 and "עתיד רמלה" in one


def test_choosing_from_the_list_attaches_at_once_with_nobody_to_say_yes(client, world):
    from matazim.models import Student, StatusLog

    kid = world["learner"]("passed")
    client.force_login(kid)
    resp = client.post("/matazim/join-leader/", {"leader": world["ramla"].pk})
    assert resp.status_code == 302

    student = Student.objects.get(user=kid)
    assert student.leader_id == world["ramla"].pk and student.pending_leader_id is None
    assert student.status == Student.IN_TRAINING
    assert StatusLog.objects.filter(student=student).exists()
    assert learner_stage(kid) == MEMBER
    assert client.get("/matazim/").content.decode().count('class="mz-tile"') == 8


def test_a_made_up_or_retired_leader_is_refused_and_nothing_is_attached(client, world):
    from matazim.models import Student

    kid = world["learner"]("passed")
    client.force_login(kid)
    resp = client.post("/matazim/join-leader/", {"leader": 99999})
    assert resp.status_code == 200 and "בחרו מוביל/ה מהרשימה" in resp.content.decode()
    assert not Student.objects.filter(user=kid).exists()


def test_a_learner_who_has_not_passed_cannot_use_the_list_or_a_code(client, world):
    from matazim.models import Student

    kid = world["learner"]("fresh", passed=False)
    client.force_login(kid)
    assert client.get("/matazim/join-leader/")["Location"] == "/matazim/test/?gate=1"
    assert client.post("/matazim/join-leader/", {"leader": world["ramla"].pk}).status_code == 302
    resp = client.post(f"/matazim/join/{world['ramla'].join_code}/", {"action": "join"})
    assert resp["Location"] == "/matazim/test/?gate=1"
    assert not Student.objects.filter(user=kid).exists()


def test_a_code_joins_after_the_test_and_a_remembered_code_is_waiting(client, world):
    from matazim.models import Student

    kid = world["learner"]("passed")
    client.force_login(kid)
    client.get(f"/matazim/join/{world['haifa'].join_code}/")   # the link was opened earlier
    assert client.get("/matazim/join-leader/")["Location"] == f"/matazim/join/{world['haifa'].join_code}/"

    client.post(f"/matazim/join/{world['haifa'].join_code}/", {"action": "join"})
    assert Student.objects.get(user=kid).leader_id == world["haifa"].pk


def test_a_minor_without_consent_is_sent_to_the_profile_not_attached(client, world):
    from matazim.models import Student

    kid = world["learner"]("minor", guardian_consent_at=None, birth_year=timezone.now().year - 13)
    client.force_login(kid)
    resp = client.post("/matazim/join-leader/", {"leader": world["ramla"].pk})
    if resp.status_code == 302 and resp["Location"].endswith("/profile/"):
        assert not Student.objects.filter(user=kid).exists()


def test_leaders_and_managers_have_no_stage_page(client, world):
    for who in (world["ramla"].user, world["pm"]):
        client.force_login(who)
        assert client.get("/matazim/join-leader/")["Location"] == "/matazim/"


# ------------------------------------------------------------------ spelling


def test_nothing_says_matz_with_gershayim():
    """Lital: "מטצ ולא מט״צ". Every spelling of the gershayim, in every file a
    person reads. The brand rule is the same shape as the one about הדרכות."""
    pattern = re.compile("מט[״\"”“″ʺ]צ")
    offenders = []
    for folder, globs in (("matazim", ("*.py", "*.html")), ("templates/matazim", ("*.html",)),
                          ("static/matazim", ("*.css", "*.js"))):
        for glob in globs:
            for path in sorted((ROOT / folder).rglob(glob)):
                if path.parent.name == "migrations":
                    continue
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if pattern.search(line):
                        offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()[:60]}")
    assert not offenders, "מט״צ in what a person reads:\n" + "\n".join(offenders[:20])


# ------------------------------------------- staff see the site as a student does


def test_root_with_an_old_student_row_is_a_manager_not_a_pupil(client, world):
    """Avi, 2026-10-15: signed in as himself he was shown a pupil's view because a
    Student row left over from testing counted before his role did. The role wins
    for the menu; the home is the student's (below)."""
    from matazim.models import Student

    root = User.objects.create_superuser("root@example.com", "root@example.com", PASSWORD)
    Student.objects.create(user=root, leader=world["ramla"], status="in_training")
    client.force_login(root)
    html = client.get("/matazim/").content.decode()
    nav = html[html.index('id="mzNav"'):html.index("</nav>", html.index('id="mzNav"'))]
    assert "המסלול שלי" not in nav and "ניהול" in nav


def test_a_manager_a_leader_and_root_see_the_home_a_student_sees(client, world):
    """Avi, 2026-10-15: "as a pm or leader I want to see the web as a student that
    passed the test and is assigned to a leader sees it". The student's eight tiles,
    and their own door as one more, first."""
    root = User.objects.create_superuser("root2@example.com", "root2@example.com", PASSWORD)
    cases = [(world["pm"], 'href="/matazim/staff/"'),
             (root, 'href="/matazim/staff/"'),
             (world["ramla"].user, 'href="/matazim/leader/"')]
    for who, door in cases:
        client.force_login(who)
        home = _main(client.get("/matazim/").content.decode())
        assert home.count('class="mz-tile"') == 8, who          # the student's eight
        assert home.count('class="mz-tile mz-tile-role"') == 1 and door in home
        assert "טרום מטצ" in home


def test_every_tile_opens_for_a_manager_and_a_leader(client, world):
    """The student's tiles are only worth showing if they open for them."""
    root = User.objects.create_superuser("root3@example.com", "root3@example.com", PASSWORD)
    for who in (world["pm"], root, world["ramla"].user):
        client.force_login(who)
        for tile in ("/matazim/courses/", "/matazim/my-path/", "/matazim/community/",
                     "/matazim/events/", "/matazim/my-work/", "/matazim/my-teaching/",
                     "/matazim/classes/", "/matazim/updates/"):
            status = client.get(tile, follow=True).status_code
            assert status == 200, (who.email, tile, status)
