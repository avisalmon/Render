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

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from .gate import paid_only

LOGIN_URL = "/login/?next=/blackjack/"


@login_required(login_url=LOGIN_URL)
def home(request):
    """The front door: one sentence and one button.

    For somebody who has played, the button says "continue" and a strip above
    it says where they stand: streak, hands, accuracy. The review pass found
    the front page identical for a first visit and a fortieth, which told a
    returning person nothing about why to come back.
    """
    from . import mastery, streaks
    from .models import Attempt, Player

    player = Player.objects.filter(user=request.user).first()
    hands = Attempt.objects.filter(player=player).count() if player else 0
    standing = None
    if hands:
        right = Attempt.objects.filter(player=player, is_correct=True).count()
        summary = mastery.summary(player)
        standing = {
            "hands": hands,
            "accuracy": round(100 * right / hands),
            "streak": streaks.of(player),
            "solid": summary["solid"],
            "learning": summary["learning"],
            "total": summary["total"],
        }
    return render(request, "blackjack/home.html", {"standing": standing})


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

# Any view wider than a thumb is drawn as two tables, weak dealers and strong
# dealers, stacked on a phone and side by side on a desk. The review pass
# found the soft, pairs and doubles views clipped at 390px with the 8, 9, 10
# and A columns off the left edge and nothing saying "scroll": the sheet's own
# rule, five columns is a thumb, applied to the hard table and to nothing else.
HALVES = (("דילר חלש", (2, 3, 4, 5, 6)), ("דילר חזק", (7, 8, 9, 10, 11)))


def _split(rows, dealers):
    """One wide table into the halves a phone can show whole.

    Returns a list of (subtitle, dealers, rows). A table that already fits is
    returned as a single unlabelled half, so the template has one shape.
    """
    if len(dealers) <= 5:
        return [("", list(dealers), rows)]
    halves = []
    for subtitle, group in HALVES:
        keep = [d for d in dealers if d in group]
        if not keep:
            continue
        halves.append((subtitle, keep, [
            {**row, "cells": [cell for cell, d in zip(row["cells"], dealers, strict=True)
                              if d in group]}
            for row in rows
        ]))
    return halves


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
        "tables": _split(rows, dealers),
        "clip_groups": _clip_groups(),
    })


def _clip_groups():
    """The videos that are switched on, in the groups the screen shows them.

    A group with nothing in it is left out, so taking the last video of a group
    down does not leave a heading over nothing.
    """
    from .models import Clip

    clips = list(Clip.objects.filter(is_active=True))
    groups = []
    for key, label in Clip.GROUPS:
        mine = [clip for clip in clips if clip.group == key]
        if mine:
            groups.append((key, label, mine))
    return groups


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
def simulator(request):
    """The play table (REQ-B.9.1): full hands against a real shuffled shoe, with
    play money.

    Free for everybody signed in, which is why nothing here asks the gate.
    The page carries only the table as it stands now, and the browser then
    talks to the API for every deal and every decision. The shoe and the
    dealer's hole card are on the server and stay there.
    """
    import json

    from django.core.serializers.json import DjangoJSONEncoder

    from . import play, streaks
    from .models import Chart, Player
    from .strategy import supports

    player = Player.for_user(request.user)
    ok, why = supports(player.rule_set.rules)
    if not ok or not Chart.objects.filter(rule_set=player.rule_set).exists():
        return render(request, "blackjack/sheet_missing.html", {
            "player": player,
            "rules": player.rule_set,
            "why": why if not ok else ["הטבלה לשולחן הזה עוד לא נבנתה"],
        })

    table = play.table_for(player)
    return render(request, "blackjack/play.html", {
        "player": player,
        "rules": player.rule_set,
        "streak": streaks.of(player),
        "table_json": json.dumps(play.present(table), cls=DjangoJSONEncoder, ensure_ascii=False),
    })


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

    from . import gate, mastery, streaks
    from .models import Attempt, BatchNote, Session

    payload = chart_payload(chart)
    payload["review"] = recent_misses(player)

    # Where this person is inside the current batch of twenty, so the drill
    # can say "hand 7 of 20" and the note at twenty does not come from nowhere.
    # The review pass found the note was written and shown only on the history
    # page, which nobody reads mid-drill: the thing the spec promised "every
    # twenty hands" was never seen at the table.
    in_session = Attempt.objects.filter(player=player, session=Session.current(player)).count()
    payload["in_batch"] = in_session % BatchNote.BATCH
    payload["batch"] = BatchNote.BATCH

    # REQ-B.8.2 — the scheduler, for whoever is paying. Free practice is
    # random with recent misses mixed back in; paid practice is driven by when
    # each cell is actually due. Both are arithmetic: the difference somebody
    # pays for is that the second one remembers across sittings.
    access = gate.ai_is_open(request.user)
    payload["adaptive"] = bool(access)
    payload["due"] = mastery.due_cells(player) if access else []

    return render(request, "blackjack/drill.html", {
        "player": player,
        "rules": player.rule_set,
        "streak": streaks.of(player),
        "access": access,
        "chart_json": json.dumps(payload, cls=DjangoJSONEncoder, ensure_ascii=False),
    })


def recent_misses(player, window=40):
    """Cells this person has missed lately and not since put right.

    REQ-B.5.7, the free half of spaced repetition. The paid tier gets the real
    scheduler reading `Mastery.due_at` (REQ-B.8.2); this is the weak form, and
    the weak form is deliberately in the free product because a free tier that
    does not actually teach converts nobody. Drilling pure random forever is
    how people plateau.

    Read from `Attempt` rather than from `Mastery`, because "lately" is a
    question about the last few dozen hands rather than about a running total,
    and this way the list cannot drift from what they actually just played.
    """
    from .models import Attempt

    recent = list(
        Attempt.objects.filter(player=player)
        .order_by("-created_at")[:window]
        .values("cell_kind", "cell_player", "cell_dealer", "is_correct")
    )

    settled, waiting = set(), []
    for row in recent:           # newest first, so a later success wins
        key = (row["cell_kind"], row["cell_player"], row["cell_dealer"])
        if key in settled:
            continue
        if row["is_correct"]:
            settled.add(key)
        else:
            settled.add(key)
            waiting.append({"kind": key[0], "player": key[1], "dealer": key[2]})
    return waiting


PROGRESS_VIEWS = (
    ("weak", "דילר חלש", "hard", (2, 3, 4, 5, 6)),
    ("strong", "דילר חזק", "hard", (7, 8, 9, 10, 11)),
    ("soft", "ידיים רכות", "soft", (2, 3, 4, 5, 6, 7, 8, 9, 10, 11)),
    ("pairs", "זוגות", "pair", (2, 3, 4, 5, 6, 7, 8, 9, 10, 11)),
)


@login_required(login_url=LOGIN_URL)
def progress(request):
    """What this person knows, decision by decision (REQ-B.5.2).

    The same shape as the cheat sheet on purpose. A learner who has spent an
    hour reading the chart in that layout should be able to read their own
    progress without learning a second one, and the overlap is the point: this
    screen is that chart with their history painted onto it.

    Four states rather than a percentage, and the counts live underneath each
    cell for anybody who wants them.
    """
    from . import mastery
    from .models import Chart, Player

    player = Player.for_user(request.user)
    chart = Chart.objects.filter(rule_set=player.rule_set).first()
    if chart is None:
        from .strategy import supports

        ok, why = supports(player.rule_set.rules)
        return render(request, "blackjack/sheet_missing.html", {
            "player": player,
            "rules": player.rule_set,
            "why": why if not ok else ["הטבלה לשולחן הזה עוד לא נבנתה"],
        })

    chosen = request.GET.get("view") or "weak"
    chosen = chosen if chosen in {key for key, *_ in PROGRESS_VIEWS} else "weak"
    _key, title, kind, dealers = next(v for v in PROGRESS_VIEWS if v[0] == chosen)

    known = {
        (row["cell"].kind, row["cell"].player, row["cell"].dealer): row
        for row in mastery.grid(player)
    }

    cells = chart.cells.filter(kind=kind, dealer__in=dealers).order_by("player", "dealer")
    by_row = {}
    for cell in cells:
        found = known.get((cell.kind, cell.player, cell.dealer))
        by_row.setdefault(cell.player, {})[cell.dealer] = found

    rows = [
        {
            "label": _row_label(kind, value),
            "cells": [found.get(dealer) for dealer in dealers],
        }
        for value, found in sorted(by_row.items())
    ]

    return render(request, "blackjack/progress.html", {
        "player": player,
        "rules": player.rule_set,
        "summary": mastery.summary(player),
        "views": PROGRESS_VIEWS,
        "chosen": chosen,
        "title": title,
        "tables": _split(rows, list(dealers)),
        "lifetime": player.attempts.count(),
    })


@login_required(login_url=LOGIN_URL)
def history(request):
    """Everything that happened, and the shape of it (REQ-B.5.1, B.5.3, B.5.4).

    Three things on one screen because they answer one question. The graph says
    whether somebody is improving, the notes say what changed, and the hands say
    what actually happened. Separating them would make a person navigate to
    assemble an answer they came with.

    POST starts a new session. **Reset means fresh, never gone** (REQ-B.5.6):
    the open session is closed and a new one opened, and not one row is deleted.
    A product that lets somebody erase the hands they got wrong is a product
    whose numbers mean nothing.
    """
    from .models import Attempt, BatchNote, Player, Session

    player = Player.for_user(request.user)

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()[:60]
        open_now = Session.objects.filter(player=player, ended_at__isnull=True).first()
        if open_now:
            open_now.ended_at = timezone.now()
            open_now.save(update_fields=["ended_at"])
        Session.objects.create(player=player, name=name)
        return redirect("blackjack:history")

    session = Session.current(player)
    in_session = Attempt.objects.filter(player=player, session=session)
    notes = list(BatchNote.objects.filter(player=player)[:12])

    from . import streaks

    return render(request, "blackjack/history.html", {
        "player": player,
        "session": session,
        "streak": streaks.of(player),
        "played_here": in_session.count(),
        "notes": notes,
        "graph": _graph(notes),
        "hands": list(
            Attempt.objects.filter(player=player).select_related("rule_set")[:40]
        ),
        "lifetime": Attempt.objects.filter(player=player).count(),
        "lifetime_right": Attempt.objects.filter(player=player, is_correct=True).count(),
        "sessions": Session.objects.filter(player=player)[:10],
    })


@login_required(login_url=LOGIN_URL)
def share(request):
    """Your shared links: make one, send it, close it (REQ-B.5.8).

    A POST freezes this moment and hands back a link. Free, and deliberately
    so: sharing is how the app reaches the next person, and putting it behind
    the paid tier would be charging for the thing that grows the product.

    `dir="ltr"` on every URL shown here, because RTL bidi reorders a Latin URL
    into something that looks broken and copies wrong. That cost us a round of
    coupon links already.
    """
    from . import sharing
    from .models import Player, Share

    player = Player.for_user(request.user)
    fresh = None

    if request.method == "POST":
        token = (request.POST.get("revoke") or "").strip()
        if token:
            sharing.revoke(player, token)
            return redirect("blackjack:share")
        fresh = sharing.make(player)
        return redirect(f"{reverse('blackjack:share')}?new={fresh.token}")

    shares = list(Share.objects.filter(player=player)[:20])
    wanted = request.GET.get("new")
    fresh = next((s for s in shares if s.token == wanted), None)

    rows = []
    for item in shares:
        url = request.build_absolute_uri(item.path)
        rows.append({"share": item, "url": url})

    return render(request, "blackjack/share.html", {
        "rows": rows,
        "fresh": fresh,
        "fresh_url": request.build_absolute_uri(fresh.path) if fresh else "",
        "fresh_qr": _qr_svg(request.build_absolute_uri(fresh.path)) if fresh else "",
        "lifetime": player.attempts.count(),
    })


def shared(request, token):
    """Somebody's frozen result, open to anybody holding the link.

    **The only screen in this app that does not require an account.** It has to
    be: a link that asks a stranger to sign in before it shows them anything is
    not a shared result, it is a sign-up wall, and nobody forwards one of those.

    It renders `share.snapshot` and nothing else. Reading through to the player
    here would be how a field added next month appears on a link shared last
    month.
    """
    from django.http import Http404

    from . import sharing
    from .models import Share

    share_row = sharing.live(token)
    if share_row is None:
        raise Http404("אין כאן תוצאה. יכול להיות שהקישור נסגר.")

    # Counted with an update rather than a save, so two people opening it at
    # once do not overwrite each other's count.
    from django.db.models import F

    Share.objects.filter(pk=share_row.pk).update(views=F("views") + 1)

    # A signed-in stranger can follow the person whose result they were just
    # shown, which is the only way into the circle: there is no directory.
    from . import friends as circle_of

    me = request.user
    mine = getattr(me, "is_authenticated", False) and me.pk == share_row.player.user_id
    can_follow = (
        getattr(me, "is_authenticated", False)
        and not mine
        and not circle_of.follows(me, share_row.player.user)
    )

    return render(request, "blackjack/shared.html", {
        "data": share_row.snapshot,
        "headline": share_row.headline,
        "shared_on": share_row.snapshot.get("shared_on", ""),
        "token": share_row.token,
        "can_follow": can_follow,
        "is_mine": mine,
    })


@login_required(login_url=LOGIN_URL)
def friends(request):
    """The people you follow, and how they are doing (REQ-B.5.8, Q2).

    Free. Following is how people pull each other back to a practice app, and
    putting it behind the paid tier would be charging for the thing that grows
    the product.

    There is no search box here on purpose. Looking somebody up would mean
    typing part of their email address and being told whether it exists. You
    arrive at a person through a result they shared with you.
    """
    from . import friends as circle_of
    from .models import Player

    player = Player.for_user(request.user)

    if request.method == "POST":
        if "token" in request.POST:
            circle_of.follow_by_share(request.user, request.POST["token"].strip())
        elif "unfollow" in request.POST:
            from django.contrib.auth.models import User

            other = User.objects.filter(pk=request.POST["unfollow"]).first()
            if other is not None:
                circle_of.unfollow(request.user, other)
        elif "visibility" in request.POST:
            player.show_to_followers = request.POST["visibility"] == "on"
            player.save(update_fields=["show_to_followers"])
        return redirect("blackjack:friends")

    return render(request, "blackjack/friends.html", {
        "player": player,
        "circle": circle_of.circle(request.user),
        "shows": player.show_to_followers,
    })


def _spark(points, lo=0):
    """The accuracy line, as SVG points in a 0-100 square.

    Drawn here rather than by a charting library, for the same reason the drill
    has no framework: this is one polyline, and a library would be 90KB on a
    phone to draw it. Users of competing trainers ask for this graph by name.

    The square is stretched to the plot by the template, so these numbers are
    shares of the width and height, not pixels. `lo` is the accuracy at the
    bottom edge; the top is always 100.

    Returns None below two points: a line through one point is not a trend, it
    is a dot pretending to be information.
    """
    if len(points) < 2:
        return None

    last = len(points) - 1
    span = 100 - lo
    return " ".join(
        f"{index * 100 / last:.2f},{100 - (value - lo) / span * 100:.2f}"
        for index, value in enumerate(points)
    )


def _graph(notes):
    """Everything the history graph draws, in the order time runs.

    `notes` arrive newest first, as the model orders them. The graph goes oldest
    to newest, left to right, because that is how time reads even on a page that
    reads right to left.

    Each point carries its percentage and the moment it was written, because a
    line with no numbers on it is a line a person has to take on faith (Avi: "make
    numbers there to see my percentage and time"). The bottom of the plot is the
    lowest batch rounded down to a multiple of twenty and then twenty below that,
    so a person who never drops under 90 sees their wobble rather than a flat
    line against a floor of zero, and the axis says where the floor is.
    """
    from .models import BatchNote

    ordered = list(reversed(notes))
    if len(ordered) < 2:
        return None

    values = [round(note.accuracy * 100) for note in ordered]
    lo = max(0, min(values) // 20 * 20 - 20)
    span = 100 - lo
    last = len(values) - 1

    points = [
        {
            "pct": value,
            "at": note.created_at,
            "x": f"{index * 100 / last:.2f}",
            "y": f"{(value - lo) / span * 100:.2f}",
        }
        for index, (note, value) in enumerate(zip(ordered, values, strict=True))
    ]
    return {
        "points": points,
        "line": _spark(values, lo),
        "lo": lo,
        "mid": (lo + 100) // 2,
        "first": points[0],
        "last": points[-1],
        "batch": BatchNote.BATCH,
    }


# ------------------------------------------------------------ the paid door


@login_required(login_url=LOGIN_URL)
def redeem(request, code=""):
    """Open a coupon (REQ-B.6.4).

    Reached two ways: a link or QR carrying the code, which is how Avi sends
    them, and a plain form for somebody who was read the code over the phone.
    Both land here, and both end on the advanced screen with the week open.

    A GET with a code in the path does not redeem by itself. A link previewer
    in WhatsApp fetches every URL it is shown, and a coupon that spent itself
    on preview would be spent before the person ever saw it. So the link shows
    a button, and the button posts.
    """
    from . import gate

    if request.method == "POST":
        typed = request.POST.get("code") or code
        grant = gate.redeem(request.user, typed)
        if grant is None:
            return render(request, "blackjack/redeem.html", {"code": typed, "refused": True})
        return redirect("blackjack:advanced")

    return render(request, "blackjack/redeem.html", {"code": code, "refused": False})


@login_required(login_url=LOGIN_URL)
@paid_only
def advanced(request):
    """The coach (REQ-B.8.1).

    A POST asks the model to read this person's practice; a GET shows what it
    has said before. The reading is on demand rather than automatic, because a
    coach that speaks unprompted every time you open a page is a coach you stop
    reading, and because every reading costs money.
    """
    from . import coach
    from .models import BatchNote, Player, Trick

    player = Player.for_user(request.user)
    refused = None

    if request.method == "POST":
        if request.POST.get("what") == "tricks":
            answer = coach.tricks(request.user, player, _weak_cells(player))
        else:
            answer = coach.feedback(request.user, player)
        if isinstance(answer, coach.Refused):
            refused = answer.reason
        else:
            return redirect("blackjack:advanced")

    return render(request, "blackjack/advanced.html", {
        "access": request.bj_access,
        "refused": refused,
        "notes": BatchNote.objects.filter(player=player, is_ai=True)[:5],
        "tricks": Trick.objects.filter(player=player)[:8],
        "hands": player.attempts.count(),
    })


def _weak_cells(player, limit=5):
    """The hands worth a mnemonic, with their correct play attached.

    Read here rather than in the coach, so the coach still has no way to look a
    play up. Same arrangement as `explain`, for the same reason.
    """
    from . import mastery
    from .models import Chart

    chart = Chart.objects.filter(rule_set=player.rule_set).first()
    if chart is None:
        return []

    found = []
    for row in mastery.summary(player)["worst"][:limit]:
        cell = row["cell"]
        found.append({
            "kind": cell.kind,
            "player": cell.player,
            "dealer": cell.dealer,
            "hand": _hand_label(cell.kind, cell.player, cell.dealer),
            "action": cell.action,
            "reason": cell.reason,
        })
    return found


# ------------------------------------------------------------ admin


@login_required(login_url=LOGIN_URL)
def admin_coupons(request):
    """Mint coupons and watch the app (REQ-B.7.1 to B.7.4).

    Root only: not staff, not a tier. Counts and accuracy, never a named
    person's hands. A teacher's dashboard, not surveillance.
    """
    from django.core.exceptions import PermissionDenied

    from .models import Attempt, Coupon, Grant, Player

    if not request.user.is_superuser:
        raise PermissionDenied

    if request.method == "POST":
        days = int(request.POST.get("days") or 7)
        label = (request.POST.get("label") or "").strip()[:80]
        Coupon.mint(by=request.user, days=max(1, min(days, 365)), label=label)
        return redirect("blackjack:admin_coupons")

    now = timezone.now()
    week = now - timedelta(days=7)
    coupons = list(Coupon.objects.select_related("redeemed_by")[:50])
    for coupon in coupons:
        coupon.link = request.build_absolute_uri(
            reverse("blackjack:redeem_code", kwargs={"code": coupon.code})
        )
        coupon.qr = _qr_svg(coupon.link)

    return render(request, "blackjack/admin_coupons.html", {
        "coupons": coupons,
        "players": Player.objects.count(),
        "active_week": Player.objects.filter(attempts__created_at__gte=week).distinct().count(),
        "hands": Attempt.objects.count(),
        "hands_week": Attempt.objects.filter(created_at__gte=week).count(),
        "accuracy": _accuracy(Attempt.objects.filter(created_at__gte=week)),
        "trials_open": Player.objects.filter(first_used_at__gte=now - timedelta(minutes=30)).count(),
        "grants_open": Grant.objects.filter(starts_at__lte=now, ends_at__gt=now).count(),
        "coupons_open": Coupon.objects.filter(redeemed_by__isnull=True).count(),
    })


def _accuracy(attempts):
    total = attempts.count()
    if not total:
        return None
    return round(100 * attempts.filter(is_correct=True).count() / total)


def _qr_svg(text):
    """A QR as inline SVG, from the library the site already carries."""
    import io

    import qrcode
    import qrcode.image.svg

    image = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=6, border=2)
    out = io.BytesIO()
    image.save(out)
    return out.getvalue().decode("utf-8")


@login_required(login_url=LOGIN_URL)
@paid_only
def explain(request):
    """A deeper explanation of one cell, for the drill's verdict panel.

    **The view reads the chart, not the coach.** It looks the cell up here and
    hands the correct action to `coach.explain`, which keeps the coach unable
    to decide anything even if somebody later edits its prompt.

    JSON, because the drill is a page that never reloads. A free account is
    refused by the same decorator every other paid screen uses, and gets JSON
    rather than an HTML page because that is what asked.
    """
    from django.http import JsonResponse

    from . import coach
    from .models import Chart, Mastery, Player

    player = Player.for_user(request.user)
    chart = Chart.objects.filter(rule_set=player.rule_set).first()
    if chart is None:
        return JsonResponse({"refused": "אין טבלה לשולחן הזה."}, status=400)

    try:
        kind = request.POST["kind"]
        value = int(request.POST["player"])
        dealer = int(request.POST["dealer"])
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"refused": "חסרים פרטי היד."}, status=400)

    cell = chart.cells.filter(kind=kind, player=value, dealer=dealer).first()
    if cell is None:
        return JsonResponse({"refused": "אין תא כזה בטבלה."}, status=400)

    record = Mastery.objects.filter(
        player=player, cell_kind=kind, cell_player=value, cell_dealer=dealer
    ).first()

    answer = coach.explain(request.user, player, {
        "hand": _hand_label(kind, value, dealer),
        "action": cell.action,
        "fallback": cell.fallback,
        "reason": cell.reason,
        "seen": record.seen if record else 0,
        "correct": record.correct if record else 0,
    })

    if isinstance(answer, coach.Refused):
        return JsonResponse({"refused": answer.reason}, status=402)
    return JsonResponse({"text": answer})


def _hand_label(kind, value, dealer):
    face = "A" if dealer == 11 else str(dealer)
    return f"{_row_label(kind, value)} מול {face}"
