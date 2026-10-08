const test = require("node:test");
const assert = require("node:assert");
const Work = require("../../static/improv/work.js");

const empty = { scales: [], slowest_chords: [], weakest_keys: [], totals: { runs: 0, passes: 0, attempts: 0, clean: 0 } };
const run = (root_pc, octaves, score) => ({ root_pc, octaves, score, tempo_bpm: 60, passed: score >= 80, runs: 1 });

test("a player with no runs is told where to begin", () => {
  assert.match(Work.scaleWork(empty, "sharps"), /No scale run yet/);
  assert.match(Work.scaleWork(empty, "sharps"), /C at 2 octaves/);
});

test("the weakest scale not yet passed is the one to work on", () => {
  const read = { ...empty, scales: [run(7, 2, 90), run(2, 2, 55), run(9, 3, 70)], totals: { runs: 3, passes: 1, attempts: 0, clean: 0 } };
  assert.match(Work.scaleWork(read, "sharps"), /D at 2 octaves/);
  assert.match(Work.scaleWork(read, "sharps"), /55/);
});

test("when every run passed, the next key in the circle at the same length is suggested", () => {
  const read = { ...empty, scales: [run(0, 2, 90)], totals: { runs: 1, passes: 1, attempts: 0, clean: 0 } };
  assert.match(Work.scaleWork(read, "sharps"), /Next: G at 2 octaves/);
});

test("the circle moves on to three octaves once all twelve keys pass at two", () => {
  const scales = Work.CIRCLE.map((pc) => run(pc, 2, 85));
  const read = { ...empty, scales, totals: { runs: 12, passes: 12, attempts: 0, clean: 0 } };
  assert.match(Work.scaleWork(read, "sharps"), /Next: C at 3 octaves/);
});

test("when everything passed at every length there is nothing left to chase", () => {
  const scales = [];
  for (const o of [2, 3, 4]) for (const pc of Work.CIRCLE) scales.push(run(pc, o, 90));
  const read = { ...empty, scales, totals: { runs: 36, passes: 36, attempts: 0, clean: 0 } };
  assert.match(Work.scaleWork(read, "sharps"), /every key at every length/i);
});

test("keys are spelled the way the player spells them", () => {
  const read = { ...empty, scales: [run(6, 2, 40)], totals: { runs: 1, passes: 0, attempts: 0, clean: 0 } };
  assert.match(Work.scaleWork(read, "flats"), /Gb at 2 octaves/);
  assert.match(Work.scaleWork(read, "sharps"), /F# at 2 octaves/);
});

test("a player with no answers is told where to begin", () => {
  assert.match(Work.chordWork(empty, "sharps"), /No chord answers yet/);
});

test("with answers but too few of any one to judge, it says so", () => {
  const read = { ...empty, totals: { runs: 0, passes: 0, attempts: 4, clean: 3 } };
  assert.match(Work.chordWork(read, "sharps"), /Not enough answers/);
});

test("the slowest chord and the weakest key are both named", () => {
  const read = {
    ...empty,
    slowest_chords: [{ title: "Am7, second position", key_pc: 9, position: 2, median_ms: 6400, attempts: 3 }],
    weakest_keys: [{ key_pc: 6, attempts: 8, missed: 5, miss_share: 0.625 }],
    totals: { runs: 0, passes: 0, attempts: 8, clean: 3 },
  };
  const words = Work.chordWork(read, "sharps");
  assert.match(words, /Am7, second position/);
  assert.match(words, /6\.4 s/);
  assert.match(words, /F#/);
  assert.match(words, /63%/);
});

test("only a weak key, or only a slow chord, still gives a line", () => {
  const slow = { ...empty, slowest_chords: [{ title: "C7, first position", key_pc: 0, position: 1, median_ms: 3000, attempts: 3 }], totals: { runs: 0, passes: 0, attempts: 3, clean: 3 } };
  assert.match(Work.chordWork(slow, "sharps"), /C7, first position/);
  const weak = { ...empty, weakest_keys: [{ key_pc: 2, attempts: 5, missed: 2, miss_share: 0.4 }], totals: { runs: 0, passes: 0, attempts: 5, clean: 3 } };
  assert.match(Work.chordWork(weak, "sharps"), /D is missed/);
});

test("a key with nothing missed is not called weak", () => {
  const read = { ...empty, weakest_keys: [{ key_pc: 2, attempts: 5, missed: 0, miss_share: 0 }], totals: { runs: 0, passes: 0, attempts: 5, clean: 5 } };
  assert.match(Work.chordWork(read, "sharps"), /Not enough answers|No key is being missed/);
  assert.doesNotMatch(Work.chordWork(read, "sharps"), /D is missed/);
});
