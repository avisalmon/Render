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

    from . import gate, mastery

    payload = chart_payload(chart)
    payload["review"] = recent_misses(player)

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
        "rows": rows,
        "dealers": dealers,
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

    # Oldest first, so the graph reads left to right the way time does.
    points = list(reversed([round(note.accuracy * 100) for note in notes]))

    return render(request, "blackjack/history.html", {
        "player": player,
        "session": session,
        "played_here": in_session.count(),
        "notes": notes,
        "points": points,
        "spark": _spark(points),
        "hands": list(
            Attempt.objects.filter(player=player).select_related("rule_set")[:40]
        ),
        "lifetime": Attempt.objects.filter(player=player).count(),
        "lifetime_right": Attempt.objects.filter(player=player, is_correct=True).count(),
        "sessions": Session.objects.filter(player=player)[:10],
    })


def _spark(points, width=300, height=70):
    """The accuracy graph, as an SVG path.

    Drawn here rather than by a charting library, for the same reason the drill
    has no framework: this is one polyline, and a library would be 90KB on a
    phone to draw it. Users of competing trainers ask for this graph by name.

    Returns None below two points: a line through one point is not a trend, it
    is a dot pretending to be information.
    """
    if len(points) < 2:
        return None

    pad = 6
    span = max(1, len(points) - 1)
    step = (width - pad * 2) / span
    floor, ceiling = 0, 100

    coords = []
    for index, value in enumerate(points):
        x = pad + index * step
        y = height - pad - ((value - floor) / (ceiling - floor)) * (height - pad * 2)
        coords.append(f"{x:.1f},{y:.1f}")
    return " ".join(coords)


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
