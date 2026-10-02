"""SPR-B.7.2 — sharing a result, as a link somebody can open.

**The load-bearing test is `test_a_shared_link_is_frozen_and_does_not_keep_reporting`.**
A link that keeps updating is not a shared result, it is a tracker somebody
handed to a group chat: they posted one good evening and would be publishing
every evening after it, including the bad ones, to a group they have forgotten
they posted in. What is shared is what was true when they pressed the button.

Close behind: `test_the_page_a_stranger_sees_carries_nothing_but_the_snapshot`.
Accounts here are keyed by email address, so this is the one page in the app
where a careless template leaks a real person's address to anybody holding a
forwarded link.

Traces: REQ-B.5.8.
"""

from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

pytestmark = pytest.mark.sprb72

PASSWORD = "sprb72-pass-8120"


@pytest.fixture
def person(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(
        username="shareme@example.com", email="shareme@example.com",
        password=PASSWORD, first_name="דני", last_name="כהן",
    )


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


def _big_number(html):
    """The accuracy as the page actually shows it, and only that.

    Scoped on purpose. The first version of this test searched the whole page
    for "100%" and passed against a page showing 25%, because the `<title>`
    carries the frozen headline and the headline still said 100. An assertion
    that finds the right answer in the tab title while the page says something
    else is the exact failure mode methodology entry 1 is about.
    """
    start = html.find('class="bj-shared-big"')
    assert start != -1, "the shared page has no result on it"
    chunk = html[html.find(">", start) + 1:html.find("<span", start)]
    return chunk.strip()


def _make_share(client):
    """Press the share button, come back with the row."""
    from blackjack.models import Share

    before = set(Share.objects.values_list("pk", flat=True))
    assert client.post("/blackjack/share/").status_code == 302
    return Share.objects.exclude(pk__in=before).get()


# ------------------------------------------------- the one that matters


def test_a_shared_link_is_frozen_and_does_not_keep_reporting(client, person):
    """Play badly after sharing: the link still says what it said.

    Recomputing on read would be the obvious implementation and it turns one
    shared evening into a standing feed of somebody's results to a group chat
    they no longer think about.
    """
    client.force_login(person)
    _play(client, times=10, right=True)

    share = _make_share(client)
    assert _big_number(client.get(share.path).content.decode()) == "100"

    _play(client, times=30, right=False)        # a long bad run, after sharing

    page = client.get(share.path).content.decode()
    assert _big_number(page) == "100", (
        "the shared link reported results from after it was shared"
    )
    assert "10 מתוך 10" in page, "the counts moved with the hands played since"

    share.refresh_from_db()
    assert share.snapshot["hands"] == 10, "the frozen snapshot was rewritten"
    assert share.snapshot["accuracy"] == 100


def test_the_page_a_stranger_sees_carries_nothing_but_the_snapshot(client, person):
    """No email, no username, no hand history, nobody else's anything.

    Usernames on this site are email addresses, so a template that printed one
    would publish a real address to whoever the link was forwarded to.
    """
    client.force_login(person)
    _play(client, times=4, right=True)
    _play(client, times=1, right=False)
    share = _make_share(client)

    client.logout()
    body = client.get(share.path).content.decode()

    assert "shareme@example.com" not in body, "the page published an email address"
    assert "example.com" not in body
    assert "כהן" not in body, "a last name reached a page strangers can open"
    assert "דני" in body, "the first name they chose to show is missing"

    # The hands themselves stay private: a shared result is a number, not a log.
    assert "16 מול" not in body
    assert "/blackjack/history/" not in body
    assert "/blackjack/drill/" not in body


# ------------------------------------------------- open, and closable


def test_a_stranger_with_the_link_can_open_it_without_an_account(client, person):
    """The whole point. A link that asks you to sign in before it shows you
    anything is a sign-up wall, and nobody forwards one of those."""
    client.force_login(person)
    _play(client, times=6)
    share = _make_share(client)

    client.logout()
    answer = client.get(share.path)
    assert answer.status_code == 200, "a shared link asked a stranger to sign in"
    assert "login" not in answer.get("Location", "")


def test_closing_a_link_closes_it_for_everybody(client, person):
    """A thing you sent to a group chat is a thing you may want back."""
    client.force_login(person)
    _play(client, times=3)
    share = _make_share(client)
    assert client.get(share.path).status_code == 200

    assert client.post("/blackjack/share/", {"revoke": share.token}).status_code == 302

    client.logout()
    assert client.get(share.path).status_code == 404, "a closed link still opened"

    share.refresh_from_db()
    assert share.revoked_at is not None
    assert share.snapshot, "closing a link destroyed the record of what was shared"


def test_one_person_cannot_close_another_persons_link(client, person, db):
    """Revoking is addressed by token, which is the thing a stranger might have
    seen. So the token alone must not be enough to act on somebody's share."""
    other = User.objects.create_user(username="nosy@example.com",
                                     email="nosy@example.com", password=PASSWORD)
    client.force_login(person)
    _play(client, times=3)
    share = _make_share(client)

    client.force_login(other)
    client.post("/blackjack/share/", {"revoke": share.token})

    share.refresh_from_db()
    assert share.revoked_at is None, "somebody closed a link that was not theirs"


def test_a_token_is_random_and_not_a_row_number(client, person):
    """The link is the only thing guarding the page, so it cannot be walkable.

    A sequential id would turn one forwarded link into a tour of everybody
    else's results.
    """
    from blackjack.models import Share

    client.force_login(person)
    _play(client, times=2)
    first = _make_share(client)
    second = _make_share(client)

    assert first.token != second.token
    for token in (first.token, second.token):
        assert len(token) >= 10, "a short token is a guessable one"
        assert str(first.pk) != token and not token.isdigit()
        assert set(token) <= set(Share.ALPHABET)

    assert client.get("/blackjack/r/1/").status_code == 404
    assert client.get(f"/blackjack/r/{first.pk}/").status_code == 404


# ------------------------------------------------- the usual guards


def test_sharing_is_free(client, person):
    """Sharing is how the app reaches the next person. Charging for it is
    charging to grow."""
    from blackjack.models import Player

    client.force_login(person)
    _play(client, times=5)

    player = _player(person)
    Player.objects.filter(pk=player.pk).update(
        first_used_at=player.first_used_at.replace(year=2020)
    )

    assert client.get("/blackjack/share/").status_code == 200
    share = _make_share(client)
    assert client.get(share.path).status_code == 200


def test_a_share_is_read_only_through_the_api_and_scoped_to_its_owner(client, person, db):
    from blackjack.models import Share

    other = User.objects.create_user(username="other@example.com",
                                     email="other@example.com", password=PASSWORD)
    client.force_login(person)
    _play(client, times=3)
    share = _make_share(client)

    for send, body in ((client.post, {"headline": "mine"}),):
        assert send("/blackjack/api/shares/", body,
                    content_type="application/json").status_code in (403, 405)
    assert client.patch(f"/blackjack/api/shares/{share.pk}/", {"headline": "x"},
                        content_type="application/json").status_code in (403, 405)
    assert client.delete(f"/blackjack/api/shares/{share.pk}/").status_code in (403, 405)

    client.force_login(other)
    rows = client.get("/blackjack/api/shares/").json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert rows == [], "somebody else's share links were listable"

    assert Share.objects.get(pk=share.pk).revoked_at is None


def test_the_snapshot_holds_only_the_fields_sharing_decided(client, person):
    """One function decides what leaves the account, and the page renders that
    dict and nothing else. A field added to `Player` next month must not be
    able to appear on a link shared last month."""
    client.force_login(person)
    _play(client, times=7)
    share = _make_share(client)

    assert set(share.snapshot) == {
        "name", "hands", "right", "accuracy", "streak", "best_streak",
        "rules", "shared_on",
    }


def test_somebody_with_no_hands_still_gets_a_sentence_not_a_crash(client, person):
    """Nothing played is a real case: people press share to see what it does."""
    client.force_login(person)
    share = _make_share(client)

    assert share.snapshot["hands"] == 0
    assert share.headline.strip()
    assert client.get(share.path).status_code == 200


def test_the_url_on_the_share_screen_is_marked_left_to_right(client, person):
    """RTL bidi reorders a Latin URL into something that looks broken and
    copies wrong. It already cost us a round of coupon links."""
    client.force_login(person)
    _play(client, times=2)
    share = _make_share(client)

    body = client.get(f"/blackjack/share/?new={share.token}").content.decode()

    # Scope the search to the paragraph that carries the URL, rather than
    # asking whether `dir="ltr"` appears anywhere on a page that has plenty of
    # other elements.
    start = body.find('class="bj-share-url"')
    assert start != -1, "the share screen did not render the link"
    paragraph = body[body.rfind("<p", 0, start):body.find("</p>", start)]
    assert 'dir="ltr"' in paragraph, "the URL was left to the bidi algorithm"
    assert share.token in paragraph


def test_the_date_on_the_public_page_is_isolated_from_bidi(client, person):
    """Latin digits with hyphens inside a Hebrew sentence is the shape bidi
    reorders, and this one is the only date a stranger ever sees."""
    client.force_login(person)
    _play(client, times=2)
    share = _make_share(client)

    body = client.get(share.path).content.decode()
    stamp = share.snapshot["shared_on"]
    at = body.find(stamp)
    assert at != -1, "the public page does not say when the snapshot was taken"
    assert "<bdi" in body[max(0, at - 60):at], "the date was left to the bidi algorithm"
