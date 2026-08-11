"""Chapter 10 §10.7 - checking an entrance-test submission against its target.

The one thing to keep in mind reading this: **it measures commitment, not
precision** (Avi, 2026-08-08). Tolerances are deliberately generous, the verdict
is "accepted" or "not yet" and never "rejected", and every message is written to
send a teenager back into Tinkercad rather than to inform them they have failed.

Six checks, in the order a person would notice the problems:

    outer size      bounding box, sorted, so orientation is free
    hole count      genus, from the Euler number
    one solid       shell count - loose shapes that were never grouped
    hole size       bounding-box volume minus solid volume
    hole position   centroid offset, inverted into real millimetres
    overall shape   surface area, as the catch-all

Nothing here needs to find a hole, recognise a feature, or align two meshes.
"""

import json
from pathlib import Path

from django.conf import settings

from .matazim_geometry import implied_hole_shift, measure, read_stl

TARGET_DATA_DIR = Path(settings.BASE_DIR) / "app" / "matazim_assets" / "targets"

# Calibrated for "you clearly built the thing I showed you", not for precision.
# Outer dimensions are typed into Tinkercad so they are usually exact; a hole is
# dragged into place, so its position gets real slack (§10.7).
TOLERANCES = {
    "dim_mm": 3.0,          # each outer dimension
    "cut_volume_pct": 0.30,  # how much material was carved away
    "hole_shift_mm": 5.0,    # how far a hole drifted
    "area_pct": 0.15,        # overall shape, catch-all
    "max_upload_bytes": 20 * 1024 * 1024,
}


def load_target(target_id):
    """The target's parameters and reference measurements. Read server-side
    only: this is the answer key, which is why it does not live in static/."""
    path = TARGET_DATA_DIR / f"{target_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"unknown target {target_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def available_target_ids():
    return sorted(p.stem for p in TARGET_DATA_DIR.glob("*.json"))


def _pct_off(actual, expected):
    if not expected:
        return 0.0
    return abs(actual - expected) / abs(expected)


def check(stl_bytes, target):
    """Measure a submission and judge it against its target.

    Returns (passed, issues, measured). `issues` are already phrased in Hebrew
    for the applicant, each with the actual number, because "your height is 43
    instead of 40" sends them somewhere and "incorrect" does not.
    """
    issues = []
    ref = target["reference"]

    try:
        tris = read_stl(stl_bytes)
    except Exception:
        return False, [{
            "code": "unreadable",
            "text": "לא הצלחנו לקרוא את הקובץ. ודאו שייצאתם STL מטינקרקאד.",
        }], {}

    if not tris:
        return False, [{"code": "empty", "text": "הקובץ ריק."}], {}

    m = measure(tris)
    measured = {
        "dims": list(m["dims"]), "volume": m["volume"], "area": m["area"],
        "cut_volume": m["cut_volume"], "genus": m["genus"],
        "shells": m["shells"], "watertight": m["watertight"],
        "triangles": m["triangles"],
        "hole_shift": implied_hole_shift(m) if m["cut_volume"] > 0 else 0.0,
    }

    # --- outer size ------------------------------------------------------
    want = sorted(ref["dims"])
    got = sorted(m["dims"])
    worst = max(abs(a - b) for a, b in zip(want, got))
    if worst > TOLERANCES["dim_mm"]:
        issues.append({
            "code": "dims",
            "text": (f'המידות החיצוניות לא מתאימות. אצלכם '
                     f'{" × ".join(f"{v:.0f}" for v in reversed(got))} מ"מ, '
                     f'צריך {" × ".join(f"{v:.0f}" for v in reversed(want))} מ"מ.'),
        })

    # --- one closed solid ------------------------------------------------
    if m["shells"] > 1:
        issues.append({
            "code": "shells",
            "text": (f'הקובץ מכיל {m["shells"]} גופים נפרדים. בטינקרקאד '
                     f'סמנו הכל ולחצו Group כדי לאחד לגוף אחד.'),
        })

    # --- holes -----------------------------------------------------------
    # Genus needs a closed surface. A mesh with gaps is not the kid's fault and
    # must not be read as "no hole", so fall back to the volume evidence.
    want_holes = ref["genus"]
    if m["watertight"] and m["genus"] is not None:
        if m["genus"] != want_holes:
            if want_holes == 0:
                text = "יש בדגם חור שלא היה אמור להיות."
            elif m["genus"] == 0:
                text = (f'חסר חור עובר. צריך {want_holes} '
                        f'{"חורים" if want_holes > 1 else "חור"} שעוברים מצד לצד.')
            else:
                text = f'יש {m["genus"]} חורים במקום {want_holes}.'
            issues.append({"code": "holes", "text": text})
    elif not m["watertight"]:
        issues.append({
            "code": "not_watertight",
            "text": ("הדגם לא סגור לגמרי, אז לא הצלחנו לספור את החורים. "
                     "בדרך כלל זה נפתר בייצוא מחדש מטינקרקאד."),
        })

    # --- how much material was removed -----------------------------------
    if ref["cut_volume"] > 1.0:
        off = _pct_off(m["cut_volume"], ref["cut_volume"])
        if off > TOLERANCES["cut_volume_pct"]:
            bigger = m["cut_volume"] > ref["cut_volume"]
            issues.append({
                "code": "cut_volume",
                "text": ("החור גדול מדי." if bigger else "החור קטן מדי.")
                        + " בדקו את הקוטר בשרטוט.",
            })

    # --- where the hole ended up ----------------------------------------
    if want_holes and m["cut_volume"] > 0:
        shift = implied_hole_shift(m)
        if shift > TOLERANCES["hole_shift_mm"]:
            issues.append({
                "code": "hole_position",
                "text": f'החור לא במקום: הוא זז בערך {shift:.0f} מ"מ מהמיקום בשרטוט.',
            })

    # --- catch-all -------------------------------------------------------
    if _pct_off(m["area"], ref["area"]) > TOLERANCES["area_pct"] and not issues:
        issues.append({
            "code": "shape",
            "text": "הצורה הכללית לא מתאימה לשרטוט. שווה להשוות שוב מול המידות.",
        })

    return (not issues), issues, measured


def encouragement(issues, attempt_number):
    """The line above the issue list. What a kid reads first decides whether
    they open Tinkercad again, so it is never the word 'failed'."""
    if not issues:
        return "יפה מאוד. הדגם שלכם תואם לשרטוט."
    if attempt_number == 1:
        return "כמעט. הנה מה שצריך לתקן, וזה בהחלט לא נורא:"
    return "עוד קצת. אתם מתקרבים, הנה מה שנשאר:"
