// SPR-I.3.4 improv: calibration. Sixteen taps against a click, and one number out of it.
// The maths is the spike's timing.js, already tested; what is tested here is the calibration
// rules on top of it: which taps count, when a run is good enough to store, and what the
// player is told. The screen is checked by the pytest wrapper and in a real browser, and the
// result itself is only true when Avi taps it on his own piano (SPR-I.3.4 is an at-the-piano
// sprint for exactly that reason).

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const C = require(path.join(root, "static", "improv", "calibrate.js"));

const GAP = 750; // ms, 80 bpm

// Clicks at a steady 80 bpm, starting at 1000 ms on the performance clock.
function clicks(count, from = 1000) {
  return Array.from({ length: count }, (_, i) => from + i * GAP);
}

// Taps all `offset` ms from each click they were aimed at.
function tapsAt(clickTimes, offset) {
  return clickTimes.map((t) => t + offset);
}

// ---------------------------------------------------------------- what to play

test("the click track is long enough for the taps, plus a few to find the pulse first", () => {
  const plan = C.clickPlan(80);
  assert.equal(plan.gapSeconds, 0.75);
  assert.equal(plan.countIn, C.COUNT_IN_CLICKS);
  assert.equal(plan.taps, C.TAPS_WANTED);
  assert.ok(plan.count >= C.COUNT_IN_CLICKS + C.TAPS_WANTED);
  assert.equal(C.clickPlan(60).gapSeconds, 1);
  assert.throws(() => C.clickPlan(5), /Tempo/, "the click cannot run at any tempo at all");
});

test("sixteen taps is what it asks for, because fewer is not a measurement", () => {
  assert.equal(C.TAPS_WANTED, 16);
  assert.ok(C.COUNT_IN_CLICKS >= 2);
});

// --------------------------------------------------------- which taps count

test("a tap near a click is measured against that click, early or late", () => {
  const c = clicks(8);
  const got = C.collect(tapsAt(c, -48), c, GAP);
  assert.equal(got.offsets.length, 8);
  assert.deepEqual([...new Set(got.offsets)], [-48], "every tap was 48 ms early");
  assert.equal(got.ignored, 0);
  assert.deepEqual([...new Set(C.collect(tapsAt(c, 30), c, GAP).offsets)], [30]);
});

test("a tap nearer the next click is counted against the next click, not stretched to the last", () => {
  const c = clicks(4);
  const got = C.collect([c[1] - 20, c[2] + 10], c, GAP);
  assert.deepEqual(got.offsets, [-20, 10]);
});

test("a tap halfway between clicks still counts, and the spread is what calls the run bad", () => {
  const c = clicks(16);
  const halfway = c.map((t, i) => (i % 2 ? t + GAP * 0.45 : t - 10));
  const got = C.collect(halfway, c, GAP);
  assert.equal(got.offsets.length, 16, "nothing is thrown away for being a bad tap");
  assert.equal(C.result(got.offsets).usable, false, "but a run like that is not stored");
  assert.match(C.result(got.offsets).reason, /uneven|spread/i);
});

test("a setup with a huge delay is measured and reported, not quietly filtered out", () => {
  const c = clicks(16);
  const got = C.collect(tapsAt(c, -300), c, GAP);
  assert.equal(got.offsets.length, 16);
  const found = C.result(got.offsets);
  assert.equal(found.offsetMs, -300);
  assert.equal(found.usable, true, "300 ms early is within what the profile holds");
  assert.match(C.describe(found), /300 ms early/);
});

test("two taps on one click count once, because the piano bounced, not the player", () => {
  const c = clicks(4);
  const got = C.collect([c[1] - 12, c[1] + 40], c, GAP);
  assert.deepEqual(got.offsets, [-12], "the nearer of the two is the tap");
  assert.equal(got.ignored, 1);
});

test("no taps and no clicks are not an error", () => {
  assert.deepEqual(C.collect([], clicks(4), GAP).offsets, []);
  assert.deepEqual(C.collect(tapsAt(clicks(4), 0), [], GAP).offsets, []);
  assert.deepEqual(C.collect(null, null, GAP).offsets, []);
});

// -------------------------------------------------------------- the one number

test("the stored number is the mean, rounded, and the spread is reported beside it", () => {
  const offsets = [-50, -46, -52, -48, -44, -50, -48, -46, -50, -48];
  const got = C.result(offsets);
  assert.equal(got.count, 10);
  assert.equal(got.offsetMs, -48, "the mean, rounded to a whole millisecond");
  assert.ok(got.spreadMs < 4, `the spread should be small here, not ${got.spreadMs}`);
  assert.equal(got.min, -52);
  assert.equal(got.max, -44);
  assert.equal(got.usable, true);
});

test("a run all over the place is refused rather than quietly stored", () => {
  const got = C.result([-200, 150, -30, 90, -170, 40, 120, -80, 200, -150]);
  assert.equal(got.usable, false);
  assert.match(got.reason, /spread/i);
  assert.ok(got.spreadMs > 30);
});

test("too few taps to mean anything is refused, and says how many were counted", () => {
  const got = C.result([-40, -50, -45]);
  assert.equal(got.usable, false);
  assert.match(got.reason, /3/);
  assert.equal(C.result([]).usable, false);
  assert.equal(C.result([]).count, 0);
});

test("an offset too big for the profile to hold is refused, however steady it was", () => {
  const steady = Array.from({ length: 12 }, () => -900);
  const got = C.result(steady);
  assert.equal(got.usable, false);
  assert.match(got.reason, /too far/i);
  assert.ok(Math.abs(C.OFFSET_LIMIT_MS) === 500);
});

test("what the player is told says the direction in words, not a sign to work out", () => {
  const early = C.describe(C.result(Array.from({ length: 12 }, (_, i) => -48 + (i % 3))));
  assert.match(early, /early/);
  assert.match(early, /48|47|46/);
  const late = C.describe(C.result(Array.from({ length: 12 }, (_, i) => 30 + (i % 3))));
  assert.match(late, /late/);
  assert.doesNotMatch(late, /early/);
  assert.match(C.describe(C.result([])), /not enough/i);
});

// ------------------------------------------------------------- the warning

test("an output that reports a long delay is called out, because Bluetooth cannot be calibrated away", () => {
  assert.equal(C.latencyNote(0.012), "");
  assert.equal(C.latencyNote(0.048), "", "a normal laptop output says nothing");
  const warning = C.latencyNote(0.22);
  assert.match(warning, /220 ms/);
  assert.match(warning, /Bluetooth/);
  assert.equal(C.latencyNote(null), "");
  assert.equal(C.latencyNote(undefined), "");
});

test("the warning does not pretend to know the output is Bluetooth, only that it is slow", () => {
  assert.match(C.latencyNote(0.3), /cable|wired/i);
});
