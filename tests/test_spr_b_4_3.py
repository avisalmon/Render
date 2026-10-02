"""SPR-B.4.3 to B.4.6 — redemption, the paid door, expiry, and the admin.

**The load-bearing test is `test_every_paid_door_refuses_a_free_account`.** It
knocks on every view registered as paid with a free account and expects to be
turned away, and its other half reads the URL conf for anything that looks paid
and is not registered. A paid screen that forgot its decorator is caught by one
half or the other. This is REQ-B.6.6 as a sweep rather than a promise, and the
reason the gate was built before the AI it guards.

Second: `test_a_link_preview_cannot_spend_a_coupon`. WhatsApp fetches every URL
it previews, and a coupon that spent itself on preview would be gone before the
person ever saw it.

Traces: REQ-B.6.4, B.6.6, B.6.7, B.7.1 to B.7.4.
"""

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone

pytestmark = pytest.mark.sprb43

PASSWORD = "sprb43-pass-9915"


@pytest.fixture
def person(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(
        username="door@example.com", email="door@example.com", password=PASSWORD
    )


@pytest.fixture
def root(db):
    return User.objects.create_superuser(
        username="root@example.com", email="root@example.com", password=PASSWORD
    )


# ------------------------------------------------- the one that matters


def test_every_paid_door_refuses_a_free_account(client, person):
    """Both halves: everything registered refuses, and nothing paid-looking is
    unregistered."""
    import re

    from blackjack import urls as bj_urls
    from blackjack.gate import PAID_VIEWS

    assert PAID_VIEWS, "no paid view is registered, so the sweep has nothing to sweep"

    client.force_login(person)
    for pattern in bj_urls.urlpatterns:
        callback = getattr(pattern, "callback", None)
        if callback is None:
            continue
        route = str(pattern.pattern)
        # Anything that is paid must be registered; anything registered must refuse.
        looks_paid = route.startswith("advanced")
        registered = any(_same(callback, paid) for paid in PAID_VIEWS)
        if looks_paid:
            assert registered, f"/blackjack/{route} looks paid and is not behind the gate"
        if registered:
            response = client.get("/blackjack/" + route)
            assert response.status_code == 402, (
                f"/blackjack/{route} answered {response.status_code} to a free account"
            )
            assert "bj-soon" not in response.content.decode() or "המאמן" in response.content.decode()

    assert re.search(r"advanced", str([str(p.pattern) for p in bj_urls.urlpatterns]))


def _same(callback, paid):
    """A view wrapped by login_required is still the paid view underneath."""
    seen = callback
    for _ in range(5):
        if seen is paid:
            return True
        seen = getattr(seen, "__wrapped__", None)
        if seen is None:
            return False
    return False


# ------------------------------------------------- redemption


def test_a_link_preview_cannot_spend_a_coupon(client, person):
    """A GET with the code in the path shows a button and spends nothing."""
    from blackjack.models import Coupon, Grant

    coupon = Coupon.mint()
    client.force_login(person)

    response = client.get(f"/blackjack/redeem/{coupon.code}/")
    assert response.status_code == 200
    assert coupon.code in response.content.decode()

    coupon.refresh_from_db()
    assert not coupon.is_spent, "a GET spent the coupon"
    assert not Grant.objects.exists()


def test_pressing_the_button_opens_the_week_and_lands_on_the_coach(client, person):
    from blackjack.gate import ai_is_open
    from blackjack.models import Coupon

    coupon = Coupon.mint()
    client.force_login(person)

    response = client.post(f"/blackjack/redeem/{coupon.code}/")
    assert response.status_code == 302
    assert response["Location"].endswith("/blackjack/advanced/")
    assert ai_is_open(person).source == "coupon"

    assert client.get("/blackjack/advanced/").status_code == 200


def test_a_typed_code_works_too(client, person):
    from blackjack.gate import ai_is_open
    from blackjack.models import Coupon

    coupon = Coupon.mint()
    client.force_login(person)
    client.post("/blackjack/redeem/", {"code": coupon.code.lower()})
    assert ai_is_open(person).open


def test_a_bad_code_is_refused_in_words_and_spends_nothing(client, person):
    from blackjack.models import Grant

    client.force_login(person)
    response = client.post("/blackjack/redeem/", {"code": "NOPE1234"})
    assert response.status_code == 200
    assert "לא פתוח" in response.content.decode()
    assert not Grant.objects.exists()


# ------------------------------------------------- expiry


def test_expiry_closes_the_coach_and_loses_nothing(client, person):
    """REQ-B.6.7. The paid surface closes; the free product is untouched."""
    from blackjack.models import Attempt, Cell, Coupon, Grant, Mastery, Player

    client.force_login(person)
    cell = Cell.objects.get(kind="hard", player=16, dealer=10)
    for _ in range(3):
        client.post("/blackjack/api/attempts/", {
            "cell_kind": "hard", "cell_player": 16, "cell_dealer": 10,
            "chosen": cell.action, "player_cards": [10, 6], "answer_ms": 400,
            "source": "random",
        }, content_type="application/json")

    client.post(f"/blackjack/redeem/{Coupon.mint().code}/")
    assert client.get("/blackjack/advanced/").status_code == 200

    player = Player.objects.get(user=person)
    Grant.objects.filter(player=player).update(ends_at=timezone.now() - timedelta(minutes=1))
    player.first_used_at = timezone.now() - timedelta(hours=2)
    player.save(update_fields=["first_used_at"])

    locked = client.get("/blackjack/advanced/")
    assert locked.status_code == 402
    assert "נגמרו" in locked.content.decode() or "המאמן" in locked.content.decode()

    assert Attempt.objects.filter(player=player).count() == 3, "history was lost on expiry"
    assert Mastery.objects.filter(player=player).exists(), "mastery was lost on expiry"
    assert client.get("/blackjack/history/").status_code == 200
    assert client.get("/blackjack/progress/").status_code == 200
    assert client.get("/blackjack/drill/").status_code == 200, "the free drill closed with the coach"


# ------------------------------------------------- admin


def test_the_admin_screen_is_root_only(client, person, root):
    client.force_login(person)
    assert client.get("/blackjack/staff/coupons/").status_code == 403

    staff = User.objects.create_user(username="staff@e.com", email="staff@e.com",
                                     password=PASSWORD, is_staff=True)
    client.force_login(staff)
    assert client.get("/blackjack/staff/coupons/").status_code == 403, "staff is not root"

    client.force_login(root)
    assert client.get("/blackjack/staff/coupons/").status_code == 200


def test_root_can_mint_a_coupon_and_gets_a_link_and_a_qr(client, root):
    from blackjack.models import Coupon

    client.force_login(root)
    client.post("/blackjack/staff/coupons/", {"label": "לנעמי", "days": "7"})

    coupon = Coupon.objects.get()
    assert coupon.label == "לנעמי" and coupon.days == 7 and coupon.created_by_id == root.pk

    html = client.get("/blackjack/staff/coupons/").content.decode()
    assert coupon.code in html
    assert f"/blackjack/redeem/{coupon.code}/" in html
    assert "<svg" in html, "no QR on the page"
    assert "wa.me" in html, "no WhatsApp share"


def test_the_admin_screen_never_shows_a_persons_hands(client, person, root):
    """REQ-B.7.4. Counts, not people."""
    from blackjack.models import Cell

    client.force_login(person)
    cell = Cell.objects.get(kind="soft", player=18, dealer=9)
    client.post("/blackjack/api/attempts/", {
        "cell_kind": "soft", "cell_player": 18, "cell_dealer": 9,
        "chosen": cell.action, "player_cards": [11, 7], "answer_ms": 400, "source": "random",
    }, content_type="application/json")

    client.force_login(root)
    html = client.get("/blackjack/staff/coupons/").content.decode()
    assert "door@example.com" not in html, "a named person appears on the admin screen"
    assert "A,7" not in html, "a person's hand appears on the admin screen"
    assert "ידיים השבוע" in html


def test_a_spent_coupon_is_shown_as_spent_and_without_its_link(client, person, root):
    from blackjack.models import Coupon

    coupon = Coupon.mint(by=root)
    client.force_login(person)
    client.post(f"/blackjack/redeem/{coupon.code}/")

    client.force_login(root)
    html = client.get("/blackjack/staff/coupons/").content.decode()
    assert "is-spent" in html
    assert f"/blackjack/redeem/{coupon.code}/" not in html, "a spent coupon still offers its link"


# ------------------------------------------------- the endpoints


def test_only_root_can_mint_a_coupon_through_the_api(client, person, root):
    """A coupon is a week of the paid tier. An endpoint that let a signed-in
    person mint one would be a free product with a self-service paid tier."""
    from blackjack.models import Coupon

    client.force_login(person)
    refused = client.post("/blackjack/api/coupons/", {"days": 7, "label": "me"},
                          content_type="application/json")
    assert refused.status_code == 403
    assert not Coupon.objects.exists()
    assert client.get("/blackjack/api/coupons/").status_code == 403

    client.force_login(root)
    made = client.post("/blackjack/api/coupons/", {"days": 3, "label": "api"},
                       content_type="application/json")
    assert made.status_code == 201, made.content[:200]
    coupon = Coupon.objects.get()
    assert coupon.days == 3 and coupon.created_by_id == root.pk
    assert len(coupon.code) == 8, "the code was not minted"


def test_a_coupon_code_cannot_be_chosen(client, root):
    """A chosen code is a guessable code."""
    from blackjack.models import Coupon

    client.force_login(root)
    client.post("/blackjack/api/coupons/", {"code": "FREEWEEK", "days": 7},
                content_type="application/json")
    assert not Coupon.objects.filter(code="FREEWEEK").exists()


def test_a_coupon_is_never_edited_or_deleted_through_the_api(client, person, root):
    """Editing changes what a code already in somebody's WhatsApp is worth.
    Deleting erases the record of who was let in."""
    from blackjack.models import Coupon

    coupon = Coupon.mint(by=root, days=7)
    client.force_login(person)
    client.post(f"/blackjack/redeem/{coupon.code}/")

    client.force_login(root)
    for send in (client.put, client.patch):
        assert send(f"/blackjack/api/coupons/{coupon.pk}/", {"days": 365},
                    content_type="application/json").status_code in (403, 405)
    assert client.delete(f"/blackjack/api/coupons/{coupon.pk}/").status_code in (403, 405)

    coupon.refresh_from_db()
    assert coupon.days == 7 and coupon.is_spent


def test_nobody_can_write_a_grant(client, person, root):
    """A writable grant is a client handing itself the paid tier. Root
    included: root mints coupons, which leave a record; root does not
    conjure access."""
    from django.utils import timezone

    from blackjack.gate import ai_is_open
    from blackjack.models import Grant

    body = {"source": "gift", "starts_at": timezone.now().isoformat(),
            "ends_at": (timezone.now() + timedelta(days=30)).isoformat()}
    for who in (person, root):
        client.force_login(who)
        answer = client.post("/blackjack/api/grants/", body, content_type="application/json")
        assert answer.status_code in (403, 405), f"{who.username} could write a grant"
    assert not Grant.objects.exists()
    assert not ai_is_open(person)


def test_a_person_reads_only_their_own_grants(client, person, root):
    from blackjack.models import Coupon

    other = User.objects.create_user(username="other@e.com", email="other@e.com",
                                     password=PASSWORD)
    client.force_login(other)
    client.post(f"/blackjack/redeem/{Coupon.mint().code}/")

    client.force_login(person)
    rows = client.get("/blackjack/api/grants/").json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert rows == [], "somebody else's access window was readable"
