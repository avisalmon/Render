// SPR-I.13.1 improv: the repertoire's rules. Run with: node --test tests/js/spri131.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const R = require("../../static/improv/reading.js");
const P = require("../../static/improv/repertoire.js");

const pieces = JSON.parse(fs.readFileSync(path.join(__dirname, "../../improv/seed_data/pieces.json"), "utf-8"));
const piece = (slug) => pieces.find((p) => p.slug === slug);
const beatMs = (tempo) => 60000 / tempo;
const perfect = (notes, tempo) => notes.map((n) => ({ t_ms: Math.round(n.beat * beatMs(tempo)), type: "on", note: n.midi, velocity: 80 }));

test("a slice starts at bar 0, beat 0 and keeps the notes in time order", () => {
  const ode = piece("ode-to-joy");
  const ex = P.slice(ode, 5, 8, "R");
  assert.equal(ex.bars, 4);
  assert.equal(ex.firstBar, 5);
  assert.equal(ex.beats, 4);
  assert.equal(ex.perPage, 4);
  assert.equal(ex.hands, "R");
  assert.equal(Math.min(...ex.notes.map((n) => n.beat)), 0);
  assert.equal(Math.min(...ex.notes.map((n) => n.bar)), 0);
  assert.equal(Math.max(...ex.notes.map((n) => n.bar)), 3);
  ex.notes.forEach((n, i) => assert.equal(n.index, i));
  for (let i = 1; i < ex.notes.length; i++) assert.ok(ex.notes[i].beat >= ex.notes[i - 1].beat);
  assert.equal(ex.notes.length, ode.notes.filter((n) => n.bar >= 5 && n.bar <= 8).length, "both hands are on the staff");
});

test("every note is inside its bar and under the control keys, in every piece", () => {
  for (const p of pieces) {
    const ex = P.slice(p, 1, p.bars, "B");
    for (const n of ex.notes) {
      assert.equal(Math.floor(n.beat / p.beats_per_bar + 1e-9), n.bar, `${p.slug}: note at beat ${n.beat} is in bar ${n.bar}`);
      assert.ok(n.midi < R.CONTROL_FLOOR, `${p.slug}: ${n.midi} reaches the control keys`);
      assert.ok(n.beat + n.dur <= (n.bar + 1) * p.beats_per_bar + 1e-9, `${p.slug}: a note runs past its bar line`);
    }
  }
});

test("a one-bar drill is one bar wide", () => {
  const ex = P.slice(piece("minuet-in-g"), 3, 3, "L");
  assert.equal(ex.bars, 1);
  assert.equal(ex.perPage, 1);
  assert.equal(ex.beats, 3);
  assert.ok(ex.notes.every((n) => n.bar === 0 && n.beat < 3));
});

test("a tie moves with the slice and is dropped when it would fall outside it", () => {
  const prelude = piece("prelude-in-c");
  const whole = P.slice(prelude, 1, 1, "B");
  const held = whole.notes.find((n) => n.ties);
  assert.ok(held, "bar 1 has a tied left-hand note");
  assert.deepEqual(held.ties, [[1.0, 1.0]]);
  assert.equal(held.hold, 1.75);
  const later = P.slice(prelude, 2, 2, "B");
  const tied = later.notes.find((n) => n.ties);
  assert.ok(tied.ties[0][0] < 4 && tied.ties[0][0] >= 0, "rebased into the one bar");
  const synthetic = { key: "C", beats_per_bar: 2, bars: 2, notes: [{ hand: "R", step: 28, acc: 0, midi: 60, beat: 1.5, dur: 0.5, bar: 1, ties: [[2.0, 1.0]] }], phrases: [] };
  const cut = P.slice(synthetic, 1, 1, "R");
  assert.equal(cut.notes[0].ties, undefined, "a tie into the next bar is not drawn in a one-bar slice");
});

test("an accidental is drawn where the piece wrote it, not where the key already says it", () => {
  const musette = P.slice(piece("musette-in-d"), 1, 8, "B");
  assert.ok(musette.notes.some((n) => n.acc !== 0), "the Musette has sharps");
  assert.ok(musette.notes.every((n) => n.shown === ""), "all of them are in the key of D");
  const prelude = P.slice(piece("prelude-in-c"), 1, 35, "B");
  const marked = prelude.notes.filter((n) => n.shown);
  assert.equal(marked.length, 12);
  assert.ok(marked.every((n) => ["#", "b", "n"].includes(n.shown)));
  assert.ok(prelude.notes.filter((n) => n.acc !== 0).length > marked.length, "a repeat in the same bar is not marked again");
});

test("a model player passes every phrase, either hand and both, and the whole of every piece", () => {
  for (const p of pieces) {
    const stretches = p.phrases.map((ph) => [ph.first_bar, ph.last_bar]);
    stretches.push([1, p.bars]);
    for (const [first, last] of stretches) {
      for (const hands of ["R", "L", "B"]) {
        const ex = P.slice(p, first, last, hands);
        const notes = R.activeNotes(ex);
        assert.ok(notes.length > 0, `${p.slug} ${first}-${last} ${hands} has notes to play`);
        const tempo = p.tempo_bpm;
        const j = R.judge({ notes, tempo, events: perfect(notes, tempo) });
        assert.equal(j.score, 100, `${p.slug} bars ${first}-${last} ${hands}: ${j.score}`);
        assert.equal(j.matched, notes.length);
      }
    }
  }
});

test("a model player also passes at the slow tempo", () => {
  for (const p of pieces) {
    const ex = P.slice(p, 1, p.bars, "B");
    const j = R.judge({ notes: ex.notes, tempo: p.slow_bpm, events: perfect(ex.notes, p.slow_bpm) });
    assert.ok(j.score >= 95, `${p.slug} at ${p.slow_bpm}: ${j.score}`);
  }
});

test("step mode finishes a whole piece with the right notes in order", () => {
  for (const p of pieces) {
    const ex = P.slice(p, 1, p.bars, "B");
    const run = R.createStepRun(ex.notes, [0, ex.bars - 1], "B");
    run.arrive(0);
    let guard = 0;
    while (run.target() !== null && guard++ < 5000) {
      for (const i of run.waiting()) run.press(ex.notes[i].midi, guard);
    }
    const s = run.summary();
    assert.ok(s.done, `${p.slug} step run is done`);
    assert.equal(s.score >= 90, true, `${p.slug} step score ${s.score}`);
  }
});

test("the left hand alone is judged on the left hand only", () => {
  const ex = P.slice(piece("ode-to-joy"), 1, 4, "L");
  const mine = R.activeNotes(ex);
  assert.ok(mine.every((n) => n.hand === "L"));
  assert.ok(mine.length < ex.notes.length);
});

test("the count-in is a bar, and four clicks when a bar is two beats", () => {
  assert.equal(P.countIn(4), 4);
  assert.equal(P.countIn(3), 3);
  assert.equal(P.countIn(2), 4);
});

test("each rung is said in plain words, with the tempo it asks for", () => {
  const rungs = [
    { key: "p1-R-slow", kind: "phrase", hands: "R", first_bar: 1, last_bar: 4, tempo: "slow", line: 80, phrase: 1 },
    { key: "p2-B-tempo", kind: "phrase", hands: "B", first_bar: 5, last_bar: 8, tempo: "tempo", line: 80, phrase: 2 },
    { key: "j1-2", kind: "join", hands: "B", first_bar: 1, last_bar: 8, tempo: "tempo", line: 80, phrase: 2 },
    { key: "whole-B-slow", kind: "whole", hands: "B", first_bar: 1, last_bar: 16, tempo: "slow", line: 80, phrase: null },
    { key: "perform", kind: "perform", hands: "B", first_bar: 1, last_bar: 16, tempo: "tempo", line: 90, phrase: null },
  ];
  assert.equal(P.rungWords(rungs[0]), "Bars 1 to 4: right hand, slowly");
  assert.equal(P.rungWords(rungs[1]), "Bars 5 to 8: both hands, at tempo");
  assert.equal(P.rungWords(rungs[2]), "Join, bars 1 to 8: both hands, at tempo");
  assert.equal(P.rungWords(rungs[3]), "The whole piece, both hands, slowly");
  assert.equal(P.rungWords(rungs[4]), "Performance: the whole piece, both hands, line 90");
  assert.equal(P.rungWords({ key: "drill", hands: "L", first_bar: 3, last_bar: 3 }), "Drill bar 3, left hand");
  const ode = piece("ode-to-joy");
  assert.equal(P.bpmOf(rungs[0], ode), ode.slow_bpm);
  assert.equal(P.bpmOf(rungs[1], ode), ode.tempo_bpm);
  assert.match(P.advice(rungs[0], ode), /^Right hand alone\./);
  assert.match(P.advice(rungs[0], ode), /Right hand starts on/);
  assert.equal(P.groupOf(rungs[0], ode).label, `Phrase 1: ${ode.phrases[0].title}`);
  assert.equal(P.groupOf(rungs[2], ode).id, "join");
  assert.equal(P.groupOf(rungs[4], ode).id, "whole");
});

test("a take is posted in the shape the API takes, within its limits", () => {
  const prelude = piece("prelude-in-c");
  const ex = P.slice(prelude, 1, prelude.bars, "B");
  const tempo = prelude.tempo_bpm;
  const events = perfect(ex.notes, tempo);
  const j = R.judge({ notes: ex.notes, tempo, events });
  const rung = { key: "whole-B-tempo", kind: "whole", hands: "B", first_bar: 1, last_bar: prelude.bars, tempo: "tempo", line: 80 };
  const record = P.toRecord(prelude, rung, ex, j, { tempo, curtain: false, events });
  assert.equal(record.piece, "prelude-in-c");
  assert.equal(record.rung, "whole-B-tempo");
  assert.equal(record.first_bar, 1);
  assert.equal(record.last_bar, 35);
  assert.equal(record.hands, "B");
  assert.equal(record.mode, "flow");
  assert.equal(record.notes.length, record.results.length);
  assert.ok(record.notes.length <= 800 && record.events.length <= 6000, "within the server's limits");
  assert.deepEqual(Object.keys(record.notes[0]).sort(), ["acc", "bar", "beat", "dur", "hand", "midi", "step"]);
  assert.equal(record.judge_version, R.JUDGE_VERSION);
  const drill = P.toRecord(prelude, { key: "drill" }, P.slice(prelude, 7, 8, "R"), j, { tempo, events: [] });
  assert.equal(drill.first_bar, 7);
  assert.equal(drill.last_bar, 8);
});

test("the path line says where the rung sits", () => {
  const entry = {
    total: 3,
    next: "b",
    done: false,
    rungs: [{ key: "a", passed: true, best: 91 }, { key: "b", passed: false, best: null }, { key: "c", passed: false, best: null }],
  };
  assert.equal(P.pathLine(entry, { key: "a" }), "Step 1 of 3. Passed already, best 91.");
  assert.equal(P.pathLine(entry, { key: "b" }), "Step 2 of 3. This is the next step on the path.");
  assert.equal(P.pathLine(entry, { key: "c" }), "Step 3 of 3. The path is at step 2. A pass here counts.");
  assert.match(P.pathLine(entry, { key: "drill" }), /never counts/);
  assert.equal(P.pieceLine({ title: "Ode to Joy", passed_count: 3, total: 22, done: false }), "Ode to Joy: 3 of 22");
  assert.equal(P.pieceLine({ title: "Ode to Joy", passed_count: 22, total: 22, done: true }), "Ode to Joy: finished");
});

test("a bar is named as printed, not as counted inside the slice", () => {
  const ex = P.slice(piece("ode-to-joy"), 5, 8, "R");
  const first = ex.notes.find((n) => n.hand === "R");
  assert.match(P.noteWords(ex, first.index, null, "sharps"), /^Bar 5, right hand: /);
  const result = { results: ex.notes.map((n) => ({ state: n.bar === 2 ? "missed" : "right", timing: "ontime", offset_ms: 0, played: null })) };
  assert.deepEqual(P.badBars(ex, result), [7]);
});
