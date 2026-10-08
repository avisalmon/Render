// SPR-I.8.3 improv: the words and the clock of the scales screen. Pure, no browser.
// Run by tests/test_spri_8_3.py (node --test).

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");

const Scale = require(path.join("..", "..", "static", "improv", "scale.js"));
const seed = JSON.parse(fs.readFileSync(path.join("improv", "seed_data", "fingerings.json"), "utf8")).fingerings;

test("the keys come in circle-of-fifths order from C", () => {
  assert.deepEqual(Scale.CIRCLE, [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]);
  assert.deepEqual(Scale.CIRCLE.map((pc) => Scale.keyName(pc, "sharps")), ["C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F"]);
  assert.equal(new Set(Scale.CIRCLE).size, 12);
});

test("the next key follows the circle and comes round from F to C", () => {
  assert.equal(Scale.nextKey(0), 7);
  assert.equal(Scale.nextKey(7), 2);
  assert.equal(Scale.nextKey(5), 0);
  assert.equal(Scale.nextKey(99), 0);
});

test("a tempo is a whole number from 30 to 160, and 60 when it is nonsense", () => {
  assert.equal(Scale.clampTempo(72), 72);
  assert.equal(Scale.clampTempo("84"), 84);
  assert.equal(Scale.clampTempo(10), 30);
  assert.equal(Scale.clampTempo(500), 160);
  assert.equal(Scale.clampTempo(61.6), 62);
  assert.equal(Scale.clampTempo("fast"), 60);
  assert.equal(Scale.clampTempo(""), 60);
  assert.equal(Scale.clampTempo(null), 60);
  assert.equal(Scale.TEMPO_DEFAULT, 60);
});

test("the clock: four clicks of count-in, then one step every beat over the notes a beat", () => {
  const t = Scale.timeline(60, 2);
  assert.equal(t.beatMs, 1000);
  assert.equal(t.stepMs, 500);
  assert.equal(t.countInBeats, 4);
  assert.equal(t.countInMs, 4000);
  const fast = Scale.timeline(120, 4);
  assert.equal(fast.stepMs, 125);
  assert.equal(fast.countInMs, 2000);
});

test("how long a run lasts, and how many beats it has", () => {
  const plan = Scale.plan(7, 2, "sharps", seed);
  const t = Scale.timeline(60, 2);
  assert.equal(Scale.runBeats(plan, 2), 14.5);
  assert.equal(Scale.runMs(plan, t), 29 * 500);
});

test("the level names say the octaves and the notes a beat", () => {
  assert.equal(Scale.levelLabel(1), "2 octaves, 2 notes a beat");
  assert.equal(Scale.levelLabel(3), "4 octaves, 4 notes a beat");
});

test("the verdict says the score and the line", () => {
  assert.equal(Scale.verdict({ score: 92, passed: true }), "Passed: 92. The line is 80.");
  assert.equal(Scale.verdict({ score: 74, passed: false }), "Not yet: 74. The line is 80.");
});

test("the feel says early, late or steady in plain words", () => {
  assert.equal(Scale.feelWords({ feel: "steady", meanOffsetMs: 4 }), "Steady: 4 ms late on average.");
  assert.equal(Scale.feelWords({ feel: "steady", meanOffsetMs: -4 }), "Steady: 4 ms early on average.");
  assert.equal(Scale.feelWords({ feel: "steady", meanOffsetMs: 0 }), "Steady: right on the beat.");
  assert.equal(Scale.feelWords({ feel: "late", meanOffsetMs: 63 }), "You were behind: 63 ms late on average.");
  assert.equal(Scale.feelWords({ feel: "early", meanOffsetMs: -48 }), "You rushed: 48 ms early on average.");
});

test("the misses are named by note and direction, and a long list is cut", () => {
  const plan = Scale.plan(0, 2, "sharps", seed);
  const none = Scale.missedWords(plan, { missedSteps: [] });
  assert.deepEqual(none, []);
  const some = Scale.missedWords(plan, { missedSteps: [0, 3, 14, 20] });
  assert.deepEqual(some, ["C up (step 1)", "F up (step 4)", "C at the top (step 15)", "D down (step 21)"]);
  const many = Scale.missedWords(plan, { missedSteps: Array.from({ length: 12 }, (_, i) => i) }, 5);
  assert.equal(many.length, 6);
  assert.equal(many[5], "and 7 more");
});

test("the fingering line for a step reads the left and the right hand", () => {
  const plan = Scale.plan(0, 2, "sharps", seed);
  assert.equal(Scale.fingerWords(plan.steps[0]), "C: left 5, right 1");
  assert.equal(Scale.fingerWords(Scale.plan(0, 2, "sharps", []).steps[0]), "C");
});

test("the best of a key and level is the highest score, and the latest tempo it was passed at", () => {
  const runs = [
    { root_pc: 3, octaves: 2, score: 70, passed: false, tempo_bpm: 60 },
    { root_pc: 3, octaves: 2, score: 92, passed: true, tempo_bpm: 72 },
    { root_pc: 3, octaves: 3, score: 99, passed: true, tempo_bpm: 60 },
    { root_pc: 7, octaves: 2, score: 100, passed: true, tempo_bpm: 60 },
  ];
  assert.deepEqual(Scale.bestOf(runs, 3, 2), { score: 92, tempo: 72, passed: true });
  assert.equal(Scale.bestOf(runs, 3, 4), null);
  assert.equal(Scale.bestOf([], 3, 2), null);
});

test("the keyboard drawn for a plan covers every note of both hands", () => {
  for (let pc = 0; pc < 12; pc++) {
    for (const octaves of [2, 3, 4]) {
      const plan = Scale.plan(pc, octaves, "sharps", seed);
      const range = Scale.keyboardRange(plan);
      for (const s of plan.steps) {
        assert.ok(s.left >= range.from && s.right <= range.to);
      }
      assert.ok(range.from >= 21 && range.to < 106);
    }
  }
});

test("the notes lit for a step are what is asked, what is held and what is wrong", () => {
  const plan = Scale.plan(0, 2, "sharps", seed);
  const step = plan.steps[0];
  const lit = Scale.litNotes(step, [step.left, 61]);
  const byNote = Object.fromEntries(lit.map((n) => [n.midi, n.className]));
  assert.equal(byNote[step.left], "im-key-chord");
  assert.equal(byNote[step.right], "im-key-pending");
  assert.equal(byNote[61], "im-key-outside");
  assert.deepEqual(Scale.litNotes(null, [60]).map((n) => n.className), ["im-key-on"]);
});
