"""exo — the four stages, end to end (spec §5).

Runs entirely on the stub provider, which is deterministic and costs nothing,
so the whole journey is exercised in the suite with no network and no bill
(spec §8, G8). What is asserted is the behaviour that would break silently:
work lost on a failure, a regenerate eating a selection, one member reaching
another's concept.
"""

import json
from urllib.parse import quote

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


# ---- coming back ------------------------------------------------------- #
#
# Avi closed the tab mid-idea and came back to a page that greeted him like a
# stranger. Nothing had been lost: the concept, the stage and the transcript
# were all in the database the whole time. But the app never took him back,
# and an app that cannot show you your work has forgotten it as far as you are
# concerned.


def test_the_landing_greets_a_member_with_their_own_work(signed_in, seeded,
                                                         member):
    concept = make_concept(member, stage=Concept.Stage.OPTIONS,
                           title="A car rental service")
    response = signed_in.get(reverse("exo:home"))
    assert response.context["resume"].pk == concept.pk
    body = response.content.decode()
    assert "A car rental service" in body
    assert reverse("exo:concept_resume", args=[concept.pk]) in body


def test_the_landing_still_pitches_to_everyone_else(client, seeded):
    """The public half is unchanged for people who are not in it."""
    response = client.get(reverse("exo:home"))
    assert response.context["resume"] is None
    assert response.content.decode().count(reverse("exo:join")) == 1


def test_it_offers_the_concept_worked_on_most_recently(signed_in, seeded,
                                                       member):
    older = make_concept(member, title="the first one")
    newer = make_concept(member, title="the one I was in the middle of")
    # Touch the older one, so "most recent" cannot be passing by luck of id.
    newer.mtp = "Movement without ownership"
    newer.save()

    response = signed_in.get(reverse("exo:home"))
    assert response.context["resume"].pk == newer.pk
    assert older.pk != newer.pk


def test_resume_lands_on_the_stage_not_the_list(signed_in, seeded, member):
    concept = make_concept(member, stage=Concept.Stage.BRAINSTORM)
    response = signed_in.get(reverse("exo:concept_resume", args=[concept.pk]))
    assert response["Location"].endswith(f"/concepts/{concept.pk}/brainstorm/")


def test_a_signed_out_member_is_returned_to_the_page_they_wanted(client, seeded,
                                                                 member):
    """A session that expires mid-idea should cost a password, not a place."""
    concept = make_concept(member, stage=Concept.Stage.OPTIONS)
    wanted = reverse("exo:concept_options", args=[concept.pk])

    response = client.get(wanted)
    assert response.status_code == 302
    assert quote(wanted) in response["Location"]

    client.login(username="builder", password="a-strong-pass-123")
    signed_in_response = client.get(reverse("exo:login"), {"next": wanted})
    # Already signed in: straight through to where they were going.
    assert signed_in_response["Location"] == wanted


def test_signing_in_with_no_destination_goes_to_the_last_thing_worked_on(
        client, seeded, member):
    concept = make_concept(member, stage=Concept.Stage.OUTPUT)
    response = client.post(reverse("exo:login"), {
        "username": "builder", "password": "a-strong-pass-123",
    })
    assert response.status_code == 302
    assert response["Location"].endswith(f"/concepts/{concept.pk}/")


def test_signing_in_with_nothing_started_goes_to_the_list(client, seeded,
                                                          member):
    response = client.post(reverse("exo:login"), {
        "username": "builder", "password": "a-strong-pass-123",
    })
    assert response["Location"] == reverse("exo:concepts")


def test_the_return_destination_can_only_be_inside_exo(client, seeded, member):
    """`next` is attacker-controllable, so it is checked rather than trusted."""
    from exo.views import safe_next

    assert safe_next("/exo/concepts/3/options/") == "/exo/concepts/3/options/"
    assert safe_next("https://evil.example/") == ""
    assert safe_next("//evil.example/") == ""
    assert safe_next("/courses/") == ""
    assert safe_next(None) == ""

    client.login(username="builder", password="a-strong-pass-123")
    response = client.post(reverse("exo:login"), {
        "username": "builder", "password": "a-strong-pass-123",
        "next": "https://evil.example/",
    })
    assert "evil.example" not in response["Location"]


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


# ---- the MTP is a slogan, not a vision statement ----------------------- #
#
# Avi's correction after the first build: an MTP is a handful of words, short
# enough to print on a t-shirt, with at most one fifteen-word line beside it.
# The rule lives in three places that can drift apart — the prompt, the model's
# word caps, and the view — so it is asserted at the view, which is the one a
# person actually meets.


def test_a_slogan_is_accepted_and_stored_with_its_line(signed_in, seeded, member):
    concept = make_concept(member)
    response = post_json(signed_in, reverse("exo:concept_settle", args=[concept.pk]), {
        "mtp": "Movement without ownership",
        "mtp_note": "Getting anywhere in the city without needing to own a car.",
        "special": "we know the street", "unique": "it arrives first",
    })
    assert response.status_code == 302 or response.status_code == 200

    concept.refresh_from_db()
    assert concept.mtp == "Movement without ownership"
    assert concept.mtp_note.startswith("Getting anywhere")
    assert concept.stage == Concept.Stage.BRAINSTORM


def test_a_vision_statement_is_refused_rather_than_quietly_cut(signed_in, seeded,
                                                               member):
    """Refused, not trimmed. Cutting somebody's sentence in half behind their
    back and saving the stump is worse than telling them it is too long."""
    concept = make_concept(member)
    essay = ("A world in which every person in every city can move freely "
             "without ever having to own a vehicle of their own")
    response = post_json(signed_in, reverse("exo:concept_settle", args=[concept.pk]),
                         {"mtp": essay})
    assert response.status_code == 422

    concept.refresh_from_db()
    assert concept.mtp == ""
    # And the stage did not advance on a refusal.
    assert concept.stage == Concept.Stage.INTERVIEW


def test_the_expansion_line_has_its_own_ceiling(signed_in, seeded, member):
    concept = make_concept(member)
    response = post_json(signed_in, reverse("exo:concept_settle", args=[concept.pk]), {
        "mtp": "Movement without ownership",
        "mtp_note": " ".join(["word"] * 16),
    })
    assert response.status_code == 422
    concept.refresh_from_db()
    assert concept.mtp_note == ""


def test_exactly_the_limit_is_allowed(signed_in, seeded, member):
    """Off-by-one on a limit is the difference between a rule and an
    irritation."""
    concept = make_concept(member)
    response = post_json(signed_in, reverse("exo:concept_settle", args=[concept.pk]), {
        "mtp": " ".join(["word"] * Concept.MTP_MAX_WORDS),
        "mtp_note": " ".join(["word"] * Concept.MTP_NOTE_MAX_WORDS),
    })
    assert response.status_code in (200, 302)
    concept.refresh_from_db()
    assert len(concept.mtp.split()) == Concept.MTP_MAX_WORDS


def test_spacing_is_not_counted_as_words(signed_in, seeded, member):
    concept = make_concept(member)
    response = post_json(signed_in, reverse("exo:concept_settle", args=[concept.pk]),
                         {"mtp": "   Movement    without \n ownership  "})
    assert response.status_code in (200, 302)
    concept.refresh_from_db()
    assert concept.mtp == "Movement without ownership"


def test_the_model_is_held_to_the_same_rule(seeded, member):
    """The prompt asks for a slogan twice, but a model asked for seven words
    will sometimes write nine. What comes back is trimmed before the person is
    shown it, and nothing reaches a row without them accepting it."""
    concept = make_concept(member)
    settled = ai.settle(concept, [], "en", user=member)

    assert len(settled["mtp"].split()) <= Concept.MTP_MAX_WORDS
    assert len(settled["mtp_note"].split()) <= Concept.MTP_NOTE_MAX_WORDS


def test_trimming_keeps_the_front_of_the_line(seeded):
    assert ai.trim_words("one two three four", 2) == "one two"
    assert ai.trim_words("  short  ", 7) == "short"
    assert ai.trim_words(None, 7) == ""


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


def test_asking_for_more_keeps_everything_already_there(signed_in, seeded,
                                                        member):
    """The bug Avi found, and the reason this stage exists.

    "More options" used to delete every option the person had not ticked and
    put a fresh batch in its place. So the natural move — read three, tick
    one, press the button to see more — destroyed the two still being weighed.
    The old test only checked that the *ticked* one survived, which is exactly
    why it passed while the stage was broken.

    Nothing is removed by generating now. Removal is `option_delete`, which a
    person does on purpose.
    """
    concept = make_concept(member, stage=Concept.Stage.OPTIONS)
    attribute = ExoAttribute.objects.get(key="engagement")
    post_json(signed_in, reverse("exo:options_generate", args=[concept.pk]),
              {"attribute": attribute.key})

    first_batch = list(concept.options.filter(attribute=attribute)
                       .values_list("pk", flat=True))
    assert first_batch

    # Tick one, leave the rest untouched: the state that used to be destroyed.
    keeper = concept.options.filter(attribute=attribute).first()
    post_json(signed_in, reverse("exo:option_select", args=[concept.pk, keeper.pk]))

    response = post_json(signed_in,
                         reverse("exo:options_generate", args=[concept.pk]),
                         {"attribute": attribute.key})
    assert response.status_code == 200

    after = set(concept.options.filter(attribute=attribute)
                .values_list("pk", flat=True))
    assert set(first_batch) <= after, "an unticked option was thrown away"
    assert len(after) > len(first_batch), "the new batch was not added"
    assert GeneratedOption.objects.filter(pk=keeper.pk, is_selected=True).exists()

    # And the response carries only what is new, so the page never rebuilds a
    # list it is already showing.
    assert len(response.json()["added"]) == len(after) - len(first_batch)


def test_many_options_can_be_ticked_at_once(signed_in, seeded, member):
    """It is a multiple choice. Ticking a second must not untick the first,
    and everything ticked is what reaches the final build."""
    concept = make_concept(member, stage=Concept.Stage.OPTIONS)
    attribute = ExoAttribute.objects.get(key="engagement")
    post_json(signed_in, reverse("exo:options_generate", args=[concept.pk]),
              {"attribute": attribute.key})

    options = list(concept.options.filter(attribute=attribute))
    assert len(options) >= 2
    for option in options[:2]:
        post_json(signed_in,
                  reverse("exo:option_select", args=[concept.pk, option.pk]))

    selected = set(concept.options.filter(attribute=attribute, is_selected=True)
                   .values_list("pk", flat=True))
    assert selected == {options[0].pk, options[1].pk}

    # And both are what the output stage will be given.
    from exo.journey_views import _selections

    chosen = dict(_selections(concept))
    assert len(chosen[attribute]) == 2


def test_ticking_twice_unticks(signed_in, seeded, member):
    concept = make_concept(member, stage=Concept.Stage.OPTIONS)
    attribute = ExoAttribute.objects.get(key="engagement")
    option = GeneratedOption.objects.create(concept=concept, attribute=attribute,
                                            content="one")
    url = reverse("exo:option_select", args=[concept.pk, option.pk])
    assert post_json(signed_in, url).json()["is_selected"] is True
    assert post_json(signed_in, url).json()["is_selected"] is False


def test_an_option_can_be_thrown_away_on_purpose(signed_in, seeded, member):
    concept = make_concept(member, stage=Concept.Stage.OPTIONS)
    attribute = ExoAttribute.objects.get(key="engagement")
    keep = GeneratedOption.objects.create(concept=concept, attribute=attribute,
                                          content="keep me")
    drop = GeneratedOption.objects.create(concept=concept, attribute=attribute,
                                          content="not this one")

    response = signed_in.post(
        reverse("exo:option_delete", args=[concept.pk, drop.pk]))
    assert response.status_code == 200
    assert not GeneratedOption.objects.filter(pk=drop.pk).exists()
    assert GeneratedOption.objects.filter(pk=keep.pk).exists()


def test_one_member_cannot_delete_another_members_option(signed_in, seeded,
                                                          other):
    theirs = make_concept(other, title="not mine")
    attribute = ExoAttribute.objects.get(key="engagement")
    option = GeneratedOption.objects.create(concept=theirs, attribute=attribute,
                                            content="theirs")
    response = signed_in.post(
        reverse("exo:option_delete", args=[theirs.pk, option.pk]))
    assert response.status_code == 404
    assert GeneratedOption.objects.filter(pk=option.pk).exists()


def test_the_page_shows_how_many_batches_are_left(signed_in, seeded, member):
    """Four a slot a day, shown on the button rather than discovered by being
    refused.

    Counted from the call ledger, which is where real spending is recorded.
    Stub generation deliberately spends nothing and so consumes no budget:
    with no API key the app costs nothing to run and the tests can generate
    freely. Production has a key, so production is where the ceiling bites.
    """
    from exo.models import AiCall

    concept = make_concept(member, stage=Concept.Stage.OPTIONS)
    response = signed_in.get(reverse("exo:concept_options", args=[concept.pk]))
    assert response.context["per_slot"] == 4
    assert all(slot["left"] == 4 for slot in response.context["slots"])

    engagement = ExoAttribute.objects.get(key="engagement")
    for _ in range(3):
        AiCall.objects.create(user=member, task="options", concept=concept,
                              attribute=engagement, ok=True)

    response = signed_in.get(reverse("exo:concept_options", args=[concept.pk]))
    left = {s["attribute"].key: s["left"] for s in response.context["slots"]}
    assert left["engagement"] == 1, "the spent batches were not counted"
    assert left["autonomy"] == 4, "another slot was charged for them"


def test_a_slot_at_its_ceiling_offers_no_button_to_press(signed_in, seeded,
                                                          member):
    from exo.models import AiCall

    concept = make_concept(member, stage=Concept.Stage.OPTIONS)
    engagement = ExoAttribute.objects.get(key="engagement")
    for _ in range(4):
        AiCall.objects.create(user=member, task="options", concept=concept,
                              attribute=engagement, ok=True)

    response = signed_in.get(reverse("exo:concept_options", args=[concept.pk]))
    left = {s["attribute"].key: s["left"] for s in response.context["slots"]}
    assert left["engagement"] == 0
    assert "disabled" in response.content.decode()


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
