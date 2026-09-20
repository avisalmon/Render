"""Generate SPR-Z.6's bundled game sounds (spec §9.1): tiny, procedural,
committed — no external audio library, no licensing question.

    .\\env\\Scripts\\python.exe memz\\seed_assets\\make_sounds.py

Two files: the last-5-seconds countdown tick, and the reveal's drumroll
swell. Both are pure Python sine synthesis via the standard library's
`wave` module — no numpy, no external assets. Deterministic, so
re-running produces the same bytes.
"""

import math
import os
import struct
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "static" / "memz" / "sound"
RATE = 22050


def _write(path, samples):
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", max(-32000, min(32000, int(s)))) for s in samples))


def _tone(freq, dur, amp=0.5, fade=0.01):
    n = int(RATE * dur)
    out = []
    for i in range(n):
        t = i / RATE
        env = min(1.0, t / fade) if t < fade else max(0.0, (dur - t) / fade) if t > dur - fade else 1.0
        out.append(amp * 32000 * env * math.sin(2 * math.pi * freq * t))
    return out


def _sweep(f0, f1, dur, amp=0.45, fade=0.03):
    n = int(RATE * dur)
    out = []
    for i in range(n):
        t = i / RATE
        env = min(1.0, t / fade) if t < fade else max(0.0, (dur - t) / fade) if t > dur - fade else 1.0
        phase = 2 * math.pi * (f0 * t + (f1 - f0) * t * t / (2 * dur))
        out.append(amp * 32000 * env * math.sin(phase))
    return out


def _mix(*parts):
    """Overlay equal-length-or-shorter sample lists, clipped."""
    n = max(len(p) for p in parts)
    out = [0.0] * n
    for p in parts:
        for i, s in enumerate(p):
            out[i] += s
    return out


def _seq(*parts):
    """Play sample lists one after another."""
    out = []
    for p in parts:
        out.extend(p)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    # The last-5-seconds tick (Rule 4.4.4): short, high, unmistakable.
    _write(OUT / "tick.wav", _tone(1500, 0.08, amp=0.5, fade=0.005))
    # The reveal's drumroll (spec §9.1): a quick rising swell.
    _write(OUT / "drumroll.wav", _sweep(220, 660, 0.5, amp=0.4, fade=0.03))

    # SPR-W.1, three more, same recipe (spec Rule 4.5.6, §9.1):
    # A verdict landing: a soft, quick "pop" -- a short downward chirp with
    # a bright top, over before the thumb has lifted.
    _write(OUT / "pop.wav", _sweep(900, 420, 0.09, amp=0.45, fade=0.008))
    # A new meme arriving on screen: two rising notes, a small fanfare of
    # its own so every slot has a beginning you can hear across the room.
    _write(OUT / "reveal.wav", _seq(_tone(523, 0.09, amp=0.35, fade=0.01), _tone(784, 0.16, amp=0.4, fade=0.02)))
    # The podium: a major triad arpeggio that lands on the octave. Long
    # enough to be an event, short enough not to be a jingle.
    _write(OUT / "fanfare.wav", _seq(
        _tone(523, 0.12, amp=0.4, fade=0.01),
        _tone(659, 0.12, amp=0.4, fade=0.01),
        _tone(784, 0.12, amp=0.4, fade=0.01),
        _mix(_tone(1046, 0.45, amp=0.35, fade=0.03), _tone(784, 0.45, amp=0.2, fade=0.03), _tone(523, 0.45, amp=0.15, fade=0.03)),
    ))
    print(f"wrote 5 sounds to {OUT}")


if __name__ == "__main__":
    main()
