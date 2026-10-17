"""The strategy lab's server side (SPR-B.12, REQ-B.11).

The lab plays its hands in the person's own browser (REQ-B.11.23). This module
is what the server still has to do, and it is deliberately small:

1. **Hand the browser a chart** for the rules it chose, built by `strategy` so
   the browser never carries its own idea of the right play.
2. **Keep only what is worth keeping** (Avi, 2026-10-16: "don't bombard the
   database ... just save the results, the policy, the trend graph, a minimum
   set of data"). A finished run is its conditions, its policy, and a short
   summary. The hundreds of thousands of hands, the day-by-day lines and the
   candidates a search tried live in the page that ran them and are gone when
   it closes.
3. **Refuse to be a free notebook.** The summary is reported by the browser, so
   its shape is checked field by field and its size is capped; nothing outside
   the lists below is stored, and a person keeps only their newest `KEEP_RUNS`.

Play money only. Nothing here is ranked or shared.
"""

import json
import math
from functools import lru_cache

from . import strategy
from .models import DEFAULT_RULES, RULE_FIELDS

MAX_DAYS = 500
MAX_HANDS = 100_000
KEEP_RUNS = 50
MAX_LADDER = 12
MAX_FREEZE = 12
MAX_BYTES = 6000          # per stored JSON field
CURVE_POINTS = 60
HIST_BINS = 20
BIG = 10 ** 9

MODES = ("days", "search")
GOALS = ("ahead", "avg", "survive", "mix")
CHARTS = ("classic", "calculated")
CALC_DECKS = (1, 2, 3, 4, 5, 6, 7, 8)
AFTER_WIN = ("reset", "stay", "back")
AT_LIMIT = ("stay", "restart", "stop")
SHORT = ("rest", "restart", "stop")
FREEZE_AFTER = ("stop", "repeat")

# What the lab lets a person change, and what it fixes because the classic
# chart is only built for these (`strategy.supports`).
CHOOSABLE = {
    "decks": (4, 6, 8),
    "max_splits": (2, 3, 4),
    "blackjack_pays": ("3:2", "6:5"),
}
SWITCHES = ("dealer_hits_soft_17", "double_after_split", "resplit_aces", "hit_split_aces")


class Refused(ValueError):
    """A message a person can read."""


def clean_rules(data, chart="classic"):
    """The full rule dict for a request, with the app's defaults for anything
    left out, or `Refused`.

    With the classic chart the rules must be ones `strategy` has a chart for.
    With a calculated chart (REQ-B.11.26) any number of decks from 1 to 8 is
    fine, because the browser works the chart out; the rules the engine does not
    play are still fixed, since there would be nothing to play them with."""
    data = data or {}
    if not isinstance(data, dict):
        raise Refused("הכללים לא הגיעו כמו שצריך.")
    rules = dict(DEFAULT_RULES)
    choosable = dict(CHOOSABLE)
    if chart == "calculated":
        choosable["decks"] = CALC_DECKS
    for field, allowed in choosable.items():
        if field in data:
            value = data[field]
            if isinstance(value, str) and field != "blackjack_pays":
                value = int(value) if value.isdigit() else value
            if value not in allowed:
                raise Refused("ערך לא מוכר בשדה " + field + ".")
            rules[field] = value
    for field in SWITCHES:
        if field in data:
            rules[field] = _flag(data[field])
    if chart == "classic":
        ok, why = strategy.supports(rules)
        if not ok:
            raise Refused("; ".join(why))
    return rules


def _flag(value):
    if isinstance(value, bool):
        return value
    if str(value).lower() in ("1", "true", "on", "yes"):
        return True
    if str(value).lower() in ("0", "false", "off", "no", ""):
        return False
    raise Refused("מתג לא מובן.")


@lru_cache(maxsize=64)
def _cells(key):
    rules = dict(zip(RULE_FIELDS, key))
    return [[k, p, d, a, f] for (k, p, d, a, f, _reason) in strategy.every_cell(rules)]


def chart_cells(rules):
    """`[[kind, player, dealer, action, fallback], ...]` for these rules."""
    return _cells(tuple(rules[f] for f in RULE_FIELDS))


# ---------------------------------------------------------------- numbers


def _int(value, low, high, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Refused(what + ": צריך מספר.")
    if isinstance(value, float):
        if not value.is_integer():
            raise Refused(what + ": צריך מספר שלם.")
        value = int(value)
    if value < low or value > high:
        raise Refused(f"{what}: בין {low:,} ל-{high:,}.")
    return value


def _num(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise Refused(what + ": צריך מספר.")
    if abs(value) > 10 ** 12:
        raise Refused(what + ": המספר גדול מדי.")
    return round(value, 4) if isinstance(value, float) else value


def _one_of(value, allowed, what):
    if value not in allowed:
        raise Refused(what + ": ערך לא מוכר.")
    return value


def _list(value, low, high, longest, what):
    if not isinstance(value, list) or len(value) > longest:
        raise Refused(f"{what}: רשימה של עד {longest} מספרים.")
    return [_int(v, low, high, what) for v in value]


def _pairs(value, longest, what):
    """A list of freeze steps, each `[profit that sets it off, amount sent home]`.
    A bare number is the old form of a step, where both were the same."""
    if not isinstance(value, list) or len(value) > longest:
        raise Refused(f"{what}: רשימה של עד {longest} שלבים.")
    out = []
    for entry in value:
        if isinstance(entry, list) and len(entry) == 2:
            gain, take = entry
        elif isinstance(entry, list):
            raise Refused(what + ": בכל שלב שני מספרים, כמה רווח וכמה להוציא הביתה.")
        else:
            gain = take = entry
        out.append([_int(gain, 1, BIG, what), _int(take, 1, BIG, what)])
    return out


# ---------------------------------------------------------------- the policy


def clean_policy(data):
    if not isinstance(data, dict):
        raise Refused("חסרה מדיניות.")
    start = _int(data.get("start"), 1, BIG, "כסף להתחלה")
    min_bet = _int(data.get("minBet"), 1, BIG, "הימור מינימלי")
    limit = _int(data.get("limit"), min_bet, BIG, "מגבלת שולחן")
    ladder = _list(data.get("ladder"), 1, BIG, MAX_LADDER, "סולם ההימורים")
    if not ladder:
        raise Refused("סולם ההימורים ריק.")
    freeze = _pairs(data.get("freeze"), MAX_FREEZE, "שלבי ההקפאה")
    return {
        "start": start,
        "minBet": min_bet,
        "limit": limit,
        "ladder": ladder,
        "afterWin": _one_of(data.get("afterWin"), AFTER_WIN, "אחרי ניצחון"),
        "atLimit": _one_of(data.get("atLimit"), AT_LIMIT, "בסוף הסולם"),
        "short": _one_of(data.get("short"), SHORT, "כשחסר כסף"),
        "freeze": freeze,
        "freezeAfter": _one_of(data.get("freezeAfter"), FREEZE_AFTER, "אחרי שלב ההקפאה האחרון"),
    }


_KINDS = {"hard": (5, 20), "soft": (13, 20), "pair": (2, 11)}


def clean_overrides(data):
    if data in (None, ""):
        return {}
    if not isinstance(data, dict) or len(data) > 400:
        raise Refused("שינויים בטבלה: רשימה לא תקינה.")
    out = {}
    for key, action in data.items():
        parts = str(key).split("|")
        if len(parts) != 3 or parts[0] not in _KINDS:
            raise Refused("שינוי בטבלה לא מוכר.")
        low, high = _KINDS[parts[0]]
        try:
            player, dealer = int(parts[1]), int(parts[2])
        except ValueError:
            raise Refused("שינוי בטבלה לא מוכר.")
        if not (low <= player <= high and 2 <= dealer <= 11):
            raise Refused("שינוי בטבלה מחוץ לטבלה.")
        out[f"{parts[0]}|{player}|{dealer}"] = _one_of(action, ("H", "S", "D", "P"), "פעולה")
    return out


def clean_settings(mode, data):
    """Everything needed to set the same run up again, and nothing else."""
    if not isinstance(data, dict):
        raise Refused("חסרות הגדרות.")
    out = {
        "policy": clean_policy(data.get("policy")),
        "overrides": clean_overrides(data.get("overrides")),
        "handsPerDay": _int(data.get("handsPerDay"), 1, MAX_HANDS, "מספר ידיים ביום"),
        "seed": _int(data.get("seed"), 0, 2 ** 32 - 1, "זרע"),
        "chart": _one_of(data.get("chart", "classic"), CHARTS, "טבלה"),
    }
    if mode == "days":
        out["days"] = _int(data.get("days"), 1, MAX_DAYS, "מספר ימים")
    else:
        out["goal"] = _one_of(data.get("goal"), GOALS, "מטרה")
        if out["goal"] == "mix":
            mix = data.get("mix")
            if not isinstance(mix, dict):
                raise Refused("חסרים משקלים לשילוב.")
            out["mix"] = {k: _int(mix.get(k), 0, 10, "משקל") for k in ("ahead", "avg", "survive")}
            if not sum(out["mix"].values()):
                raise Refused("לפחות משקל אחד צריך להיות גדול מאפס.")
        out["days"] = _int(data.get("days"), 1, MAX_DAYS, "ימים לכל מדיניות")
        out["holdoutDays"] = _int(data.get("holdoutDays"), 1, MAX_DAYS, "ימים לבדיקה")
    _fit(out)
    return out


# ---------------------------------------------------------------- the summary


_DAY_NUMBERS = (
    "days", "handsPerDay", "start", "ahead", "classicAhead", "helped", "hurt",
    "avg", "classicAvg", "best", "worst", "classicBest", "classicWorst",
    "bust", "classicBust", "medianRounds", "classicMedianRounds",
    "frozenAvg", "classicFrozenAvg", "overrideFallbacks",
)


def _curve(value, what):
    if not isinstance(value, list) or not (1 <= len(value) <= CURVE_POINTS):
        raise Refused(f"{what}: עד {CURVE_POINTS} נקודות.")
    return [_num(v, what) for v in value]


def _hist(value):
    if not isinstance(value, dict):
        raise Refused("היסטוגרמה חסרה.")
    out = {"lo": _num(value.get("lo"), "היסטוגרמה"), "hi": _num(value.get("hi"), "היסטוגרמה")}
    for field in ("counts", "classicCounts"):
        counts = value.get(field)
        if not isinstance(counts, list) or len(counts) != HIST_BINS:
            raise Refused(f"היסטוגרמה: {HIST_BINS} עמודות.")
        out[field] = [_int(c, 0, MAX_DAYS, "עמודה") for c in counts]
    return out


def _score(value):
    if not isinstance(value, dict):
        raise Refused("ציון חסר.")
    return {k: _num(value.get(k), "ציון") for k in ("value", "ahead", "avg", "survive")}


def clean_summary(mode, data):
    if not isinstance(data, dict):
        raise Refused("חסרות תוצאות.")
    if mode == "days":
        out = {k: _num(data.get(k), k) for k in _DAY_NUMBERS}
        out["changed"] = bool(data.get("changed"))
        out["chart"] = _one_of(data.get("chart", "classic"), CHARTS, "טבלה")
        out["curve"] = _curve(data.get("curve"), "גרף")
        out["classicCurve"] = _curve(data.get("classicCurve"), "גרף קלאסי")
        out["hist"] = _hist(data.get("hist"))
        if out["days"] > MAX_DAYS or out["handsPerDay"] > MAX_HANDS:
            raise Refused("התוצאות חורגות מהמגבלות.")
    else:
        best = data.get("best") or {}
        base = data.get("baseline") or {}
        out = {
            "tries": _int(data.get("tries"), 0, 10 ** 7, "ניסיונות"),
            "ms": _int(data.get("ms") or 0, 0, 10 ** 9, "זמן"),
            "improved": bool(data.get("improved")),
            "baseline": {"train": _score(base.get("train")), "holdout": _score(base.get("holdout"))},
            "best": {
                "policy": clean_policy(best.get("policy")),
                "train": _score(best.get("train")),
                "holdout": _score(best.get("holdout")),
            },
        }
    _fit(out)
    return out


def _fit(value):
    if len(json.dumps(value, separators=(",", ":"))) > MAX_BYTES:
        raise Refused("הנתונים גדולים מדי לשמירה.")


# ---------------------------------------------------------------- keeping


def prune(player):
    """Keep a person's newest `KEEP_RUNS` and let the rest go."""
    from .models import LabRun

    keep = list(LabRun.objects.filter(player=player).order_by("-created_at", "-id").values_list("id", flat=True)[:KEEP_RUNS])
    LabRun.objects.filter(player=player).exclude(id__in=keep).delete()


def default_settings():
    """What the conditions screen opens with: Avi's own run (REQ-B.11.18)."""
    return {
        "policy": {
            "start": 1000, "minBet": 15, "limit": 500,
            "ladder": [15, 50, 150, 500],
            "afterWin": "reset", "atLimit": "stay", "short": "rest",
            "freeze": [[500, 1000], [500, 500], [1000, 500], [2000, 1000]], "freezeAfter": "stop",
        },
        "overrides": {},
        "handsPerDay": 400,
        "days": 30,
        "goal": "ahead",
        "mix": {"ahead": 5, "avg": 3, "survive": 2},
        "chart": "classic",
        "holdoutDays": 100,
    }
