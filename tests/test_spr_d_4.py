"""SPR-D.4 — dentist: the mouth.

The chart is a history, not a drawing (Rule 5.1): every observation is a
dated, authored row, the chart on screen is the latest per tooth and
surface, nothing is overwritten. FDI numbering drawn as a mouth (5.2).
The plan is an ordered list whose "done" only a visit can set (5.3). The
chart and the plan print on one page (5.4). Refusals first.
"""

import re

import pytest
from django.contrib.auth.models import User

from dentist import mouth
from dentist.models import (
    AccessLog,
    Clinic,
    ClinicMember,
    Patient,
    PlanItem,
    ProcedureType,
    ToothState,
)

pytestmark = [pytest.mark.sprd4, pytest.mark.django_db]


def _user(email, **flags):
    return User.objects.create_user(username=email.split("@")[0], email=email, password="dentist-7781", **flags)


class World:
    def __init__(self):
        self.a = Clinic.objects.create(name="Clinic A", slug="clinic-a")
        self.b = Clinic.objects.create(name="Clinic B", slug="clinic-b")
        self.dentist = _user("dentist-a@example.com")
        ClinicMember.objects.create(clinic=self.a, user=self.dentist, role="dentist")
        self.admin_b = _user("admin-b@example.com")
        ClinicMember.objects.create(clinic=self.b, user=self.admin_b, role="admin")
        self.pa = Patient.objects.create(clinic=self.a, first_name="Amal")
        self.pb = Patient.objects.create(clinic=self.b, first_name="Boris")
        self.fill = ProcedureType.objects.create(clinic=self.a, code="FILL", name_en="Filling")
        self.crown = ProcedureType.objects.create(clinic=self.a, code="CROWN", name_en="Crown")
        self.fill_b = ProcedureType.objects.create(clinic=self.b, code="FILL", name_en="Filling B")
        self.url = f"/dentist/c/{self.a.slug}/p/{self.pa.pk}/"


@pytest.fixture
def world():
    return World()


# ------------------------------------------------------------------ refusals


@pytest.mark.parametrize("path", ["mouth/", "print/"])
def test_the_mouth_and_the_print_are_the_clinics_alone(client, world, path):
    assert client.get(world.url + path).status_code == 302
    client.force_login(world.admin_b)
    assert client.get(world.url + path).status_code == 403
    me = _user("me@example.com")
    world.pa.user = me
    world.pa.save()
    client.force_login(me)
    assert client.get(world.url + path).status_code == 403
    client.force_login(world.dentist)
    assert client.get(f"/dentist/c/{world.a.slug}/p/{world.pb.pk}/{path}").status_code == 404
    assert client.get(world.url + path).status_code == 200


def test_nobody_records_on_another_clinics_patient(client, world):
    client.force_login(world.admin_b)
    r = client.post(world.url + "mouth/record/", {"tooth": 16, "surface": "O", "condition": "decay"})
    assert r.status_code == 403 and not ToothState.objects.exists()
    client.force_login(world.dentist)
    r = client.post(f"/dentist/c/{world.a.slug}/p/{world.pb.pk}/mouth/record/", {"tooth": 16, "surface": "O", "condition": "decay"})
    assert r.status_code == 404 and not ToothState.objects.exists()
    # A procedure of clinic B cannot be planned for A's patient.
    r = client.post(world.url + "plan/add/", {"procedure": world.fill_b.pk}, follow=True)
    assert "Pick a procedure" in r.content.decode() and not PlanItem.objects.exists()


# ------------------------------------------------------------ the chart


def test_a_tooth_is_a_history_and_the_chart_is_the_latest_row(client, world):
    client.force_login(world.dentist)
    client.post(world.url + "mouth/record/", {"tooth": 16, "surface": "O", "condition": "decay", "note": "small"})
    client.post(world.url + "mouth/record/", {"tooth": 16, "surface": "O", "condition": "filling"})
    client.post(world.url + "mouth/record/", {"tooth": 36, "surface": "", "condition": "crown"})
    rows = list(world.pa.teeth.order_by("id"))
    assert [(r.tooth, r.surface, r.condition) for r in rows] == [(16, "O", "decay"), (16, "O", "filling"), (36, "", "crown")]
    assert all(r.noted_by == world.dentist for r in rows) and rows[0].note == "small"
    latest = mouth.chart(world.pa)
    assert latest[(16, "O")].condition == "filling" and latest[(36, "")].condition == "crown"
    assert AccessLog.objects.filter(patient=world.pa, action="edited", what="tooth 16O recorded").count() == 2
    body = client.get(world.url + "mouth/?tooth=16").content.decode()
    tooth16 = re.search(r'<a class="dn-tooth[^"]*" href="\?tooth=16"[^>]*aria-label="([^"]+)"', body).group(1)
    assert tooth16 == "Tooth 16, first molar: sound, O: filling"
    assert 'dn-seg dn-seg--filling" x="12"' in body  # the O square of tooth 16 painted as filling
    assert body.count("dn-seg--crown") >= 5  # tooth 36, every segment
    # The tooth's history, newest first, under the chart.
    panel = body[body.index("What was recorded for this tooth"):]
    assert panel.index("Filling") < panel.index("Decay") and "small" in panel


def test_the_chart_draws_32_adult_teeth_the_way_a_dentist_reads_it(client, world):
    client.force_login(world.dentist)
    body = client.get(world.url + "mouth/").content.decode()
    numbers = [int(n) for n in re.findall(r'data-tooth="(\d+)"', body)]
    assert len(numbers) == 32 and len(set(numbers)) == 32
    assert numbers[:16] == list(range(18, 10, -1)) + list(range(21, 29))
    assert numbers[16:] == list(range(48, 40, -1)) + list(range(31, 39))
    # Child teeth on request, or by themselves when the record has one.
    body = client.get(world.url + "mouth/?child=1").content.decode()
    assert len(re.findall(r'data-tooth="(\d+)"', body)) == 20 and 'data-tooth="55"' in body
    ToothState.objects.create(patient=world.pa, tooth=75, condition="decay")
    body = client.get(world.url + "mouth/").content.decode()
    assert 'data-tooth="75"' in body and "Adult teeth" in body


def test_a_bad_record_is_refused_with_words_not_a_crash(client, world):
    client.force_login(world.dentist)
    for bad in ({"tooth": 19, "surface": "O", "condition": "decay"}, {"tooth": 16, "surface": "Q", "condition": "decay"},
                {"tooth": 16, "surface": "O", "condition": "gold"}, {"surface": "O", "condition": "decay"}):
        r = client.post(world.url + "mouth/record/", bad, follow=True)
        assert r.status_code == 200 and "Pick a tooth, a surface and a condition." in r.content.decode(), bad
    assert not ToothState.objects.exists()


def test_the_last_condition_is_offered_again(client, world):
    """Two taps record the common case: the second tooth starts with what
    the first one got."""
    client.force_login(world.dentist)
    client.post(world.url + "mouth/record/", {"tooth": 16, "surface": "O", "condition": "fracture"})
    body = client.get(world.url + "mouth/?tooth=17").content.decode()
    assert re.search(r'value="fracture" checked', body)
    assert "Tap tooth 17 again to record." in body


def test_opening_the_mouth_is_logged(client, world):
    client.force_login(world.dentist)
    client.get(world.url + "mouth/")
    assert AccessLog.objects.filter(patient=world.pa, action="viewed", what="mouth", user=world.dentist).exists()


# -------------------------------------------------------------- the plan


def test_the_plan_is_ordered_droppable_and_never_done_from_here(client, world):
    client.force_login(world.dentist)
    client.post(world.url + "plan/add/", {"procedure": world.fill.pk, "tooth": 16, "note": "first"})
    client.post(world.url + "plan/add/", {"procedure": world.crown.pk, "tooth": 36})
    client.post(world.url + "plan/add/", {"procedure": world.fill.pk, "tooth": "abc"})
    items = list(world.pa.plan.order_by("priority"))
    assert [(i.priority, i.procedure.code, i.tooth) for i in items] == [(1, "FILL", 16), (2, "CROWN", 36), (3, "FILL", None)]
    assert all(i.status == "planned" and i.planned_by == world.dentist for i in items)
    client.post(world.url + f"plan/{items[2].pk}/up/")
    assert [i.procedure.code for i in world.pa.plan.order_by("priority")] == ["FILL", "FILL", "CROWN"]
    client.post(world.url + f"plan/{items[1].pk}/drop/")
    items[1].refresh_from_db()
    assert items[1].status == "dropped" and PlanItem.objects.filter(pk=items[1].pk).exists()
    assert client.post(world.url + f"plan/{items[0].pk}/done/").status_code == 404
    assert not world.pa.plan.filter(status="done").exists()
    body = client.get(world.url + "mouth/").content.decode()
    assert "Dropped, kept: Crown 36." in body
    # The record page shows the live plan, in order, without the dropped one.
    body = client.get(world.url).content.decode()
    assert body.count("Filling") >= 2 and "Crown" not in body.split("The mouth and the plan")[1].split("Appointments")[0]


# ---------------------------------------------------------------- print


def test_the_print_page_holds_the_chart_and_the_plan_and_is_logged(client, world):
    client.force_login(world.dentist)
    ToothState.objects.create(patient=world.pa, tooth=16, surface="O", condition="decay", note="buccal cusp")
    PlanItem.objects.create(patient=world.pa, procedure=world.fill, tooth=16, priority=1)
    body = client.get(world.url + "print/").content.decode()
    assert 'class="dn-mouth dn-mouth--static"' in body and "data-tooth" not in body
    assert body.count('class="dn-tooth ') == 32
    assert "Filling" in body and "tooth <span class=\"dn-mono\">16</span>" in body
    assert "buccal cusp" in body and "window.print()" in body
    assert AccessLog.objects.filter(patient=world.pa, action="printed", what="chart and plan").exists()


# ------------------------------------------------------------------ the API


def test_the_api_gives_teeth_and_plan_through_the_same_scope(client, world):
    base = f"/dentist/api/c/{world.a.slug}/"
    client.force_login(world.dentist)
    r = client.post(f"{base}teeth/", {"patient": world.pa.pk, "tooth": 26, "surface": "M", "condition": "decay"})
    assert r.status_code == 201 and r.json()["noted_by"] == world.dentist.pk
    assert client.post(f"{base}teeth/", {"patient": world.pb.pk, "tooth": 26, "surface": "", "condition": "decay"}).status_code == 400
    row = r.json()["id"]
    assert client.patch(f"{base}teeth/{row}/", {"condition": "sound"}, content_type="application/json").status_code == 405
    assert client.delete(f"{base}teeth/{row}/").status_code == 405
    assert client.get(f"{base}teeth/?patient={world.pa.pk}").json()[0]["tooth"] == 26
    r = client.post(f"{base}plan/", {"patient": world.pa.pk, "procedure": world.fill.pk, "tooth": 26, "priority": 1})
    assert r.status_code == 201
    item = r.json()["id"]
    r = client.patch(f"{base}plan/{item}/", {"status": "done"}, content_type="application/json")
    assert r.status_code == 400 and "visit" in r.content.decode()
    assert client.delete(f"{base}plan/{item}/").status_code == 204
    assert PlanItem.objects.get(pk=item).status == "dropped"
    client.force_login(world.admin_b)
    assert client.get(f"{base}teeth/").status_code == 403
