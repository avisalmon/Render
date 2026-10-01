"""The app's screens.

One screen so far: the front door. Sign-in is required because there is no
anonymous product (REQ-B.6.1), and a stranger is *sent to sign in* rather than
refused, because they are a future player.

The login URL points at babook's, which is the one thing this app shares: the
account. Rule 3 says no link back to the main site, and an auth redirect is not
a link in the menu, it is the shared front door the methodology explicitly
keeps shared ("Auth: reuse the User model, but a lighter front door is fine").
A blackjack-branded sign-in page of our own is SPR-B.1.2 work.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

LOGIN_URL = "/login/?next=/blackjack/"


@login_required(login_url=LOGIN_URL)
def home(request):
    """The front door. Three sections, two of them not built yet.

    It says what is coming rather than hiding it, because an app whose menu
    items do nothing feels broken, while an app that says "the drill is next"
    feels like it is being built.
    """
    return render(request, "blackjack/home.html", {})


@login_required(login_url=LOGIN_URL)
def table(request):
    """Choose the rules of your table (REQ-B.2.1, B.2.2, B.2.3).

    A POST never edits the current rule set. `Player.play_by` points the person
    at the row for the new rules, making it if nobody has played it yet, so
    every hand already dealt keeps the rules it was dealt under and stays
    judgeable.

    Checkboxes are read as present-or-absent, which is how a browser sends
    them, and anything missing falls back to the common case rather than to
    False: an unchecked box and an absent field look identical over the wire,
    and defaulting a missing `blackjack_pays` to nothing would deal a table
    nobody chose.
    """
    from .models import DEFAULT_RULES, Player, RuleSet

    player = Player.for_user(request.user)

    if request.method == "POST":
        posted = {
            "decks": int(request.POST.get("decks") or DEFAULT_RULES["decks"]),
            "max_splits": int(request.POST.get("max_splits") or DEFAULT_RULES["max_splits"]),
            "surrender": request.POST.get("surrender") or DEFAULT_RULES["surrender"],
            "blackjack_pays": request.POST.get("blackjack_pays") or DEFAULT_RULES["blackjack_pays"],
        }
        for flag in ("dealer_hits_soft_17", "double_any_two", "double_after_split",
                     "resplit_aces", "hit_split_aces", "dealer_peeks"):
            posted[flag] = request.POST.get(flag) == "on"
        player.play_by(**posted)
        return redirect("blackjack:table")

    return render(request, "blackjack/table.html", {
        "player": player,
        "rules": player.rule_set,
        "deck_choices": [1, 2, 4, 6, 8],
        "surrender_choices": RuleSet._meta.get_field("surrender").choices,
        "payout_choices": RuleSet._meta.get_field("blackjack_pays").choices,
    })
