"""Builds improv/seed_data/pieces.json from the LilyPond sources in docs/improv/scores/.

The three Bach pieces are Mutopia Project files (public domain, typeset by Allen Garvin and Tobias Erbsland);
Ode to Joy is written out by hand in the same notation. This reads the small part of LilyPond those files use
(notes, chords, rests, ties, relative and absolute pitch, repeats, simultaneous voices, transpose) and ignores
the rest (ornaments, fermatas, graces, layout). Each piece is checked against its .mid file: every sounded pitch
at every time must be in the file, apart from the ornaments the .mid also leaves out.

Run: env/Scripts/python.exe docs/improv/build_pieces.py          writes improv/seed_data/pieces.json
     env/Scripts/python.exe docs/improv/build_pieces.py --check  also prints the comparison with the .mid files
"""

import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCORES = HERE / "scores"
OUT = HERE.parent.parent / "improv" / "seed_data" / "pieces.json"

LETTER = {"c": 0, "d": 1, "e": 2, "f": 3, "g": 4, "a": 5, "b": 6}
SEMI = [0, 2, 4, 5, 7, 9, 11]
NAMES = ["C", "D", "E", "F", "G", "A", "B"]
KEY_SIGNATURE = {
    "C": {},
    "G": {3: 1},
    "D": {3: 1, 0: 1},
}

TOKEN = re.compile(
    r"""
    (?P<string>"[^"]*")
  | (?P<voicesep>\\\\)
  | (?P<command>\\[A-Za-z]+)
  | (?P<open2><<) | (?P<close2>>>)
  | (?P<lt><) | (?P<gt>>)
  | (?P<lbrace>\{) | (?P<rbrace>\})
  | (?P<hash>\#\#[tf])
  | (?P<fraction>\d+/\d+)
  | (?P<note>[a-g](?:isis|eses|is|es)?[',]*[!?]?(?![A-Za-z]))
  | (?P<rest>[rRs](?![A-Za-z]))
  | (?P<number>\d+\.*)
  | (?P<ident>[A-Za-z][A-Za-z0-9_.]*)
  | (?P<punct>[|\[\]()~^_\-=!?.])
    """,
    re.X,
)


def tokenize(text):
    text = re.sub(r"%\{.*?%\}", " ", text, flags=re.S)
    text = re.sub(r"%[^\n]*", " ", text)
    out = []
    pos = 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        m = TOKEN.match(text, pos)
        if not m:
            raise ValueError(f"cannot read {text[pos:pos + 30]!r}")
        out.append((m.lastgroup, m.group()))
        pos = m.end()
    return out


def block(text, name):
    """The text of `name = <prefix> { ... }`: the prefix (such as \\relative c'') and the braced body."""
    m = re.search(rf"^{name}\s*=\s*", text, re.M)
    if not m:
        raise KeyError(name)
    start = m.end()
    brace = text.index("{", start)
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unbalanced braces")


class Event:
    def __init__(self, start, dur, pitches, voice=None, tie=False):
        self.start, self.dur, self.pitches, self.voice, self.tie = start, dur, pitches, voice, tie


class Parser:
    def __init__(self, text, ref_after="first"):
        self.toks = tokenize(text)
        self.i = 0
        self.rel = False
        self.ref = 28
        self.dur = 1.0
        self.ref_after = ref_after
        self.beats = None

    def peek(self, k=0):
        return self.toks[self.i + k] if self.i + k < len(self.toks) else (None, None)

    def take(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def duration(self):
        kind, val = self.peek()
        if kind == "number":
            self.take()
            digits = val.rstrip(".")
            dots = len(val) - len(digits)
            length = 4.0 / int(digits)
            add, half = length, length
            for _ in range(dots):
                half /= 2
                add += half
            self.dur = add
        return self.dur

    def pitch(self, token, ref):
        m = re.match(r"([a-g])(isis|eses|is|es)?([',]*)", token)
        letter = LETTER[m.group(1)]
        acc = {None: 0, "is": 1, "isis": 2, "es": -1, "eses": -2}[m.group(2)]
        marks = m.group(3).count("'") - m.group(3).count(",")
        if self.rel:
            octave = (ref - letter) // 7
            best = min(range(octave - 1, octave + 3), key=lambda o: abs(7 * o + letter - ref))
            step = 7 * best + letter + 7 * marks
        else:
            step = 7 * 3 + letter + 7 * marks
        return step, acc

    def skip_group(self):
        depth = 0
        while True:
            kind, _ = self.take()
            if kind == "lbrace":
                depth += 1
            elif kind == "rbrace":
                depth -= 1
                if depth == 0:
                    return

    def sequence(self, closer):
        events, t = [], 0.0
        while self.peek()[0] != closer:
            got, length = self.item()
            for e in got:
                e.start += t
            events.extend(got)
            t += length
        self.take()
        return events, t

    def simultaneous(self):
        start_ref = self.ref
        children, loose = [], []
        ends = []
        while self.peek()[0] != "close2":
            kind, _ = self.peek()
            if kind == "voicesep":
                self.take()
            elif kind == "lbrace":
                self.take()
                self.ref = start_ref
                children.append(self.sequence("rbrace"))
                ends.append(self.ref)
            else:
                loose.append(self.item())
        self.take()
        if loose:
            events, t = [], 0.0
            for got, length in loose:
                for e in got:
                    e.start += t
                events.extend(got)
                t += length
            children.append((events, t))
            ends.append(self.ref)
        if len(children) > 1:
            for index, (events, _) in enumerate(children):
                for e in events:
                    if e.voice is None:
                        e.voice = index + 1
        if ends:
            self.ref = ends[0] if self.ref_after == "first" else ends[-1]
        events = [e for ev, _ in children for e in ev]
        return events, max((length for _, length in children), default=0.0)

    def item(self):
        kind, val = self.take()
        if kind == "lbrace":
            return self.sequence("rbrace")
        if kind == "open2":
            return self.simultaneous()
        if kind == "note":
            step, acc = self.pitch(val, self.ref)
            if self.rel:
                self.ref = step
            length = self.duration()
            tie = self.peek() == ("punct", "~")
            if tie:
                self.take()
            return [Event(0.0, length, [(step, acc)], tie=tie)], length
        if kind == "lt":
            pitches, prev, first = [], self.ref, None
            while self.peek()[0] != "gt":
                _, tok = self.take()
                step, acc = self.pitch(tok, prev)
                prev = step
                first = step if first is None else first
                pitches.append((step, acc))
            self.take()
            if self.rel:
                self.ref = first
            length = self.duration()
            tie = self.peek() == ("punct", "~")
            if tie:
                self.take()
            return [Event(0.0, length, pitches, tie=tie)], length
        if kind == "rest":
            length = self.duration()
            return [], length if val != "R" else length
        if kind == "command":
            return self.command(val)
        return [], 0.0

    def command(self, name):
        if name == "\\relative":
            _, tok = self.take()
            was, was_ref = self.rel, self.ref
            self.rel = True
            marks = tok.count("'") - tok.count(",")
            self.ref = 7 * (3 + marks) + LETTER[tok[0]]
            got = self.item()
            self.rel = was
            return got
        if name == "\\transpose":
            a, b = self.take()[1], self.take()[1]
            was = self.rel
            self.rel = False
            sa, sb = self.pitch(a, 0)[0], self.pitch(b, 0)[0]
            self.rel = was
            events, length = self.item()
            for e in events:
                e.pitches = [(s + (sb - sa), acc) for s, acc in e.pitches]
            return events, length
        if name == "\\repeat":
            self.take()
            self.take()
            return self.item()
        if name in ("\\grace", "\\acciaccatura", "\\appoggiatura"):
            self.item()
            return [], 0.0
        if name == "\\context":
            self.take()
            if self.peek() == ("punct", "="):
                self.take()
                self.take()
            return self.item()
        if name in ("\\markup", "\\markuplines"):
            if self.peek()[0] == "lbrace":
                self.skip_group()
            else:
                self.take()
            return [], 0.0
        if name in ("\\clef", "\\bar"):
            self.take()
        elif name == "\\time":
            _, frac = self.take()
            self.beats = int(frac.split("/")[0])
        elif name == "\\key":
            self.take()
            self.take()
        elif name == "\\tempo":
            while self.peek()[0] in ("number", "string") or self.peek() == ("punct", "="):
                self.take()
        elif name == "\\set":
            self.take()
            self.take()
            self.take()
        return [], 0.0


def collect(text, name, hand, ref_after="first"):
    parser = Parser(block(text, name), ref_after)
    events, length = parser.item()
    return parser.beats, merge_ties(events), length


def merge_ties(events):
    """Fold a tied note into the one before it: the first keeps `dur`, and `ties` lists the rest."""
    events = sorted(events, key=lambda e: (e.start, e.voice or 1))
    out = []
    open_tie = {}
    for e in events:
        key = (tuple(e.pitches), e.voice or 1)
        head = open_tie.get(key)
        if head is not None and abs(head["end"] - e.start) < 1e-6:
            head["event"].ties.append([e.start, e.dur])
            head["end"] = e.start + e.dur
            if not e.tie:
                del open_tie[key]
            continue
        e.ties = []
        out.append(e)
        if e.tie:
            open_tie[key] = {"event": e, "end": e.start + e.dur}
    return out


def midi_of(step, acc):
    return SEMI[step % 7] + acc + 12 * (step // 7 + 1)


def name_of(step, acc):
    return NAMES[step % 7] + {-1: "b", 0: "", 1: "#"}.get(acc, "") + str(step // 7)


def build_notes(rh, lh, beats, key, bars):
    signature = KEY_SIGNATURE[key]
    notes = []
    for hand, events in (("R", rh), ("L", lh)):
        for e in events:
            for step, acc in e.pitches:
                total = e.dur + sum(d for _, d in e.ties)
                bar = int(e.start // beats) + 1
                note = {
                    "hand": hand,
                    "step": step,
                    "acc": acc,
                    "midi": midi_of(step, acc),
                    "beat": round(e.start, 4),
                    "dur": round(e.dur, 4),
                    "bar": bar,
                    "voice": e.voice or 1,
                }
                if e.ties:
                    note["ties"] = [[round(s, 4), round(d, 4)] for s, d in e.ties]
                    note["hold"] = round(total, 4)
                if bar <= bars:
                    notes.append(note)
    notes.sort(key=lambda n: (n["beat"], n["hand"] != "R", n["voice"], -n["step"]))
    shown = {}
    for n in notes:
        k = (n["hand"], n["bar"], n["step"])
        state = shown.get(k, signature.get(n["step"] % 7, 0))
        if n["acc"] != state:
            n["shown"] = {1: "#", -1: "b", 0: "n"}[n["acc"]]
        shown[k] = n["acc"]
    return notes


def read_midi(path):
    data = path.read_bytes()
    pos = 14
    division = struct.unpack(">H", data[12:14])[0]
    sounded = []
    while pos < len(data):
        assert data[pos : pos + 4] == b"MTrk"
        size = struct.unpack(">I", data[pos + 4 : pos + 8])[0]
        pos += 8
        end = pos + size
        tick, status = 0, 0
        while pos < end:
            delta = 0
            while True:
                b = data[pos]
                pos += 1
                delta = (delta << 7) | (b & 0x7F)
                if not b & 0x80:
                    break
            tick += delta
            b = data[pos]
            if b == 0xFF:
                length = data[pos + 2]
                pos += 3 + length
                continue
            if b >= 0x80:
                status = b
                pos += 1
            kind = status & 0xF0
            if kind in (0x90, 0x80, 0xA0, 0xB0, 0xE0):
                a, v = data[pos], data[pos + 1]
                pos += 2
                if kind == 0x90 and v:
                    sounded.append((tick / division, a))
            elif kind in (0xC0, 0xD0):
                pos += 1
            else:
                pos += 1
    return sounded


PIECES = [
    dict(
        slug="ode-to-joy", title="Ode to Joy", composer="Ludwig van Beethoven", catalog="Symphony No. 9, theme",
        level=1, order=1, key="C", file="ode-to-joy.ly", rh="rh", lh="lh", mid=None,
        bars=16, phrase=4, tempo_bpm=92, slow_bpm=60,
        blurb="The tune everyone knows, one step at a time: it hardly leaves five notes.",
        teacher_note="The right hand is Beethoven's theme. The left hand is a simple two-note bass written for improv, not Beethoven's. The right hand sits in the five-finger position C to G, with one drop to the low G in bar 12.",
        source="Theme: Beethoven, 1824, public domain. Written out for improv.",
    ),
    dict(
        slug="minuet-in-g", title="Minuet in G", composer="Johann Sebastian Bach", catalog="BWV Anh. 114",
        level=1, order=2, key="G", file="anna-magdalena-04.ly", rh="voiceone", lh="voicetwo", mid="anna-magdalena-04.mid",
        bars=16, phrase=4, tempo_bpm=108, slow_bpm=66,
        blurb="From the Notebook for Anna Magdalena Bach. Eight notes against a steady left hand, in three beats to the bar.",
        teacher_note="This is the first half only (bars 1 to 16, the repeat is left out). The little ornaments (mordents and the grace note in bar 8) are left out so the line is plain.",
        source="Mutopia Project, typeset by Allen Garvin, public domain.",
    ),
    dict(
        slug="musette-in-d", title="Musette in D", composer="Johann Sebastian Bach", catalog="BWV Anh. 126",
        level=1, order=3, key="D", file="anna-magdalena-22.ly", rh="voiceone", lh="voicetwo", mid="anna-magdalena-22.mid",
        bars=8, phrase=2, tempo_bpm=100, slow_bpm=64,
        blurb="A little bagpipe dance: a bouncing left hand and a tune that runs in sixteenth notes.",
        teacher_note="This is the first eight bars only (the repeat and the second half are left out). The pause (fermata) at the end is left out.",
        source="Mutopia Project, typeset by Allen Garvin, public domain.",
    ),
    dict(
        slug="prelude-in-c", title="Prelude in C", composer="Johann Sebastian Bach", catalog="BWV 846, Well-Tempered Clavier I",
        level=1, order=4, key="C", file="wtk1-prelude1.ly", rh="right", lh="left", mid="wtk1-prelude1.mid",
        bars=35, phrase=4, tempo_bpm=66, slow_bpm=46,
        blurb="Broken chords that rise and fall. Each bar is one chord, played twice; learn the chords and the piece plays itself.",
        teacher_note="All 35 bars. The pause on the last chord and the arpeggio sign are left out: play the last chord together. In bars 33 and 34 the right hand dips below the treble staff, which is how Bach wrote it.",
        source="Mutopia Project, typeset by Tobias Erbsland, public domain.",
    ),
]


def phrases_of(piece, notes):
    out = []
    first, order = 1, 1
    while first <= piece["bars"]:
        last = min(first + piece["phrase"] - 1, piece["bars"])
        starts = {}
        for n in notes:
            if first <= n["bar"] <= last and (n["hand"] not in starts or (n["beat"], n["step"] if n["hand"] == "L" else -n["step"]) < starts[n["hand"]][0]):
                starts[n["hand"]] = ((n["beat"], n["step"] if n["hand"] == "L" else -n["step"]), name_of(n["step"], n["acc"]))
        hint = f"Right hand starts on {starts['R'][1]}." if "R" in starts else ""
        if "L" in starts:
            hint += f" Left hand starts on {starts['L'][1]}."
        out.append({
            "order": order,
            "first_bar": first,
            "last_bar": last,
            "title": f"Bar {first}" if first == last else f"Bars {first} to {last}",
            "hint": hint.strip(),
        })
        first, order = last + 1, order + 1
    return out


def build(check=False):
    pieces = []
    for p in PIECES:
        text = (SCORES / p["file"]).read_text(encoding="utf-8")
        ref_after = p.get("ref_after", "first")
        beats_r, rh, _ = collect(text, p["rh"], "R", ref_after)
        beats_l, lh, _ = collect(text, p["lh"], "L", ref_after)
        beats = beats_r or beats_l
        notes = build_notes(rh, lh, beats, p["key"], p["bars"])
        row = {k: p[k] for k in ("slug", "title", "composer", "catalog", "level", "order", "key", "bars", "tempo_bpm", "slow_bpm", "blurb", "teacher_note", "source")}
        row["beats_per_bar"] = beats
        row["notes"] = notes
        row["phrases"] = phrases_of(p, notes)
        pieces.append(row)
        if check and p["mid"]:
            compare(p, notes, read_midi(SCORES / p["mid"]), beats)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(pieces, indent=1) + "\n", encoding="utf-8")
    return pieces


def compare(p, notes, sounded, beats):
    """Notes in the file for the bars we kept, against the .mid (which plays repeats, so only the first pass counts)."""
    limit = p["bars"] * beats
    mine = sorted({(round(n["beat"], 3), n["midi"]) for n in notes})
    theirs = sorted({(round(t, 3), m) for t, m in sounded if t < limit})
    only_mine = [x for x in mine if x not in set(theirs)]
    only_theirs = [x for x in theirs if x not in set(mine)]
    print(f"{p['slug']}: {len(mine)} mine, {len(theirs)} in the midi, only mine {only_mine[:12]}, only midi {only_theirs[:12]}")


if __name__ == "__main__":
    for row in build(check="--check" in sys.argv):
        counts = {h: sum(1 for n in row["notes"] if n["hand"] == h) for h in "RL"}
        print(row["slug"], row["bars"], "bars", counts, len(row["phrases"]), "phrases")
