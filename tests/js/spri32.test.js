// SPR-I.3.2 improv: naming what the player is holding. The golden cases in
// fixtures/chords.json are the real test: they are musical judgements, and the chord
// qualities come from the app's own theory table, so a change to the table shows up here.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const R = require(path.join(root, "static", "improv", "recognize.js"));
const theory = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "theory.json"), "utf8"));
const golden = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "chords.json"), "utf8"));

const qualities = theory.chord_qualities.map((q, index) => ({
  symbol: q.symbol,
  intervals: q.intervals,
  roles: q.roles,
  family: q.family,
  aliases: q.aliases,
  sort_order: q.sort_order === undefined ? index : q.sort_order,
}));
const PC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

const read = (notes, options) => R.recognize(notes, qualities, options);

// ------------------------------------------------------------------- the golden cases

test("every golden case is named the way a musician would name it", () => {
  assert.ok(golden.cases.length >= 30, "the fixtures are the test; there have to be enough of them");
  const wrong = [];
  for (const item of golden.cases) {
    const got = read(item.notes, { spelling: item.spelling || "sharps" });
    const where = `${JSON.stringify(item.notes)}${item.why ? ` (${item.why})` : ""}`;
    const complain = (what, had, wanted) => wrong.push(`${where}: ${what} is ${JSON.stringify(had)}, not ${JSON.stringify(wanted)}`);
    const kind = item.kind || "chord";
    if (got.kind !== kind) {
      complain("the kind", got.kind, kind);
      continue;
    }
    if (kind === "chord") {
      if (got.name !== item.name) complain("the name", got.name, item.name);
      if (item.exact !== undefined && got.exact !== item.exact) complain("exact", got.exact, item.exact);
      if (item.alternatives && String(got.alternatives) !== String(item.alternatives)) {
        complain("the alternatives", got.alternatives, item.alternatives);
      }
    } else if (kind === "notes") {
      if (got.text !== item.text) complain("the text", got.text, item.text);
      if (item.guesses && String(got.guesses) !== String(item.guesses)) complain("the guesses", got.guesses, item.guesses);
    }
  }
  assert.deepEqual(wrong, [], wrong.join(" | "));
});

test("a chord read exactly is offered with no alternatives, because there is nothing to choose", () => {
  const got = read([62, 65, 69, 72]);
  assert.equal(got.exact, true);
  assert.deepEqual(got.alternatives, []);
  assert.equal(got.slash, false);
});

// ------------------------------------------------------------- what the answer carries

test("the answer says the root, the quality and the bass, not only the name", () => {
  const got = read([52, 55, 60]);
  assert.equal(got.name, "C/E");
  assert.equal(got.root, "C");
  assert.equal(got.quality, "maj");
  assert.equal(got.bass, "E");
  assert.equal(got.slash, true);
  assert.deepEqual(got.notes, ["E3", "G3", "C4"]);
});

test("the same note in two octaves is one note, and the lowest one is the bass", () => {
  const plain = read([60, 64, 67]);
  const doubled = read([60, 64, 67, 72, 76]);
  assert.equal(doubled.name, plain.name);
  assert.equal(read([48, 64, 67, 72]).name, "C", "a low C doubled below does not make it a slash chord");
});

test("the notes come back in order however they were pressed", () => {
  assert.deepEqual(read([67, 60, 64]).notes, ["C4", "E4", "G4"]);
});

// ------------------------------------------------------------------ sharps or flats

test("notes and chords are spelled the way the player asked", () => {
  assert.equal(read([61, 65, 68], { spelling: "sharps" }).name, "C#");
  assert.equal(read([61, 65, 68], { spelling: "flats" }).name, "Db");
  assert.equal(read([61, 65, 68]).name, "C#", "sharps are the fallback");
  assert.equal(read([66, 70], { spelling: "flats" }).text, "Gb4 Bb4, a major third");
});

// ----------------------------------------------------------------- fewer than three

test("one note is a note, and two are two notes and the interval between them", () => {
  assert.deepEqual(read([]).kind, "none");
  assert.equal(read([60]).text, "C4");
  assert.equal(read([60]).interval, "");
  assert.equal(read([48, 60]).text, "C3 C4, an octave");
  assert.equal(read([60, 61]).text, "C4 C#4, a minor second");
  assert.equal(read([60, 71]).text, "C4 B4, a major seventh");
});

test("two notes are never forced into a chord name", () => {
  for (const pair of [[60, 64], [60, 67], [59, 65], [60, 70]]) {
    assert.equal(read(pair).kind, "notes", `${pair} was forced into a chord`);
    assert.equal(read(pair).name, undefined);
  }
});

test("a wide interval is still named by the interval inside it", () => {
  assert.equal(read([48, 76]).text, "C3 E5, a major third");
});

// ----------------------------------------------------------------- the jazz shell

test("a third and a seventh with no root offer both chords they belong to", () => {
  assert.deepEqual(read([59, 65]).guesses, ["C#7", "G7"], "ordered by root, spelled with sharps as asked");
  assert.deepEqual(read([59, 65], { spelling: "flats" }).guesses, ["Db7", "G7"]);
  assert.deepEqual(read([64, 70], { spelling: "flats" }).guesses, ["C7", "Gb7"]);
  assert.equal(read([59, 65]).guesses.length, 2, "a tritone belongs to exactly two dominant sevenths");
});

test("two notes that are nobody's third and seventh offer no guesses", () => {
  assert.deepEqual(read([60, 67]).guesses, []);
  assert.deepEqual(read([60, 62]).guesses, []);
});

// ------------------------------------------------------- when the reading is a guess

test("a chord with a note of it missing is a guess, with the other readings beside it", () => {
  const got = read([59, 65, 69]);
  assert.equal(got.exact, false);
  assert.ok(got.alternatives.length > 0);
  assert.ok(!got.alternatives.includes(got.name), "the winner is not its own alternative");
});

test("an alternative is a chord every held note belongs to, the lowest one included", () => {
  for (const held of [[59, 65, 69], [60, 63, 65, 67, 70], [55, 59, 64]]) {
    const got = read(held);
    const pcs = new Set(held.map((n) => ((n % 12) + 12) % 12));
    for (const name of got.alternatives || []) {
      const [, rootName, symbol] = /^([A-G]#?)([^/]*)/.exec(name);
      const quality = qualities.find((q) => q.symbol === (symbol || "maj"));
      assert.ok(quality, `${name} is not a chord the table knows`);
      const rootPc = PC_NAMES.indexOf(rootName);
      const covered = new Set(quality.intervals.map((i) => (rootPc + i) % 12));
      for (const pc of pcs) assert.ok(covered.has(pc), `${name} does not explain every note of ${held}`);
    }
  }
});

// --------------------------------------------------------------- a quiet table

test("with no chord table nothing is named, and nothing throws", () => {
  assert.equal(R.recognize([60, 64, 67], []).kind, "notes");
  assert.equal(R.recognize([60, 64, 67], null).kind, "notes");
  assert.equal(R.recognize(null, qualities).kind, "none");
});
