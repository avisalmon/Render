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
from django.views.decorators.csrf import ensure_csrf_cookie

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


# The sheet is split because a ten-column chart is unreadable in a hand
# (REQ-B.3.3). These are the views Avi named, plus the two the hard table
# needs because it is the widest.
SHEET_VIEWS = (
    ("weak", "דילר חלש", "hard", (2, 3, 4, 5, 6)),
    ("strong", "דילר חזק", "hard", (7, 8, 9, 10, 11)),
    ("soft", "ידיים רכות", "soft", (2, 3, 4, 5, 6, 7, 8, 9, 10, 11)),
    ("pairs", "זוגות", "pair", (2, 3, 4, 5, 6, 7, 8, 9, 10, 11)),
    ("doubles", "הכפלות", None, None),
)


@login_required(login_url=LOGIN_URL)
def sheet(request):
    """The cheat sheet for this person's table (REQ-B.3.1 to B.3.5).

    Every cell on screen is a row from the database. Nothing here computes a
    play, which is what makes the promise in spec 1.5 structural: the drill
    will serialise the same rows, so the sheet and the drill cannot disagree
    about what the right answer is.

    A table with no chart says so rather than rendering an empty grid. An empty
    grid looks like a bug; a sentence looks like an answer, and REQ-B.2.5 says
    we refuse rather than approximate.
    """
    from .models import Chart, Player
    from .strategy import supports

    player = Player.for_user(request.user)
    rules = player.rule_set.rules
    chart = Chart.objects.filter(rule_set=player.rule_set).first()

    if chart is None:
        ok, why = supports(rules)
        return render(request, "blackjack/sheet_missing.html", {
            "player": player,
            "rules": player.rule_set,
            "why": why if not ok else ["הטבלה לשולחן הזה עוד לא נבנתה"],
        })

    chosen = request.GET.get("view") or "weak"
    chosen = chosen if chosen in {key for key, *_ in SHEET_VIEWS} else "weak"
    _key, title, kind, dealers = next(v for v in SHEET_VIEWS if v[0] == chosen)

    if chosen == "doubles":
        # The cross-cutting view: every cell that says double, on one sheet.
        # Beginners miss doubles more than anything else, so they get a page.
        cells = chart.cells.filter(action="D").order_by("kind", "player", "dealer")
        rows, dealers = _as_rows(cells)
    else:
        cells = chart.cells.filter(kind=kind, dealer__in=dealers).order_by("player", "dealer")
        rows, dealers = _as_rows(cells, dealers)

    return render(request, "blackjack/sheet.html", {
        "player": player,
        "rules": player.rule_set,
        "views": SHEET_VIEWS,
        "chosen": chosen,
        "title": title,
        "rows": rows,
        "dealers": dealers,
    })


def _as_rows(cells, dealers=None):
    """Group cells into the rows a table draws, keeping the order stable.

    Written here rather than in the template because a template that builds a
    grid is a template nobody can test.
    """
    cells = list(cells)
    if dealers is None:
        dealers = sorted({cell.dealer for cell in cells})
    by_row = {}
    for cell in cells:
        by_row.setdefault((cell.kind, cell.player), {})[cell.dealer] = cell
    rows = []
    for (kind, player), found in sorted(by_row.items(), key=lambda item: (item[0][0], item[0][1])):
        rows.append({
            "kind": kind,
            "player": player,
            "label": _row_label(kind, player),
            "cells": [found.get(dealer) for dealer in dealers],
        })
    return rows, dealers


def _row_label(kind, player):
    if kind == "pair":
        return "A,A" if player == 11 else f"{player},{player}"
    if kind == "soft":
        return f"A,{player - 11}"
    return str(player)


def chart_payload(chart):
    """The chart, as the browser needs it (REQ-B.4.5).

    Serialised from the same rows the sheet renders, which is what makes the
    promise in spec 1.5 hold through the drill as well: there is one set of
    rows and two readers, so a cell cannot say one thing on the sheet and
    another at the table.

    Shipped with the page rather than fetched, so the drill answers instantly
    and keeps working with no signal. The server is never asked what the right
    play was.
    """
    return {
        "rules": chart.rule_set.rules,
        "cells": [
            {
                "kind": cell.kind,
                "player": cell.player,
                "dealer": cell.dealer,
                "action": cell.action,
                "fallback": cell.fallback,
                "reason": cell.reason,
            }
            for cell in chart.cells.all().order_by("kind", "player", "dealer")
        ],
    }


@ensure_csrf_cookie
@login_required(login_url=LOGIN_URL)
def drill(request):
    """The practice table (REQ-B.4.1 to B.4.5).

    `ensure_csrf_cookie` because the page posts attempts without ever rendering
    a form. Without it there is no csrftoken cookie, every POST is refused, and
    the queue drops them as unfixable, so a person drills happily while nothing
    is recorded. Found by the browser test rather than by reading, which is the
    argument for driving the real page.

    The whole chart goes down with the page and the decision happens in the
    browser. That is not an optimisation, it is the product: a person drilling
    on a train must get their answer in the time it takes to look up, and a
    round trip per hand would make the tutor feel slower than the thought it is
    trying to replace.
    """
    import json

    from django.core.serializers.json import DjangoJSONEncoder

    from .models import Chart, Player
    from .strategy import supports

    player = Player.for_user(request.user)
    chart = Chart.objects.filter(rule_set=player.rule_set).first()

    if chart is None:
        ok, why = supports(player.rule_set.rules)
        return render(request, "blackjack/sheet_missing.html", {
            "player": player,
            "rules": player.rule_set,
            "why": why if not ok else ["הטבלה לשולחן הזה עוד לא נבנתה"],
        })

    return render(request, "blackjack/drill.html", {
        "player": player,
        "rules": player.rule_set,
        "chart_json": json.dumps(chart_payload(chart), cls=DjangoJSONEncoder,
                                 ensure_ascii=False),
    })
