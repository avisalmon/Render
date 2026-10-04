"""The shape of a groove, checked in one place (data model, section 2, `Style`).

A groove is three JSON values the band engine reads whole. Nothing queries a
single hit of them, so they stay columns; but the engine can only play what it
understands, so a groove that does not match this shape is refused when it is
saved, by the model, the admin and the API alike, and never when it is played.

drums   {instrument: [one strength 0..1 per sixteenth of the bar]}
        4/4 has 16 steps, 3/4 has 12. Swing is applied to the off-beat steps by the
        band, not written into the grid.
bass    {"rule": one of BASS_RULES, "range": [lowest MIDI note, highest MIDI note]}
        The range is inside 24..72 and spans at least BASS_MIN_SPAN (12) semitones.
comp    {"rhythm": [[start step, length in steps], ...], "voicing": one of VOICINGS,
         "register": [lowest MIDI note, highest MIDI note]}
        The register is inside 36..96 and spans at least COMP_MIN_SPAN (19) semitones.
"""

import re

DRUM_INSTRUMENTS = ("kick", "snare", "rim", "hat", "openhat", "ride", "shaker", "clave")
BASS_RULES = ("walking", "two_feel", "root_fifth", "eighths", "bossa", "boogie")
VOICINGS = ("shell", "triad", "seventh")
BASS_LIMITS = (24, 72)
COMP_LIMITS = (36, 96)
# The engine has to find every pitch class inside a range, and a voicing inside a register.
BASS_MIN_SPAN = 12
COMP_MIN_SPAN = 19
SIGNATURE = re.compile(r"^([2-9]|1[0-2])/4$")


def beats_in(time_signature):
    """Beats in a bar for a signature the band can play, or None."""
    match = SIGNATURE.match(time_signature or "")
    return int(match.group(1)) if match else None


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _range(value, limits, what, min_span):
    if not (isinstance(value, list) and len(value) == 2 and all(isinstance(v, int) and not isinstance(v, bool) for v in value)):
        return f"{what} has to be two whole MIDI notes: [lowest, highest]."
    low, high = value
    if not limits[0] <= low < high <= limits[1]:
        return f"{what} has to run from low to high inside {limits[0]} to {limits[1]}."
    if high - low < min_span:
        return f"{what} has to span at least {min_span} semitones so the band can reach every note."
    return None


def check_drums(drums, steps):
    if not isinstance(drums, dict) or not drums:
        return "Drums has to be an object with at least one instrument."
    for name, grid in drums.items():
        if name not in DRUM_INSTRUMENTS:
            return f'"{name}" is not a drum voice the band has. Use: {", ".join(DRUM_INSTRUMENTS)}.'
        if not isinstance(grid, list) or len(grid) != steps:
            return f'"{name}" needs exactly {steps} steps for this bar, one per sixteenth.'
        if not all(_is_number(v) and 0 <= v <= 1 for v in grid):
            return f'"{name}" steps have to be numbers from 0 (silent) to 1 (hard).'
    return None


def check_bass(bass):
    if not isinstance(bass, dict):
        return "Bass has to be an object with a rule and a range."
    if bass.get("rule") not in BASS_RULES:
        return f"Bass needs a rule, one of: {', '.join(BASS_RULES)}."
    return _range(bass.get("range"), BASS_LIMITS, "Bass range", BASS_MIN_SPAN)


def check_comp(comp, steps):
    if not isinstance(comp, dict):
        return "Comp has to be an object with a rhythm, a voicing and a register."
    if comp.get("voicing") not in VOICINGS:
        return f"Comp needs a voicing, one of: {', '.join(VOICINGS)}."
    rhythm = comp.get("rhythm")
    if not isinstance(rhythm, list) or not rhythm:
        return "Comp needs a rhythm: a list of [start step, length] pairs, at least one."
    cursor = 0
    for hit in rhythm:
        if not (isinstance(hit, list) and len(hit) == 2 and all(isinstance(v, int) and not isinstance(v, bool) for v in hit)):
            return "Each comp hit is a pair of whole numbers: [start step, length in steps]."
        start, length = hit
        if length < 1 or start < cursor or start + length > steps:
            return f"Comp hits have to be in order, not overlap, and stay inside the {steps}-step bar."
        cursor = start + length
    return _range(comp.get("register"), COMP_LIMITS, "Comp register", COMP_MIN_SPAN)


def check_groove(time_signature, drums, bass, comp):
    """Return {field: message} for everything wrong, empty when the groove is playable."""
    problems = {}
    beats = beats_in(time_signature)
    if beats is None:
        problems["time_signature"] = "The band plays 2/4 to 12/4. Write it like 4/4 or 3/4."
        return problems
    steps = beats * 4
    for field, message in (
        ("drums", check_drums(drums, steps)),
        ("bass", check_bass(bass)),
        ("comp", check_comp(comp, steps)),
    ):
        if message:
            problems[field] = message
    return problems
