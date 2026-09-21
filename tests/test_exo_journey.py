"""exo — the four stages, end to end (spec §5).

Runs entirely on the stub provider, which is deterministic and costs nothing,
so the whole journey is exercised in the suite with no network and no bill
(spec §8, G8). What is asserted is the behaviour that would break silently:
work lost on a failure, a regenerate eating a selection, one member reaching
another's concept.
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse

from exo import ai
from exo.access import approve, membership_for
from exo.models import (
    BrainstormEntry,
    Concept,
    ExoAttribute,
    GeneratedOption,
    InterviewMessage,
    PressRelease,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded():
    call_command("seed_exo", quiet=True)


@pytest.fixture
def member(db):
    user = User.objects.create_user("builder", "b@example.com", "a-strong-pass-123")
    approve(membership_for(user, create=True))
    return user


@pytest.fixture
def other(db):
    user = User.objects.create_user("intruder", "i@example.com", "a-strong-pass-123")
    approve(membership_for(user, create=True))
    return user


@pytest.fixture
def signed_in(client, member):
    client.login(username="builder", password="a-strong-pass-123")
    return client


def make_concept(user, **kw):
    return Concept.objects.create(owner=user, title=kw.pop("title", "A car rental service"), **kw)


def post_json(client, url, payload=None):
    return client.post(url, data=json.dumps(payload or {}),
                       content_type="application/json")


# ---- the stub is what makes this suite possible ---------------------- #

def test_the_suite_runs_on_the_stub_provider():
    """No key in the test environment, so nothing here can cost money or
    vary between runs."""
    assert ai.is_stub()


# ---- concepts: CRUD, ownership, resume -------------------------------- #

def test_creating_a_concept_needs_only_a_title(signed_in, seeded, member):
    response = signed_in.post(reverse("exo:concept_create"), {"title": "A bakery"})
    assert response.status_code == 302
    concept = Concept.objects.get(owner=member)
    assert concept.title == "A bakery"
    assert concept.stage == Concept.Stage.INTERVIEW


def test_a_member_may_have_many_concepts(signed_in, seeded, member):
    for name in ["one", "two", "three"]:
        signed_in.post(reverse("exo:concept_create"), {"title": name})
    assert Concept.objects.filter(owner=member).count() == 3


def test_resume_lands_on_the_stage_it_was_left_at(signed_in, seeded, member):
    concept = make_concept(member, stage=Concept.Stage.OPTIONS)
    response = signed_in.get(reverse("exo:concept_resume", args=[concept.pk]))
    assert response.status_code == 302
    assert response["Location"].endswith(f"/concepts/{concept.pk}/options/")


def test_deleting_takes_the_whole_journey_and_nothing_else(signed_in, seeded, member, other):
    mine = make_concept(member)
    theirs = make_concept(other, title="not mine")
    attribute = ExoAttribute.objects.first()
    BrainstormEntry.objects.create(concept=mine, attribute=attribute, text="x")
    InterviewMessage.objects.create(concept=mine, role="user", content="hi")

    signed_in.post(reverse("exo:concept_delete", args=[mine.pk]))

    assert not Concept.objects.filter(pk=mine.pk).exists()
    assert BrainstormEntry.objects.count() == 0
    assert InterviewMessage.objects.count() == 0
    assert Concept.objects.filter(pk=theirs.pk).exists()


def test_one_member_cannot_touch_another_members_concept(signed_in, seeded, other):
    theirs = make_concept(other, title="private")
    for url in [
        reverse("exo:concept_resume", args=[theirs.pk]),
        reverse("exo:concept_interview", args=[theirs.pk]),
        reverse("exo:concept_brainstorm", args=[theirs.pk]),
        reverse("exo:concept_options", args=[theirs.pk]),
        reverse("exo:concept_output", args=[theirs.pk]),
    ]:
        assert signed_in.get(url).status_code == 404, url
    assert signed_in.post(reverse("exo:concept_delete", args=[theirs.pk])).status_code == 404
    assert Concept.objects.filter(pk=theirs.pk).exists()


# ---- stage 1: the interview ------------------------------------------- #

def test_the_assistant_opens_the_conversation(signed_in, seeded, member):
    concept = make_concept(member)
    signed_in.get(reverse("exo:concept_interview", args=[concept.pk]))
    first = concept.messages.first()
    assert first is not None and first.role == "assistant"


def test_a_user_turn_is_saved_before_the_model_is_asked(signed_in, seeded, member, monkeypatch):
    """An outage must never swallow what the person typed."""
    concept = make_concept(member)
    signed_in.get(reverse("exo:concept_interview", args=[concept.pk]))

    def boom(*a, **kw):
        raise ai.AiError("provider down")

    monkeypatch.setattr(ai, "interview_reply", boom)
    response = post_json(
        signed_in, reverse("exo:concept_interview_send", args=[concept.pk]),
        {"text": "I want to build a car rental service"},
    )
    assert response.status_code == 503
    assert concept.messages.filter(role="user",
                                   content__icontains="car rental").exists()


def test_settling_stores_the_edited_text_not_the_models(signed_in, seeded, member):
    """The person edits the summary; their edit is what is stored. The model
    does not get the last word on their own purpose."""
    concept = make_concept(member)
    post_json(signed_in, reverse("exo:concept_settle", args=[concept.pk]), {
        "mtp": "My own words for the purpose",
        "special": "my special", "unique": "my unique",
    })
    concept.refresh_from_db()
    assert concept.mtp == "My own words for the purpose"
    assert concept.stage == Concept.Stage.BRAINSTORM


# ---- stage 2: the brainstorm ------------------------------------------ #

def test_entries_can_be_added_edited_and_deleted(signed_in, seeded, member):
    concept = make_concept(member, stage=Concept.Stage.BRAINSTORM)
    attribute = ExoAttribute.objects.get(key="algorithms")

    created = post_json(signed_in, reverse("exo:entry_add", args=[concept.pk]),
                        {"attribute": attribute.key, "text": "match cars to demand"})
    assert created.status_code == 200
    entry_id = created.json()["id"]

    edited = post_json(signed_in, reverse("exo:entry_edit", args=[concept.pk, entry_id]),
                       {"text": "predict demand per street"})
    assert edited.json()["text"] == "predict demand per street"

    signed_in.post(reverse("exo:entry_delete", args=[concept.pk, entry_id]))
    assert not BrainstormEntry.objects.filter(pk=entry_id).exists()


def test_all_thirteen_slots_are_offered(signed_in, seeded, member):
    concept = make_concept(member, stage=Concept.Stage.BRAINSTORM)
    response = signed_in.get(reverse("exo:concept_brainstorm", args=[concept.pk]))
    assert len(response.context["slots"]) == 13


def test_the_stage_advances_even_with_empty_slots(signed_in, seeded, member):
    """No slot is mandatory (spec §5.2, D2.4)."""
    concept = make_concept(member, stage=Concept.Stage.BRAINSTORM)
    signed_in.post(reverse("exo:concept_to_options", args=[concept.pk]))
    concept.refresh_from_db()
    assert concept.stage == Concept.Stage.OPTIONS


# ---- stage 3: options and selection ----------------------------------- #

def test_options_are_generated_per_attribute(signed_in, seeded, member):
    concept = make_concept(member, stage=Concept.Stage.OPTIONS)
    attribute = ExoAttribute.objects.get(key="engagement")
    response = post_json(signed_in, reverse("exo:options_generate", args=[concept.pk]),
                         {"attribute": attribute.key})
    assert response.status_code == 200
    assert 1 <= concept.options.filter(attribute=attribute).count() <= 4


def test_regenerating_keeps_what_was_selected(signed_in, seeded, member):
    """A regenerate that eats a person's picks is the bug this guards."""
    concept = make_concept(member, stage=Concept.Stage.OPTIONS)
    attribute = ExoAttribute.objects.get(key="engagement")
    post_json(signed_in, reverse("exo:options_generate", args=[concept.pk]),
              {"attribute": attribute.key})

    keeper = concept.options.filter(attribute=attribute).first()
    post_json(signed_in, reverse("exo:option_select", args=[concept.pk, keeper.pk]))
    keeper.refresh_from_db()
    assert keeper.is_selected

    post_json(signed_in, reverse("exo:options_generate", args=[concept.pk]),
              {"attribute": attribute.key})
    assert GeneratedOption.objects.filter(pk=keeper.pk, is_selected=True).exists()


def test_a_users_own_option_survives_a_regenerate(signed_in, seeded, member):
    concept = make_concept(member, stage=Concept.Stage.OPTIONS)
    attribute = ExoAttribute.objects.get(key="autonomy")
    mine = post_json(signed_in, reverse("exo:option_add_own", args=[concept.pk]),
                     {"attribute": attribute.key, "text": "my own idea"}).json()

    post_json(signed_in, reverse("exo:options_generate", args=[concept.pk]),
              {"attribute": attribute.key})
    assert GeneratedOption.objects.filter(pk=mine["id"]).exists()


def test_a_failed_generation_leaves_the_slot_as_it_was(signed_in, seeded, member, monkeypatch):
    concept = make_concept(member, stage=Concept.Stage.OPTIONS)
    attribute = ExoAttribute.objects.get(key="interfaces")
    post_json(signed_in, reverse("exo:options_generate", args=[concept.pk]),
              {"attribute": attribute.key})
    before = list(concept.options.filter(attribute=attribute).values_list("pk", flat=True))

    def boom(*a, **kw):
        raise ai.AiError("provider down")

    monkeypatch.setattr(ai, "generate_options", boom)
    response = post_json(signed_in, reverse("exo:options_generate", args=[concept.pk]),
                         {"attribute": attribute.key})
    assert response.status_code == 503
    after = list(concept.options.filter(attribute=attribute).values_list("pk", flat=True))
    assert before == after


def test_a_daily_limit_refuses_rather_than_spends(signed_in, seeded, member, monkeypatch):
    concept = make_concept(member, stage=Concept.Stage.OPTIONS)
    attribute = ExoAttribute.objects.get(key="dashboards")

    def over(*a, **kw):
        raise ai.AiLimit("options: daily limit reached")

    monkeypatch.setattr(ai, "generate_options", over)
    response = post_json(signed_in, reverse("exo:options_generate", args=[concept.pk]),
                         {"attribute": attribute.key})
    assert response.status_code == 429


# ---- stage 4: the output ---------------------------------------------- #

def test_generating_writes_both_artifacts_and_a_score(signed_in, seeded, member):
    concept = make_concept(member, stage=Concept.Stage.OUTPUT, mtp="a purpose")
    attribute = ExoAttribute.objects.get(key="community-and-crowd")
    GeneratedOption.objects.create(concept=concept, attribute=attribute,
                                   content="a community of owners", is_selected=True)

    response = post_json(signed_in, reverse("exo:output_generate", args=[concept.pk]))
    assert response.status_code == 200

    release = PressRelease.objects.get(concept=concept)
    assert release.headline and release.body and release.document_body
    assert release.exponential_score is not None


def test_switching_style_never_changes_the_words(signed_in, seeded, member):
    concept = make_concept(member, stage=Concept.Stage.OUTPUT)
    post_json(signed_in, reverse("exo:output_generate", args=[concept.pk]))
    release = PressRelease.objects.get(concept=concept)
    before = (release.headline, release.body, release.document_body)

    from exo.models import NewspaperStyle
    other_style = NewspaperStyle.objects.exclude(
        pk=release.newspaper_style_id
    ).first()
    post_json(signed_in, reverse("exo:output_style", args=[concept.pk]),
              {"style": other_style.key})

    release.refresh_from_db()
    assert (release.headline, release.body, release.document_body) == before
    assert release.newspaper_style_id == other_style.pk


def test_regenerating_over_a_hand_edit_needs_confirmation(signed_in, seeded, member):
    concept = make_concept(member, stage=Concept.Stage.OUTPUT)
    post_json(signed_in, reverse("exo:output_generate", args=[concept.pk]))
    post_json(signed_in, reverse("exo:output_edit", args=[concept.pk]),
              {"headline": "My own headline"})

    refused = post_json(signed_in, reverse("exo:output_generate", args=[concept.pk]))
    assert refused.status_code == 409
    assert PressRelease.objects.get(concept=concept).headline == "My own headline"

    allowed = post_json(signed_in, reverse("exo:output_generate", args=[concept.pk]),
                        {"confirm": True})
    assert allowed.status_code == 200


def test_the_stress_test_is_stored(signed_in, seeded, member):
    concept = make_concept(member, stage=Concept.Stage.OUTPUT)
    post_json(signed_in, reverse("exo:output_generate", args=[concept.pk]))
    response = post_json(signed_in, reverse("exo:output_stress_test", args=[concept.pk]))
    assert response.status_code == 200
    assert PressRelease.objects.get(concept=concept).stress_test_feedback


# ---- going back -------------------------------------------------------- #

def test_going_back_marks_stale_and_deletes_nothing(signed_in, seeded, member):
    """Spec §5.5: navigation never destroys work."""
    concept = make_concept(member, stage=Concept.Stage.OPTIONS)
    attribute = ExoAttribute.objects.get(key="experimentation")
    GeneratedOption.objects.create(concept=concept, attribute=attribute, content="keep me")

    signed_in.post(reverse("exo:concept_back", args=[concept.pk]),
                   {"stage": "brainstorm"})

    concept.refresh_from_db()
    assert concept.stage == Concept.Stage.BRAINSTORM
    assert concept.downstream_stale
    assert concept.options.count() == 1
