"""Every role can find what it needs, and is shown nothing it does not.

SPR-M.24, REQ-M.101 and REQ-M.102. This is the review Avi asked for, kept as a
test rather than left as a one-off pass, because it earned that within minutes:
trimming the navigation orphaned בתי הספר and המסלול השנתי for every signed-in
role, and this caught it on the first run after the change.

Two directions, and they are different failures.

**Can they find it.** Sign in as each role, start at their entry point, and
follow only the links that role can actually see. A screen a role needs but
never reaches by clicking is a screen findable only by knowing the URL, which
this project has now learned four times is a screen nobody uses.

**Are they shown only what is theirs.** The menu is checked against an explicit
map. A leader carrying המסלול שלי is not a permission breach, it is a product
that does not know who is reading it: §4.9 is explicit that a leader is not a
מט״צ, and an adult teacher was being offered a pupil's journey and a
parental-consent panel.
"""

import re

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm24

PASSWORD = "roles-pass-8841"


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


@pytest.fixture
def world(db):
    """One world holding every role at once."""
    from app.models import Course, CourseCertificate, UserVideoProgress, Video
    from matazim.certification import certify
    from matazim.history import record_arrival, set_status
    from matazim.models import EntranceTarget, Leader, MemberProfile, Student

    now = timezone.now()
    courses = {}
    for slug, title, n in (("scratch", "סקראץ׳", 6), ("scratch-advanced", "סקראץ׳ מתקדם", 4)):
        course = Course.objects.create(slug=slug, title=title, is_published=True)
        for i in range(n):
            Video.objects.create(
                course=course, title=f"שיעור {i + 1}", lesson_order=i + 1, bunny_video_id="abc"
            )
        courses[slug] = course
    EntranceTarget.objects.get_or_create(
        target_id="t0000", defaults={"shape": "plate", "title": "לוח", "brief": "בנו."}
    )

    manager = _user("pm@example.com", "נעמי")
    MemberProfile.objects.update_or_create(user=manager, defaults={"is_program_manager": True})

    leader = Leader.objects.create(
        user=_user("leader@example.com", "נעה מורה"), program_manager=manager, approved_at=now
    )
    candidate = Leader.objects.create(
        user=_user("candidate@example.com", "מורה ממתינה"),
        program_manager=manager,
        approved_at=None,
    )

    def member(email, name, passed=True):
        user = _user(email, name)
        MemberProfile.objects.update_or_create(
            user=user,
            defaults={
                "entrance_test_passed_at": now if passed else None,
                "birth_year": now.year - 14,
                "guardian_consent_at": now,
                "welcome_accepted_at": now,
            },
        )
        return user

    member("fresh@example.com", "נועה חדשה", passed=False)
    member("free@example.com", "איתי ברק")

    student = Student.objects.create(user=member("mid@example.com", "מאיה לוי"), leader=leader)
    record_arrival(student, by=student.user)
    set_status(student, Student.IN_TRAINING, by=leader.user)

    done = member("done@example.com", "דניאל אזולאי")
    certified = Student.objects.create(user=done, leader=leader)
    record_arrival(certified, by=done)
    set_status(certified, Student.IN_TRAINING, by=leader.user)
    for slug in ("scratch", "scratch-advanced"):
        for video in courses[slug].videos.all():
            UserVideoProgress.objects.update_or_create(
                user=done,
                video=video,
                defaults={"percent_watched": 100.0, "quiz_passed": True, "completed_at": now},
            )
        CourseCertificate.objects.get_or_create(user=done, course=courses[slug])
    certify(leader.user, certified)

    root = User.objects.create_superuser("root@example.com", "root@example.com", PASSWORD)
    from app.models import UserProfile

    UserProfile.objects.update_or_create(user=root, defaults={"display_name": "אבי"})

    return {"student": student, "leader": leader, "candidate": candidate}


# What each role needs to be able to reach by clicking. Deliberately a list of
# needs rather than of permissions: a leader may open the learning track and has
# no need of it, and not finding it is the correct outcome.
NEEDS = {
    None: ["home", "about", "track", "courses", "schools", "community", "events",
           "entrance_test", "login", "register", "privacy", "terms", "leader_entrance"],
    "fresh@example.com": ["my_path", "entrance_test", "test_lessons", "test_task",
                          "profile", "my_data", "privacy", "terms"],
    "free@example.com": ["my_path", "apply", "profile", "my_data", "privacy", "terms",
                         "learn_course"],
    "mid@example.com": ["my_path", "learn_course", "profile", "my_data", "delete_me",
                        "privacy", "terms", "courses", "community", "events"],
    "done@example.com": ["my_path", "my_certificate", "profile", "my_data", "privacy"],
    "candidate@example.com": ["leader_entrance", "profile", "my_data", "privacy", "terms"],
    "leader@example.com": ["leader_home", "roster", "classes", "profile", "my_data",
                           "privacy", "terms", "community", "events"],
    # REQ-M.114 — appointing a program manager is root's, so `staff_admins` is
    # no longer among her needs. This test caught that the moment the rule
    # changed, which is the whole reason the review was kept as a test.
    "pm@example.com": ["pm_leaders", "cohort", "staff_home",
                       "staff_retention", "staff_targets", "staff_leaders", "profile"],
    "root@example.com": ["pm_leaders", "cohort", "staff_home", "staff_admins", "profile"],
}


def _path_for(name, world):
    special = {
        "learn_course": "/matazim/learn/scratch/",
        "test_lesson": "/matazim/test/lesson/1/",
    }
    return special.get(name) or reverse(f"matazim:{name}")


def _crawl(client, start="/matazim/"):
    seen, queue = set(), [start]
    while queue and len(seen) < 140:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        response = client.get(url, follow=True)
        if response.status_code != 200:
            continue
        for href in re.findall(r'href="([^"]+)"', response.content.decode("utf-8", "replace")):
            href = href.split("#")[0].split("?")[0]
            if href.startswith("/matazim/") and href not in seen:
                queue.append(href)
    return seen


@pytest.mark.parametrize("email", list(NEEDS))
def test_each_role_can_click_its_way_to_everything_it_needs(world, email):
    """T-F-M.24.4-1: REQ-M.101, REQ-M.103, REQ-M.104."""
    client = Client()
    if email:
        assert client.login(username=email, password=PASSWORD), email

    reached = _crawl(client)
    missing = []
    for name in NEEDS[email]:
        path = _path_for(name, world)
        if path not in reached:
            # Reachable through a redirect chain counts: what matters is that a
            # person clicking can get there.
            if client.get(path).status_code != 200 or path not in reached:
                missing.append(f"{name} ({path})")

    assert not missing, (
        f"{email or 'a visitor'} needs these and cannot click to any of them: "
        + ", ".join(missing)
    )


# The menu each role should carry. Checked as URLs rather than labels so a copy
# change does not fail this, and a role change does.
MENU = {
    "mid@example.com": {
        "has": ["my_path", "courses", "entrance_test", "community", "events", "about"],
        "hasnt": ["schools", "leader_home", "pm_leaders", "staff_home", "roster"],
    },
    "leader@example.com": {
        "has": ["leader_home", "roster", "classes", "community", "events", "about"],
        # §4.9 — a leader is not a מט״צ, so a pupil's screens are not theirs.
        "hasnt": ["my_path", "entrance_test", "pm_leaders", "staff_home"],
    },
    "candidate@example.com": {
        # REQ-M.99 — one thing to read, which is what they are waiting for.
        "has": ["leader_entrance", "about"],
        "hasnt": ["my_path", "leader_home", "roster", "entrance_test", "staff_home"],
    },
    "pm@example.com": {
        "has": ["pm_leaders", "cohort", "staff_home", "about"],
        "hasnt": ["my_path", "entrance_test", "roster"],
    },
}


@pytest.mark.parametrize("email", list(MENU))
def test_the_menu_carries_only_what_that_role_needs(world, email):
    """T-F-M.24.4-2: REQ-M.101, REQ-M.102, §4.9.

    Avi: "hide everything this role does not need to see. Make everything on a
    need-to-know basis."
    """
    client = Client()
    assert client.login(username=email, password=PASSWORD)

    html = client.get(reverse("matazim:profile")).content.decode()
    nav = html.split('<nav class="mz-nav"')[1].split("</nav>")[0]

    complaints = []
    for name in MENU[email]["has"]:
        if _path_for(name, world) not in nav:
            complaints.append(f"missing {name}")
    for name in MENU[email]["hasnt"]:
        if _path_for(name, world) in nav:
            complaints.append(f"shows {name}, which this role has no use for")

    assert not complaints, f"{email} menu: " + "; ".join(complaints)


def test_nobody_carries_a_menu_they_have_to_read_past(world):
    """T-F-M.24.4-3: REQ-M.101.

    Eight recruitment items sat on every page for every role, forever. This is
    not a styling rule: a menu that does not change is a menu nobody reads, and
    then the one item that is theirs is as hard to find as the rest.
    """
    fat = {}
    for email in ("mid@example.com", "leader@example.com", "pm@example.com",
                  "candidate@example.com"):
        client = Client()
        client.login(username=email, password=PASSWORD)
        html = client.get(reverse("matazim:profile")).content.decode()
        nav = html.split('<nav class="mz-nav"')[1].split("</nav>")[0]
        count = len(re.findall(r"<a\s", nav))
        if count > 7:
            fat[email] = count

    assert not fat, f"a signed-in role is reading too many menu items: {fat}"
