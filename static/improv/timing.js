// improv: timing maths. Pure: no clock, no browser. Run under Node by the tests.
//
// Two clocks are involved. MIDI messages carry a timestamp on the performance.now()
// clock. The band and the click run on the AudioContext clock. To compare a note
// with the click it was meant for, both are put on the performance clock, and the
// click is placed where it is HEARD (output latency included), not where it was
// scheduled, because that is what the player is listening to.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovTiming = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const MIN_BPM = 20;
  const MAX_BPM = 300;

  // `outputTimestamp` is what AudioContext.getOutputTimestamp() returns: the
  // audio-clock time of the sample leaving the speaker at that performance time.
  function makeAnchor(outputTimestamp) {
    const t = outputTimestamp;
    const ok =
      t &&
      Number.isFinite(t.contextTime) &&
      Number.isFinite(t.performanceTime) &&
      t.performanceTime > 0;
    if (!ok) throw new Error("No usable output timestamp yet (the audio context has not started producing sound)");
    return { audio: t.contextTime, perf: t.performanceTime };
  }

  // Performance-clock time (ms) at which a click scheduled at `audioTime` (s) is heard.
  function heardAt(anchor, audioTime) {
    return anchor.perf + (audioTime - anchor.audio) * 1000;
  }

  // The audio-clock time (s) that was heard at performance time `perfMs`: the inverse, for
  // putting a MIDI note on the band's own clock.
  function audioAt(anchor, perfMs) {
    return anchor.audio + (perfMs - anchor.perf) / 1000;
  }

  function beatTimes(startAudio, bpm, count) {
    if (!(bpm >= MIN_BPM && bpm <= MAX_BPM)) throw new Error(`Tempo must be ${MIN_BPM} to ${MAX_BPM} bpm`);
    const gap = 60 / bpm;
    const out = [];
    for (let i = 0; i < count; i++) out.push(startAudio + i * gap);
    return out;
  }

  // The next `count` beats after the ones already scheduled (audio-clock seconds).
  // Only clicks within the look-ahead are scheduled, so a note played early for the
  // next beat would otherwise be matched to the previous click and read very late.
  function upcoming(nextAudio, gapSeconds, count) {
    return beatTimes(nextAudio, 60 / gapSeconds, count);
  }

  // The grid a note is judged against: each gap between clicks cut into `parts`
  // equal pieces (2 = eighth notes). Works in any unit, as long as it is the same one.
  function subdivide(clicks, parts) {
    if (!Number.isInteger(parts) || parts < 1 || parts > 8) throw new Error("Division must be a whole number from 1 to 8");
    const out = [];
    for (let i = 0; i < clicks.length; i++) {
      out.push(clicks[i]);
      if (i < clicks.length - 1) {
        const step = (clicks[i + 1] - clicks[i]) / parts;
        for (let p = 1; p < parts; p++) out.push(clicks[i] + p * step);
      }
    }
    return out;
  }

  // Gaps between consecutive notes (ms). Their spread says how steady the playing
  // and the MIDI path are, independent of where the click is.
  function intervals(timesMs) {
    const out = [];
    for (let i = 1; i < timesMs.length; i++) out.push(timesMs[i] - timesMs[i - 1]);
    return out;
  }

  // The click a note was most likely aimed at, and how far off it landed (ms, positive = late).
  function nearestClick(noteMs, clickMs) {
    if (!clickMs.length) return null;
    let best = 0;
    for (let i = 1; i < clickMs.length; i++) {
      if (Math.abs(noteMs - clickMs[i]) < Math.abs(noteMs - clickMs[best])) best = i;
    }
    return { index: best, offsetMs: noteMs - clickMs[best] };
  }

  function stats(values) {
    const n = values.length;
    if (!n) return { n: 0, mean: null, sd: null, min: null, max: null };
    const mean = values.reduce((a, b) => a + b, 0) / n;
    const sd = n > 1 ? Math.sqrt(values.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1)) : null;
    return { n, mean, sd, min: Math.min(...values), max: Math.max(...values) };
  }

  // Whether one stored offset can stand for this player's setup. The thresholds are
  // a first guess to be tuned from the numbers the spike produces on a real piano.
  function verdict(s) {
    if (s.n < 5) return { usable: false, reason: `only ${s.n} notes, play at least 5 with the click` };
    if (s.sd > 30) return { usable: false, reason: "too scattered for one offset to describe it (spread over 30 ms)" };
    return { usable: true, reason: "steady enough for one offset" };
  }

  return { makeAnchor, heardAt, audioAt, beatTimes, upcoming, subdivide, intervals, nearestClick, stats, verdict, MIN_BPM, MAX_BPM };
});
