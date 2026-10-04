"""SPR-I.1.4 improv: the DRF base, the gate repeated inside the API, the reference endpoints.

Rule 6: every model has a documented REST endpoint from the start. The page
sweep in test_spri_1_1 already proves the middleware gate covers every route; this
file proves the API does not depend on it, because a gate that is the only lock is
one refactor away from no lock.

Load-bearing: `test_every_model_has_an_endpoint_and_the_endpoint_is_documented`
(the next model somebody adds cannot ship without both) and
`test_the_permission_class_refuses_on_its_own`, which calls the views with no
middleware at all.

Traces: spec ch. 7 "The API", data model section 1.
"""

import pathlib

import pytest
from django.apps import apps
from django.contrib.auth.models import AnonymousUser, Group, User
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from improv.models import ChordQuality, ChordScale, Scale

pytestmark = pytest.mark.spri14

PASSWORD = "spri14-pass-9931"
API = "/improv/api/"


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    stranger = User.objects.create_user(username="stranger", password=PASSWORD)
    member = User.objects.create_user(username="member", password=PASSWORD)
    admin = User.objects.create_user(username="admin", password=PASSWORD, is_staff=True, is_superuser=True)
    member.groups.add(group)
    call_command("seed_improv_theory", stdout=__import__("io").StringIO())
    return {"stranger": stranger, "member": member, "admin": admin}


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


# ------------------------------------------------------- the endpoint registry


def test_every_model_has_an_endpoint_and_the_endpoint_is_documented():
    from improv import api

    models = list(apps.get_app_config("improv").get_models())
    assert models
    registered = {viewset.queryset.model: path for path, viewset in api.ENDPOINTS.items()}
    docs = pathlib.Path("docs/improv/api.md").read_text(encoding="utf-8")

    for model in models:
        assert model in registered, f"{model.__name__} has no endpoint (Rule 6)"
        path = registered[model]
        assert f"/improv/api/{path}/" in docs, f"{model.__name__}: /improv/api/{path}/ is not in docs/improv/api.md"


def test_every_endpoint_is_behind_the_player_permission():
    from improv import api
    from improv.permissions import IsPlayer

    for path, viewset in api.ENDPOINTS.items():
        assert list(viewset.permission_classes) == [IsPlayer], (
            f"{path} must use exactly IsPlayer, not the site default and nothing weaker"
        )


def test_the_api_root_names_every_endpoint(people):
    response = client_for(people["member"]).get(API)
    assert response.status_code == 200
    from improv import api

    for path in api.ENDPOINTS:
        assert path in response.json(), f"the API root does not list {path}"


# ------------------------------------------------- the gate repeated in the API


@pytest.mark.parametrize("who", ["anonymous", "stranger"])
def test_the_permission_class_refuses_on_its_own(people, who):
    """No middleware, no urlconf: the view alone, called directly. If the gate is
    ever removed or reordered, the API must still answer 404 to an outsider and
    must not reveal that it exists by answering 401 or 403."""
    from improv import api

    user = AnonymousUser() if who == "anonymous" else people["stranger"]
    factory = APIRequestFactory()
    for path, viewset in api.ENDPOINTS.items():
        for action, kwargs in (("list", {}), ("retrieve", {"pk": 1})):
            request = factory.get(f"{API}{path}/")
            if who != "anonymous":
                force_authenticate(request, user=user)
            response = viewset.as_view({"get": action})(request, **kwargs)
            assert response.status_code == 404, f"{who} {action} {path} got {response.status_code}"


def test_a_member_and_the_admin_may_read(people):
    from improv import api

    for who in ("member", "admin"):
        for path in api.ENDPOINTS:
            response = client_for(people[who]).get(f"{API}{path}/")
            assert response.status_code == 200, f"{who} {path} got {response.status_code}"


# ------------------------------------------------------- reference is read-only


@pytest.mark.parametrize("who", ["member", "admin"])
def test_reference_rows_cannot_be_written_through_the_api(people, who):
    """Reference rows are edited in the admin. A player who could rewrite a chord
    quality could make every chart in the app judge wrongly."""
    from improv import api

    before = (ChordQuality.objects.count(), Scale.objects.count(), ChordScale.objects.count())
    client = client_for(people[who])
    for path in api.REFERENCE_ENDPOINTS:
        detail = f"{API}{path}/1/"
        assert client.post(f"{API}{path}/", {"x": 1}).status_code == 405, f"POST {path}"
        for method in ("put", "patch", "delete"):
            response = getattr(client, method)(detail, {"x": 1}, content_type="application/json")
            assert response.status_code == 405, f"{method.upper()} {detail} got {response.status_code}"
    assert (ChordQuality.objects.count(), Scale.objects.count(), ChordScale.objects.count()) == before


# ------------------------------------------------------------- what they return


def test_the_chord_quality_list_is_the_whole_table_in_order(people):
    body = client_for(people["member"]).get(f"{API}chord-qualities/").json()
    assert isinstance(body, list), "a short reference table is returned whole, not paged"
    assert len(body) == ChordQuality.objects.count()
    assert [row["symbol"] for row in body] == list(ChordQuality.objects.values_list("symbol", flat=True))


def test_a_chord_quality_carries_its_notes_roles_and_ranked_scales(people):
    rows = client_for(people["member"]).get(f"{API}chord-qualities/").json()
    m7 = next(row for row in rows if row["symbol"] == "m7")
    assert m7["intervals"] == [0, 3, 7, 10]
    assert m7["roles"]["3"] == "third"
    assert "-7" in m7["aliases"]
    assert [s["slug"] for s in m7["scales"]][:2] == ["dorian", "aeolian"]
    assert [s["preference"] for s in m7["scales"]] == sorted(s["preference"] for s in m7["scales"])


def test_a_scale_carries_its_parent_and_mode(people):
    rows = client_for(people["member"]).get(f"{API}scales/").json()
    dorian = next(row for row in rows if row["slug"] == "dorian")
    assert dorian["intervals"] == [0, 2, 3, 5, 7, 9, 10]
    assert dorian["parent_slug"] == "major" and dorian["mode_number"] == 2
    major = next(row for row in rows if row["slug"] == "major")
    assert major["parent_slug"] is None


def test_chord_scales_filter_by_chord_and_by_scale(people):
    client = client_for(people["member"])
    by_chord = client.get(f"{API}chord-scales/", {"quality": "7"}).json()
    assert by_chord and {row["quality_symbol"] for row in by_chord} == {"7"}
    assert [row["preference"] for row in by_chord] == sorted(row["preference"] for row in by_chord)
    assert by_chord[0]["scale_slug"] == "mixolydian"

    by_scale = client.get(f"{API}chord-scales/", {"scale": "dorian"}).json()
    assert by_scale and {row["scale_slug"] for row in by_scale} == {"dorian"}
    assert "m7" in {row["quality_symbol"] for row in by_scale}


def test_an_unknown_filter_value_is_an_empty_list_not_an_error(people):
    response = client_for(people["member"]).get(f"{API}chord-scales/", {"quality": "no-such-chord"})
    assert response.status_code == 200 and response.json() == []


def test_a_detail_read_returns_one_row(people):
    row = ChordQuality.objects.get(symbol="maj7")
    body = client_for(people["member"]).get(f"{API}chord-qualities/{row.pk}/").json()
    assert body["symbol"] == "maj7" and body["intervals"] == [0, 4, 7, 11]
    assert client_for(people["member"]).get(f"{API}chord-qualities/999999/").status_code == 404


def test_the_api_names_resolve(people):
    from improv import api

    for path in api.ENDPOINTS:
        assert reverse(f"improv:api-{path}-list") == f"{API}{path}/"
