// SPR-I.8.7 improv: Avi's live check of the trainer. Pure, no browser.
// Run by tests/test_spri_8_7.py (node --test).

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Scale = require(path.join("..", "..", "static", "improv", "scale.js"));
const Work = require(path.join("..", "..", "static", "improv", "work.js"));
const Drill = require(path.join("..", "..", "static", "improv", "drill.js"));

test("the keys start at C and go round the circle of fifths", () => {
  assert.deepEqual(Scale.CIRCLE, [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]);
  assert.deepEqual(Scale.CIRCLE.map((pc) => Scale.keyName(pc, "sharps")), ["C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F"]);
  assert.deepEqual(Drill.CIRCLE, Scale.CIRCLE);
  assert.deepEqual(Work.CIRCLE, Scale.CIRCLE);
});

test("the next key follows the circle and comes round from F to C", () => {
  assert.equal(Scale.nextKey(0), 7);
  assert.equal(Scale.nextKey(7), 2);
  assert.equal(Scale.nextKey(5), 0);
  assert.equal(Scale.nextKey(99), 0);
});

// ------------------------------------------------------------ keep going

test("a pass at two octaves goes straight on to three, in the same key", () => {
  assert.deepEqual(Scale.afterRun(7, 1, true), { pc: 7, level: 2, auto: true, newKey: false });
});

test("a pass at three octaves goes straight on to four", () => {
  assert.deepEqual(Scale.afterRun(7, 2, true), { pc: 7, level: 3, auto: true, newKey: false });
});

test("a pass at four octaves moves to the next key at two octaves and waits for the player", () => {
  assert.deepEqual(Scale.afterRun(7, 3, true), { pc: 2, level: 1, auto: false, newKey: true });
  assert.deepEqual(Scale.afterRun(5, 3, true), { pc: 0, level: 1, auto: false, newKey: true });
});

test("a run that did not pass stays where it is and waits", () => {
  assert.deepEqual(Scale.afterRun(7, 2, false), { pc: 7, level: 2, auto: false, newKey: false });
});

test("the words for what comes next name the level, or the key", () => {
  assert.match(Scale.nextWords(Scale.afterRun(7, 1, true), "sharps"), /3 octaves, 3 notes a beat/);
  assert.match(Scale.nextWords(Scale.afterRun(7, 3, true), "sharps"), /D, 2 octaves/);
  assert.match(Scale.nextWords(Scale.afterRun(7, 2, false), "sharps"), /Start again/);
});

// ------------------------------------------------------------ where the scale starts

test("two octaves start lower than they used to: the left hand on the tonic two octaves below middle C", () => {
  const steps = Scale.buildSteps(0, 2);
  assert.equal(steps[0].left, 36);
  assert.equal(steps[0].right, 48);
  assert.equal(steps[28].left, 36);
  assert.equal(Scale.buildSteps(7, 2)[0].left, 43);
});

test("a chosen starting octave puts the left hand's tonic there", () => {
  assert.equal(Scale.buildSteps(0, 2, 3)[0].left, 48);
  assert.equal(Scale.buildSteps(0, 2, 4)[0].left, 60);
  assert.equal(Scale.buildSteps(7, 2, 3)[0].left, 55);
  assert.equal(Scale.buildSteps(0, 3, 1)[0].left, 24);
});

test("the start choices never reach below the piano or into the control keys", () => {
  for (let pc = 0; pc < 12; pc++) {
    for (const octaves of [2, 3, 4]) {
      const choices = Scale.startChoices(pc, octaves);
      assert.ok(choices.length >= 2, `pc ${pc}, ${octaves} octaves has choices`);
      for (const octave of choices) {
        const steps = Scale.buildSteps(pc, octaves, octave);
        assert.ok(Math.min(...steps.map((s) => s.left)) >= Scale.LOWEST_KEY);
        assert.ok(Math.max(...steps.map((s) => s.right)) < Scale.CONTROL_FLOOR);
      }
      assert.ok(choices.includes(Scale.defaultStart(pc, octaves)), "the default is one of the choices");
    }
  }
});

test("a start the scale cannot use is pulled to the nearest one it can", () => {
  const high = Scale.buildSteps(0, 4, 7);
  assert.ok(Math.max(...high.map((s) => s.right)) < Scale.CONTROL_FLOOR);
  const low = Scale.buildSteps(0, 2, -3);
  assert.ok(Math.min(...low.map((s) => s.left)) >= Scale.LOWEST_KEY);
});

test("the start octave is named the way a pianist names it", () => {
  assert.equal(Scale.startName(0, 2, "sharps"), "C2");
  assert.equal(Scale.startName(7, 3, "sharps"), "G3");
  assert.equal(Scale.startName(6, 2, "flats"), "Gb2");
});

test("the plan carries the start octave through to its notes", () => {
  const plan = Scale.plan(0, 2, "sharps", [], 3);
  assert.equal(plan.steps[0].left, 48);
  assert.equal(plan.startOctave, 3);
  assert.equal(Scale.plan(0, 2, "sharps", []).startOctave, 2);
});

// ------------------------------------------------------------ the work line

test("a player with no runs is told to start with C", () => {
  const empty = { scales: [], slowest_chords: [], weakest_keys: [], totals: { runs: 0, passes: 0, attempts: 0, clean: 0 } };
  assert.match(Work.scaleWork(empty, "sharps"), /Start with C at 2 octaves/);
});
