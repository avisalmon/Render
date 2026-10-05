// SPR-I.3.5 improv: any chord or scale in any key, worked out from the theory table so the
// Reference screen only has to draw it. The page is glue and is checked by the pytest wrapper
// and in a real browser.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const Ref = require(path.join(root, "static", "improv", "reference.js"));
const theory = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "theory.json"), "utf8"));

const quality = (symbol) => theory.chord_qualities.find((q) => q.symbol === symbol);
const scale = (slug) => theory.scales.find((s) => s.slug === slug);

// ------------------------------------------------------------------------- keys

test("every key is offered, spelled the way the player asked", () => {
  const sharps = Ref.keyChoices("sharps");
  const flats = Ref.keyChoices("flats");
  assert.equal(sharps.length, 12);
  assert.deepEqual(sharps[1], [1, "C#"]);
  assert.deepEqual(flats[1], [1, "Db"]);
  assert.deepEqual(sharps[0], [0, "C"]);
});

// ------------------------------------------------------------------------ chords

test("a chord is laid out from its own row in the table, named and in order", () => {
  const view = Ref.chordView(quality("maj7"), 0, { spelling: "sharps" });
  assert.equal(view.name, "Cmaj7");
  assert.deepEqual(view.notes.map((n) => n.label), ["C4", "E4", "G4", "B4"]);
  assert.deepEqual(view.notes.map((n) => n.midi), [60, 64, 67, 71]);
  assert.deepEqual(view.notes.map((n) => n.role), ["root", "third", "fifth", "seventh"]);
  assert.deepEqual(view.notes.map((n) => n.step), ["1", "3", "5", "7"]);
  assert.deepEqual(view.pcs, [0, 4, 7, 11]);
});

test("a plain major triad is written with no symbol at all, as it is on a chart", () => {
  assert.equal(Ref.chordView(quality("maj"), 2, {}).name, "D");
  assert.equal(Ref.chordView(quality("m7"), 2, {}).name, "Dm7");
});

test("a chord in another key is the same shape moved, and stays in one reach of the hand", () => {
  const view = Ref.chordView(quality("m7"), 10, { spelling: "flats" });
  assert.equal(view.name, "Bbm7");
  assert.deepEqual(view.notes.map((n) => n.label), ["Bb4", "Db5", "F5", "Ab5"]);
  const spread = view.notes[view.notes.length - 1].midi - view.notes[0].midi;
  assert.ok(spread <= 12, `a reference chord should sit inside an octave, not span ${spread}`);
});

test("a role the table spells with an underscore is written for a person to read", () => {
  const view = Ref.chordView(quality("m7b5"), 0, {});
  assert.deepEqual(view.notes.map((n) => n.role), ["root", "third", "flat fifth", "seventh"]);
  assert.deepEqual(view.notes.map((n) => n.step), ["1", "b3", "b5", "b7"]);
});

test("a chord says which scales fit it, in the order the table prefers", () => {
  const row = { ...quality("m7"), scales: [
    { slug: "aeolian", name: "Aeolian (natural minor)", preference: 2, note: "as a vi chord" },
    { slug: "dorian", name: "Dorian", preference: 1, note: "as a ii chord" },
  ] };
  const view = Ref.chordView(row, 2, {});
  assert.deepEqual(view.scales.map((s) => s.name), ["D Dorian", "D Aeolian (natural minor)"]);
  assert.deepEqual(view.scales.map((s) => s.slug), ["dorian", "aeolian"]);
  assert.equal(view.scales[0].note, "as a ii chord");
});

test("a chord with no scales in the table is still laid out", () => {
  const view = Ref.chordView({ ...quality("maj"), scales: undefined }, 0, {});
  assert.deepEqual(view.scales, []);
  assert.equal(view.notes.length, 3);
});

// ------------------------------------------------------------------------ scales

test("a scale is laid out with its degrees, root to root", () => {
  const view = Ref.scaleView(scale("dorian"), 2, { spelling: "sharps" });
  assert.equal(view.name, "D Dorian");
  assert.deepEqual(view.notes.map((n) => n.label), ["D4", "E4", "F4", "G4", "A4", "B4", "C5", "D5"]);
  assert.deepEqual(view.notes.map((n) => n.step), ["1", "2", "b3", "4", "5", "6", "b7", "1"]);
  assert.deepEqual(view.pcs, [2, 4, 5, 7, 9, 11, 0]);
  assert.equal(view.notes[view.notes.length - 1].octave, true, "the last note closes the scale");
});

test("the blues scale keeps its blue note", () => {
  const view = Ref.scaleView(scale("blues"), 0, {});
  assert.deepEqual(view.notes.map((n) => n.step), ["1", "b3", "4", "b5", "5", "b7", "1"]);
});

test("a scale in a flat key is spelled with flats", () => {
  const view = Ref.scaleView(scale("major"), 10, { spelling: "flats" });
  assert.equal(view.name, "Bb Major (Ionian)");
  assert.deepEqual(view.notes.map((n) => n.label), ["Bb4", "C5", "D5", "Eb5", "F5", "G5", "A5", "Bb5"]);
});

test("a scale says which chords it fits", () => {
  // The rows are exactly what GET /improv/api/chord-scales/?scale=dorian sends.
  const view = Ref.scaleView(scale("dorian"), 2, {}, [
    { quality_symbol: "m7", scale_slug: "dorian", preference: 1, note: "as a ii chord" },
    { quality_symbol: "m6", scale_slug: "dorian", preference: 2, note: "" },
  ]);
  assert.deepEqual(view.chords.map((c) => c.name), ["Dm7", "Dm6"]);
  assert.equal(view.chords[0].note, "as a ii chord");
  assert.deepEqual(Ref.scaleView(scale("dorian"), 2, {}).chords, []);
});

// --------------------------------------------------------------- the keyboard range

test("the keyboard shows two octaves from the C below the chord, so the shape is visible", () => {
  const range = Ref.keyboardRange(Ref.chordView(quality("maj7"), 0, {}));
  assert.equal(range.from % 12, 0, "a keyboard starts on a C");
  assert.ok(range.from <= 60 && range.to >= 71);
  assert.ok(range.to - range.from >= 24);
  const high = Ref.keyboardRange(Ref.scaleView(scale("major"), 11, {}));
  assert.ok(high.to >= 71 + 12, "a scale starting high still fits on the keyboard shown");
});

// ------------------------------------------------------------------- bad input

test("a missing row names nothing and throws nothing", () => {
  assert.equal(Ref.chordView(null, 0, {}), null);
  assert.equal(Ref.scaleView(null, 0, {}), null);
  assert.equal(Ref.chordView({ symbol: "x", intervals: [] }, 0, {}), null);
});
