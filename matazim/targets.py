"""The entrance-test bank: files on disk, decisions in the database.

The objects were generated offline by a management command and committed, so the
web process never needs a CAD engine (REQ-10.25, carried over). It reads a
drawing, reads an answer key, and compares. What lives in the database is only
what a human decided: which targets are too hard and should stop being handed
out.

The measuring itself is not ours either. `app.matazim_check` and
`app.matazim_geometry` were written for the first version of this program,
survived its retirement, and are still under test. Reusing them rather than
rewriting them is the same call we made about the course engine.
"""

import random
from pathlib import Path

from django.conf import settings

from app.matazim_check import TOLERANCES, available_target_ids, check, encouragement, load_target

from .models import EntranceTarget

DRAWINGS = Path(settings.BASE_DIR) / "static" / "matazim" / "targets"

__all__ = [
    "sync_bank",
    "pick_target",
    "measure_submission",
    "encouragement",
    "TOLERANCES",
]


def sync_bank():
    """Make sure every generated target has a row. Returns how many were added.

    Runs on deploy, so it has to be idempotent and it must never reset a
    decision: a target Avi retired stays retired the next time this runs.
    """
    existing = set(EntranceTarget.objects.values_list("target_id", flat=True))
    rows = []
    for target_id in available_target_ids():
        if target_id in existing:
            continue
        facts = load_target(target_id)
        rows.append(
            EntranceTarget(
                target_id=target_id,
                shape=facts.get("shape", ""),
                title=facts.get("title", ""),
                brief="\n".join(facts.get("brief", [])),
            )
        )
    EntranceTarget.objects.bulk_create(rows)
    return len(rows)


def pick_target(exclude=()):
    """An object for someone to build. None when staff have retired them all.

    Random rather than sequential, and a fresh one on every retry, because that
    is what makes a model downloaded from the internet useless: nothing out
    there matches an object we invented.
    """
    pool = list(
        EntranceTarget.objects.filter(is_retired=False)
        .exclude(target_id__in=list(exclude))
        .values_list("target_id", flat=True)
    )
    if not pool:
        # Everything left is either retired or already seen. Falling back to the
        # seen ones beats handing a member a dead end.
        pool = list(
            EntranceTarget.objects.filter(is_retired=False).values_list("target_id", flat=True)
        )
    if not pool:
        return None
    return EntranceTarget.objects.get(target_id=random.choice(pool))


def measure_submission(raw_bytes, target_id):
    """Judge an upload against its assigned target.

    Returns (passed, issues, measured). Anything unreadable comes back as a
    single kind sentence rather than an exception: a teenager who uploaded a
    holiday photo by mistake gets told what happened, not a stack trace.
    """
    try:
        facts = load_target(target_id)
    except FileNotFoundError:
        return False, [{"text": "לא הצלחנו למצוא את המשימה שלכם. נסו לרענן את הדף."}], {}

    try:
        return check(raw_bytes, facts)
    except Exception:
        return (
            False,
            [
                {
                    "text": "לא הצלחנו לקרוא את הקובץ. ודאו שייצאתם STL מטינקרקאד "
                    "(Export ואז STL) ושהקובץ לא ריק.",
                }
            ],
            {},
        )


def drawing_exists(target_id):
    return (DRAWINGS / f"{target_id}.svg").exists()


def target_facts(target_id):
    """The public half of a target: what the applicant is allowed to see."""
    facts = load_target(target_id)
    return {
        "id": target_id,
        "title": facts.get("title", ""),
        "brief": facts.get("brief", []),
        "drawing_url": f"/static/matazim/targets/{target_id}.svg",
        "model_url": f"/static/matazim/targets/{target_id}.stl",
    }
