// SPR-I.8.4 improv: the chord pool, the positions, the matcher and the prompt order of the chord trainer.
// Pure, no browser. Run by tests/test_spri_8_4.py (node --test).

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Drill = require(path.join("..", "..", "static", "improv", "drill.js"));

function seeded(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const names = (pool) => pool.map((c) => c.name);

test("the keys come in circle-of-fifths order from G", () => {
  assert.deepEqual(Drill.CIRCLE, [7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5, 0]);
  assert.deepEqual(Drill.CIRCLE.map((pc) => Drill.keyName(pc, "sharps")), ["G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F", "C"]);
  assert.equal(Drill.keyName(6, "flats"), "Gb");
});

test("level 1 is the seven triads of the key", () => {
  assert.deepEqual(names(Drill.pool(0, 1, "sharps")), ["C", "Dm", "Em", "F", "G", "Am", "Bdim"]);
  assert.deepEqual(names(Drill.pool(7, 1, "sharps")), ["G", "Am", "Bm", "C", "D", "Em", "F#dim"]);
});

test("level 2 is the seven sevenths of the key", () => {
  assert.deepEqual(names(Drill.pool(0, 2, "sharps")), ["Cmaj7", "Dm7", "Em7", "Fmaj7", "G7", "Am7", "Bm7b5"]);
});

test("level 3 adds the borrowed I7 and IV7 after the sevenths", () => {
  const pool = Drill.pool(0, 3, "sharps");
  assert.deepEqual(names(pool), ["Cmaj7", "Dm7", "Em7", "Fmaj7", "G7", "Am7", "Bm7b5", "C7", "F7"]);
  assert.deepEqual(pool.slice(7).map((c) => c.kind), ["borrowed", "borrowed"]);
  assert.deepEqual(pool.slice(7).map((c) => c.roman), ["I7", "IV7"]);
});

test("every chord is spelled in its key", () => {
  assert.deepEqual(names(Drill.pool(1, 1, "sharps")), ["Db", "Ebm", "Fm", "Gb", "Ab", "Bbm", "Cdim"]);
  assert.deepEqual(names(Drill.pool(6, 1, "sharps")), ["F#", "G#m", "A#m", "B", "C#", "D#m", "E#dim"]);
  assert.deepEqual(names(Drill.pool(6, 1, "flats")), ["Gb", "Abm", "Bbm", "Cb", "Db", "Ebm", "Fdim"]);
});

test("the tones of a chord are spelled by the letters, so a seventh is never an odd sharp", () => {
  const byName = (pc, level, name) => Drill.pool(pc, level, "sharps").find((c) => c.name === name);
  assert.deepEqual(byName(0, 2, "Cmaj7").tones, ["C", "E", "G", "B"]);
  assert.deepEqual(byName(0, 1, "Bdim").tones, ["B", "D", "F"]);
  assert.deepEqual(byName(0, 3, "C7").tones, ["C", "E", "G", "Bb"]);
  assert.deepEqual(byName(0, 3, "F7").tones, ["F", "A", "C", "Eb"]);
  assert.deepEqual(byName(1, 2, "Cm7b5").tones, ["C", "Eb", "Gb", "Bb"]);
  assert.deepEqual(byName(6, 2, "E#m7b5").tones, ["E#", "G#", "B", "D#"]);
});

test("a chord carries its quality symbol, intervals and pitch classes from the table's own names", () => {
  const g7 = Drill.pool(0, 2, "sharps").find((c) => c.name === "G7");
  assert.equal(g7.symbol, "7");
  assert.deepEqual(g7.intervals, [0, 4, 7, 10]);
  assert.equal(g7.rootPc, 7);
  assert.deepEqual(g7.pcs, [2, 5, 7, 11]);
  assert.equal(g7.roman, "V");
  assert.equal(g7.degree, 5);
  assert.equal(Drill.pool(0, 1, "sharps")[0].symbol, "maj");
});

test("triads have three positions and sevenths four", () => {
  assert.equal(Drill.positionCount(Drill.pool(0, 1, "sharps")[0]), 3);
  assert.equal(Drill.positionCount(Drill.pool(0, 2, "sharps")[0]), 4);
  assert.equal(Drill.positionCount(Drill.pool(0, 3, "sharps")[8]), 4);
});

test("first position is root position, second the first inversion, and the title says both", () => {
  const cmaj7 = Drill.pool(0, 2, "sharps")[0];
  const first = Drill.makePrompt(0, 2, cmaj7, 1, "sharps");
  const second = Drill.makePrompt(0, 2, cmaj7, 2, "sharps");
  const fourth = Drill.makePrompt(0, 2, cmaj7, 4, "sharps");
  assert.equal(first.title, "Cmaj7, first position");
  assert.equal(first.detail, "root position, C in the bass");
  assert.equal(first.inversion, "root position");
  assert.equal(second.inversion, "first inversion");
  assert.equal(second.title, "Cmaj7, second position");
  assert.equal(second.detail, "first inversion, E in the bass");
  assert.equal(second.slash, "Cmaj7/E");
  assert.equal(first.slash, "Cmaj7");
  assert.equal(fourth.title, "Cmaj7, fourth position");
  assert.equal(fourth.detail, "third inversion, B in the bass");
});

test("the bass of each position is the next tone up the chord", () => {
  const g7 = Drill.pool(0, 2, "sharps")[4];
  const bass = [1, 2, 3, 4].map((p) => Drill.makePrompt(0, 2, g7, p, "sharps").bassPc);
  assert.deepEqual(bass, [7, 11, 2, 5]);
  const triad = Drill.pool(0, 1, "sharps")[0];
  assert.deepEqual([1, 2, 3].map((p) => Drill.makePrompt(0, 1, triad, p, "sharps").bassPc), [0, 4, 7]);
});

test("a position outside the chord is refused", () => {
  const triad = Drill.pool(0, 1, "sharps")[0];
  assert.throws(() => Drill.makePrompt(0, 1, triad, 4, "sharps"), /position/);
  assert.throws(() => Drill.makePrompt(0, 1, triad, 0, "sharps"), /position/);
});

test("a prompt is plain data that can be stored", () => {
  const prompt = Drill.makePrompt(7, 2, Drill.pool(7, 2, "sharps")[4], 3, "sharps");
  assert.deepEqual(JSON.parse(JSON.stringify(prompt)), prompt);
  assert.equal(prompt.key_pc, 7);
  assert.equal(prompt.level, 2);
  assert.equal(prompt.position, 3);
  assert.equal(prompt.name, "D7");
  assert.deepEqual(prompt.pcs, [0, 2, 6, 9]);
});

test("the shown voicing has the expected bass lowest and rises through the chord", () => {
  for (const pc of [0, 7, 1, 6]) {
    for (const level of [1, 2, 3]) {
      for (const chord of Drill.pool(pc, level, "sharps")) {
        for (let p = 1; p <= Drill.positionCount(chord); p++) {
          const prompt = Drill.makePrompt(pc, level, chord, p, "sharps");
          const notes = Drill.voicing(prompt);
          assert.equal(notes.length, chord.intervals.length);
          assert.equal(notes[0] % 12, prompt.bassPc);
          assert.deepEqual([...notes].sort((a, b) => a - b), notes);
          assert.equal(new Set(notes.map((n) => n % 12)).size, notes.length);
          assert.ok(notes[0] >= Drill.DISPLAY.from && notes[notes.length - 1] <= Drill.DISPLAY.to, `${prompt.title} ${notes}`);
          assert.deepEqual([...new Set(notes.map((n) => n % 12))].sort((a, b) => a - b), prompt.pcs);
        }
      }
    }
  }
});

// ------------------------------------------------------------------ the matcher

const cmaj7second = () => Drill.makePrompt(0, 2, Drill.pool(0, 2, "sharps")[0], 2, "sharps");

test("the right notes with the expected bass are right, in any octave and either hand", () => {
  const prompt = cmaj7second();
  assert.equal(Drill.judgeHeld(prompt, [64, 67, 71, 72]).state, "right");
  assert.equal(Drill.judgeHeld(prompt, [52, 79, 71, 72]).state, "right");
  assert.equal(Drill.judgeHeld(prompt, [40, 64, 67, 71, 72]).state, "right");
});

test("a doubled note is fine", () => {
  assert.equal(Drill.judgeHeld(cmaj7second(), [52, 64, 67, 71, 72]).state, "right");
});

test("the right notes with the wrong bass are wrong, and the reason says the bass", () => {
  const result = Drill.judgeHeld(cmaj7second(), [60, 64, 67, 71]);
  assert.equal(result.state, "wrong");
  assert.equal(result.reason, "bass");
});

test("a note outside the chord is wrong at once, even before the chord is complete", () => {
  const stray = Drill.judgeHeld(cmaj7second(), [64, 67, 71, 72, 74]);
  assert.equal(stray.state, "wrong");
  assert.equal(stray.reason, "extra");
  assert.deepEqual(stray.extra, [2]);
  assert.equal(Drill.judgeHeld(cmaj7second(), [64, 66]).state, "wrong");
});

test("fewer notes than the chord are waiting, not wrong", () => {
  const partial = Drill.judgeHeld(cmaj7second(), [64, 67]);
  assert.equal(partial.state, "incomplete");
  assert.deepEqual(partial.missing, [0, 11]);
  assert.equal(Drill.judgeHeld(cmaj7second(), []).state, "incomplete");
  assert.equal(Drill.judgeHeld(cmaj7second(), [60, 64]).state, "incomplete");
});

test("a triad is right with three notes and its bass", () => {
  const dm = Drill.makePrompt(0, 1, Drill.pool(0, 1, "sharps")[1], 3, "sharps");
  assert.equal(dm.bassPc, 9);
  assert.equal(Drill.judgeHeld(dm, [57, 62, 65]).state, "right");
  assert.equal(Drill.judgeHeld(dm, [45, 50, 53]).state, "right");
  assert.equal(Drill.judgeHeld(dm, [50, 53, 57]).state, "wrong");
});

test("the notes of a seventh played as a triad are waiting for the seventh", () => {
  const g7 = Drill.makePrompt(0, 2, Drill.pool(0, 2, "sharps")[4], 1, "sharps");
  assert.equal(Drill.judgeHeld(g7, [55, 59, 62]).state, "incomplete");
  assert.equal(Drill.judgeHeld(g7, [55, 59, 62, 65]).state, "right");
});

// ------------------------------------------------------------------ the order of prompts

test("a drill for a key asks every chord in every position once", () => {
  for (const [level, count] of [[1, 21], [2, 28], [3, 36]]) {
    const prompts = Drill.makeDrill(0, level, "sharps", seeded(5));
    assert.equal(prompts.length, count);
    assert.equal(new Set(prompts.map((p) => p.id)).size, count);
    assert.ok(prompts.every((p) => p.key_pc === 0 && p.level === level));
  }
});

test("a drill never asks the same chord twice running when it can avoid it", () => {
  for (let seed = 1; seed <= 30; seed++) {
    const prompts = Drill.makeDrill(7, 2, "sharps", seeded(seed));
    for (let i = 1; i < prompts.length; i++) assert.notEqual(prompts[i].chordId, prompts[i - 1].chordId, `seed ${seed} at ${i}`);
  }
});

test("a different seed gives a different order, the same seed the same", () => {
  const a = Drill.makeDrill(0, 1, "sharps", seeded(1)).map((p) => p.id);
  const b = Drill.makeDrill(0, 1, "sharps", seeded(1)).map((p) => p.id);
  const c = Drill.makeDrill(0, 1, "sharps", seeded(2)).map((p) => p.id);
  assert.deepEqual(a, b);
  assert.notDeepEqual(a, c);
});

test("the circle asks each chord of each key once, round the keys from G", () => {
  const prompts = Drill.makeCircle(1, "sharps", seeded(3));
  assert.equal(prompts.length, 84);
  assert.deepEqual([...new Set(prompts.map((p) => p.key_pc))], Drill.CIRCLE);
  for (const pc of Drill.CIRCLE) {
    const inKey = prompts.filter((p) => p.key_pc === pc);
    assert.equal(inKey.length, 7);
    assert.deepEqual([...new Set(inKey.map((p) => p.degree))].sort(), [1, 2, 3, 4, 5, 6, 7]);
  }
  assert.equal(Drill.makeCircle(3, "sharps", seeded(3)).length, 108);
  assert.equal(Drill.makeCircle(2, "sharps", seeded(3)).length, 84);
});

test("the circle's positions are drawn from the ones the chord has", () => {
  const prompts = Drill.makeCircle(2, "sharps", seeded(9));
  assert.ok(prompts.every((p) => p.position >= 1 && p.position <= 4));
  const triads = Drill.makeCircle(1, "sharps", seeded(9));
  assert.ok(triads.every((p) => p.position >= 1 && p.position <= 3));
  assert.ok(new Set(prompts.map((p) => p.position)).size > 1);
});

test("the learn list gives every chord of the key with each of its positions", () => {
  const rows = Drill.learnList(0, 3, "sharps");
  assert.equal(rows.length, 9);
  assert.equal(rows[0].chord.name, "Cmaj7");
  assert.equal(rows[0].prompts.length, 4);
  assert.equal(rows[0].prompts[1].title, "Cmaj7, second position");
  assert.equal(Drill.learnList(0, 1, "sharps")[0].prompts.length, 3);
});

// ------------------------------------------------------------------ the record

test("an answered prompt becomes a stored attempt", () => {
  const prompt = cmaj7second();
  const body = Drill.toAttempt(prompt, { wrongTries: 0, hintUsed: false, skipped: false, responseMs: 2412.4, notes: [64, 67, 71, 72], called: "Cmaj7/E" });
  assert.equal(body.kind, "chord_position");
  assert.equal(body.key_pc, 0);
  assert.equal(body.level, 2);
  assert.deepEqual(body.prompt, prompt);
  assert.deepEqual(body.answer, { notes: [64, 67, 71, 72], called: "Cmaj7/E" });
  assert.equal(body.is_correct, true);
  assert.equal(body.wrong_tries, 0);
  assert.equal(body.hint_used, false);
  assert.equal(body.skipped, false);
  assert.equal(body.response_ms, 2412);
});

test("a right answer after wrong tries is stored, but not as correct", () => {
  const body = Drill.toAttempt(cmaj7second(), { wrongTries: 2, hintUsed: false, skipped: false, responseMs: 5000, notes: [64, 67, 71, 72], called: "" });
  assert.equal(body.is_correct, false);
  assert.equal(body.wrong_tries, 2);
  assert.equal(body.response_ms, 5000);
});

test("a hinted answer is correct but wears the hint flag", () => {
  const body = Drill.toAttempt(cmaj7second(), { wrongTries: 0, hintUsed: true, skipped: false, responseMs: 4000, notes: [], called: "" });
  assert.equal(body.is_correct, true);
  assert.equal(body.hint_used, true);
});

test("a skipped prompt is a miss with no time", () => {
  const body = Drill.toAttempt(cmaj7second(), { wrongTries: 1, hintUsed: false, skipped: true, responseMs: 7000, notes: [60], called: "C" });
  assert.equal(body.skipped, true);
  assert.equal(body.is_correct, false);
  assert.equal(body.response_ms, null);
});

test("the words for a result are plain", () => {
  assert.equal(Drill.seconds(2412), "2.4 s");
  assert.equal(Drill.seconds(10000), "10.0 s");
  assert.equal(Drill.seconds(null), "no time");
});

test("the words for a wrong try say what was played and why it missed", () => {
  const prompt = cmaj7second();
  assert.equal(Drill.wrongWords(prompt, { state: "wrong", reason: "bass", extra: [] }, "Cmaj7"), "That was Cmaj7. The right notes, but the lowest note should be E.");
  assert.equal(Drill.wrongWords(prompt, { state: "wrong", reason: "extra", extra: [2] }, "Cmaj9"), "That was Cmaj9. D is not in this chord.");
  assert.equal(Drill.wrongWords(prompt, { state: "wrong", reason: "extra", extra: [2, 5] }, ""), "D and F are not in this chord.");
});
