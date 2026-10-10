"""Where the player is on each piece of the repertoire: a read over piece takes, stored nowhere (spec chapter 12).

Each published piece comes with its ladder (improv/ladder.py), and against every rung whether it was passed, the
best Flow score and how many takes it has had. `next` is the first rung not yet passed: the place a teacher would
set the next task. Nothing is locked; a pass further along counts and the pointer still names the first gap.
A superuser who is reading the drafts sees those pieces too.
"""

from . import ladder
from .models import Piece, PieceTake


def _stats(takes):
    stats = {}
    for take in takes:
        row = stats.setdefault((take["piece_id"], take["rung"]), {"passed": False, "best": None, "takes": 0})
        row["takes"] += 1
        if take["passed"]:
            row["passed"] = True
        if take["mode"] == PieceTake.Mode.FLOW and (row["best"] is None or take["score"] > row["best"]):
            row["best"] = take["score"]
    return stats


def piece_rungs(piece):
    return ladder.rungs([(p.first_bar, p.last_bar) for p in piece.phrases.all()])


def report(player, user):
    pieces = Piece.objects.prefetch_related("phrases")
    if not user.is_superuser:
        pieces = pieces.filter(status=Piece.Status.PUBLISHED)
    takes = list(PieceTake.objects.filter(player=player).values("piece_id", "rung", "passed", "score", "mode"))
    stats = _stats([t for t in takes if t["rung"] != ladder.DRILL])
    out = []
    for piece in pieces:
        rows = []
        for rung in piece_rungs(piece):
            seen = stats.get((piece.pk, rung["key"]), {"passed": False, "best": None, "takes": 0})
            rows.append({**rung, **seen})
        nxt = next((r["key"] for r in rows if not r["passed"]), None)
        done = sum(1 for r in rows if r["passed"])
        out.append(
            {
                "slug": piece.slug, "title": piece.title, "level": piece.level, "order": piece.order,
                "rungs": rows, "next": nxt, "passed_count": done, "total": len(rows), "done": bool(rows) and nxt is None,
            }  # fmt: skip
        )
    return {
        "pieces": out,
        "totals": {"takes": len(takes), "passes": sum(1 for t in takes if t["passed"]), "pieces_done": sum(1 for p in out if p["done"])},
    }
