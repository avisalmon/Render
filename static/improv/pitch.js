// improv: hearing the piano through a microphone. Pure DSP, no browser, runs under Node in the tests.
//
// A frame of audio goes in; up to four piano notes come out. The method is the plain one: a windowed FFT, the
// spectral peaks, and for each note from C2 to C7 a score for how well its harmonics (1x to 8x its pitch) line up
// with those peaks. The best note is taken, its peaks are damped so they are not counted twice, and the search runs
// again for the next. A tracker turns the frames into note on and note off events with a time, the same two
// events the MIDI keyboard gives, so the rest of improv does not know the difference.
//
// What it cannot do, said once: it hears from about C2 up, a chord reads best from C3 up, two notes a semitone
// apart can merge, a repeated note is only caught if it is struck again with a gap of loudness, and any other sound
// in the room (the band from the speakers, a voice) is heard as notes too.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovPitch = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const LOW = 36; // C2
  const HIGH = 96; // C7
  const HARMONICS = 8;
  const MAX_VOICES = 4;
  const SIZE = 4096;
  const WEIGHTS = [0, 1.0, 0.9, 0.8, 0.7, 0.55, 0.45, 0.35, 0.3];
  const ON_FRAMES = 2; // a note must be heard this many frames in a row
  const OFF_FRAMES = 3; // and gone this many before it ends
  const RMS_FLOOR = 0.004;
  const PEAKY = 18;
  // A note is first heard once about a third of its start is inside the window, so it began that far back.
  const ONSET_IN_WINDOW = 0.35;

  const hz = (midi) => 440 * Math.pow(2, (midi - 69) / 12);

  function fftInPlace(re, im, cos, sin, rev) {
    const n = re.length;
    for (let i = 0; i < n; i++) {
      const j = rev[i];
      if (j > i) {
        let t = re[i];
        re[i] = re[j];
        re[j] = t;
        t = im[i];
        im[i] = im[j];
        im[j] = t;
      }
    }
    for (let size = 2; size <= n; size <<= 1) {
      const half = size >> 1;
      const step = n / size;
      for (let start = 0; start < n; start += size) {
        for (let k = 0, w = 0; k < half; k++, w += step) {
          const a = start + k;
          const b = a + half;
          const tr = re[b] * cos[w] + im[b] * sin[w];
          const ti = im[b] * cos[w] - re[b] * sin[w];
          re[b] = re[a] - tr;
          im[b] = im[a] - ti;
          re[a] += tr;
          im[a] += ti;
        }
      }
    }
  }

  // Everything that depends only on the frame size and the sample rate, made once.
  function makeAnalyser(sampleRate, size) {
    const n = size || SIZE;
    const cos = new Float64Array(n / 2);
    const sin = new Float64Array(n / 2);
    for (let i = 0; i < n / 2; i++) {
      cos[i] = Math.cos((2 * Math.PI * i) / n);
      sin[i] = Math.sin((2 * Math.PI * i) / n);
    }
    const rev = new Uint32Array(n);
    const bits = Math.log2(n);
    for (let i = 0; i < n; i++) {
      let r = 0;
      for (let b = 0; b < bits; b++) if (i & (1 << b)) r |= 1 << (bits - 1 - b);
      rev[i] = r;
    }
    const win = new Float64Array(n);
    let sum = 0;
    for (let i = 0; i < n; i++) {
      win[i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / (n - 1));
      sum += win[i];
    }
    const re = new Float64Array(n);
    const im = new Float64Array(n);
    return { size: n, sampleRate, binHz: sampleRate / n, cos, sin, rev, win, sum, re, im };
  }

  function rmsOf(frame) {
    let s = 0;
    for (let i = 0; i < frame.length; i++) s += frame[i] * frame[i];
    return Math.sqrt(s / frame.length);
  }

  // The magnitude spectrum, scaled so a sine of amplitude 1 reads about 1.
  function spectrum(an, frame) {
    const n = an.size;
    for (let i = 0; i < n; i++) {
      an.re[i] = (frame[i] || 0) * an.win[i];
      an.im[i] = 0;
    }
    fftInPlace(an.re, an.im, an.cos, an.sin, an.rev);
    const mag = new Float64Array(n / 2);
    const scale = 2 / an.sum;
    for (let k = 0; k < n / 2; k++) mag[k] = Math.hypot(an.re[k], an.im[k]) * scale;
    return mag;
  }

  // Local maxima with their frequency and height sharpened by a parabola through three bins.
  function peaks(an, mag) {
    let top = 0;
    for (let k = 1; k < mag.length; k++) if (mag[k] > top) top = mag[k];
    const bar = Math.max(0.0015, top * 0.04);
    const out = [];
    const lowBin = Math.max(2, Math.floor(50 / an.binHz));
    const highBin = Math.min(mag.length - 2, Math.ceil(8500 / an.binHz));
    for (let k = lowBin; k <= highBin; k++) {
      const v = mag[k];
      if (v < bar || v < mag[k - 1] || v <= mag[k + 1]) continue;
      const a = Math.log(mag[k - 1] + 1e-12);
      const b = Math.log(v + 1e-12);
      const c = Math.log(mag[k + 1] + 1e-12);
      const denom = a - 2 * b + c;
      const shift = denom === 0 ? 0 : (0.5 * (a - c)) / denom;
      out.push({ f: (k + shift) * an.binHz, a: Math.exp(b - 0.25 * (a - c) * shift) });
    }
    return out;
  }

  const compress = (a) => Math.pow(a, 0.55);

  function toleranceHz(an, f) {
    return Math.max(1.4 * an.binHz, f * 0.012);
  }

  // The peak nearest h*f0 within the tolerance, or -1.
  function matchPeak(an, list, f) {
    const tol = toleranceHz(an, f);
    let best = -1;
    let bestGap = tol;
    for (let i = 0; i < list.length; i++) {
      const gap = Math.abs(list[i].f - f);
      if (gap <= bestGap && list[i].a > 0) {
        best = i;
        bestGap = gap;
      }
    }
    return best;
  }

  // A note has to show its own pitch (the 1x peak) as well as its overtones, or the octave below a chord
  // would be found from the chord's own overtones.
  function score(an, list, midi) {
    const f0 = hz(midi);
    let total = 0;
    let found = 0;
    let top = 0;
    let own = 0;
    const used = [];
    for (let h = 1; h <= HARMONICS; h++) {
      const f = f0 * h;
      if (f > 8500) break;
      const i = matchPeak(an, list, f);
      if (i < 0) continue;
      total += WEIGHTS[h] * compress(list[i].a);
      found += 1;
      top = Math.max(top, list[i].a);
      if (h === 1) own = list[i].a;
      used.push(i);
    }
    return { total, found, own, top, used };
  }

  // Sound with a pitch has a few tall peaks; hiss and rumble are flat. The tallest peak against the average.
  function peakiness(an, mag) {
    const from = Math.floor(80 / an.binHz);
    const to = Math.min(mag.length, Math.ceil(5000 / an.binHz));
    let sum = 0;
    let top = 0;
    for (let k = from; k < to; k++) {
      sum += mag[k];
      if (mag[k] > top) top = mag[k];
    }
    return top / (sum / (to - from) + 1e-12);
  }

  // Up to MAX_VOICES notes in this frame, strongest first: [{ midi, salience }].
  function analyse(an, frame, options) {
    const opts = options || {};
    const rms = rmsOf(frame);
    if (rms < (opts.floor || RMS_FLOOR)) return { rms, notes: [] };
    const mag = spectrum(an, frame);
    if (peakiness(an, mag) < PEAKY) return { rms, notes: [] };
    const list = peaks(an, mag);
    const notes = [];
    const taken = new Set();
    let first = 0;
    for (let voice = 0; voice < MAX_VOICES; voice++) {
      let best = null;
      for (let midi = LOW; midi <= HIGH; midi++) {
        if (taken.has(midi)) continue;
        const s = score(an, list, midi);
        if (s.found < 3 || s.own < 0.12 * s.top) continue;
        if (!best || s.total > best.total) best = { midi, total: s.total, used: s.used };
      }
      if (!best) break;
      if (voice === 0) first = best.total;
      else if (best.total < 0.34 * first) break;
      taken.add(best.midi);
      notes.push({ midi: best.midi, salience: best.total });
      for (const i of best.used) list[i].a *= 0.04;
    }
    return { rms, notes };
  }

  // Turns frames into note events. push() is called with each frame and the time (ms) its last sample was taken;
  // it returns the events found so far: { type, note, velocity, t }. The time of a note-on is estimated from the
  // first window it was heard in.
  function createTracker(sampleRate, options) {
    const opts = options || {};
    const an = makeAnalyser(sampleRate, opts.size || SIZE);
    const windowMs = (an.size / sampleRate) * 1000;
    const active = new Map(); // midi -> { quiet, since }
    const pending = new Map(); // midi -> { frames, firstAt, rms }
    let lastRms = 0;
    let riseGate = true;
    let recent = []; // the last few levels, to see a rise that is spread over several frames
    let settleUntil = 0;

    function push(frame, endMs) {
      const events = [];
      const read = analyse(an, frame, { floor: opts.floor });
      const heard = new Map(read.notes.map((n) => [n.midi, n]));
      const at = endMs - windowMs * ONSET_IN_WINDOW;
      let fresh = false;
      const lowest = recent.length ? Math.min(...recent) : 0;

      for (const midi of heard.keys()) {
        if (active.has(midi)) {
          active.get(midi).quiet = 0;
          continue;
        }
        const p = pending.get(midi) || { frames: 0, firstAt: at, rms: read.rms };
        p.frames += 1;
        if (p.frames >= ON_FRAMES) {
          pending.delete(midi);
          active.set(midi, { quiet: 0, since: p.firstAt });
          events.push({ type: "on", note: midi, velocity: velocityOf(p.rms), t: p.firstAt });
          fresh = true;
        } else {
          pending.set(midi, p);
        }
      }
      for (const midi of [...pending.keys()]) if (!heard.has(midi)) pending.delete(midi);

      // The same notes struck again: the level jumps while nothing new has joined.
      // The window is 90 ms long, so a strike raises its level over several frames: compare with the lowest
      // of the last three, and leave a note that has just joined to settle first.
      if (fresh) settleUntil = endMs + 150;
      const jump = read.rms > lowest * 1.6 && read.rms > 2.5 * (opts.floor || RMS_FLOOR);
      if (jump && riseGate && !fresh && endMs >= settleUntil && heard.size > 0 && pending.size === 0) {
        for (const midi of heard.keys()) {
          if (!active.has(midi)) continue;
          events.push({ type: "off", note: midi, velocity: 0, t: at - 1 });
          events.push({ type: "on", note: midi, velocity: velocityOf(read.rms), t: at });
          active.get(midi).since = at;
        }
        riseGate = false;
        settleUntil = endMs + 150;
      }
      if (read.rms < lastRms * 1.15) riseGate = true;

      for (const [midi, state] of [...active.entries()]) {
        if (heard.has(midi)) continue;
        state.quiet += 1;
        if (state.quiet >= OFF_FRAMES) {
          active.delete(midi);
          events.push({ type: "off", note: midi, velocity: 0, t: at });
        }
      }
      lastRms = read.rms;
      recent.push(read.rms);
      if (recent.length > 3) recent.shift();
      return events;
    }

    function reset() {
      active.clear();
      pending.clear();
      lastRms = 0;
      riseGate = true;
      recent = [];
      settleUntil = 0;
    }

    return { push, reset, windowMs, size: an.size, hopMs: opts.hopMs || (1024 / sampleRate) * 1000, held: () => [...active.keys()] };
  }

  function velocityOf(rms) {
    return Math.max(20, Math.min(120, Math.round(55 + 28 * Math.log10(Math.max(rms, 1e-6) / 0.05))));
  }

  return { LOW, HIGH, SIZE, RMS_FLOOR, hz, makeAnalyser, spectrum, peaks, analyse, createTracker, velocityOf };
});
