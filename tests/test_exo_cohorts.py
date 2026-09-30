"""exo — workshop groups: the link Avi sends to a room (spec §4.2, EPIC K).

**The refusals come first and outnumber the happy paths**, because this link
is a key: it approves whoever opens it. That ratio is the point. These tests
are what make it safe to paste the link into a group chat, and what stops
tomorrow's edit from quietly widening what it grants.

The second half is about the clock, and the half of *that* which matters most
is what keeps working after a window closes. A gate that took too much would
end a workshop with people locked out of their own writing, which is a worse
failure than the tokens it was trying to save.
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from exo import ai
from exo.access import GROUP_NAME, approve, is_exo_member, membership_for
from exo.models import (
    Cohort,
    CohortMember,
    Concept,
    Membership,
    current_cohort,
    has_open_window,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded():
    call_command("seed_exo", quiet=True)


@pytest.fixture
def workshop(db):
    return Cohort.objects.create(name="סדנת מנהלים, אוקטובר")


def link(cohort):
    return reverse("exo:join_by_link", args=[cohort.token])


# ---- the refusals -------------------------------------------------------- #

def test_an_unknown_token_is_simply_not_there(client, seeded):
    response = client.get(reverse("exo:join_by_link", args=["not-a-real-token"]))
    assert response.status_code == 404
    assert not Membership.objects.exists()


def test_a_finished_workshop_refuses_and_says_so_plainly(client, seeded, workshop):
    """Somebody arriving a day late has done nothing wrong, so this is a page
    that explains, not an error."""
    workshop.starts_at = timezone.now() - timezone.timedelta(hours=30)
    workshop.save()

    response = client.get(link(workshop))
    assert response.status_code == 410
    assert not Membership.objects.exists()
    assert not CohortMember.objects.exists()


def test_a_workshop_closed_by_hand_refuses(client, seeded, workshop):
    workshop.is_closed = True
    workshop.save()
    assert client.get(link(workshop)).status_code == 410
    assert not Membership.objects.exists()


def test_a_workshop_that_has_not_started_refuses(client, seeded, workshop):
    workshop.starts_at = timezone.now() + timezone.timedelta(days=1)
    workshop.save()
    assert client.get(link(workshop)).status_code == 410
    assert not Membership.objects.exists()


def test_a_full_workshop_refuses(client, seeded, workshop):
    """The one bound on a forwarded link, since this key deliberately creates
    accounts (spec K7)."""
    workshop.max_joins = 2
    workshop.save()
    for i in range(2):
        CohortMember.objects.create(
            cohort=workshop,
            user=User.objects.create_user(f"seat{i}", f"s{i}@example.com", "x-pass-123"),
        )

    assert client.get(link(workshop)).status_code == 410
    assert workshop.members.count() == 2


def test_no_refusal_ever_leaves_a_half_made_member(client, seeded, workshop):
    """Every refusal path, asserted together: none of them may create an
    account, a membership, or a group row."""
    before = (User.objects.count(), Membership.objects.count())
    for setup in [
        lambda c: setattr(c, "is_closed", True),
        lambda c: setattr(c, "starts_at", timezone.now() - timezone.timedelta(days=2)),
        lambda c: setattr(c, "starts_at", timezone.now() + timezone.timedelta(days=2)),
    ]:
        setup(workshop)
        workshop.save()
        client.get(link(workshop))
        workshop.is_closed = False
        workshop.starts_at = timezone.now()

    assert (User.objects.count(), Membership.objects.count()) == before


# ---- what the key may and may not grant ---------------------------------- #

def test_the_token_is_not_guessable_and_not_sequential(seeded):
    tokens = {Cohort.objects.create(name=f"w{i}").token for i in range(5)}
    assert len(tokens) == 5
    for token in tokens:
        assert len(token) >= 30, token
        assert not token.isdigit()


def test_the_link_grants_ordinary_membership_and_nothing_above_it(client, seeded,
                                                                  workshop):
    client.get(link(workshop))
    user = User.objects.exclude(is_superuser=True).get()

    assert is_exo_member(user)
    assert user.groups.filter(name=GROUP_NAME).exists()
    assert not user.is_staff
    assert not user.is_superuser
    assert user.groups.count() == 1, "the link handed out more than its one group"


def test_the_group_cannot_be_chosen_by_whoever_opens_the_link(client, seeded,
                                                              workshop):
    """The privileged thing is named in code, never in the request."""
    Group.objects.get_or_create(name="staff")
    client.get(link(workshop) + "?group=staff&is_staff=1")
    user = User.objects.exclude(is_superuser=True).get()

    assert user.groups.filter(name=GROUP_NAME).exists()
    assert not user.groups.filter(name="staff").exists()
    assert not user.is_staff


def test_every_arrival_is_recorded(client, seeded, workshop):
    """"Who came through this link" is the question Avi asked."""
    client.get(link(workshop))
    joined = CohortMember.objects.get()
    assert joined.cohort == workshop
    assert joined.joined_at is not None


def test_opening_the_link_twice_is_one_arrival(client, seeded, workshop):
    client.get(link(workshop))
    client.get(link(workshop))
    assert CohortMember.objects.count() == 1


# ---- the happy path ------------------------------------------------------ #

def test_one_click_from_the_link_to_the_builder(client, seeded, workshop):
    """Thirty people in a room cannot each wait for a tap, which is the whole
    reason this link approves on the spot."""
    response = client.get(link(workshop))
    assert response.status_code == 302
    assert response["Location"] == reverse("exo:concepts")

    membership = Membership.objects.get()
    assert membership.status == Membership.Status.APPROVED
    assert membership.ai_needs_open_window is True


def test_somebody_who_already_has_an_account_keeps_it(client, seeded, workshop):
    user = User.objects.create_user("regular", "r@example.com", "a-strong-pass-123")
    client.login(username="regular", password="a-strong-pass-123")

    client.get(link(workshop))

    assert User.objects.filter(pk=user.pk).exists()
    assert User.objects.exclude(is_superuser=True).count() == 1
    assert CohortMember.objects.get().user == user


# ---- the clock: what stops, and what must not ---------------------------- #

def test_a_participant_can_generate_while_the_window_is_open(seeded, workshop):
    user = User.objects.create_user("inside", "i@example.com", "a-strong-pass-123")
    membership = membership_for(user, create=True)
    approve(membership)
    membership.ai_needs_open_window = True
    membership.save()
    CohortMember.objects.create(cohort=workshop, user=user)

    assert has_open_window(user)
    assert ai._workshop_window_closed(user) is False


def test_when_the_window_closes_the_spending_stops(seeded, workshop):
    user = User.objects.create_user("after", "a@example.com", "a-strong-pass-123")
    membership = membership_for(user, create=True)
    approve(membership)
    membership.ai_needs_open_window = True
    membership.save()
    CohortMember.objects.create(cohort=workshop, user=user)

    workshop.starts_at = timezone.now() - timezone.timedelta(hours=25)
    workshop.save()

    assert not has_open_window(user)
    assert ai._workshop_window_closed(user) is True


def test_the_refusal_is_a_licence_ending_not_a_ceiling_resetting(seeded, workshop,
                                                                 monkeypatch):
    """"Try again tomorrow" would be untrue, so it says something else."""
    user = User.objects.create_user("expired", "e@example.com", "a-strong-pass-123")
    membership = membership_for(user, create=True)
    approve(membership)
    membership.ai_needs_open_window = True
    membership.save()
    CohortMember.objects.create(cohort=workshop, user=user)
    workshop.starts_at = timezone.now() - timezone.timedelta(days=3)
    workshop.save()

    monkeypatch.setattr(ai, "is_stub", lambda: False)
    monkeypatch.setattr("app.ai_chat.call_openai",
                        lambda *a, **k: pytest.fail("a provider was reached"))

    with pytest.raises(ai.AiLimit) as caught:
        ai._call([{"role": "user", "content": "hi"}], "system", "interview",
                 user=user)
    assert str(caught.value) == "limit_window"


def test_every_task_is_covered_not_only_the_three_with_ceilings(seeded, workshop,
                                                                monkeypatch):
    """The window is checked at the single door to the provider rather than in
    the ceilings guard, because only three of the six tasks pass through the
    ceilings. The interview and the summary must not keep spending."""
    user = User.objects.create_user("all", "all@example.com", "a-strong-pass-123")
    membership = membership_for(user, create=True)
    approve(membership)
    membership.ai_needs_open_window = True
    membership.save()
    CohortMember.objects.create(cohort=workshop, user=user)
    workshop.is_closed = True
    workshop.save()

    monkeypatch.setattr(ai, "is_stub", lambda: False)
    monkeypatch.setattr("app.ai_chat.call_openai",
                        lambda *a, **k: pytest.fail("a provider was reached"))

    for task in ["interview", "settle", "options", "output", "score",
                 "stress_test"]:
        with pytest.raises(ai.AiLimit):
            ai._call([{"role": "user", "content": "x"}], "s", task, user=user)


def test_a_closed_window_takes_the_ai_and_nothing_else(client, seeded, workshop):
    """The half that matters. Everything that does not reach a model keeps
    working: reading, the museum, editing what you wrote, downloading it,
    choosing who sees it."""
    from exo.models import NewspaperStyle, PressRelease

    user = User.objects.create_user("still", "s@example.com", "a-strong-pass-123")
    membership = membership_for(user, create=True)
    approve(membership)
    membership.ai_needs_open_window = True
    membership.save()
    CohortMember.objects.create(cohort=workshop, user=user)

    concept = Concept.objects.create(owner=user, title="mine",
                                     stage=Concept.Stage.OUTPUT)
    release = PressRelease.objects.create(
        concept=concept, headline="Eighteen months on",
        body="A paragraph.\n\nAnd another one.", document_body="doc",
        newspaper_style=NewspaperStyle.objects.first(),
    )

    workshop.starts_at = timezone.now() - timezone.timedelta(days=2)
    workshop.save()
    client.login(username="still", password="a-strong-pass-123")

    # Reading their own work.
    for name in ["exo:concepts", "exo:museum", "exo:learn"]:
        assert client.get(reverse(name)).status_code == 200, name
    assert client.get(
        reverse("exo:concept_output", args=[concept.pk])).status_code == 200

    # Editing it.
    edited = client.post(
        reverse("exo:output_edit", args=[concept.pk]),
        data=json.dumps({"headline": "My own headline", "body": "Still mine."}),
        content_type="application/json")
    assert edited.status_code == 200
    release.refresh_from_db()
    assert release.headline == "My own headline"

    # Downloading it, and choosing who sees it.
    assert client.get(
        reverse("exo:article_download", args=[release.pk, "pdf"])
    ).status_code == 200
    assert client.post(
        reverse("exo:output_visibility", args=[concept.pk]),
        data=json.dumps({"visibility": "private"}),
        content_type="application/json").status_code == 200


def test_somebody_avi_approved_by_hand_never_acquires_a_window(seeded, workshop):
    """A hand-approved member has no window and must not grow one by attending
    a workshop later."""
    user = User.objects.create_user("byhand", "h@example.com", "a-strong-pass-123")
    membership = membership_for(user, create=True)
    approve(membership)  # the cockpit route: ai_needs_open_window stays False

    CohortMember.objects.create(cohort=workshop, user=user)
    workshop.is_closed = True
    workshop.save()

    assert membership.ai_needs_open_window is False
    assert ai._workshop_window_closed(user) is False


# ---- belonging accumulates ------------------------------------------------ #

def test_a_second_workshop_reopens_the_ai_and_keeps_the_first(client, seeded,
                                                              workshop):
    october = workshop
    october.starts_at = timezone.now() - timezone.timedelta(days=30)
    october.save()

    user = User.objects.create_user("returner", "r2@example.com", "a-strong-pass-123")
    membership = membership_for(user, create=True)
    approve(membership)
    membership.ai_needs_open_window = True
    membership.save()
    CohortMember.objects.create(cohort=october, user=user)
    assert ai._workshop_window_closed(user) is True

    november = Cohort.objects.create(name="סדנה שנייה")
    client.login(username="returner", password="a-strong-pass-123")
    client.get(link(november))

    assert ai._workshop_window_closed(user) is False
    assert CohortMember.objects.filter(user=user).count() == 2, (
        "attending a second workshop dropped them from the first")
    assert set(CohortMember.objects.filter(user=user)
               .values_list("cohort__name", flat=True)) == {october.name,
                                                            november.name}


def test_new_work_is_stamped_with_the_newest_workshop(client, seeded, workshop):
    user = User.objects.create_user("maker", "m@example.com", "a-strong-pass-123")
    approve(membership_for(user, create=True))
    CohortMember.objects.create(cohort=workshop, user=user)

    client.login(username="maker", password="a-strong-pass-123")
    client.post(reverse("exo:concept_create"), {"title": "first idea"})
    first = Concept.objects.get(title="first idea")
    assert first.cohort == workshop

    later = Cohort.objects.create(name="סדנה מאוחרת")
    CohortMember.objects.create(cohort=later, user=user)
    assert current_cohort(user) == later

    client.post(reverse("exo:concept_create"), {"title": "second idea"})
    assert Concept.objects.get(title="second idea").cohort == later

    # And the first one did not move.
    first.refresh_from_db()
    assert first.cohort == workshop, "a later workshop reattributed earlier work"


# ---- Avi's page ----------------------------------------------------------- #

@pytest.fixture
def admin(client, db):
    User.objects.create_superuser("root", "root@example.com", "a-strong-pass-123")
    client.login(username="root", password="a-strong-pass-123")
    return client


def test_only_an_admin_sees_the_workshops(client, seeded, workshop):
    user = User.objects.create_user("plain", "p@example.com", "a-strong-pass-123")
    approve(membership_for(user, create=True))
    client.login(username="plain", password="a-strong-pass-123")
    assert client.get(reverse("exo:manage_cohorts")).status_code == 403
    assert client.post(reverse("exo:manage_cohort_create"),
                       {"name": "mine"}).status_code == 403
    assert not Cohort.objects.filter(name="mine").exists()


def test_the_page_shows_the_link_and_who_came(admin, seeded, workshop):
    User.objects.create_user("guest", "guest@example.com", "a-strong-pass-123")
    CohortMember.objects.create(cohort=workshop,
                                user=User.objects.get(username="guest"))

    response = admin.get(reverse("exo:manage_cohorts"))
    assert response.status_code == 200
    body = response.content.decode()
    assert workshop.token in body, "the link is not on the page that exists to show it"
    assert "guest@example.com" in body


def test_creating_a_workshop_from_the_page(admin, seeded):
    admin.post(reverse("exo:manage_cohort_create"),
               {"name": "סדנה חדשה", "window_hours": "6", "max_joins": "12"})
    cohort = Cohort.objects.get(name="סדנה חדשה")
    assert cohort.window_hours == 6
    assert cohort.max_joins == 12
    assert cohort.is_open()
    assert cohort.token


def test_nonsense_numbers_fall_back_instead_of_breaking_the_workshop(admin, seeded):
    admin.post(reverse("exo:manage_cohort_create"),
               {"name": "typo", "window_hours": "abc", "max_joins": "-4"})
    cohort = Cohort.objects.get(name="typo")
    assert cohort.window_hours == Cohort.WINDOW_HOURS
    assert cohort.max_joins == 60


def test_closing_a_room_by_hand_works_immediately(admin, seeded, workshop):
    assert workshop.is_open()
    admin.post(reverse("exo:manage_cohort_close", args=[workshop.pk]),
               data=json.dumps({"closed": True}),
               content_type="application/json")
    workshop.refresh_from_db()
    assert not workshop.is_open()

    admin.post(reverse("exo:manage_cohort_close", args=[workshop.pk]),
               data=json.dumps({"closed": False}),
               content_type="application/json")
    workshop.refresh_from_db()
    assert workshop.is_open()


# ---- the window itself ---------------------------------------------------- #

def test_the_window_is_computed_never_stored(seeded, workshop):
    """Like the museum's timed visibility: nothing runs on a schedule to close
    a window, so nothing can fail to run and leave one open."""
    assert workshop.is_open()

    later = timezone.now() + timezone.timedelta(hours=25)
    assert workshop.is_open(now=later) is False
    assert workshop.refusal(now=later) == "finished"

    workshop.refresh_from_db()
    assert workshop.is_closed is False, "the row was rewritten by a read"


def test_twenty_four_hours_is_the_default(seeded):
    cohort = Cohort.objects.create(name="default")
    assert cohort.window_hours == 24
    assert (cohort.ends_at - cohort.starts_at) == timezone.timedelta(hours=24)
