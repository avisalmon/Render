"""Where the player is in the reading ladder, and what they misread: a read over reading takes, stored nowhere.

The ladder mirrors static/improv/reading.js: twelve keys, each with the right hand, then the left, then both.
The path's stage is one past the highest stage passed in Flow; a pass further along counts, as in the lessons
(spec ch. 6 "Start anywhere"). The weak-spot map counts, per part of the staff, how many notes of the last
thirty days were missed or misread, and names the worst as the focus the generator leans toward.
"""

import datetime as dt

from django.utils import timezone

from .models import ReadingTake

KEYS = ["C", "G", "F", "D", "Bb", "A", "Eb", "E", "Ab", "B", "Db", "F#"]
HANDS = ["R", "L", "B"]
STAGES = len(KEYS) * len(HANDS)
WINDOW_DAYS = 30
MIN_ZONE_NOTES = 6
FOCUS_SHARE = 0.25
FOCUS_SHOWN = 2
TREBLE = (30, 38)
BASS = (18, 26)


def stage_index(key, hands):
    if key not in KEYS or hands not in HANDS:
        return None
    return KEYS.index(key) * len(HANDS) + HANDS.index(hands)


def stage_of(index):
    i = max(0, min(STAGES - 1, int(index)))
    return {"index": i, "key": KEYS[i // len(HANDS)], "hands": HANDS[i % len(HANDS)], "difficulty": 1 + (i // len(HANDS)) // 4, "total": STAGES}


def zone_of(hand, step):
    bottom, top = TREBLE if hand == "R" else BASS
    name = "treble" if hand == "R" else "bass"
    if step < bottom:
        return f"{name}-below"
    if step > top:
        return f"{name}-above"
    return f"{name}-on"


def _bests(takes):
    best = {}
    count = {}
    for take in takes:
        index = stage_index(take.key, take.hands)
        if index is None or take.mode != ReadingTake.Mode.FLOW:
            continue
        count[index] = count.get(index, 0) + 1
        if index not in best or take.score > best[index].score:
            best[index] = take
    return [
        {"index": index, "key": take.key, "hands": take.hands, "score": take.score, "tempo_bpm": take.tempo_bpm, "passed": take.passed, "takes": count[index], "at": take.created_at.isoformat()}
        for index, take in sorted(best.items())
    ]


def _zones(takes):
    since = timezone.now() - dt.timedelta(days=WINDOW_DAYS)
    seen = {}
    for take in takes:
        if take.created_at < since:
            continue
        notes = take.notes if isinstance(take.notes, list) else []
        results = take.results if isinstance(take.results, list) else []
        for note, result in zip(notes, results):
            if not isinstance(note, dict) or not isinstance(result, dict) or result.get("state") in ("out", "pending"):
                continue
            zone = zone_of(note.get("hand"), int(note.get("step", 0)))
            total, missed = seen.get(zone, (0, 0))
            seen[zone] = (total + 1, missed + (1 if result.get("state") in ("wrong", "missed") else 0))
    rows = [{"zone": zone, "seen": total, "missed": missed, "share": round(missed / total, 3)} for zone, (total, missed) in seen.items()]
    rows.sort(key=lambda r: (-r["share"], -r["seen"], r["zone"]))
    return rows


def report(player):
    takes = list(ReadingTake.objects.filter(player=player).order_by("created_at", "pk"))
    passed = sorted({stage_index(t.key, t.hands) for t in takes if t.passed and stage_index(t.key, t.hands) is not None})
    highest = passed[-1] if passed else -1
    done = highest >= STAGES - 1
    stage = stage_of(min(highest + 1, STAGES - 1))
    stage["done"] = done
    zones = _zones(takes)
    focus = [z["zone"] for z in zones if z["seen"] >= MIN_ZONE_NOTES and z["share"] >= FOCUS_SHARE][:FOCUS_SHOWN]
    return {
        "stage": stage,
        "passed": passed,
        "bests": _bests(takes),
        "zones": zones,
        "focus": focus,
        "totals": {"takes": len(takes), "passes": sum(1 for t in takes if t.passed)},
    }
