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


def main():
    os.makedirs(OUT, exist_ok=True)
    # The last-5-seconds tick (Rule 4.4.4): short, high, unmistakable.
    _write(OUT / "tick.wav", _tone(1500, 0.08, amp=0.5, fade=0.005))
    # The reveal's drumroll (spec §9.1): a quick rising swell.
    _write(OUT / "drumroll.wav", _sweep(220, 660, 0.5, amp=0.4, fade=0.03))
    print(f"wrote {OUT / 'tick.wav'} and {OUT / 'drumroll.wav'}")


if __name__ == "__main__":
    main()
