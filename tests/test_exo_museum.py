"""exo — the museum, visibility, and likes (spec §7).

The visibility matrix is the part of this app with the most ways to leak a
person's idea, so it is tested as a matrix rather than as a few happy paths:
every combination of who is asking and what the owner chose.

The timed case is tested by moving the clock, not by sleeping, and both
directions are checked — an expiry that never expires and an expiry that
expires too early are equally wrong.
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from exo.access import approve, membership_for
from exo.models import Concept, PressRelease, PressReleaseLike
from exo.museum_views import publicly_visible

User = get_user_model()
pytestmark = pytest.mark.django_db

HOUR = timezone.timedelta(hours=1)


@pytest.fixture
def seeded():
    call_command("seed_exo", quiet=True)


def make_user(username):
    return User.objects.create_user(username, f"{username}@example.com",
                                    "a-strong-pass-123")


@pytest.fixture
def owner(db):
    user = make_user("owner")
    approve(membership_for(user, create=True))
    return user


@pytest.fixture
def stranger(db):
    return make_user("stranger")


def make_release(owner, **kw):
    concept = Concept.objects.create(owner=owner, title="A car rental service",
                                     stage=Concept.Stage.OUTPUT)
    return PressRelease.objects.create(
        concept=concept,
        headline=kw.pop("headline", "Cars arrive before you ask"),
        body="body", document_body="document",
        **kw,
    )


# ---- the wall is public ------------------------------------------------ #

def test_the_museum_opens_with_no_account(client, seeded, owner):
    make_release(owner)
    response = client.get(reverse("exo:museum"))
    assert response.status_code == 200
    assert "Cars arrive before you ask" in response.content.decode()


def test_an_unfinished_release_is_not_on_the_wall(client, seeded, owner):
    """A concept whose output was never generated has an empty headline, and
    an empty frame on the wall looks like a bug to every visitor."""
    make_release(owner, headline="")
    assert publicly_visible().count() == 0


def test_sharing_is_the_default(seeded, owner):
    """Spec §7.1: default in, opt out — the museum is the point of the
    workshop."""
    release = make_release(owner)
    assert release.visibility == PressRelease.Visibility.PUBLIC


# ---- the visibility matrix --------------------------------------------- #

def scenarios(owner, other, friend):
    """(name, release, {viewer: may_see}) for every choice an owner can make."""
    now = timezone.now()
    public = make_release(owner, visibility=PressRelease.Visibility.PUBLIC)
    private = make_release(owner, visibility=PressRelease.Visibility.PRIVATE)
    live = make_release(owner, visibility=PressRelease.Visibility.TIMED,
                        public_until=now + HOUR)
    expired = make_release(owner, visibility=PressRelease.Visibility.TIMED,
                           public_until=now - HOUR)
    specific = make_release(owner, visibility=PressRelease.Visibility.SPECIFIC)
    specific.shared_with.add(friend)
    hidden = make_release(owner, visibility=PressRelease.Visibility.PUBLIC,
                          hidden_by_admin=True)

    anon = None
    return [
        ("public", public, {anon: True, other: True, friend: True, owner: True}),
        ("private", private, {anon: False, other: False, friend: False, owner: True}),
        ("timed live", live, {anon: True, other: True, friend: True, owner: True}),
        ("timed expired", expired,
         {anon: False, other: False, friend: False, owner: True}),
        ("specific", specific,
         {anon: False, other: False, friend: True, owner: True}),
        ("hidden", hidden, {anon: False, other: False, friend: False, owner: True}),
    ]


def test_visible_to_covers_every_combination(seeded, owner):
    other, friend = make_user("other"), make_user("friend")
    for name, release, expectations in scenarios(owner, other, friend):
        for viewer, expected in expectations.items():
            actual = release.visible_to(viewer)
            assert actual is expected, f"{name} / {viewer}: got {actual}"


def test_the_owner_always_reaches_their_own_work(seeded, owner, client):
    """Including after it expires: the release does not vanish from the person
    who wrote it (spec §7.1)."""
    client.login(username="owner", password="a-strong-pass-123")
    expired = make_release(owner, visibility=PressRelease.Visibility.TIMED,
                           public_until=timezone.now() - HOUR)
    response = client.get(reverse("exo:museum_item", args=[expired.pk]))
    assert response.status_code == 200
    assert response.context["expired"] is True


def test_a_private_release_is_a_404_not_a_403(client, seeded, owner):
    """A 403 confirms it exists. For someone elses unpublished idea, the honest
    answer is that there is nothing here for you."""
    private = make_release(owner, visibility=PressRelease.Visibility.PRIVATE)
    assert client.get(reverse("exo:museum_item", args=[private.pk])).status_code == 404


def test_hidden_by_admin_outranks_the_owners_choice(client, seeded, owner):
    hidden = make_release(owner, hidden_by_admin=True)
    assert client.get(reverse("exo:museum_item", args=[hidden.pk])).status_code == 404
    assert hidden.pk not in [r.pk for r in publicly_visible()]


def test_the_wall_and_the_page_never_disagree(client, seeded, owner):
    """One queryset behind both, asserted rather than assumed."""
    other = make_user("other2")
    friend = make_user("friend2")
    for _name, release, _expected in scenarios(owner, other, friend):
        on_wall = release.pk in [r.pk for r in publicly_visible()]
        opens = client.get(
            reverse("exo:museum_item", args=[release.pk])
        ).status_code == 200
        assert on_wall == opens, release.visibility


# ---- the clock, not a scheduled job ------------------------------------ #

def test_expiry_needs_no_job_to_run(seeded, owner):
    """Spec §7.1: visibility is a query. Nothing runs on a schedule, so there
    is nothing to fail quietly at 3am."""
    release = make_release(owner, visibility=PressRelease.Visibility.TIMED,
                           public_until=timezone.now() + HOUR)
    assert release.pk in [r.pk for r in publicly_visible()]

    later = timezone.now() + timezone.timedelta(hours=2)
    assert release.pk not in [r.pk for r in publicly_visible(now=later)]
    assert release.is_public_now(now=later) is False
    # and the row was never touched
    release.refresh_from_db()
    assert release.visibility == PressRelease.Visibility.TIMED


def test_a_timed_window_does_not_expire_early(seeded, owner):
    release = make_release(owner, visibility=PressRelease.Visibility.TIMED,
                           public_until=timezone.now() + timezone.timedelta(hours=24))
    almost = timezone.now() + timezone.timedelta(hours=23, minutes=59)
    assert release.is_public_now(now=almost) is True


# ---- the owner changes their mind -------------------------------------- #

def post_json(client, url, payload):
    return client.post(url, data=json.dumps(payload),
                       content_type="application/json")


def test_the_owner_can_take_it_off_the_wall(client, seeded, owner):
    release = make_release(owner)
    client.login(username="owner", password="a-strong-pass-123")
    post_json(client, reverse("exo:output_visibility", args=[release.concept_id]),
              {"visibility": "private"})
    assert publicly_visible().count() == 0


def test_a_timed_window_is_clamped_to_something_sane(client, seeded, owner):
    release = make_release(owner)
    client.login(username="owner", password="a-strong-pass-123")
    response = post_json(
        client, reverse("exo:output_visibility", args=[release.concept_id]),
        {"visibility": "timed", "hours": 99999},
    )
    assert response.status_code == 200
    release.refresh_from_db()
    assert release.public_until <= timezone.now() + timezone.timedelta(
        days=30, minutes=1)


def test_a_nonsense_visibility_is_refused(client, seeded, owner):
    release = make_release(owner)
    client.login(username="owner", password="a-strong-pass-123")
    response = post_json(
        client, reverse("exo:output_visibility", args=[release.concept_id]),
        {"visibility": "everyone-on-earth"},
    )
    assert response.status_code == 400
    release.refresh_from_db()
    assert release.visibility == PressRelease.Visibility.PUBLIC


def test_another_member_cannot_change_visibility(client, seeded, owner):
    """The ownership check, tested with someone who is past the gate — so what
    refuses here is ownership itself and not membership."""
    release = make_release(owner)
    intruder = make_user("intruder")
    approve(membership_for(intruder, create=True))

    client.login(username="intruder", password="a-strong-pass-123")
    response = post_json(
        client, reverse("exo:output_visibility", args=[release.concept_id]),
        {"visibility": "private"},
    )
    assert response.status_code == 404
    release.refresh_from_db()
    assert release.visibility == PressRelease.Visibility.PUBLIC


def test_a_non_member_never_reaches_the_ownership_check(client, seeded, owner,
                                                        stranger):
    """The gate is the outer door: someone who was never approved is turned
    away before the view runs at all."""
    release = make_release(owner)
    client.login(username="stranger", password="a-strong-pass-123")
    response = post_json(
        client, reverse("exo:output_visibility", args=[release.concept_id]),
        {"visibility": "private"},
    )
    assert response.status_code == 302
    assert reverse("exo:join") in response["Location"]
    release.refresh_from_db()
    assert release.visibility == PressRelease.Visibility.PUBLIC


# ---- likes -------------------------------------------------------------- #

def test_a_like_toggles_and_counts_once(client, seeded, owner, stranger):
    release = make_release(owner)
    client.login(username="stranger", password="a-strong-pass-123")
    url = reverse("exo:museum_like", args=[release.pk])

    first = client.post(url)
    assert first.json() == {"liked": True, "likes": 1}

    # Pressing it twice more must not accumulate.
    client.post(url)
    again = client.post(url)
    assert again.json() == {"liked": True, "likes": 1}
    assert PressReleaseLike.objects.filter(release=release).count() == 1


def test_two_people_are_two_likes(client, seeded, owner):
    release = make_release(owner)
    for name in ["a", "b"]:
        make_user(name)
        client.login(username=name, password="a-strong-pass-123")
        client.post(reverse("exo:museum_like", args=[release.pk]))
    assert PressReleaseLike.objects.filter(release=release).count() == 2


def test_liking_asks_for_an_account_rather_than_failing(client, seeded, owner):
    release = make_release(owner)
    response = client.post(reverse("exo:museum_like", args=[release.pk]))
    assert response.status_code == 403
    assert PressReleaseLike.objects.count() == 0


def test_a_release_you_cannot_see_cannot_be_liked(client, seeded, owner, stranger):
    private = make_release(owner, visibility=PressRelease.Visibility.PRIVATE)
    client.login(username="stranger", password="a-strong-pass-123")
    response = client.post(reverse("exo:museum_like", args=[private.pk]))
    assert response.status_code == 404
    assert PressReleaseLike.objects.count() == 0


# ---- views -------------------------------------------------------------- #

def test_a_refresh_is_not_a_second_view(client, seeded, owner):
    release = make_release(owner)
    url = reverse("exo:museum_item", args=[release.pk])
    client.get(url)
    client.get(url)
    client.get(url)
    release.refresh_from_db()
    assert release.view_count == 1


# ---- sorting and filtering ---------------------------------------------- #

def test_sorting_by_likes_puts_the_liked_one_first(client, seeded, owner):
    quiet = make_release(owner, headline="Quiet one")
    loud = make_release(owner, headline="Loud one")
    fan = make_user("fan")
    PressReleaseLike.objects.create(release=loud, user=fan)

    response = client.get(reverse("exo:museum"), {"sort": "liked"})
    order = [r.pk for r in response.context["releases"]]
    assert order.index(loud.pk) < order.index(quiet.pk)


def test_the_wall_can_be_filtered_to_one_language(client, seeded, owner):
    hebrew = make_release(owner, headline="בעברית", language="he")
    english = make_release(owner, headline="In English", language="en")
    response = client.get(reverse("exo:museum"), {"lang": "en"})
    shown = [r.pk for r in response.context["releases"]]
    assert english.pk in shown and hebrew.pk not in shown
