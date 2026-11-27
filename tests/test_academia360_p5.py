"""Academia360 sprints P.5 and P.6: the coverage list, and replication by model

- /academia360/manage/coverage/ is the admin's: a row per institution with
  what it has, a state (empty / partial / rich), a filter, and the research
  status set in place and logged;
- the same rows through api/admin/coverage/ for the chat, token or admin only;
- `replicate_to --models A,B` sends only those models' rows, and refuses a
  name it does not know, so the committee's work never travels by accident.
"""
import json

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError

from academia360.management.commands import replicate_to
from academia360.models import (
    ChangeLog,
    Distinction,
    Institution,
    ProfileSection,
    Researcher,
    ResearcherMetric,
    Role,
    Unit,
    UnitEnrollment,
)

pytestmark = pytest.mark.django_db
TOKEN = "p5-agent-token-4411"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = TOKEN
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def world(db):
    rich = Institution.objects.create(slug="rich", name_he="מוסד עשיר", kind=Institution.UNIVERSITY, identity="פסקה.",
                                      research_status="imported")
    for i in range(3):
        ProfileSection.objects.create(institution=rich, title=f"קטע {i}", body="טקסט", order=i)
        r = Researcher.objects.create(institution=rich, slug=f"r{i}", name_he=f"חוקר {i}")
        if i == 0:
            ResearcherMetric.objects.create(researcher=r, metric="h_index", value=40)
    partial = Institution.objects.create(slug="partial", name_he="מוסד חלקי", kind=Institution.COLLEGE)
    Researcher.objects.create(institution=partial, slug="p0", name_he="חוקר יחיד")
    Researcher.objects.create(institution=partial, slug="ghost", name_he="כותרת שאינה אדם", verified=False)
    empty = Institution.objects.create(slug="empty", name_he="מוסד ריק", kind=Institution.TEACHER)
    admin = User.objects.create_user("admin@example.com", "admin@example.com", "pw-a360-4411", is_superuser=True,
                                     is_staff=True)
    member = User.objects.create_user("member@example.com", "member@example.com", "pw-a360-4411")
    Role.objects.create(user=member, kind=Role.COMMITTEE_MEMBER)
    return {"rich": rich, "partial": partial, "empty": empty, "admin": admin, "member": member}


def test_the_coverage_page_counts_states_and_filters(client, world):
    assert client.get("/academia360/manage/coverage/").status_code in (302, 403)
    client.force_login(world["member"])
    assert client.get("/academia360/manage/coverage/").status_code in (403, 302)
    client.force_login(world["admin"])
    r = client.get("/academia360/manage/coverage/")
    assert r.status_code == 200
    html = r.content.decode()
    assert "3 מוסדות: 1 ריק, 1 חלקי, 1 עשיר" in html
    rows = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    rich = rows.split('href="/academia360/institutions/rich/"', 1)[1].split("</tr>", 1)[0]
    assert 'a360-state-rich">עשיר' in rich and rich.count('<span class="a360-num">3</span>') == 2  # sections, researchers
    partial = rows.split('href="/academia360/institutions/partial/"', 1)[1].split("</tr>", 1)[0]
    assert 'a360-state-partial">חלקי' in partial and '<span class="a360-num">1</span>' in partial, "the unverified ghost is not counted"
    only_empty = client.get("/academia360/manage/coverage/?state=empty").content.decode()
    assert "/institutions/empty/" in only_empty and "/institutions/rich/" not in only_empty
    assert 'name="research_status"' in only_empty and "לשמור" in only_empty


def test_the_admin_sets_the_research_status_in_place_and_it_is_logged(client, world):
    client.force_login(world["admin"])
    before = ChangeLog.objects.count()
    r = client.post("/academia360/manage/coverage/set/", {"institution": world["empty"].pk, "research_status": "rechecked",
                                                           "research_note": "נבדק ידנית, אין אתר מחקר", "state": "empty"})
    assert r.status_code == 302 and r.url.endswith("/academia360/manage/coverage/?state=empty")
    inst = Institution.objects.get(pk=world["empty"].pk)
    assert inst.research_status == "rechecked" and inst.research_as_of is not None and "ידנית" in inst.research_note
    assert ChangeLog.objects.count() > before and ChangeLog.objects.filter(row_id=str(inst.pk)).exists()
    r = client.post("/academia360/manage/coverage/set/", {"institution": world["empty"].pk, "research_status": "bogus"})
    assert r.status_code == 302 and Institution.objects.get(pk=world["empty"].pk).research_status == "rechecked"
    client.force_login(world["member"])
    r = client.post("/academia360/manage/coverage/set/", {"institution": world["rich"].pk, "research_status": "none"})
    assert r.status_code in (403, 302) and Institution.objects.get(pk=world["rich"].pk).research_status == "imported"


def test_the_api_gives_the_same_rows_to_the_agent(client, world):
    assert client.get("/academia360/api/admin/coverage/").status_code in (401, 403)
    r = client.get("/academia360/api/admin/coverage/", HTTP_AUTHORIZATION="Bearer " + TOKEN)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 3 and body["summary"]["states"] == [["empty", "ריק", 1], ["partial", "חלקי", 1], ["rich", "עשיר", 1]]
    by = {row["slug"]: row for row in body["results"]}
    assert by["rich"]["state"] == "rich" and by["rich"]["with_metrics"] == 1 and by["rich"]["research_status"] == "imported"
    assert by["empty"]["state"] == "empty" and by["empty"]["researchers"] == 0
    r = client.get("/academia360/api/admin/coverage/?state=partial", HTTP_AUTHORIZATION="Bearer " + TOKEN)
    assert [row["slug"] for row in r.json()["results"]] == ["partial"]


def test_replicate_to_models_sends_only_those_rows(world, monkeypatch):
    unit = Unit.objects.create(institution=world["rich"], name="הפקולטה")
    UnitEnrollment.objects.create(unit=unit, students=100)
    Distinction.objects.create(institution=world["rich"], kind="nobel", title="פרס נובל", year=2004)
    sent = []

    def fake_send(self, method, url, payload, content_type):
        rows = json.loads(payload.decode("utf-8")) if payload else []
        sent.extend(r["model"] for r in rows)
        return 200, {"saved": len(rows)}

    monkeypatch.setattr(replicate_to.Command, "send", fake_send)
    call_command("replicate_to", "--base", "https://example.test", "--token", TOKEN, "--rows-only", "--force",
                 "--models", "Institution,Distinction,UnitEnrollment")
    assert set(sent) == {"academia360.institution", "academia360.distinction", "academia360.unitenrollment"}
    assert "academia360.researcher" not in sent and "academia360.profilesection" not in sent
    with pytest.raises(CommandError):
        call_command("replicate_to", "--base", "https://example.test", "--token", TOKEN, "--rows-only", "--models", "Role")
    with pytest.raises(CommandError):
        call_command("replicate_to", "--base", "https://example.test", "--token", TOKEN, "--rows-only", "--models", "Nothing")


def test_the_coverage_rows_cost_a_handful_of_queries_however_rich(django_assert_max_num_queries):
    """Eight Counts on one join multiplied the rows and took 42 s once the
    institutions were filled (production 502); one grouped query per column."""
    from academia360 import coverage
    from academia360.models import Institution, ProfileSection, Researcher
    inst = Institution.objects.create(slug="rich-one", name_he="עשיר", kind=Institution.UNIVERSITY, identity="פסקה")
    for n in range(4):
        ProfileSection.objects.create(institution=inst, title=f"s{n}", body="b")
        Researcher.objects.create(institution=inst, slug=f"r{n}", name_he=f"חוקר {n}")
    with django_assert_max_num_queries(12):
        rows = coverage.rows()
    row = next(r for r in rows if r["slug"] == "rich-one")
    assert row["counts"]["sections"] == 4 and row["counts"]["researchers"] == 4
