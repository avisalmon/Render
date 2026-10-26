"""The mouth (spec chapter 5): the chart is a history, drawn as a mouth.

Nothing here is a drawing stored anywhere. `chart(patient)` reads every
`ToothState` row and keeps the latest per tooth and surface (Rule 5.1);
`layout(...)` arranges the teeth the way a dentist reads a chart: the
patient's right on the viewer's left, upper arch above lower, quadrant 1
to 4 (adults, 11 to 48) or 5 to 8 (children, 51 to 85). Each tooth is a
five-part glyph: O in the middle, B above, L below, M towards the midline,
D away from it.
"""

from .models import FDI_ADULT, FDI_CHILD, ToothState

# Upper row reads 18..11 then 21..28; lower reads 48..41 then 31..38.
ADULT_ROWS = [list(range(18, 10, -1)) + list(range(21, 29)), list(range(48, 40, -1)) + list(range(31, 39))]
CHILD_ROWS = [list(range(55, 50, -1)) + list(range(61, 66)), list(range(85, 80, -1)) + list(range(71, 76))]

# The common names a volunteer recognises at a glance.
NAMES = {1: "central incisor", 2: "lateral incisor", 3: "canine", 4: "first premolar", 5: "second premolar",
         6: "first molar", 7: "second molar", 8: "third molar"}
CHILD_NAMES = {1: "central incisor", 2: "lateral incisor", 3: "canine", 4: "first molar", 5: "second molar"}


def chart(patient):
    """{(tooth, surface): latest ToothState}. Rows come ordered by tooth,
    surface, newest first, so the first seen per key is the latest."""
    latest = {}
    for row in patient.teeth.select_related("noted_by").order_by("tooth", "surface", "-noted_at", "-id"):
        latest.setdefault((row.tooth, row.surface), row)
    return latest


def has_child_teeth(patient):
    return patient.teeth.filter(tooth__gte=51).exists()


def _mesial_side(tooth):
    """Which side of the glyph is mesial (towards the midline): the right
    for quadrants 1 and 4 (drawn on the viewer's left), the left for 2 and 3."""
    return "right" if (tooth // 10) in (1, 4, 5, 8) else "left"


def layout(patient, child=False, latest=None):
    """Two rows of teeth, each tooth with its latest state per surface,
    ready for the template and the print page."""
    latest = chart(patient) if latest is None else latest
    rows = []
    for numbers in (CHILD_ROWS if child else ADULT_ROWS):
        row = []
        for n in numbers:
            whole = latest.get((n, ""))
            surfaces = {s: latest.get((n, s)) for s in ("M", "D", "B", "L", "O")}
            condition = whole.condition if whole else "sound"
            position = n % 10
            name = (CHILD_NAMES if child else NAMES).get(position, "")
            said = [f"{s}: {r.get_condition_display().lower()}" for s, r in surfaces.items() if r and r.condition != "sound"]
            label = f"Tooth {n}, {name}: " + (
                dict(ToothState.CONDITIONS)[condition].lower() + (", " + ", ".join(said) if said else "")
            )
            row.append({
                "n": n, "name": name, "condition": condition, "mesial": _mesial_side(n),
                # A surface with no row of its own shows the whole tooth's state.
                "surfaces": {s: (r.condition if r else condition) for s, r in surfaces.items()},
                "gone": condition in ("missing", "to_extract"),
                "label": label,
                "upper": n // 10 in (1, 2, 5, 6),
            })
        rows.append(row)
    return rows


def valid_tooth(n, child=False):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return None
    return n if n in (FDI_CHILD if child else FDI_ADULT) or n in FDI_ADULT or n in FDI_CHILD else None


def history_of(patient, tooth):
    return patient.teeth.filter(tooth=tooth).select_related("noted_by").order_by("-noted_at", "-id")
