// improv: calibration. The app hears the piano over MIDI and the click leaves through the
// laptop, each with its own delay, so "on the beat" means nothing until one number is
// measured for this player's setup. Pure: no clock, no browser, runs under Node.
//
// The maths belongs to timing.js, which the spike proved against a real piano. What is here
// is the calibration's own rules: which taps count, when a run is steady
// enough for one number to stand for it, and what the player is told about the result.
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./timing.js"));
  } else {
    root.ImprovCalibrate = factory(root.ImprovTiming);
  }
})(typeof self !== "undefined" ? self : this, function (Timing) {
  const TAPS_WANTED = 16;
  const COUNT_IN_CLICKS = 4;
  const DEFAULT_BPM = 80;
  const OFFSET_LIMIT_MS = 500; // what Player.latency_offset_ms will hold
  const LEAST_TAPS = 8;
  const MOST_SPREAD_MS = 30;
  const SLOW_OUTPUT_S = 0.1;

  function clickPlan(bpm) {
    const beats = Timing.beatTimes(0, bpm || DEFAULT_BPM, 2); // throws if the tempo is impossible
    return {
      gapSeconds: beats[1] - beats[0],
      countIn: COUNT_IN_CLICKS,
      taps: TAPS_WANTED,
      count: COUNT_IN_CLICKS + TAPS_WANTED + 1,
    };
  }

  // Each tap against the click it was nearest to. Where two taps land on the same click the
  // nearer one is the tap and the other is a bounce, so only one counts per click.
  //
  // There is deliberately no rule throwing out a tap for being far from the click. A tap is
  // always within half a gap of its nearest click, so such a rule could only ever fire on a
  // setup with a huge delay, which is exactly the case a player most needs told about. A run
  // where the pulse was lost shows up as a wide spread instead, and a wide spread is refused.
  function collect(taps, clicks) {
    const best = new Map();
    let ignored = 0;
    for (const tap of taps || []) {
      const near = Timing.nearestClick(tap, clicks || []);
      if (!near) {
        ignored += 1;
        continue;
      }
      const already = best.get(near.index);
      if (already === undefined) {
        best.set(near.index, near.offsetMs);
        continue;
      }
      ignored += 1;
      if (Math.abs(near.offsetMs) < Math.abs(already)) best.set(near.index, near.offsetMs);
    }
    const offsets = [...best.keys()].sort((a, b) => a - b).map((index) => best.get(index));
    return { offsets, ignored };
  }

  function result(offsets) {
    const s = Timing.stats(offsets || []);
    const spreadMs = s.sd === null ? 0 : Math.round(s.sd * 10) / 10;
    const offsetMs = s.mean === null ? 0 : Math.round(s.mean);
    const out = {
      count: s.n,
      offsetMs,
      spreadMs,
      min: s.min === null ? null : Math.round(s.min),
      max: s.max === null ? null : Math.round(s.max),
      usable: false,
      reason: "",
    };
    if (s.n < LEAST_TAPS) {
      out.reason = `Not enough taps to measure anything: ${s.n} of ${TAPS_WANTED} counted. Try again and tap right on the click.`;
    } else if (spreadMs > MOST_SPREAD_MS) {
      out.reason = `Those taps were spread over ${spreadMs} ms, which is too uneven for one number to describe. Try again, and stay with the click.`;
    } else if (Math.abs(offsetMs) > OFFSET_LIMIT_MS) {
      out.reason = `That is ${Math.abs(offsetMs)} ms off, too far for the app to put right. Check the wiring: something is adding a long delay.`;
    } else {
      out.usable = true;
      out.reason = "Steady enough to store.";
    }
    return out;
  }

  function describe(found) {
    // A run that cannot be stored says why and what to do about it, counts included.
    if (!found.usable) return found.reason;
    const size = Math.abs(found.offsetMs);
    const where = found.offsetMs === 0 ? "right on the click" : `${size} ms ${found.offsetMs < 0 ? "early" : "late"}`;
    return `You play ${where}, give or take ${found.spreadMs} ms over ${found.count} taps.`;
  }

  // A slow output cannot be calibrated away: the number would hold, but every change of
  // tempo would feel wrong, and the player should know why rather than blame themselves.
  function latencyNote(outputLatencySeconds) {
    const seconds = Number(outputLatencySeconds);
    if (!Number.isFinite(seconds) || seconds < SLOW_OUTPUT_S) return "";
    return (
      `This output reports a delay of ${Math.round(seconds * 1000)} ms, which is what a Bluetooth speaker ` +
      "or headphones do. One number cannot put that right. A cable, or the laptop's own speakers, is better for practice."
    );
  }

  return {
    clickPlan,
    collect,
    result,
    describe,
    latencyNote,
    TAPS_WANTED,
    COUNT_IN_CLICKS,
    DEFAULT_BPM,
    OFFSET_LIMIT_MS,
    LEAST_TAPS,
    MOST_SPREAD_MS,
  };
});
