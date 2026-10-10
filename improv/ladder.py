"""The teaching ladder of a repertoire piece: the rungs a player climbs, in order (spec chapter 12).

Pure: it knows phrases as (first_bar, last_bar) pairs and nothing else, so the model, the derived read and the
tests all take the same rungs from one place. Bars are counted from 1, as printed.

For n phrases the ladder is, in the order a teacher would set it:
  p1-R-slow  p1-L-slow  p1-B-slow  p1-B-tempo     each phrase: right hand, left hand, both slow, both at tempo
  p2-...     j1-2                                  then the join of the two phrases at tempo
  ...
  whole-B-slow  whole-B-tempo  perform             the whole piece, then a run with a higher line
That is 4n + (n - 1) + 3 rungs. Nothing is locked: the path pointer is the first rung not yet passed.
"""

DRILL = "drill"
PASS_SCORE = 80
PERFORM_SCORE = 90
HANDS = ("R", "L", "B")


def _rung(key, kind, hands, first_bar, last_bar, tempo, line=PASS_SCORE, phrase=None):
    return {
        "key": key, "kind": kind, "hands": hands, "first_bar": first_bar, "last_bar": last_bar,
        "tempo": tempo, "line": line, "phrase": phrase,
    }  # fmt: skip


def rungs(phrases):
    """The ladder for a piece whose phrases are [(first_bar, last_bar), ...] in order."""
    out = []
    for i, (first, last) in enumerate(phrases, start=1):
        out.append(_rung(f"p{i}-R-slow", "phrase", "R", first, last, "slow", phrase=i))
        out.append(_rung(f"p{i}-L-slow", "phrase", "L", first, last, "slow", phrase=i))
        out.append(_rung(f"p{i}-B-slow", "phrase", "B", first, last, "slow", phrase=i))
        out.append(_rung(f"p{i}-B-tempo", "phrase", "B", first, last, "tempo", phrase=i))
        if i > 1:
            out.append(_rung(f"j{i - 1}-{i}", "join", "B", phrases[i - 2][0], last, "tempo", phrase=i))
    if phrases:
        first, last = phrases[0][0], phrases[-1][1]
        out.append(_rung("whole-B-slow", "whole", "B", first, last, "slow"))
        out.append(_rung("whole-B-tempo", "whole", "B", first, last, "tempo"))
        out.append(_rung("perform", "perform", "B", first, last, "tempo", line=PERFORM_SCORE))
    return out


def find(phrases, key):
    for rung in rungs(phrases):
        if rung["key"] == key:
            return rung
    return None


def required_bpm(rung, slow_bpm, tempo_bpm):
    return slow_bpm if rung["tempo"] == "slow" else tempo_bpm


def next_rung(rung_list, passed_keys):
    """The first rung not yet passed, or None when the whole ladder is climbed."""
    for rung in rung_list:
        if rung["key"] not in passed_keys:
            return rung
    return None
