// SPR-I.4.2 improv: live feedback on the Play screen. The judge is already proved; what is
// proved here is the glue that has rules in it: putting a MIDI note on the take's own clock
// (beats from the first judged downbeat, count-in and loops included), the inverse clock
// mapping, and which colour a judged note gets. The page itself is checked by the pytest
// wrapper and in a real browser.

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const P = require(path.join(root, "static", "improv", "play.js"));
const Timing = require(path.join(root, "static", "improv", "timing.js"));

// A built plan as buildPlan returns it: two count-in bars, then a four-bar loop, 4/4.
const built = {
  countInBars: 2,
  loopFrom: 2,
  plan: { beatsPerBar: 4, bars: [0, 1, 2, 3, 4, 5].map((i) => ({ index: i, beats: 4, countIn: i < 2 })) },
};

// ------------------------------------------------------------- the take's clock

test("the first judged downbeat is time nought, whatever the count-in was", () => {
  assert.equal(P.takeTimeMs({ index: 2, pass: 0, beat: 0 }, built, 120), 0);
  assert.equal(P.takeTimeMs({ index: 2, pass: 0, beat: 1 }, built, 120), 500);
  assert.equal(P.takeTimeMs({ index: 3, pass: 0, beat: 0 }, built, 120), 2000);
  assert.equal(P.takeTimeMs({ index: 5, pass: 0, beat: 3.5 }, built, 120), 7750);
});

test("a note during the count-in is before time nought, so the judge can leave it out", () => {
  assert.equal(P.takeTimeMs({ index: 0, pass: 0, beat: 0 }, built, 120), -4000);
  assert.equal(P.takeTimeMs({ index: 1, pass: 0, beat: 3 }, built, 120), -500);
});

test("the second time round the loop carries on counting, it does not start again", () => {
  assert.equal(P.takeTimeMs({ index: 2, pass: 1, beat: 0 }, built, 120), 8000);
  assert.equal(P.takeTimeMs({ index: 4, pass: 2, beat: 2 }, built, 120), 2 * 8000 + 2 * 2000 + 1000);
});

test("the clock follows the tempo", () => {
  assert.equal(P.takeTimeMs({ index: 3, pass: 0, beat: 0 }, built, 60), 4000);
  assert.equal(P.takeTimeMs({ index: 3, pass: 0, beat: 0 }, built, 240), 1000);
});

test("no position is no time, not a crash", () => {
  assert.equal(P.takeTimeMs(null, built, 120), null);
  assert.equal(P.takeTimeMs({ index: 2, pass: 0, beat: 0 }, null, 120), null);
});

test("a plan with no count-in starts at bar nought", () => {
  const plain = { ...built, countInBars: 0, loopFrom: 0, plan: { beatsPerBar: 3, bars: [0, 1].map((i) => ({ index: i, beats: 3, countIn: false })) } };
  assert.equal(P.takeTimeMs({ index: 0, pass: 0, beat: 0 }, plain, 120), 0);
  assert.equal(P.takeTimeMs({ index: 1, pass: 0, beat: 0 }, plain, 120), 1500);
  assert.equal(P.takeTimeMs({ index: 0, pass: 1, beat: 0 }, plain, 120), 3000);
});

// --------------------------------------------------------------- the two clocks

test("a performance-clock time maps back to the audio clock, the inverse of heardAt", () => {
  const anchor = { audio: 10.0, perf: 5000 };
  assert.equal(Timing.audioAt(anchor, 5000), 10.0);
  assert.ok(Math.abs(Timing.audioAt(anchor, 5250) - 10.25) < 1e-9);
  assert.ok(Math.abs(Timing.heardAt(anchor, Timing.audioAt(anchor, 7777)) - 7777) < 1e-6, "there and back again");
});

// -------------------------------------------------------------------- colours

test("every class the judge can give has a colour, and a guide tone is brighter", () => {
  assert.equal(P.keyClassFor({ class: "chord", guide: false }), "im-key-chord");
  assert.equal(P.keyClassFor({ class: "chord", guide: true }), "im-key-guide");
  assert.equal(P.keyClassFor({ class: "scale" }), "im-key-scale");
  assert.equal(P.keyClassFor({ class: "approach" }), "im-key-approach");
  assert.equal(P.keyClassFor({ class: "pending" }), "im-key-pending");
  assert.equal(P.keyClassFor({ class: "outside" }), "im-key-outside");
  assert.equal(P.keyClassFor({ class: "nonsense" }), "im-key-on", "an unknown class is only lit");
  assert.equal(P.keyClassFor(null), "im-key-on");
});

test("the judge's own class names are the ones the colours know", () => {
  const J = require(path.join(root, "static", "improv", "judge.js"));
  for (const cls of ["chord", "scale", "approach", "outside", "pending"]) {
    assert.notEqual(P.keyClassFor({ class: cls }), "im-key-on", `${cls} has no colour`);
  }
  assert.ok(J.JUDGE_VERSION >= 1);
});

// ------------------------------------------------------------------ the summary

test("the running summary is words a player can read mid-take", () => {
  const judged = {
    notes: [{ class: "chord" }, { class: "chord" }, { class: "scale" }, { class: "outside" }],
    metrics: { notes: 4, chordTonePct: 50, scalePct: 25, approachPct: 0, outsidePct: 25 },
    timing: { words: "you rush by 18 ms", notes: 4 },
  };
  const text = P.liveSummary(judged);
  assert.match(text, /4 notes/);
  assert.match(text, /50% chord tones/);
  assert.match(text, /You rush by 18 ms\./, "the timing words open a sentence of their own");
  assert.equal(P.liveSummary({ notes: [], metrics: { notes: 0 }, timing: { words: "no notes yet", notes: 0 } }), "Play something.");
});
