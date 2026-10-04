// SPR-I.2.1 improv: the chart parser and transposition (static/improv/chart.js).
// Run by tests/test_spri_2_1.py (node --test). No browser, no clock, no dependencies.
// The chord vocabulary is the seed file itself, so the parser is tested against the
// same symbols and aliases the database will hold.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const chart = require(path.join(root, "static", "improv", "chart.js"));
const theory = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "theory.json"), "utf8"));
const fixtures = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "charts.json"), "utf8"));
const qualities = theory.chord_qualities.map((q) => ({ symbol: q.symbol, aliases: q.aliases }));

const num = (n) => String(Math.round(n * 100) / 100);
const barText = (bar) => bar.chords.map((c) => `${c.name}@${num(c.beat)}/${num(c.beats)}`).join(" ");

function parse(text, options) {
  return chart.parseChart(text, qualities, options);
}

// ------------------------------------------------------------- golden: good charts

for (const c of fixtures.ok) {
  test(`parses: ${c.name}`, () => {
    const result = parse(c.chart, { beatsPerBar: c.beatsPerBar, homeKey: c.homeKey });
    assert.equal(result.ok, true, result.ok ? "" : JSON.stringify(result.error));
    assert.deepEqual(result.bars.map(barText), c.bars);
    if (c.keys) assert.deepEqual(result.bars.map((b) => (b.key ? b.key.name : null)), c.keys);
    if (c.written) assert.deepEqual(result.bars.map((b) => b.written), c.written);
    if (c.passes) assert.deepEqual(result.bars.map((b) => b.pass), c.passes);
  });
}

// -------------------------------------------------------------- golden: bad charts

for (const c of fixtures.errors) {
  test(`refuses: ${c.name}`, () => {
    const result = parse(c.chart);
    assert.equal(result.ok, false, "the chart should not parse");
    assert.equal(result.error.line, c.error.line, `line: ${JSON.stringify(result.error)}`);
    assert.equal(result.error.bar, c.error.bar, `bar: ${JSON.stringify(result.error)}`);
    assert.ok(
      result.error.message.toLowerCase().includes(c.error.includes.toLowerCase()),
      `message "${result.error.message}" should mention "${c.error.includes}"`
    );
    assert.equal(result.bars, undefined, "a bad chart must never hand back half a timeline");
  });
}

// ------------------------------------------------------------ the shape of a result

test("a played bar carries what the Play screen needs to light it and the editor to find it", () => {
  const result = parse("| Dm7 | G7 |\n| Cmaj7 |");
  const bar = result.bars[2];
  assert.equal(bar.written, 2);
  assert.equal(bar.line, 2);
  assert.equal(bar.n, 2);
  assert.equal(bar.pass, 1);
  assert.equal(bar.beats, 4);
  const chord = result.bars[0].chords[0];
  assert.equal(chord.typed, "Dm7");
  assert.equal(chord.root, 2);
  assert.equal(chord.quality, "m7");
  assert.equal(chord.bass, null);
});

test("a chord keeps the text it was typed as, even when the name is the canonical one", () => {
  const chord = parse("| D-7 |").bars[0].chords[0];
  assert.equal(chord.typed, "D-7");
  assert.equal(chord.name, "Dm7");
});

test("a slash chord has the bass as a pitch class", () => {
  const chord = parse("| C/E |").bars[0].chords[0];
  assert.equal(chord.root, 0);
  assert.equal(chord.bass, 4);
  assert.equal(chord.name, "C/E");
});

test("the result reports how many bars were written and how many are played", () => {
  const result = parse("|: C | G :| F |");
  assert.equal(result.writtenCount, 3);
  assert.equal(result.bars.length, 5);
});

test("the beats of every bar add up to the bar", () => {
  for (const c of fixtures.ok) {
    const result = parse(c.chart, { beatsPerBar: c.beatsPerBar });
    const size = c.beatsPerBar || 4;
    for (const bar of result.bars) {
      const total = bar.chords.reduce((sum, ch) => sum + ch.beats, 0);
      assert.ok(Math.abs(total - size) < 1e-9, `${c.name}: bar ${bar.n} adds up to ${total}`);
    }
  }
});

// ------------------------------------------------------------------ the options

test("the number of beats in a bar has to be a sensible number", () => {
  for (const bad of [0, -1, 2.5, 13, "four"]) {
    const result = parse("| C |", { beatsPerBar: bad });
    assert.equal(result.ok, false, String(bad));
  }
});

test("a home key that is not a key is refused", () => {
  assert.equal(parse("| C |", { homeKey: "H" }).ok, false);
});

test("a very long chart is refused instead of freezing the page", () => {
  const body = Array(1500).fill("C").join(" | ");
  assert.equal(parse(`| ${body} |`).ok, true);
  const repeated = parse(`|: ${body} :|`);
  assert.equal(repeated.ok, false);
  assert.ok(repeated.error.message.toLowerCase().includes("long"));
});

test("the parser does not change the chord vocabulary it was given", () => {
  const frozen = JSON.parse(JSON.stringify(qualities));
  parse("| Dm7 | G7 |");
  assert.deepEqual(qualities, frozen);
});

test("a chord vocabulary that lacks a quality leaves that chord unknown, not guessed", () => {
  const small = [{ symbol: "maj", aliases: [] }];
  const result = chart.parseChart("| C | Cm7 |", small);
  assert.equal(result.ok, false);
  assert.equal(result.error.bar, 2);
});

test("every symbol and every alias in the seed is understood on every root", () => {
  const names = ["C", "C#", "Db", "D", "Eb", "E", "F", "F#", "Gb", "G", "Ab", "A", "Bb", "B"];
  for (const q of qualities) {
    for (const spelling of [q.symbol, ...q.aliases]) {
      for (const r of names) {
        const typed = r + (spelling === "maj" ? "" : spelling);
        const result = parse(`| ${typed} |`);
        assert.equal(result.ok, true, `${typed}: ${result.ok ? "" : result.error.message}`);
        assert.equal(result.bars[0].chords[0].quality, q.symbol, typed);
      }
    }
  }
});

// -------------------------------------------------------------------------- keys

test("a key is read as a pitch class and a mode", () => {
  assert.deepEqual(chart.parseKey("Eb"), { pc: 3, minor: false, name: "Eb" });
  assert.deepEqual(chart.parseKey("F#m"), { pc: 6, minor: true, name: "F#m" });
  assert.deepEqual(chart.parseKey("Am"), { pc: 9, minor: true, name: "Am" });
  assert.deepEqual(chart.parseKey("C"), { pc: 0, minor: false, name: "C" });
});

test("anything that is not a key is null", () => {
  for (const bad of ["H", "", "e", "Cm7", "C#b", null, undefined, 3]) assert.equal(chart.parseKey(bad), null, String(bad));
});

// ------------------------------------------------------------------ transposition

const names = (parsed) => parsed.bars.map((b) => b.chords.map((c) => c.name).join(" "));

test("ii V I in C moved to Eb", () => {
  const moved = chart.transposeToKey(parse("| Dm7 | G7 | Cmaj7 |"), "C", "Eb");
  assert.deepEqual(names(moved), ["Fm7", "Bb7", "Ebmaj7"]);
});

test("a flat key is spelled with flats and a sharp key with sharps", () => {
  const original = parse("| Dm7 | G7 | Cmaj7 |");
  assert.deepEqual(names(chart.transposeToKey(original, "C", "Gb")), ["Abm7", "Db7", "Gbmaj7"]);
  assert.deepEqual(names(chart.transposeToKey(original, "C", "F#")), ["G#m7", "C#7", "F#maj7"]);
});

test("the usual keys are spelled the usual way", () => {
  const original = parse("| C | Am | F | G7 |");
  assert.deepEqual(names(chart.transposeToKey(original, "C", "F")), ["F", "Dm", "Bb", "C7"]);
  assert.deepEqual(names(chart.transposeToKey(original, "C", "G")), ["G", "Em", "C", "D7"]);
  assert.deepEqual(names(chart.transposeToKey(original, "C", "Bb")), ["Bb", "Gm", "Eb", "F7"]);
  assert.deepEqual(names(chart.transposeToKey(original, "C", "A")), ["A", "F#m", "D", "E7"]);
});

test("a minor target key uses the spelling of its relative major", () => {
  const original = parse("| Am7 | D7 | Gmaj7 |");
  assert.deepEqual(names(chart.transposeToKey(original, "G", "Dm")).slice(0, 1), ["Em7"]);
  assert.deepEqual(names(chart.transposeToKey(parse("| Am7b5 | D7 | Gm |"), "Gm", "Cm")), ["Dm7b5", "G7", "Cm"]);
});

test("a slash chord moves its bass with it", () => {
  const moved = chart.transposeToKey(parse("| C/E | Dm7/C |"), "C", "G");
  assert.deepEqual(names(moved), ["G/B", "Am7/G"]);
});

test("a key change marker moves along with the chords", () => {
  const original = parse("{key: C} | Dm7 | Cmaj7 | {key: Eb} | Fm7 | Ebmaj7 |");
  const moved = chart.transposeToKey(original, "C", "D");
  assert.deepEqual(moved.bars.map((b) => b.key.name), ["D", "D", "F", "F"]);
  assert.deepEqual(names(moved), ["Em7", "Dmaj7", "Gm7", "Fmaj7"]);
});

test("moving to the same key leaves the names as they were", () => {
  const original = parse("| Dm7 | G7 | Cmaj7 |");
  assert.deepEqual(names(chart.transposeToKey(original, "C", "C")), names(original));
});

test("up a fifth and back down again is where it started", () => {
  const original = parse("| Dm7 G7 | Cmaj7 | Am7 | D7/F# |");
  const there = chart.transposeToKey(original, "C", "G");
  const back = chart.transposeToKey(there, "G", "C");
  assert.deepEqual(names(back), names(original));
});

test("in all twelve keys every root lands exactly the right number of semitones away", () => {
  const original = parse("| Dm7 | G7/B | Cmaj7 | A7alt |");
  const keys = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"];
  keys.forEach((key, shift) => {
    const moved = chart.transposeToKey(original, "C", key);
    moved.bars.forEach((bar, i) => {
      bar.chords.forEach((c, j) => {
        const was = original.bars[i].chords[j];
        assert.equal(c.root, (was.root + shift) % 12, `${key} bar ${i + 1}`);
        assert.equal(c.bass, was.bass === null ? null : (was.bass + shift) % 12);
        assert.equal(c.quality, was.quality);
        assert.equal(c.beat, was.beat);
        assert.equal(c.beats, was.beats);
      });
    });
  });
});

test("a chart is moved by the distance between two keys, whichever way is shorter to say", () => {
  assert.equal(chart.semitonesBetween("C", "G"), -5);
  assert.equal(chart.semitonesBetween("C", "F#"), 6);
  assert.equal(chart.semitonesBetween("G", "C"), 5);
  assert.equal(chart.semitonesBetween("Eb", "Eb"), 0);
  assert.equal(chart.semitonesBetween("C", "Am"), -3, "a minor key counts by its tonic");
});

test("transposing does not change the chart it was given", () => {
  const original = parse("{key: C} | Dm7/C | G7 |");
  const before = JSON.stringify(original);
  chart.transposeToKey(original, "C", "Eb");
  assert.equal(JSON.stringify(original), before);
});

test("transposing keeps the bar numbers, lines and passes so the screen can still light the right bar", () => {
  const original = parse("|: C | [1 G :| [2 F |");
  const moved = chart.transposeToKey(original, "C", "D");
  assert.deepEqual(moved.bars.map((b) => [b.n, b.written, b.line, b.pass]), original.bars.map((b) => [b.n, b.written, b.line, b.pass]));
});

test("a key that is not a key cannot be moved to or from", () => {
  const original = parse("| C |");
  assert.throws(() => chart.transposeToKey(original, "C", "H"));
  assert.throws(() => chart.transposeToKey(original, "", "C"));
});

test("a chart that failed to parse cannot be transposed", () => {
  assert.throws(() => chart.transposeToKey(parse("| Xm7 |"), "C", "D"));
});
