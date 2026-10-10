// SPR-I.12.1 improv: the reading trainer's rules. Run with: node --test tests/js/spri121.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const R = require("../../static/improv/reading.js");

const LETTERS = ["C", "D", "E", "F", "G", "A", "B"];
const beatMs = (tempo) => 60000 / tempo;
const perfect = (ex, tempo) => ex.notes.map((n) => ({ t_ms: Math.round(n.beat * beatMs(tempo)), type: "on", note: n.midi, velocity: 80 }));

// ------------------------------------------------------------------ the ladder

test("the ladder is twelve keys, each right hand, then left, then both, C first", () => {
  assert.equal(R.stageCount(), 36);
  assert.deepEqual(R.stageOf(0), { index: 0, pc: 0, key: "C", hands: "R", difficulty: 1 });
  assert.deepEqual(R.stageOf(1), { index: 1, pc: 0, key: "C", hands: "L", difficulty: 1 });
  assert.deepEqual(R.stageOf(2), { index: 2, pc: 0, key: "C", hands: "B", difficulty: 1 });
  assert.equal(R.stageOf(3).key, "G");
  assert.equal(R.stageOf(6).key, "F");
  assert.equal(R.stageOf(12).difficulty, 2, "the fifth key brings the second difficulty");
  assert.equal(R.stageOf(35).key, "F#");
  assert.equal(R.stageOf(35).difficulty, 3);
  assert.equal(R.stageOf(99).index, 35, "past the end is the last stage");
  assert.equal(R.stageIndex("Bb", "B"), 14);
  assert.equal(R.stageIndex("H", "B"), -1);
});

test("the key is said in words next to the staff", () => {
  assert.equal(R.keyWords("C"), "no sharps or flats");
  assert.equal(R.keyWords("G"), "1 sharp (F#)");
  assert.equal(R.keyWords("Eb"), "3 flats (Bb, Eb, Ab)");
  assert.equal(R.stageTitle(R.stageOf(4)), "G major, left hand");
  assert.deepEqual(R.keyAccidentals("D"), { C: 1, D: 0, E: 0, F: 1, G: 0, A: 0, B: 0 });
  const sig = R.signaturePositions("D");
  assert.deepEqual(sig, { treble: [38, 35], bass: [24, 21], kind: "#" }, "F# on the top line, C# in the third space");
  assert.deepEqual(R.signaturePositions("F"), { treble: [34], bass: [20], kind: "b" });
});

// ------------------------------------------------------------------ the generator

test("an exercise is four full bars in the key, inside the hand's range, and the same for the same seed", () => {
  for (let s = 0; s < R.stageCount(); s++) {
    const stage = R.stageOf(s);
    for (const seed of [1, 2, 3, 4242, 987654321]) {
      const ex = R.generate(stage, seed);
      const sig = R.keyAccidentals(stage.key);
      const hands = new Set(ex.notes.map((n) => n.hand));
      assert.deepEqual([...hands].sort(), stage.hands === "B" ? ["L", "R"] : [stage.hands], `${stage.key} ${stage.hands}`);
      for (const hand of hands) {
        const total = ex.notes.filter((n) => n.hand === hand).reduce((a, n) => a + n.dur, 0);
        assert.equal(total, 16, `${stage.key} ${stage.hands} ${hand} fills four bars of four`);
      }
      for (const n of ex.notes) {
        assert.equal(n.midi, R.midiOf(n.step, n.acc));
        if (!n.shown) assert.equal(n.acc, sig[LETTERS[n.step % 7]], "a note with no accidental is in the key");
        else assert.equal(stage.difficulty, 3, "accidentals only at the third difficulty");
        const range = stage.hands === "B" && n.hand === "L" ? [14, 32] : R.RANGES[n.hand][stage.difficulty];
        assert.ok(n.step >= range[0] && n.step <= range[1], `${stage.key} ${stage.hands} ${n.hand} step ${n.step} in ${range}`);
        assert.ok(n.midi < R.CONTROL_FLOOR);
      }
      assert.deepEqual(R.generate(stage, seed).notes, ex.notes, "deterministic");
    }
  }
  assert.notDeepEqual(R.generate(R.stageOf(0), 1).notes, R.generate(R.stageOf(0), 2).notes);
});

test("the first difficulty is steps and quarters; later ones bring leaps, eighths and ledger lines", () => {
  const steps = (stage, seed) => R.generate(stage, seed).notes.filter((n) => n.hand === "R");
  for (let seed = 1; seed < 40; seed++) {
    const easy = steps(R.stageOf(0), seed);
    for (let i = 1; i < easy.length - 1; i++) assert.ok(Math.abs(easy[i].step - easy[i - 1].step) <= 2, "a step or a third at most");
    assert.ok(easy.every((n) => n.dur >= 1), "no eighths at the first difficulty");
  }
  const hard = [];
  for (let seed = 1; seed < 40; seed++) hard.push(...steps(R.stageOf(33), seed));
  assert.ok(hard.some((n) => n.dur === 0.5), "eighths appear");
  assert.ok(hard.some((n) => n.step > R.TREBLE.top || n.step < R.TREBLE.bottom), "ledger lines appear");
  assert.ok(hard.some((n) => n.shown), "an accidental appears");
  const after = hard.findIndex((n) => n.shown);
  assert.equal(hard[after + 1].step, hard[after].step + 1, "a chromatic note resolves a step up");
});

test("a weak zone leans the next exercise that way", () => {
  let above = 0;
  let plain = 0;
  for (let seed = 1; seed < 60; seed++) {
    above += R.generate(R.stageOf(15), seed, ["treble-above"]).notes.filter((n) => n.hand === "R" && n.step > R.TREBLE.top).length;
    plain += R.generate(R.stageOf(15), seed, []).notes.filter((n) => n.hand === "R" && n.step > R.TREBLE.top).length;
  }
  assert.ok(above > plain * 1.3, `leaning above the staff: ${above} against ${plain}`);
});

test("spelling a played note in the key", () => {
  assert.deepEqual(R.spell(66, "G"), { step: 31, acc: 1 }, "F# is in G");
  assert.deepEqual(R.spell(65, "G"), { step: 31, acc: 0 }, "F natural in G is F with a natural");
  assert.deepEqual(R.spell(70, "F"), { step: 34, acc: -1 }, "Bb in F");
  assert.deepEqual(R.spell(61, "C"), { step: 28, acc: 1 }, "C# in C");
  assert.deepEqual(R.spell(61, "F"), { step: 29, acc: -1 }, "Db in a flat key");
  assert.equal(R.shownAccidental(31, 1, "G"), "");
  assert.equal(R.shownAccidental(31, 0, "G"), "n");
  assert.equal(R.shownAccidental(31, 1, "C"), "#");
  assert.equal(R.noteName(70, "flats"), "Bb4");
  assert.equal(R.zoneOf("R", 28), "treble-below");
  assert.equal(R.zoneOf("L", 27), "bass-above");
  assert.equal(R.zoneWords("bass-below"), "Bass clef, below the staff");
});

// ------------------------------------------------------------------ the flow judge

test("a perfect read scores 100 and passes; a slow tempo widens nothing past the beat", () => {
  const ex = R.generate(R.stageOf(2), 11);
  for (const tempo of [40, 72, 120]) {
    const j = R.judge({ notes: ex.notes, tempo, events: perfect(ex, tempo) });
    assert.equal(j.score, 100, `at ${tempo}`);
    assert.ok(j.passed && j.done);
    assert.ok(j.results.every((r) => r.state === "right" && r.timing === "ontime"));
  }
  assert.equal(R.toleranceMs(beatMs(72)), 150);
  assert.equal(R.toleranceMs(beatMs(160)), 113);
});

test("right but late is amber, a wrong key is red with what was played, silence is a miss, and extras cost", () => {
  const ex = R.generate(R.stageOf(0), 5);
  const tempo = 60;
  const events = perfect(ex, tempo);
  events[1] = { ...events[1], t_ms: events[1].t_ms + 250 };
  events[2] = { ...events[2], note: ex.notes[2].midi + 2 };
  events.splice(3, 1);
  events.push({ t_ms: 20000, type: "on", note: 100, velocity: 60 });
  const j = R.judge({ notes: ex.notes, tempo, events });
  assert.equal(j.results[1].state, "right");
  assert.equal(j.results[1].timing, "late");
  assert.equal(j.results[1].offset_ms, 250);
  assert.equal(j.results[2].state, "wrong");
  assert.equal(j.results[2].played, ex.notes[2].midi + 2);
  assert.equal(j.results[3].state, "missed");
  assert.equal(j.extras, 1);
  assert.ok(j.score < 100);
  const n = ex.notes.length;
  assert.equal(j.pitchAccuracy, (n - 2) / (n + 1));
});

test("the latency offset moves every note", () => {
  const ex = R.generate(R.stageOf(0), 8);
  const late = perfect(ex, 72).map((e) => ({ ...e, t_ms: e.t_ms + 120 }));
  assert.ok(R.judge({ notes: ex.notes, tempo: 72, events: late }).results.some((r) => r.timing !== "ontime") || R.toleranceMs(beatMs(72)) >= 120);
  const fixed = R.judge({ notes: ex.notes, tempo: 72, events: late, latencyMs: 120 });
  assert.ok(fixed.results.every((r) => r.offset_ms === 0));
});

test("live, a note is pending until its window closes, and control keys are never judged", () => {
  const ex = R.generate(R.stageOf(1), 3);
  const tempo = 72;
  const events = perfect(ex, tempo).slice(0, 1).concat([{ t_ms: 10, type: "on", note: 108, velocity: 90 }]);
  const early = R.judge({ notes: ex.notes, tempo, events, now: 100 });
  assert.equal(early.results[0].state, "right");
  assert.ok(early.results.slice(1).every((r) => r.state === "pending"));
  assert.equal(early.extras, 0, "C8 is a control key");
  assert.ok(!early.done);
  const later = R.judge({ notes: ex.notes, tempo, events, now: ex.notes[1].beat * beatMs(tempo) + beatMs(tempo) });
  assert.equal(later.results[1].state, "missed");
});

test("two eighths are told apart: a note on the second eighth is not the first one late", () => {
  const notes = [
    { index: 0, hand: "R", step: 32, acc: 0, midi: 67, beat: 0, dur: 0.5, bar: 0, shown: "" },
    { index: 1, hand: "R", step: 33, acc: 0, midi: 69, beat: 0.5, dur: 0.5, bar: 0, shown: "" },
    { index: 2, hand: "R", step: 32, acc: 0, midi: 67, beat: 1, dur: 1, bar: 0, shown: "" },
  ];
  const tempo = 60;
  const j = R.judge({ notes, tempo, events: [{ t_ms: 500, type: "on", note: 69, velocity: 80 }, { t_ms: 1000, type: "on", note: 67, velocity: 80 }] });
  assert.equal(j.results[0].state, "missed");
  assert.equal(j.results[1].state, "right");
  assert.equal(j.results[2].state, "right");
});

// ------------------------------------------------------------------ step mode

test("step mode waits at each onset, counts wrong tries, and never passes", () => {
  const ex = R.generate(R.stageOf(2), 9);
  const run = R.createStepRun(ex.notes);
  const first = ex.notes.filter((n) => n.beat === 0);
  assert.equal(run.target(), 0);
  assert.deepEqual(run.waiting(), first.map((n) => n.index));
  const wrong = run.press(first[0].midi + 1, 100);
  assert.equal(wrong.right, false);
  assert.equal(run.target(), 0, "still waiting");
  let t = 200;
  for (const n of first) run.press(n.midi, (t += 100));
  assert.notEqual(run.target(), 0, "moved on once every note at the onset was played");
  for (const n of ex.notes.filter((m) => m.beat > 0)) run.press(n.midi, (t += 2000));
  assert.equal(run.target(), null);
  const s = run.summary();
  assert.ok(s.done);
  assert.equal(s.passed, false);
  assert.equal(s.mode, "step");
  assert.equal(s.results[first[0].index].state, "right");
  assert.equal(s.results[first[0].index].timing, "fixed", "found after a wrong try");
  assert.equal(s.results[first[0].index].played, first[0].midi + 1);
  assert.ok(s.pitchAccuracy < 1 && s.timingAccuracy < 1, "slow notes count against timing");
});

test("a drilled bar judges only its own notes; the others are out", () => {
  const ex = R.generate(R.stageOf(0), 21);
  const run = R.createStepRun(ex.notes, [2, 2]);
  const inside = ex.notes.filter((n) => n.bar === 2);
  assert.equal(run.target(), inside[0].beat);
  let t = 0;
  for (const n of inside) run.press(n.midi, (t += 300));
  const s = run.summary();
  assert.ok(s.done);
  assert.equal(s.score, 100);
  assert.ok(ex.notes.filter((n) => n.bar !== 2).every((n) => s.results[n.index].state === "out"));
});

// ------------------------------------------------------------------ words and the record

test("the slips are named by kind and by part of the staff, and the bad bars are listed", () => {
  const ex = R.generate(R.stageOf(0), 5);
  const tempo = 60;
  const events = perfect(ex, tempo);
  events[0] = { ...events[0], note: R.midiOf(ex.notes[0].step + 1, R.keyAccidentals("C")[LETTERS[(ex.notes[0].step + 1) % 7]]) };
  events[1] = { ...events[1], note: ex.notes[1].midi + 12 };
  events.splice(2, 1);
  const j = R.judge({ notes: ex.notes, tempo, events });
  const kinds = R.slips(ex, j).map((s) => s.kind);
  assert.deepEqual(kinds.slice(0, 3), ["wrong-step", "wrong-octave", "missed"]);
  const words = R.spotWords(ex, j);
  assert.ok(words.some((w) => /^Treble clef, (on|below|above) the staff: \d+ of \d+ missed or misread\.$/.test(w)), words);
  assert.ok(words.includes("1 off by one step: a line read as the next space, or the other way."));
  assert.ok(words.includes("1 in the wrong octave."));
  assert.deepEqual(R.badBars(ex, j), [...new Set([ex.notes[0].bar, ex.notes[1].bar, ex.notes[2].bar])]);
  assert.equal(R.verdict(j), `${j.passed ? "Passed" : "Not yet"}: ${j.score}. The line is 80.`);
  assert.equal(R.verdict({ ...j, score: 50, passed: false }), "Not yet: 50. The line is 80.");
  assert.equal(R.verdict({ mode: "step", score: 90 }), "Step mode: 90. Only a Flow take can pass the stage.");
  assert.equal(R.noteWords(ex, 1, j, "sharps"), `Bar ${ex.notes[1].bar + 1}, right hand: ${R.noteName(ex.notes[1].midi, "sharps")}, you played ${R.noteName(ex.notes[1].midi + 12, "sharps")}.`);
  assert.deepEqual(R.spotWords(ex, R.judge({ notes: ex.notes, tempo, events: perfect(ex, tempo) })), ["Nothing to fix here."]);
});

test("the record is what the API takes", () => {
  const ex = R.generate(R.stageOf(4), 77);
  const events = perfect(ex, 90);
  const j = R.judge({ notes: ex.notes, tempo: 90, events });
  const record = R.toRecord(ex, j, { tempo: 90, curtain: true, events });
  assert.equal(record.key, "G");
  assert.equal(record.hands, "L");
  assert.equal(record.difficulty, 1);
  assert.equal(record.mode, "flow");
  assert.equal(record.curtain, true);
  assert.equal(record.seed, 77);
  assert.equal(record.notes.length, ex.notes.length);
  assert.deepEqual(Object.keys(record.notes[0]), ["hand", "step", "acc", "midi", "beat", "dur"]);
  assert.equal(record.results.length, ex.notes.length);
  assert.equal(record.events, events);
  assert.equal(record.score, 100);
  assert.equal(record.judge_version, R.JUDGE_VERSION);
});

test("the stage line and the work line", () => {
  const report = { stage: { index: 4, key: "G", hands: "L", done: false }, focus: ["bass-below"] };
  assert.equal(R.stageLine(report, R.stageOf(4)), "Stage 5 of 36: G major, left hand. Pass it in Flow to move on.");
  assert.equal(R.stageLine(report, R.stageOf(1)), "Stage 2 of 36: C major, left hand. Passed already; the path is at stage 5.");
  assert.equal(R.stageLine(report, R.stageOf(9)), "Stage 10 of 36: D major, right hand. Ahead of the path, which is at stage 5. A pass here counts.");
  assert.equal(R.stageLine({ stage: { index: 35, done: true } }, R.stageOf(35)), "Stage 36 of 36: F# major, both hands. Every stage is passed. Keep reading, or raise the tempo.");
  assert.equal(R.workWords(report), "Work on: Bass clef, below the staff. The next exercises lean that way.");
  assert.equal(R.workWords({ focus: [] }), "");
  assert.equal(R.clampTempo("500"), 160);
  assert.equal(R.clampTempo(""), 72);
});

test("the keys lit while reading: due notes amber, a held right note green, a stray one red", () => {
  const ex = R.generate(R.stageOf(0), 5);
  const lit = R.litNotes(ex, null, [0], [ex.notes[0].midi, 40]);
  assert.deepEqual(lit, [{ midi: ex.notes[0].midi, className: "im-key-chord" }, { midi: 40, className: "im-key-outside" }]);
  assert.deepEqual(R.litNotes(ex, null, [0], []), [{ midi: ex.notes[0].midi, className: "im-key-pending" }]);
  const range = R.keyboardRange(ex);
  assert.equal(range.from % 12, 0);
  assert.equal(range.to % 12, 11);
});
