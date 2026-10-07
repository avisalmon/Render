"""What to work on in the scales and chords trainer: a read over runs and attempts, stored nowhere.

The best run of each key at each octave count, the slowest chords (median time to the right answer,
skips have no time and are left out), the keys missed most often, and plain totals.
"""

from statistics import median

from .models import DrillAttempt, ScaleRun

MIN_CHORD_ANSWERS = 3
MIN_KEY_PROMPTS = 5
SLOWEST_SHOWN = 5


def _scales(player):
    best = {}
    count = {}
    for run in ScaleRun.objects.filter(player=player).order_by("created_at", "pk"):
        slot = (run.root_pc, run.octaves)
        count[slot] = count.get(slot, 0) + 1
        if slot not in best or run.score > best[slot].score:
            best[slot] = run
    return [
        {
            "root_pc": slot[0], "octaves": slot[1], "score": run.score, "tempo_bpm": run.tempo_bpm,
            "passed": run.passed, "runs": count[slot], "at": run.created_at.isoformat(),
        }
        for slot, run in sorted(best.items(), key=lambda item: item[0])
    ]


def _slowest(attempts):
    groups = {}
    for a in attempts:
        prompt = a.prompt if isinstance(a.prompt, dict) else {}
        title = prompt.get("title")
        if not title or a.response_ms is None:
            continue
        slot = (a.key_pc, prompt.get("symbol"), prompt.get("position"))
        group = groups.setdefault(slot, {"title": title, "key_pc": a.key_pc, "position": prompt.get("position"), "times": []})
        group["times"].append(a.response_ms)
    rows = [
        {"title": g["title"], "key_pc": g["key_pc"], "position": g["position"], "median_ms": round(median(g["times"])), "attempts": len(g["times"])}
        for g in groups.values()
        if len(g["times"]) >= MIN_CHORD_ANSWERS
    ]
    rows.sort(key=lambda r: (-r["median_ms"], r["key_pc"], r["title"]))
    return rows[:SLOWEST_SHOWN]


def _weakest(attempts):
    seen = {}
    for a in attempts:
        total, missed = seen.get(a.key_pc, (0, 0))
        seen[a.key_pc] = (total + 1, missed + (0 if a.is_correct else 1))
    rows = [
        {"key_pc": pc, "attempts": total, "missed": missed, "miss_share": round(missed / total, 3)}
        for pc, (total, missed) in seen.items()
        if total >= MIN_KEY_PROMPTS
    ]
    rows.sort(key=lambda r: (-r["miss_share"], -r["attempts"], r["key_pc"]))
    return rows


def report(player):
    attempts = list(DrillAttempt.objects.filter(player=player, kind="chord_position"))
    runs = ScaleRun.objects.filter(player=player)
    return {
        "scales": _scales(player),
        "slowest_chords": _slowest(attempts),
        "weakest_keys": _weakest(attempts),
        "totals": {
            "runs": runs.count(),
            "passes": runs.filter(passed=True).count(),
            "attempts": len(attempts),
            "clean": sum(1 for a in attempts if a.is_correct and not a.hint_used),
        },
    }
