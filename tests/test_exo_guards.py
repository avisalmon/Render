"""exo — the cost guards, the moderation gate, and the cockpit (spec §8, §11).

Every guard here is tested for the thing it is actually for: refusing *before*
a provider is reached. A limit that refuses after the call has already been
paid for is not a limit, it is a message.

The moderation gate is tested in both directions, and the fail-open case is
tested deliberately: a moderation outage that quietly made the museum
unpublishable during a live workshop would do more damage than the rare thing
it would have caught.
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse

from exo import ai, journey_views
from exo.access import approve, membership_for
from exo.models import AiCall, Concept, PressRelease

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
def signed_in(client, member):
    client.login(username="builder", password="a-strong-pass-123")
    return client


def post_json(client, url, payload=None):
    return client.post(url, data=json.dumps(payload or {}),
                       content_type="application/json")


def log_calls(user, task, n, concept=None):
    for _ in range(n):
        AiCall.objects.create(user=user, task=task, concept=concept, ok=True)


def log_calls_for(user, task, n, concept=None, attribute=None):
    """Same, but recording which slot the call was for."""
    for _ in range(n):
        AiCall.objects.create(user=user, task=task, concept=concept,
                              attribute=attribute, ok=True)


def never_called(*args, **kwargs):
    raise AssertionError("a provider was reached after a guard should have refused")


# ---- the ceilings are one set of numbers ------------------------------- #

def test_the_limits_come_from_one_place(monkeypatch):
    """The usage screen and the guards read the same function, so the number
    Avi is shown cannot drift from the number enforced."""
    monkeypatch.setenv("EXO_MAX_CONCEPTS", "3")
    assert ai.limits()["concepts_per_member"] == 3


def test_a_nonsense_env_value_falls_back_instead_of_crashing(monkeypatch):
    """A typo in a Render environment variable must not take the app down."""
    monkeypatch.setenv("EXO_MAX_CONCEPTS", "twenty")
    assert ai.limits()["concepts_per_member"] == 20
    monkeypatch.setenv("EXO_MAX_CONCEPTS", "0")
    assert ai.limits()["concepts_per_member"] == 20


def test_the_timeout_is_bounded_at_both_ends(monkeypatch):
    monkeypatch.setenv("EXO_AI_TIMEOUT", "99999")
    assert ai.limits()["timeout_seconds"] == 180
    monkeypatch.setenv("EXO_AI_TIMEOUT", "1")
    assert ai.limits()["timeout_seconds"] == 5


# ---- the concept cap ---------------------------------------------------- #

def test_a_member_cannot_pass_the_concept_cap(signed_in, seeded, member,
                                              monkeypatch):
    monkeypatch.setenv("EXO_MAX_CONCEPTS", "2")
    for name in ["one", "two", "three"]:
        signed_in.post(reverse("exo:concept_create"), {"title": name})
    assert Concept.objects.filter(owner=member).count() == 2


def test_at_the_cap_the_form_is_replaced_not_left_to_fail(signed_in, seeded,
                                                          member, monkeypatch):
    monkeypatch.setenv("EXO_MAX_CONCEPTS", "1")
    Concept.objects.create(owner=member, title="the only one")
    response = signed_in.get(reverse("exo:concepts"))
    assert response.context["at_cap"] is True
    assert 'name="title"' not in response.content.decode()


def test_deleting_one_makes_room_again(signed_in, seeded, member, monkeypatch):
    monkeypatch.setenv("EXO_MAX_CONCEPTS", "1")
    first = Concept.objects.create(owner=member, title="first")
    signed_in.post(reverse("exo:concept_delete", args=[first.pk]))
    signed_in.post(reverse("exo:concept_create"), {"title": "second"})
    assert Concept.objects.filter(owner=member).count() == 1


# ---- the three rings, each refusing before any spend -------------------- #

def test_a_stage_can_be_regenerated_only_so_often_in_a_day(member, monkeypatch):
    monkeypatch.setenv("EXO_MAX_REGEN_PER_STAGE_PER_DAY", "3")
    concept = Concept.objects.create(owner=member, title="c")
    log_calls(member, "options", 3, concept=concept)

    with pytest.raises(ai.AiLimit):
        ai._limit_for(member, "options", concept=concept)


def test_another_concept_is_not_punished_for_the_first_ones_spend(member,
                                                                  monkeypatch):
    """The per-stage ceiling is per concept, so hammering one idea does not
    lock a person out of the next one."""
    monkeypatch.setenv("EXO_MAX_REGEN_PER_STAGE_PER_DAY", "2")
    monkeypatch.setenv("EXO_MAX_CALLS_PER_DAY", "500")
    busy = Concept.objects.create(owner=member, title="busy")
    fresh = Concept.objects.create(owner=member, title="fresh")
    log_calls(member, "options", 5, concept=busy)

    ai._limit_for(member, "options", concept=fresh)  # does not raise


def test_filling_every_slot_once_is_not_treated_as_hammering_one(member, seeded,
                                                                 monkeypatch):
    """The bug this guards against was found by running the real journey, and
    it would have ruined a workshop.

    The options ceiling counted every slot against one budget per concept, so a
    member who generated options for five slots was refused on the sixth —
    while doing exactly what the workshop asks of them. The ceiling exists to
    stop someone hitting *one* slot over and over, so it is counted per slot.
    """
    monkeypatch.setenv("EXO_MAX_REGEN_PER_STAGE_PER_DAY", "3")
    monkeypatch.setenv("EXO_MAX_CALLS_PER_DAY", "500")
    concept = Concept.objects.create(owner=member, title="c")

    from exo.models import ExoAttribute

    slots = list(ExoAttribute.objects.all()[:6])
    for slot in slots:
        log_calls_for(member, "options", 1, concept=concept, attribute=slot)

    # A seventh slot is still fine: none of them has been hammered.
    ai._limit_for(member, "options", concept=concept, attribute=slots[0])


def test_hammering_one_slot_is_still_refused(member, monkeypatch, seeded):
    monkeypatch.setenv("EXO_MAX_REGEN_PER_STAGE_PER_DAY", "3")
    monkeypatch.setenv("EXO_MAX_CALLS_PER_DAY", "500")
    concept = Concept.objects.create(owner=member, title="c")

    from exo.models import ExoAttribute

    slot = ExoAttribute.objects.get(key="algorithms")
    log_calls_for(member, "options", 3, concept=concept, attribute=slot)

    with pytest.raises(ai.AiLimit):
        ai._limit_for(member, "options", concept=concept, attribute=slot)

    # And a different slot is untouched by that.
    other = ExoAttribute.objects.get(key="autonomy")
    ai._limit_for(member, "options", concept=concept, attribute=other)


def test_a_member_has_a_daily_ceiling_across_everything(member, monkeypatch):
    monkeypatch.setenv("EXO_MAX_CALLS_PER_DAY", "4")
    log_calls(member, "interview", 4)
    with pytest.raises(ai.AiLimit):
        ai._limit_for(member, "output")


def test_the_site_guard_refuses_everyone_and_says_try_later(member, monkeypatch):
    monkeypatch.setenv("EXO_DAILY_SPEND_GUARD", "5")
    other = User.objects.create_user("spender", "s@example.com", "a-strong-pass-123")
    log_calls(other, "options", 5)

    with pytest.raises(ai.AiLimit) as caught:
        ai._limit_for(member, "options")
    assert "later" in str(caught.value)


def test_failed_calls_count_toward_the_ceiling(member, monkeypatch):
    """A retry storm against a provider that is down costs money for every
    attempt. A guard that only counted successes would wave through exactly
    the worst case."""
    monkeypatch.setenv("EXO_MAX_CALLS_PER_DAY", "3")
    for _ in range(3):
        AiCall.objects.create(user=member, task="options", ok=False,
                              detail="provider down")
    with pytest.raises(ai.AiLimit):
        ai._limit_for(member, "options")


def test_yesterdays_spend_does_not_count_against_today(member, monkeypatch):
    from django.utils import timezone

    monkeypatch.setenv("EXO_MAX_CALLS_PER_DAY", "2")
    old = AiCall.objects.create(user=member, task="options", ok=True)
    AiCall.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - timezone.timedelta(days=2)
    )
    ai._limit_for(member, "options")  # does not raise


def test_the_guard_refuses_before_any_provider_is_reached(member, monkeypatch):
    """The whole point: a limit that spends first and refuses after is not a
    limit."""
    monkeypatch.setenv("EXO_DAILY_SPEND_GUARD", "1")
    log_calls(member, "options", 1)
    monkeypatch.setattr("app.ai_chat.call_openai", never_called)

    with pytest.raises(ai.AiLimit):
        ai._limit_for(member, "options")


def test_a_limited_endpoint_answers_429_not_500(signed_in, seeded, member,
                                                monkeypatch):
    """A ceiling is a wait, not a fault, and must never read to a member like
    the app is broken."""
    monkeypatch.setenv("EXO_DAILY_SPEND_GUARD", "1")
    log_calls(member, "options", 1)
    concept = Concept.objects.create(owner=member, title="c",
                                     stage=Concept.Stage.OPTIONS)

    def limited(*args, **kwargs):
        raise ai.AiLimit("try later")

    monkeypatch.setattr(ai, "generate_options", limited)
    response = post_json(signed_in,
                         reverse("exo:options_generate", args=[concept.pk]),
                         {"attribute": "algorithms"})
    assert response.status_code == 429


def test_the_rest_of_the_site_is_untouched_by_the_guard(client, seeded, member,
                                                        monkeypatch):
    """Degrade, never fail (spec §8, G5): the public half does not even know
    there is a ceiling."""
    monkeypatch.setenv("EXO_DAILY_SPEND_GUARD", "1")
    log_calls(member, "options", 5)
    for url in [reverse("exo:home"), reverse("exo:learn"), reverse("exo:museum")]:
        assert client.get(url).status_code == 200


# ---- the timeout -------------------------------------------------------- #

def test_a_provider_that_never_answers_is_abandoned(member, monkeypatch):
    """Bounded wait, and the abandoned call is still logged: a timeout that
    leaves no trace is a cost nobody can explain later."""
    import time

    monkeypatch.setenv("EXO_AI_TIMEOUT", "5")  # the floor
    monkeypatch.setattr(ai, "_timeout", lambda: 1)

    def hangs(*args, **kwargs):
        # Long enough to blow the one-second deadline, short enough that the
        # abandoned thread does not hold the interpreter open at exit — Python
        # joins pool threads on shutdown even when we stopped waiting.
        time.sleep(3)
        return {"content": "too late"}

    monkeypatch.setattr("app.ai_chat.call_openai", hangs)

    started = time.monotonic()
    with pytest.raises(ai.AiError):
        ai._call([{"role": "user", "content": "hi"}], "system", "interview",
                 user=member)
    waited = time.monotonic() - started

    assert waited < 10, f"waited {waited:.1f}s for a call it had given up on"
    assert AiCall.objects.filter(task="interview", ok=False).exists()


# ---- moderation before the wall (G6) ------------------------------------ #

def test_private_work_is_never_sent_for_moderation(member, monkeypatch):
    """What a person writes for themselves is not the museum's business, and
    sending it to a provider anyway would be a quiet betrayal."""
    concept = Concept.objects.create(owner=member, title="c")
    release = PressRelease.objects.create(
        concept=concept, headline="h", body="b", document_body="d",
        visibility=PressRelease.Visibility.PRIVATE,
    )
    monkeypatch.setattr(ai, "public_text_is_safe", never_called)
    assert journey_views._screen_before_the_wall(release, member) == ""


def test_a_flagged_release_is_made_private_not_merely_refused(member, monkeypatch):
    """A refusal that leaves the text on the wall would be theatre."""
    concept = Concept.objects.create(owner=member, title="c")
    release = PressRelease.objects.create(
        concept=concept, headline="h", body="b", document_body="d",
        visibility=PressRelease.Visibility.PUBLIC,
    )
    monkeypatch.setattr(ai, "public_text_is_safe", lambda text, user=None: (False, "hate"))

    detail = journey_views._screen_before_the_wall(release, member)
    assert detail == "hate"
    release.refresh_from_db()
    assert release.visibility == PressRelease.Visibility.PRIVATE


def test_going_public_with_flagged_text_is_refused_at_the_switch(signed_in, seeded,
                                                                member, monkeypatch):
    concept = Concept.objects.create(owner=member, title="c",
                                     stage=Concept.Stage.OUTPUT)
    release = PressRelease.objects.create(
        concept=concept, headline="h", body="b", document_body="d",
        visibility=PressRelease.Visibility.PRIVATE,
    )
    monkeypatch.setattr(ai, "public_text_is_safe", lambda text, user=None: (False, "violence"))

    response = post_json(signed_in,
                         reverse("exo:output_visibility", args=[concept.pk]),
                         {"visibility": "public"})
    assert response.status_code == 409
    release.refresh_from_db()
    assert release.visibility == PressRelease.Visibility.PRIVATE


def test_a_hand_edit_on_a_public_release_is_screened_too(signed_in, seeded,
                                                         member, monkeypatch):
    """Otherwise "generate something bland, then edit it" is an open door."""
    concept = Concept.objects.create(owner=member, title="c",
                                     stage=Concept.Stage.OUTPUT)
    release = PressRelease.objects.create(
        concept=concept, headline="h", body="b", document_body="d",
        visibility=PressRelease.Visibility.PUBLIC,
    )
    monkeypatch.setattr(ai, "public_text_is_safe", lambda text, user=None: (False, "hate"))

    post_json(signed_in, reverse("exo:output_edit", args=[concept.pk]),
              {"headline": "something else entirely"})
    release.refresh_from_db()
    assert release.visibility == PressRelease.Visibility.PRIVATE


def test_moderation_fails_open_when_it_cannot_run(member, monkeypatch):
    """A moderation outage must not become a museum outage. Avi can hide
    anything from the cockpit in one click; a silent publishing freeze during a
    live workshop is the worse failure."""
    def broken(*args, **kwargs):
        raise RuntimeError("moderation endpoint down")

    monkeypatch.setattr(ai, "is_stub", lambda: False)
    monkeypatch.setattr("app.ai_chat.check_moderation", broken)

    ok, detail = ai.public_text_is_safe("some ordinary text", user=member)
    assert ok is True
    assert detail == "unavailable"


def test_empty_text_needs_no_provider(monkeypatch):
    monkeypatch.setattr(ai, "is_stub", lambda: False)
    monkeypatch.setattr("app.ai_chat.check_moderation", never_called)
    assert ai.public_text_is_safe("") == (True, "")


# ---- the cockpit -------------------------------------------------------- #

@pytest.fixture
def admin_client_(client, db):
    User.objects.create_superuser("root", "root@example.com", "a-strong-pass-123")
    client.login(username="root", password="a-strong-pass-123")
    return client


def test_hiding_a_release_takes_it_off_the_wall_immediately(admin_client_, seeded,
                                                            member):
    from exo.museum_views import publicly_visible

    concept = Concept.objects.create(owner=member, title="c")
    release = PressRelease.objects.create(concept=concept, headline="On the wall",
                                          body="b", document_body="d")
    assert release.pk in [r.pk for r in publicly_visible()]

    admin_client_.post(reverse("exo:manage_moderate", args=[release.pk]),
                       {"action": "hide"})
    assert release.pk not in [r.pk for r in publicly_visible()]

    admin_client_.post(reverse("exo:manage_moderate", args=[release.pk]),
                       {"action": "unhide"})
    assert release.pk in [r.pk for r in publicly_visible()]


def test_hiding_keeps_the_work_for_its_owner(admin_client_, client, seeded, member):
    """Moderation hides; it never destroys someone's writing (spec §10.4)."""
    concept = Concept.objects.create(owner=member, title="c")
    release = PressRelease.objects.create(concept=concept, headline="Mine",
                                          body="b", document_body="d")
    admin_client_.post(reverse("exo:manage_moderate", args=[release.pk]),
                       {"action": "hide"})

    release.refresh_from_db()
    assert release.headline == "Mine" and release.body == "b"
    assert release.visible_to(member) is True


def test_only_an_admin_can_hide(client, seeded, member):
    concept = Concept.objects.create(owner=member, title="c")
    release = PressRelease.objects.create(concept=concept, headline="h",
                                          body="b", document_body="d")
    client.login(username="builder", password="a-strong-pass-123")
    response = client.post(reverse("exo:manage_moderate", args=[release.pk]),
                           {"action": "hide"})
    assert response.status_code == 403
    release.refresh_from_db()
    assert release.hidden_by_admin is False


def test_the_usage_view_counts_what_the_log_holds(admin_client_, seeded, member):
    log_calls(member, "options", 3)
    log_calls(member, "output", 2)
    AiCall.objects.create(user=member, task="output", ok=False, detail="boom")

    response = admin_client_.get(reverse("exo:manage_usage"))
    assert response.status_code == 200
    assert response.context["total"] == 6
    assert response.context["today"] == 6
    assert response.context["failures"] == 1
    tasks = {row["task"]: row["n"] for row in response.context["by_task"]}
    assert tasks == {"options": 3, "output": 3}


def test_the_usage_view_shows_the_guard_the_guard_enforces(admin_client_, seeded,
                                                           member, monkeypatch):
    monkeypatch.setenv("EXO_DAILY_SPEND_GUARD", "10")
    log_calls(member, "options", 4)
    response = admin_client_.get(reverse("exo:manage_usage"))
    assert response.context["guard"] == {"used": 4, "ceiling": 10, "over": False}


def test_the_cockpit_says_out_loud_when_the_ceiling_is_reached(admin_client_,
                                                               seeded, member,
                                                               monkeypatch):
    monkeypatch.setenv("EXO_DAILY_SPEND_GUARD", "2")
    log_calls(member, "options", 2)
    response = admin_client_.get(reverse("exo:manage_usage"))
    assert response.context["guard"]["over"] is True
    assert "exo-notice-warn" in response.content.decode()


def test_revoking_a_member_keeps_their_work(admin_client_, seeded, member):
    """Spec §10.4: access is a door, not an eraser."""
    concept = Concept.objects.create(owner=member, title="still mine")
    membership = member.exo_membership
    admin_client_.post(reverse("exo:manage_requests"))  # page exists
    admin_client_.post(reverse("exo:manage_decide", args=[membership.pk]),
                       {"action": "revoke"})

    assert Concept.objects.filter(pk=concept.pk).exists()
    assert User.objects.filter(pk=member.pk).exists()
