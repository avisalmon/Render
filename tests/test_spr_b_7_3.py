"""SPR-B.7.3 — following, on babook's graph, never a second one.

**The load-bearing test is `test_following_here_writes_babooks_graph_and_no_other`.**
The whole decision in this sprint is that there is one answer to "who does this
person follow". A `BlackjackFollow` table would be a second one, free to
disagree, and the day it disagrees somebody has unfollowed a person in one
place and is still following them in the other. So the test checks both halves:
a follow made here lands in `app.models.Follow`, and a follow made in babook is
visible here without blackjack having been told.

Second: `test_there_is_no_way_to_look_a_person_up`. A search box over the
member list would mean typing part of somebody's email address and being told
whether it exists. You arrive at a person through a result they shared.

Traces: REQ-B.5.8, Q2.
"""

from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

pytestmark = pytest.mark.sprb73

PASSWORD = "sprb73-pass-5502"


@pytest.fixture
def people(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    avi = User.objects.create_user(username="avi@example.com", email="avi@example.com",
                                   password=PASSWORD, first_name="אבי")
    dana = User.objects.create_user(username="dana@example.com", email="dana@example.com",
                                    password=PASSWORD, first_name="דנה", last_name="לוי")
    return avi, dana


def _player(user):
    from blackjack.models import Player

    return Player.for_user(user)


def _play(client, times=1, right=True):
    from blackjack.models import Cell

    cell = Cell.objects.filter(kind="hard", player=16).first()
    chosen = cell.action if right else next(a for a in "HSDP" if a != cell.action)
    for _ in range(times):
        client.post("/blackjack/api/attempts/", {
            "cell_kind": cell.kind, "cell_player": cell.player,
            "cell_dealer": cell.dealer, "chosen": chosen,
            "player_cards": [10, 6], "answer_ms": 700, "source": "random",
        }, content_type="application/json")


def _share_as(client, user):
    from blackjack.models import Share

    client.force_login(user)
    client.post("/blackjack/share/")
    return Share.objects.filter(player__user=user).first()


# ------------------------------------------------- the one that matters


def test_following_here_writes_babooks_graph_and_no_other(client, people):
    """One graph, in both directions.

    A follow made from blackjack lands in `app.models.Follow`, and a follow
    made anywhere else is visible here with nothing told to blackjack at all.
    """
    from app.models import Follow

    avi, dana = people
    client.force_login(dana)
    _play(client, times=5)
    share = _share_as(client, dana)

    client.force_login(avi)
    assert client.post("/blackjack/friends/", {"token": share.token}).status_code == 302

    assert Follow.objects.filter(follower=avi, followed=dana).count() == 1, (
        "following from blackjack did not reach babook's graph"
    )

    # And nothing in blackjack grew a graph of its own.
    from django.apps import apps

    for model in apps.get_app_config("blackjack").get_models():
        fields = {f.name for f in model._meta.get_fields()}
        assert not {"follower", "followed"} <= fields, (
            f"{model.__name__} is a second follow graph"
        )

    # The other direction: a row made in babook shows up here untold.
    Follow.objects.all().delete()
    Follow.objects.create(follower=avi, followed=dana)
    body = client.get("/blackjack/friends/").content.decode()
    assert "דנה" in body, "a follow made in babook is invisible in blackjack"


def test_there_is_no_way_to_look_a_person_up(client, people):
    """No directory, no search. The introduction is a result they shared.

    A lookup here would be a way to type part of an email address and be told
    whether that account exists, which this app has no business offering.
    """
    avi, dana = people
    client.force_login(dana)
    _play(client, times=3)
    _share_as(client, dana)

    client.force_login(avi)
    body = client.get("/blackjack/friends/").content.decode()

    assert "dana@example.com" not in body
    assert 'type="search"' not in body
    assert 'name="q"' not in body

    # And addressing somebody directly, without a link, does nothing.
    from app.models import Follow

    client.post("/blackjack/friends/", {"token": "nosuchtoken"})
    client.post("/blackjack/friends/", {"follow": str(dana.pk)})
    assert not Follow.objects.exists(), "somebody was followed without a shared link"


# ------------------------------------------------- what a follower sees


def test_a_follower_sees_numbers_and_never_the_hands_or_the_email(client, people):
    avi, dana = people
    client.force_login(dana)
    _play(client, times=8, right=True)
    _play(client, times=2, right=False)
    share = _share_as(client, dana)

    client.force_login(avi)
    client.post("/blackjack/friends/", {"token": share.token})
    body = client.get("/blackjack/friends/").content.decode()

    assert "80%" in body, "a followed player's accuracy is missing"
    assert "דנה" in body
    assert "לוי" not in body, "a last name reached the circle screen"
    assert "dana@example.com" not in body
    assert "16 מול" not in body, "somebody's hands were published to a follower"


def test_somebody_who_turns_their_numbers_off_keeps_them_off(client, people):
    """The switch is theirs, and it is the only thing between a follower and
    their accuracy."""
    avi, dana = people
    client.force_login(dana)
    _play(client, times=8, right=True)
    share = _share_as(client, dana)
    assert client.post("/blackjack/friends/", {"visibility": "off"}).status_code == 302

    client.force_login(avi)
    client.post("/blackjack/friends/", {"token": share.token})
    body = client.get("/blackjack/friends/").content.decode()

    assert "100%" not in body, "numbers were shown after they were switched off"
    assert "דנה" in body, "the person vanished instead of their numbers"


def test_the_card_itself_withholds_the_numbers_when_the_switch_is_off(client, people):
    """**Two independent things hold this property**, and through the screen
    only the outer one is ever reached.

    `friends.card` returns zeros for somebody who switched their numbers off,
    and the template also asks `row.shows` before printing anything. Breaking
    either alone changes nothing on screen, which made both look like dead
    weight. They are not: `card` is what any future caller gets, and the
    template is what the current one renders. So each is tested where it can
    actually be reached, this one by calling the function.
    """
    from blackjack import friends

    _avi, dana = people
    client.force_login(dana)
    _play(client, times=5, right=True)
    client.post("/blackjack/friends/", {"visibility": "off"})

    row = friends.card(dana)
    assert row["shows"] is False
    assert row["accuracy"] == 0 and row["hands"] == 0 and row["streak"] == 0, (
        "the card handed out numbers that their owner switched off"
    )
    assert row["name"] == "דנה", "the person disappeared instead of their numbers"


def test_the_screen_withholds_numbers_even_if_the_card_hands_them_over(client, people):
    """The inner half of the same property, reached by rendering the template
    against a row that lies."""
    from django.template.loader import render_to_string

    avi, _dana = people
    html = render_to_string("blackjack/friends.html", {
        "shows": True,
        "circle": [{"user_id": 99, "name": "דנה", "plays": True, "shows": False,
                    "hands": 500, "accuracy": 99, "streak": 7}],
    }, request=None)

    assert "99%" not in html, "the screen printed numbers it was told to withhold"
    assert "500" not in html
    assert "דנה" in html
    assert avi.email not in html


def test_not_following_somebody_shows_you_nothing_about_them(client, people):
    """The circle is the people you follow, not everybody who plays."""
    avi, dana = people
    client.force_login(dana)
    _play(client, times=6, right=True)

    client.force_login(avi)
    body = client.get("/blackjack/friends/").content.decode()
    assert "דנה" not in body, "a stranger appeared in somebody's circle"


def test_unfollowing_removes_the_row_rather_than_hiding_it(client, people):
    from app.models import Follow

    avi, dana = people
    client.force_login(dana)
    _play(client, times=3)
    share = _share_as(client, dana)

    client.force_login(avi)
    client.post("/blackjack/friends/", {"token": share.token})
    assert Follow.objects.filter(follower=avi, followed=dana).exists()

    client.post("/blackjack/friends/", {"unfollow": str(dana.pk)})
    assert not Follow.objects.filter(follower=avi, followed=dana).exists(), (
        "unfollowing in blackjack left the row standing in babook"
    )


# ------------------------------------------------- the edges


def test_following_twice_is_following_once(client, people):
    """Two taps on a slow phone are one intention, not a server error."""
    from app.models import Follow

    avi, dana = people
    client.force_login(dana)
    _play(client, times=2)
    share = _share_as(client, dana)

    client.force_login(avi)
    for _ in range(3):
        assert client.post("/blackjack/friends/",
                           {"token": share.token}).status_code == 302
    assert Follow.objects.filter(follower=avi, followed=dana).count() == 1


def test_nobody_follows_themselves(client, people):
    from app.models import Follow

    avi, _dana = people
    client.force_login(avi)
    _play(client, times=2)
    share = _share_as(client, avi)

    client.post("/blackjack/friends/", {"token": share.token})
    assert not Follow.objects.filter(follower=avi, followed=avi).exists()

    body = client.get(share.path).content.decode()
    assert "לעקוב אחרי" not in body, "the app offered somebody a way to follow themselves"


def test_a_closed_link_is_not_a_way_in(client, people):
    """Revoking a link closes the door, including this one."""
    from app.models import Follow

    avi, dana = people
    client.force_login(dana)
    _play(client, times=2)
    share = _share_as(client, dana)
    client.post("/blackjack/share/", {"revoke": share.token})

    client.force_login(avi)
    client.post("/blackjack/friends/", {"token": share.token})
    assert not Follow.objects.filter(follower=avi, followed=dana).exists(), (
        "a revoked link still attached somebody to its owner"
    )


def test_following_is_free(client, people):
    from blackjack.models import Player

    avi, dana = people
    client.force_login(dana)
    _play(client, times=4)
    share = _share_as(client, dana)

    client.force_login(avi)
    player = _player(avi)
    Player.objects.filter(pk=player.pk).update(
        first_used_at=player.created_at.replace(year=2020)
    )

    assert client.get("/blackjack/friends/").status_code == 200
    assert client.post("/blackjack/friends/", {"token": share.token}).status_code == 302
    assert "דנה" in client.get("/blackjack/friends/").content.decode()
