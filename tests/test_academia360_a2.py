"""Academia360 sprint A.2: the program side and the import
(docs/academia360/backlog.md A.2; data model sections 4 to 10).

Proven here:
- the institution circle on submitted material: a leader of A reads and
  writes A's package and never B's, and a planted row is rolled back;
- the committee reads everything, writes its own work, and only a chair
  decides, sends a letter or accepts a correction;
- a letter is invisible to the institution until it is sent, then visible;
- the mandatory KPI definitions are public, the institutional ones are not;
- a submitted file is never under the public media folder and is served
  only to those who may see its submission, with an access log row;
- the import runs twice and the second run changes nothing, a person's edit
  survives it, and the real reference (when present on this machine) loads.
"""

import shutil
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from academia360.management.commands.import_reference import DEFAULT_ROOT
from academia360.models import (
    AcademicYear,
    AccessLog,
    ChangeLog,
    CommitteeAttribute,
    Criterion,
    Decision,
    Institution,
    KpiDefinition,
    LeaderOf,
    Participation,
    Program,
    ResponseLetter,
    Role,
    Submission,
    SubmittedFile,
)

pytestmark = pytest.mark.django_db
MINI = Path(__file__).parent / "fixtures" / "academia360_mini"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = ""
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def world(db):
    program = Program.objects.create(slug="academia-360", name="אקדמיה 360")
    year = AcademicYear.objects.create(program=program, hebrew_name="תשפ״ה", gregorian_from=2024, gregorian_to=2025)
    Criterion.objects.create(program=program, slug="innovation", name="חדשנות בהוראה", colour="#63BAC5")
    a = Institution.objects.create(slug="a", name_he="מוסד א", kind=Institution.UNIVERSITY)
    b = Institution.objects.create(slug="b", name_he="מוסד ב", kind=Institution.COLLEGE)
    pa = Participation.objects.create(program=program, institution=a, applied=True, status="submitted")
    pb = Participation.objects.create(program=program, institution=b, applied=True, status="submitted")
    sa = Submission.objects.create(participation=pa, kind="proposal", status="submitted", academic_year=year)
    sb = Submission.objects.create(participation=pb, kind="proposal", status="submitted", academic_year=year)

    def person(name, **flags):
        return User.objects.create_user(name, f"{name}@example.com", "pw-a360-4410", **flags)

    u = {k: person(k) for k in ("visitor", "leader_a", "leader_b", "member", "chair", "admin")}
    Role.objects.create(user=u["leader_a"], kind=Role.LEADER)
    Role.objects.create(user=u["leader_b"], kind=Role.LEADER)
    Role.objects.create(user=u["member"], kind=Role.COMMITTEE_MEMBER)
    Role.objects.create(user=u["chair"], kind=Role.COMMITTEE_MEMBER)
    Role.objects.create(user=u["admin"], kind=Role.ADMIN)
    LeaderOf.objects.create(user=u["leader_a"], institution=a)
    LeaderOf.objects.create(user=u["leader_b"], institution=b)
    CommitteeAttribute.objects.create(user=u["chair"], kind=CommitteeAttribute.CHAIR, program=program)
    return {"program": program, "year": year, "a": a, "b": b, "pa": pa, "pb": pb, "sa": sa, "sb": sb, **u}


def _json(client, method, url, data=None):
    return getattr(client, method)(url, data=data, content_type="application/json")


# ------------------------------------------------- the institution circle

def test_a_leader_reads_and_writes_only_their_own_package(client, world):
    client.force_login(world["leader_a"])
    subs = client.get("/academia360/api/submissions/").json()
    assert [s["id"] for s in subs] == [world["sa"].pk]
    assert client.get(f"/academia360/api/submissions/{world['sb'].pk}/").status_code == 404
    # A new package for my institution: yes. For the other: refused and rolled back.
    r = _json(client, "post", "/academia360/api/submissions/", {"participation": world["pa"].pk, "kind": "kpi_report"})
    assert r.status_code == 201
    before = Submission.objects.count()
    r = _json(client, "post", "/academia360/api/submissions/", {"participation": world["pb"].pk, "kind": "kpi_report"})
    assert r.status_code == 403 and Submission.objects.count() == before
    # Nor can a package be moved to another institution.
    r = _json(client, "patch", f"/academia360/api/submissions/{world['sa'].pk}/", {"participation": world["pb"].pk})
    assert r.status_code == 403
    assert Submission.objects.get(pk=world["sa"].pk).participation_id == world["pa"].pk


def test_a_leader_cannot_touch_a_package_the_committee_answered(client, world):
    Submission.objects.filter(pk=world["sa"].pk).update(status="responded")
    client.force_login(world["leader_a"])
    r = _json(client, "patch", f"/academia360/api/submissions/{world['sa'].pk}/", {"cover_note": "late"})
    assert r.status_code == 403
    # Reading it is still theirs.
    assert client.get(f"/academia360/api/submissions/{world['sa'].pk}/").status_code == 200


def test_the_public_never_sees_a_package(client, world):
    assert client.get("/academia360/api/submissions/").status_code in (401, 403)
    client.force_login(world["visitor"])
    assert client.get("/academia360/api/submissions/").json() == []
    assert client.get("/academia360/api/participations/").json() == []
    assert client.get("/academia360/api/kpivalues/").json() == []


def test_the_committee_reads_everything_and_writes_its_own_work(client, world):
    client.force_login(world["member"])
    assert len(client.get("/academia360/api/submissions/").json()) == 2
    r = _json(client, "post", "/academia360/api/reviews/", {"submission": world["sa"].pk, "reviewer": world["member"].pk})
    assert r.status_code == 201
    r = _json(client, "post", "/academia360/api/analyses/", {"submission": world["sb"].pk, "summary": "קריאה"})
    assert r.status_code == 201
    # The committee's work is closed to leaders and the public.
    client.force_login(world["leader_a"])
    assert client.get("/academia360/api/reviews/").json() == []
    assert client.get("/academia360/api/analyses/").json() == []


def test_only_a_chair_decides(client, world):
    client.force_login(world["member"])
    r = _json(client, "post", "/academia360/api/decisions/", {"submission": world["sa"].pk, "outcome": "approved"})
    assert r.status_code == 403 and not Decision.objects.exists()
    client.force_login(world["chair"])
    r = _json(client, "post", "/academia360/api/decisions/", {"submission": world["sa"].pk, "outcome": "approved",
                                                              "decided_by": world["chair"].pk})
    assert r.status_code == 201
    # A leader never sees the decision (spec 2.6.5).
    client.force_login(world["leader_a"])
    assert client.get("/academia360/api/decisions/").json() == []


def test_a_letter_reaches_the_institution_only_once_a_chair_sends_it(client, world):
    client.force_login(world["member"])
    r = _json(client, "post", "/academia360/api/responseletters/", {"submission": world["sa"].pk, "addressee_name": "רקטור"})
    assert r.status_code == 201
    letter = r.json()["id"]
    _json(client, "post", "/academia360/api/lettersections/", {"letter": letter, "kind": "specific", "body": "הערה פרטנית"})
    # Draft: the leader sees nothing.
    client.force_login(world["leader_a"])
    assert client.get("/academia360/api/responseletters/").json() == []
    assert client.get("/academia360/api/lettersections/").json() == []
    # A member cannot send; a chair can.
    client.force_login(world["member"])
    r = _json(client, "patch", f"/academia360/api/responseletters/{letter}/", {"sent_at": "2025-04-01"})
    assert r.status_code == 403 and ResponseLetter.objects.get(pk=letter).sent_at is None
    client.force_login(world["chair"])
    r = _json(client, "patch", f"/academia360/api/responseletters/{letter}/", {"sent_at": "2025-04-01", "sent_by": world["chair"].pk})
    assert r.status_code == 200
    # Sent: the leader of A reads it, the leader of B does not.
    client.force_login(world["leader_a"])
    assert [row["id"] for row in client.get("/academia360/api/responseletters/").json()] == [letter]
    assert len(client.get("/academia360/api/lettersections/").json()) == 1
    client.force_login(world["leader_b"])
    assert client.get("/academia360/api/responseletters/").json() == []


def test_a_member_cannot_sneak_sent_at_into_a_new_letter(client, world):
    client.force_login(world["member"])
    r = _json(client, "post", "/academia360/api/responseletters/", {"submission": world["sb"].pk, "sent_at": "2025-04-01"})
    assert r.status_code == 403 and not ResponseLetter.objects.filter(submission=world["sb"]).exists()


def test_mandatory_kpis_are_public_and_institutional_ones_are_not(client, world):
    KpiDefinition.objects.create(program=world["program"], name="מדד חובה", is_mandatory=True)
    KpiDefinition.objects.create(program=world["program"], submission=world["sa"], name="מדד של א")
    names = {k["name"] for k in client.get("/academia360/api/kpidefinitions/").json()}
    assert names == {"מדד חובה"}
    client.force_login(world["leader_b"])
    assert {k["name"] for k in client.get("/academia360/api/kpidefinitions/").json()} == {"מדד חובה"}
    client.force_login(world["leader_a"])
    assert {k["name"] for k in client.get("/academia360/api/kpidefinitions/").json()} == {"מדד חובה", "מדד של א"}


def test_anyone_proposes_a_correction_and_only_a_chair_accepts(client, world):
    client.force_login(world["visitor"])
    r = _json(client, "post", "/academia360/api/correctionproposals/", {
        "model": "academia360.Institution", "row_id": str(world["a"].pk), "field": "city",
        "current_value": "", "proposed_value": "חיפה", "proposer": world["visitor"].pk})
    assert r.status_code == 201
    pk = r.json()["id"]
    assert _json(client, "patch", f"/academia360/api/correctionproposals/{pk}/", {"status": "accepted"}).status_code == 403
    client.force_login(world["member"])
    assert len(client.get("/academia360/api/correctionproposals/").json()) == 1
    assert _json(client, "patch", f"/academia360/api/correctionproposals/{pk}/", {"status": "accepted"}).status_code == 403
    client.force_login(world["chair"])
    assert _json(client, "patch", f"/academia360/api/correctionproposals/{pk}/", {"status": "accepted"}).status_code == 200


# --------------------------------------------------------- private files

def test_a_submitted_file_is_private_and_served_by_circle(client, world, settings):
    client.force_login(world["leader_a"])
    r = client.post("/academia360/api/submittedfiles/", {
        "submission": world["sa"].pk, "kind": "plan", "original_name": "plan.pdf",
        "file": SimpleUploadedFile("plan.pdf", b"%PDF-1.4 test", content_type="application/pdf")})
    assert r.status_code == 201, r.content
    row = SubmittedFile.objects.get(pk=r.json()["id"])
    stored = Path(row.file.path)
    assert stored.exists()
    assert str(settings.ACADEMIA360_PRIVATE_DIR) in str(stored) and str(settings.MEDIA_ROOT) not in str(stored)
    assert client.get(f"/media/{row.file.name}").status_code in (403, 404)
    url = f"/academia360/files/{row.pk}/"
    assert client.get(url).status_code == 200
    client.force_login(world["leader_b"])
    assert client.get(url).status_code == 403
    client.logout()
    assert client.get(url).status_code == 403
    client.force_login(world["member"])
    assert client.get(url).status_code == 200
    assert AccessLog.objects.filter(target_id=str(row.pk)).count() == 2


# -------------------------------------------------------------- the import

def _counts():
    from django.apps import apps
    return {m.__name__: m.objects.count() for m in apps.get_app_config("academia360").get_models()
            if m.__name__ not in ("AgentRun",)}


def test_the_import_is_one_time_and_a_persons_edit_survives(db, capsys):
    call_command("import_reference", root=str(MINI))
    first = _counts()
    assert first["Institution"] == 2 and first["Participation"] == 2 and first["Submission"] == 1
    assert first["SubmittedFile"] == 2 and first["ResponseLetter"] == 1 and first["Researcher"] == 3
    assert first["Criterion"] == 11 and first["GuidelineSection"] == 2 and first["KpiDefinition"] == 5
    assert first["Analysis"] == 1 and first["CriterionFinding"] == 4 and first["ContactPerson"] == 1
    inst = Institution.objects.get(slug="example-academic-college")
    inst.city = "שונה על ידי אדם"
    inst.save()
    call_command("import_reference", root=str(MINI))
    assert _counts() == first
    assert Institution.objects.get(pk=inst.pk).city == "שונה על ידי אדם"
    out = capsys.readouterr().out
    assert "left alone" in out
    # No per-row ChangeLog noise from an import; one AgentRun per run.
    assert ChangeLog.objects.count() == 0
    from academia360.models import AgentRun
    assert AgentRun.objects.filter(purpose="import_reference").count() == 2


def test_the_import_reads_the_real_files_not_a_fixture(db):
    """Only where Avi's reference folder exists (it is confidential and
    git-ignored); elsewhere it is skipped, not faked."""
    if not (DEFAULT_ROOT / "data" / "institutions.json").exists():
        pytest.skip("reference folder not on this machine")
    call_command("import_reference")
    c = _counts()
    assert c["Institution"] >= 32 and c["Participation"] >= 32
    assert c["Submission"] >= 24 and c["SubmittedFile"] >= 60 and c["ResponseLetter"] >= 20
    assert c["ReviewQuestion"] >= 30 and c["Researcher"] >= 100 and c["KpiValue"] >= 100 and c["ProfileSection"] >= 40
    again = _counts()
    call_command("import_reference")
    assert _counts() == again


def test_without_a_reference_the_import_does_nothing(db, tmp_path, capsys):
    call_command("import_reference", root=str(tmp_path))
    assert "nothing imported" in capsys.readouterr().out
    assert Institution.objects.count() == 0


@pytest.fixture(scope="session", autouse=True)
def _clean_private_dirs(tmp_path_factory):
    yield
    shutil.rmtree(tmp_path_factory.getbasetemp(), ignore_errors=True)
