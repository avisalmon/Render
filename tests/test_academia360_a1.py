"""Academia360 sprint A.1: the skeleton and the three circles
(docs/academia360/backlog.md A.1; spec 1.3, 2.3, 3, 4.9, 4.10; Rules 2, 3, 6).

What is proven here:
- the pilot banner is on every page, every role, including error pages;
- the app has its own frame and no link out of it;
- every model has a route on the API (Rule 6), and the API root names them;
- each circle wall is crossed and refused: anonymous reads public rows only,
  a leader of A never reads a row of B, committee-circle rows need the
  committee, a person reads their own role rows and nobody else's;
- writes are the admin's, and every write lands in the ChangeLog with who;
- every class the templates use is defined in the stylesheet (mistake 13);
- the key is blanked from the first test (mistake 26), before any AI exists.
"""

import re
from pathlib import Path

import pytest
from django.contrib.auth.models import User

from academia360 import access
from academia360.api import ROUTES
from academia360.models import (
    ChangeLog,
    Criterion,
    Institution,
    LeaderOf,
    Program,
    Researcher,
    Role,
)

pytestmark = pytest.mark.django_db

BANNER = "אתר פיילוט שנבנה על ידי אבי סלמון"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = ""


@pytest.fixture
def world(db):
    program = Program.objects.create(slug="academia-360", name="אקדמיה 360", body="ות״ת", year_from=2024, year_to=2028)
    for i, (slug, name, colour) in enumerate([
        ("innovation", "חדשנות בהוראה", "#63BAC5"), ("employability", "תעסוקתיות", "#F6C21A"),
        ("community", "חברה וקהילה", "#EE6B67"), ("institutional", "מדיניות מוסדית", "#8FC457"),
        ("measurement", "מדידה והערכה", "#323435"),
    ]):
        Criterion.objects.create(program=program, slug=slug, name=name, order=i, colour=colour)
    a = Institution.objects.create(slug="technion", name_he="הטכניון – מכון טכנולוגי לישראל", short_name_he="הטכניון",
                                   name_en="Technion", kind=Institution.UNIVERSITY, city="חיפה", founded=1912)
    b = Institution.objects.create(slug="sapir", name_he="המכללה האקדמית ספיר", kind=Institution.COLLEGE)
    Researcher.objects.create(institution=a, slug="mannor", name_he="שי מנור", title="פרופ׳", is_leading=True)

    def person(name, **flags):
        return User.objects.create_user(name, f"{name}@example.com", "pw-a360-4410", **flags)

    users = {
        "visitor": person("visitor"),
        "leader_a": person("leader_a"), "leader_b": person("leader_b"),
        "member": person("member"), "chair": person("chair"),
        "admin": person("admin"), "avi": person("avi", is_superuser=True, is_staff=True),
    }
    Role.objects.create(user=users["leader_a"], kind=Role.LEADER)
    Role.objects.create(user=users["leader_b"], kind=Role.LEADER)
    Role.objects.create(user=users["member"], kind=Role.COMMITTEE_MEMBER)
    Role.objects.create(user=users["chair"], kind=Role.COMMITTEE_MEMBER)
    Role.objects.create(user=users["admin"], kind=Role.ADMIN)
    LeaderOf.objects.create(user=users["leader_a"], institution=a, title="סגנית נשיא")
    LeaderOf.objects.create(user=users["leader_b"], institution=b)
    from academia360.models import CommitteeAttribute
    CommitteeAttribute.objects.create(user=users["chair"], kind=CommitteeAttribute.CHAIR, program=program)
    return {"program": program, "a": a, "b": b, **users}


# ------------------------------------------------------------ the frame

PAGES = ["/academia360/", "/academia360/institutions/", "/academia360/institutions/technion/",
         "/academia360/login/", "/academia360/no-access/", "/academia360/nothing-here/"]


def test_the_pilot_banner_is_on_every_page_for_everyone(client, world):
    for who in (None, world["visitor"], world["leader_a"], world["member"], world["avi"]):
        if who:
            client.force_login(who)
        else:
            client.logout()
        for path in PAGES:
            body = client.get(path, follow=True).content.decode()  # login sends a signed-in person home
            banner = re.search(r'<div class="a360-pilot"[^>]*>(.*?)</div>', body, re.S)
            assert banner and BANNER in banner.group(1), (who, path)


def test_the_banner_cannot_be_dismissed():
    html = Path("templates/academia360/base.html").read_text(encoding="utf-8")
    banner = re.search(r'<div class="a360-pilot"[^>]*>', html).group(0)
    assert "hidden" not in banner and "<button" not in html.split("a360-pilot")[1].split("</div>")[0]
    js = Path("static/academia360/a360.js").read_text(encoding="utf-8")
    assert "a360-pilot" not in js


def test_its_own_frame_and_no_link_out(client, world):
    for path in PAGES[:5]:
        body = client.get(path).content.decode()
        assert "base.html" not in body or "academia360/base.html" in body
        assert 'href="/"' not in body and "babook.co.il" not in body
        outside = [h for h in re.findall(r'href="([^"]+)"', body)
                   if h.startswith("/") and not h.startswith(("/academia360/", "/static/", "/accounts/google/"))]
        assert outside == [], (path, outside)


def test_errors_stay_inside_the_app(client, world):
    r = client.get("/academia360/nothing-here/")
    assert r.status_code == 404
    body = r.content.decode()
    assert "a360-pilot" in body and "העמוד לא נמצא" in body


def test_the_home_page_shows_the_program_and_every_institution(client, world):
    body = client.get("/academia360/").content.decode()
    assert "לחשוב מחדש על התואר הראשון" in body
    main = body.split("<main", 1)[1]
    assert 'href="/academia360/institutions/technion/"' in main
    assert 'href="/academia360/institutions/sapir/"' in main
    for c in Criterion.objects.all():
        assert c.name in main


def test_the_institution_page_reads_its_rows(client, world):
    body = client.get("/academia360/institutions/technion/").content.decode()
    main = body.split("<main", 1)[1]
    assert "הטכניון – מכון טכנולוגי לישראל" in main and "שי מנור" in main
    assert 'dir="auto"' in main
    assert client.get("/academia360/institutions/nowhere/").status_code == 404


def test_every_class_used_is_defined(world):
    css = Path("static/academia360/a360.css").read_text(encoding="utf-8")
    defined = set(re.findall(r"\.(a360-[a-z0-9_-]+)", css))
    used = set()
    for path in Path("templates/academia360").rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        for classes in re.findall(r'class="([^"]+)"', text):
            used |= {c for c in re.sub(r"\{[%{].*?[%}]\}", " ", classes).split() if c.startswith("a360-")}
    # The ring segments are numbered by a loop (the prefix is left after the
    # tag is stripped); the first needs no offset; `a360` marks the body.
    allowed_unstyled = {"a360-ring-seg", "a360-ring-seg-", "a360-ring-seg-1", "a360-step-", "a360", "a360-js"}
    assert used - defined <= allowed_unstyled, sorted(used - defined - allowed_unstyled)


def test_every_css_variable_is_defined():
    css = Path("static/academia360/a360.css").read_text(encoding="utf-8")
    defined = set(re.findall(r"(--a360-[a-z0-9-]+)\s*:", css))
    used = set(re.findall(r"var\((--a360-[a-z0-9-]+)\)", css))
    assert used <= defined, sorted(used - defined)


# ---------------------------------------------------------- sign in

def test_sign_in_by_email_lands_inside_and_next_cannot_leave(client, world):
    r = client.post("/academia360/login/", {"username": "leader_a@example.com", "password": "pw-a360-4410",
                                            "next": "/books/"})
    assert r.status_code == 302 and r.url == "/academia360/"
    client.logout()
    r = client.post("/academia360/login/", {"username": "leader_a@example.com", "password": "pw-a360-4410",
                                            "next": "/academia360/institutions/"})
    assert r.url == "/academia360/institutions/"
    r = client.post("/academia360/logout/")
    assert r.status_code == 302 and r.url.startswith("/academia360/")


# ---------------------------------------------------------- the API (Rule 6)

def test_every_model_has_a_route_and_the_root_names_it(client, world):
    from django.apps import apps
    routed = {m for _p, _v, m in ROUTES}
    assert set(apps.get_app_config("academia360").get_models()) == routed
    root = client.get("/academia360/api/").json()
    assert set(root) == {p for p, _v, _m in ROUTES}
    assert {"institutions", "roles", "researchers", "programs", "changelogs"} <= set(root)


def test_anonymous_reads_public_rows_only(client, world):
    assert client.get("/academia360/api/institutions/").status_code == 200
    names = [r["slug"] for r in client.get("/academia360/api/institutions/").json()]
    assert names == ["technion", "sapir"] or set(names) == {"technion", "sapir"}
    for closed in ("roles", "leaderofs", "changelogs", "invitations", "committeeattributes"):
        assert client.get(f"/academia360/api/{closed}/").status_code in (401, 403), closed  # closed either way
    # A signed-in member of the public is still the public.
    client.force_login(world["visitor"])
    assert client.get("/academia360/api/roles/").json() == []
    assert client.get("/academia360/api/leaderofs/").json() == []
    assert client.get("/academia360/api/invitations/").json() == []


def test_a_leader_sees_own_institution_rows_and_never_another(client, world):
    client.force_login(world["leader_a"])
    mine = client.get("/academia360/api/leaderofs/").json()
    assert [r["institution"] for r in mine] == [world["a"].pk]
    other = LeaderOf.objects.get(user=world["leader_b"])
    assert client.get(f"/academia360/api/leaderofs/{other.pk}/").status_code == 404
    # Own role rows, not others'.
    assert {r["user"] for r in client.get("/academia360/api/roles/").json()} == {world["leader_a"].pk}
    # Public knowledge of every institution is open to a leader too.
    assert client.get("/academia360/api/institutions/sapir/").status_code == 404  # lookup is pk, not slug
    assert client.get(f"/academia360/api/institutions/{world['b'].pk}/").status_code == 200


def test_committee_sees_everything(client, world):
    client.force_login(world["member"])
    assert len(client.get("/academia360/api/leaderofs/").json()) == 2
    assert len(client.get("/academia360/api/roles/").json()) == Role.objects.count()


def test_writes_are_the_admins_and_land_in_the_changelog(client, world):
    row = {"slug": "haifa", "name_he": "אוניברסיטת חיפה", "kind": "university"}
    for who in (world["visitor"], world["leader_a"], world["member"], world["chair"]):
        client.force_login(who)
        assert client.post("/academia360/api/institutions/", row).status_code == 403, who
        assert client.patch(f"/academia360/api/institutions/{world['a'].pk}/", {"city": "x"},
                            content_type="application/json").status_code == 403, who
    client.force_login(world["admin"])
    r = client.post("/academia360/api/institutions/", row)
    assert r.status_code == 201
    pk = r.json()["id"]
    assert client.patch(f"/academia360/api/institutions/{pk}/", {"city": "חיפה"},
                        content_type="application/json").status_code == 200
    assert client.delete(f"/academia360/api/institutions/{pk}/").status_code == 204
    log = list(ChangeLog.objects.filter(model="academia360.Institution", row_id=str(pk)).order_by("created_at"))
    assert [(c.field, c.new or c.old) for c in log] == [("", "created"), ("city", "חיפה"), ("", "deleted")]
    assert all(c.by == world["admin"] and c.actor_kind == ChangeLog.PERSON for c in log)
    client.logout()
    assert client.get("/academia360/api/institutions/", {"slug": "haifa"}).status_code == 200


def test_a_superuser_is_the_admin_and_a_chair_is_not(world):
    assert access.is_admin(world["avi"]) and access.is_committee(world["avi"]) and access.is_chair(world["avi"])
    assert access.is_chair(world["chair"]) and not access.is_admin(world["chair"])
    assert access.is_committee(world["member"]) and not access.is_chair(world["member"])
    assert access.circle(world["leader_a"]) == "institution"
    assert access.circle(world["visitor"]) == "public"
    assert access.leader_institution_ids(world["leader_a"]) == {world["a"].pk}


def test_the_higher_role_wins(client, world):
    """A committee member who also leads an institution sees every
    institution's rows (spec 2.6.1)."""
    Role.objects.create(user=world["leader_a"], kind=Role.COMMITTEE_MEMBER)
    client.force_login(world["leader_a"])
    assert len(client.get("/academia360/api/leaderofs/").json()) == 2


def test_an_inactive_role_counts_for_nothing(client, world):
    Role.objects.filter(user=world["member"]).update(active=False)
    client.force_login(world["member"])
    assert client.get("/academia360/api/leaderofs/").json() == []


def test_the_registry_knows_the_app():
    from app.portal import APPS, NOT_IN_THE_PORTAL
    assert "academia360" in NOT_IN_THE_PORTAL or any(a.slug == "academia360" for a in APPS)
