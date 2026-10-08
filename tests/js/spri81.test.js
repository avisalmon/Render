// SPR-I.8.1 improv: the scale trainer's layout, names and fingering. Pure, no browser.
// Run by tests/test_spri_8_1.py (node --test).

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");

const Scale = require(path.join("..", "..", "static", "improv", "scale.js"));
const seed = JSON.parse(fs.readFileSync(path.join("improv", "seed_data", "fingerings.json"), "utf8")).fingerings;

const row = (pc, hand) => seed.find((r) => r.root_pc === pc && r.hand === hand);
const fingersOf = (pc, hand, octaves) => Scale.fingers(row(pc, hand), octaves);

// ------------------------------------------------------------------ levels

test("the three levels are 2, 3 and 4 octaves at 2, 3 and 4 notes per beat", () => {
  assert.deepEqual(Scale.levelInfo(1), { level: 1, octaves: 2, perBeat: 2, steps: 29 });
  assert.deepEqual(Scale.levelInfo(2), { level: 2, octaves: 3, perBeat: 3, steps: 43 });
  assert.deepEqual(Scale.levelInfo(3), { level: 3, octaves: 4, perBeat: 4, steps: 57 });
  assert.throws(() => Scale.levelInfo(4));
});

// ------------------------------------------------------------------ names

test("keys are spelled the standard way, and F#/Gb follows the player's setting", () => {
  assert.equal(Scale.keyName(3, "sharps"), "Eb");
  assert.equal(Scale.keyName(1, "sharps"), "Db");
  assert.equal(Scale.keyName(8, "sharps"), "Ab");
  assert.equal(Scale.keyName(10, "sharps"), "Bb");
  assert.equal(Scale.keyName(6, "sharps"), "F#");
  assert.equal(Scale.keyName(6, "flats"), "Gb");
  assert.equal(Scale.keyName(0, "flats"), "C");
});

test("a scale's notes are spelled by letter, one letter each", () => {
  assert.deepEqual(Scale.scaleNotes(0, "sharps"), ["C", "D", "E", "F", "G", "A", "B"]);
  assert.deepEqual(Scale.scaleNotes(3, "sharps"), ["Eb", "F", "G", "Ab", "Bb", "C", "D"]);
  assert.deepEqual(Scale.scaleNotes(6, "sharps"), ["F#", "G#", "A#", "B", "C#", "D#", "E#"]);
  assert.deepEqual(Scale.scaleNotes(6, "flats"), ["Gb", "Ab", "Bb", "Cb", "Db", "Eb", "F"]);
  assert.deepEqual(Scale.scaleNotes(1, "sharps"), ["Db", "Eb", "F", "Gb", "Ab", "Bb", "C"]);
});

// ------------------------------------------------------------------ the range

test("the left hand starts at the tonic, the right hand an octave above", () => {
  const steps = Scale.buildSteps(0, 2);
  assert.equal(steps.length, 29);
  assert.equal(steps[0].left, 36);
  assert.equal(steps[0].right, 48);
  assert.equal(steps[14].left, 60);
  assert.equal(steps[14].right, 72);
  assert.equal(steps[28].left, 36);
  assert.equal(steps[28].right, 48);
});

test("a scale goes up and comes back down the same notes, with the top note played once", () => {
  const steps = Scale.buildSteps(7, 2);
  const lefts = steps.map((s) => s.left);
  assert.deepEqual(lefts, [...lefts.slice(0, 15), ...lefts.slice(0, 14).reverse()]);
  assert.equal(steps[14].direction, "top");
  assert.equal(steps[3].direction, "up");
  assert.equal(steps[20].direction, "down");
});

test("every step is a note of the major scale in both hands", () => {
  const major = new Set([0, 2, 4, 5, 7, 9, 11]);
  for (let pc = 0; pc < 12; pc++) {
    for (const octaves of [2, 3, 4]) {
      for (const step of Scale.buildSteps(pc, octaves)) {
        assert.ok(major.has((((step.left - pc) % 12) + 12) % 12), `pc ${pc} left ${step.left}`);
        assert.equal(step.right, step.left + 12);
      }
    }
  }
});

test("three and four octaves start lower, and the top never reaches the control keys", () => {
  assert.equal(Scale.buildSteps(0, 3)[0].left, 36);
  assert.equal(Scale.buildSteps(0, 4)[0].left, 36);
  for (let pc = 0; pc < 12; pc++) {
    for (const octaves of [2, 3, 4]) {
      const steps = Scale.buildSteps(pc, octaves);
      const top = Math.max(...steps.map((s) => s.right));
      assert.ok(top < 106, `pc ${pc}, ${octaves} octaves reaches ${top}`);
      assert.ok(Math.min(...steps.map((s) => s.left)) >= 21, "below the lowest key of an 88-key piano");
    }
  }
});

test("B and Bb in four octaves drop an octave to stay off the control keys", () => {
  assert.equal(Scale.buildSteps(11, 4)[0].left, 35);
  assert.equal(Scale.buildSteps(10, 4)[0].left, 34);
  assert.equal(Scale.buildSteps(9, 4)[0].left, 45);
});

test("only four octaves needs an 88-key piano", () => {
  assert.equal(Scale.needsFullKeyboard(2), false);
  assert.equal(Scale.needsFullKeyboard(3), false);
  assert.equal(Scale.needsFullKeyboard(4), true);
});

// ------------------------------------------------------------------ fingering

test("C major: the right hand 1 2 3 1 2 3 4, thumb under, to the top and back", () => {
  assert.deepEqual(fingersOf(0, "R", 2).slice(0, 15), [1, 2, 3, 1, 2, 3, 4, 1, 2, 3, 1, 2, 3, 4, 5]);
});

test("C major: the left hand 5 4 3 2 1 3 2, then 1 4 3 2 1 3 2 and a thumb on the top", () => {
  assert.deepEqual(fingersOf(0, "L", 2).slice(0, 15), [5, 4, 3, 2, 1, 3, 2, 1, 4, 3, 2, 1, 3, 2, 1]);
});

test("coming down is the going up reversed", () => {
  const up = fingersOf(0, "L", 2);
  const all = Scale.fingersUpAndDown(row(0, "L"), 2);
  assert.equal(all.length, 29);
  assert.deepEqual(all.slice(0, 15), up);
  assert.deepEqual(all.slice(14), [...up].reverse());
});

test("three octaves repeat the middle pattern and four repeat it again", () => {
  const f = fingersOf(0, "R", 4);
  assert.equal(f.length, 29);
  assert.deepEqual(f.slice(0, 8), [1, 2, 3, 1, 2, 3, 4, 1]);
  assert.deepEqual(f.slice(21), [1, 2, 3, 1, 2, 3, 4, 5]);
});

test("B major left hand starts on 4 and the later octaves start on the thumb", () => {
  assert.deepEqual(fingersOf(11, "L", 2), [4, 3, 2, 1, 4, 3, 2, 1, 3, 2, 1, 4, 3, 2, 1]);
});

test("F# major starts on 2 in the right hand and 4 in the left", () => {
  assert.equal(fingersOf(6, "R", 2)[0], 2);
  assert.equal(fingersOf(6, "L", 2)[0], 4);
});

test("every key and hand has a fingering of the right length, with fingers 1 to 5", () => {
  assert.equal(seed.length, 24);
  for (let pc = 0; pc < 12; pc++) {
    for (const hand of ["L", "R"]) {
      for (const octaves of [2, 3, 4]) {
        const f = Scale.fingersUpAndDown(row(pc, hand), octaves);
        assert.equal(f.length, 14 * octaves + 1);
        assert.ok(f.every((n) => n >= 1 && n <= 5));
      }
    }
  }
});

test("a hand never uses the same finger on two notes in a row", () => {
  for (let pc = 0; pc < 12; pc++) {
    for (const hand of ["L", "R"]) {
      const f = fingersOf(pc, hand, 3);
      for (let i = 1; i < f.length; i++) assert.notEqual(f[i], f[i - 1], `${pc} ${hand} step ${i}`);
    }
  }
});

// ------------------------------------------------------------------ the plan

test("the plan puts names and fingers on every step", () => {
  const plan = Scale.plan(3, 2, "sharps", seed);
  assert.equal(plan.steps.length, 29);
  assert.equal(plan.key, "Eb");
  assert.equal(plan.hasFingering, true);
  assert.equal(plan.steps[0].name, "Eb");
  assert.equal(plan.steps[0].leftFinger, 3);
  assert.equal(plan.steps[0].rightFinger, 3);
  assert.equal(plan.steps[3].name, "Ab");
  assert.equal(plan.steps[14].name, "Eb");
  assert.equal(plan.steps[28].name, "Eb");
});

test("a key with no stored fingering is still playable, with no fingers shown", () => {
  const plan = Scale.plan(3, 2, "sharps", []);
  assert.equal(plan.hasFingering, false);
  assert.equal(plan.steps.length, 29);
  assert.equal(plan.steps[0].leftFinger, null);
  assert.equal(plan.steps[0].rightFinger, null);
});
