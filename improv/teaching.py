"""The shape of what a lesson teaches with: phrases and the parameters of an exercise's scoring.

Both are JSON columns read whole by the page, so Django cannot check them for us. These two
functions say what is wrong in a sentence, or return None. The scoring check mirrors what the
judge (static/improv/judge.js) reads for each kind, because a parameter the judge would throw
on is an exercise nobody can ever pass, and that is better found when the row is saved than
when a player is stuck on it.
"""

from django.db.models import Case, IntegerField, Value, When

MOST_NOTES = 200

# The order a player meets the tracks in, which is not the alphabet.
TRACK_ORDER = [
    "chord_tones",
    "guide_tones",
    "scales_modes",
    "approach_notes",
    "rhythm_motifs",
    "call_and_response",
    "voicings_comping",
]

# What the judge scores. comping_voicings is a kind the data model names and version 1 does not score.
SCORED_KINDS = [
    "free_play",
    "scale_only",
    "chord_tones_on_beats",
    "guide_tones",
    "approach_notes",
    "rhythm_motif",
    "call_and_response",
]
PARAMS_BY_KIND = {
    "free_play": (),
    "scale_only": (),
    "chord_tones_on_beats": ("beats",),
    "guide_tones": ("step",),
    "approach_notes": ("beats",),
    "rhythm_motif": ("pattern",),
    "call_and_response": ("phrase", "answerBar", "exact"),
}


def track_rank():
    """An expression that sorts lessons by TRACK_ORDER, for order_by."""
    return Case(*[When(track=slug, then=Value(i)) for i, slug in enumerate(TRACK_ORDER)], default=Value(len(TRACK_ORDER)), output_field=IntegerField())


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _whole(value):
    return isinstance(value, int) and not isinstance(value, bool)


def check_notes(notes, length_beats):
    """None when `notes` is a list of {midi, beat, length, velocity} inside the phrase."""
    if not isinstance(notes, list):
        return "notes is a list of {midi, beat, length, velocity}."
    if not notes:
        return "A phrase needs at least one note."
    if len(notes) > MOST_NOTES:
        return f"A phrase holds at most {MOST_NOTES} notes."
    for i, n in enumerate(notes):
        if not isinstance(n, dict):
            return f"note {i} is not {{midi, beat, length, velocity}}."
        if not _whole(n.get("midi")) or not 0 <= n["midi"] <= 127:
            return f"note {i}: midi has to be a whole number from 0 to 127."
        if not _number(n.get("beat")) or n["beat"] < 0:
            return f"note {i}: beat has to be a number from 0."
        if length_beats is not None and n["beat"] >= float(length_beats):
            return f"note {i}: beat {n['beat']} is not inside the {float(length_beats):g}-beat phrase."
        if not _number(n.get("length")) or n["length"] <= 0:
            return f"note {i}: length has to be above 0."
        if not _whole(n.get("velocity")) or not 1 <= n["velocity"] <= 127:
            return f"note {i}: velocity has to be a whole number from 1 to 127."
    return None


def _beat_list(name, value, beats_per_bar):
    if not isinstance(value, list) or not value:
        return f"{name} has to be a list with at least one beat number."
    if not all(_whole(b) and 1 <= b <= beats_per_bar for b in value):
        return f"{name} has to be whole beat numbers from 1 to {beats_per_bar}: each is a beat of the bar."
    return None


def check_scoring(kind, params, beats_per_bar=4, bars=4):
    """None when `params` is something the judge can score `kind` with."""
    if kind == "comping_voicings":
        return "comping_voicings is not scored in this version; it arrives in a later one."
    if kind not in PARAMS_BY_KIND:
        return f"{kind!r} is not a scoring kind."
    if not isinstance(params, dict):
        return "scoring_params has to be an object."
    for key in params:
        if key not in PARAMS_BY_KIND[kind]:
            takes = ", ".join(PARAMS_BY_KIND[kind]) or "no parameters"
            return f"{kind} does not take {key!r}; it takes {takes}."

    if kind in ("chord_tones_on_beats", "approach_notes") and "beats" in params:
        return _beat_list("beats", params["beats"], beats_per_bar)

    if kind == "guide_tones" and "step" in params:
        step = params["step"]
        if not _number(step) or step <= 0 or step > 12:
            return "step has to be a number of semitones above 0, up to 12."

    if kind == "rhythm_motif":
        pattern = params.get("pattern")
        if not isinstance(pattern, list) or not pattern:
            return "rhythm_motif needs a pattern: a list of beats inside the bar, from 0."
        if not all(_number(p) and 0 <= p < beats_per_bar for p in pattern):
            return f"pattern holds beats from 0 up to but not including {beats_per_bar}."

    if kind == "call_and_response":
        phrase = params.get("phrase")
        if not isinstance(phrase, list) or not phrase:
            return "call_and_response needs a phrase: a list of [beat, note]."
        for p in phrase:
            if not (isinstance(p, list) and len(p) == 2 and _number(p[0]) and 0 <= p[0] < beats_per_bar and _whole(p[1]) and 0 <= p[1] <= 127):
                return f"phrase is [beat, note] pairs, the beat inside one bar and the note a midi number: {p!r} is not."
        if "answerBar" in params:
            answer = params["answerBar"]
            if not _whole(answer) or not 1 <= answer < bars:
                return f"answerBar is the bar the answer is played in, counted from 0, after the call: from 1 to {bars - 1}."
        if "exact" in params and not isinstance(params["exact"], bool):
            return "exact is true or false."
    return None
