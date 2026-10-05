// SPR-I.3.3 improv: which scale a run of single notes fits. The scales come from the app's
// own theory table, so a change there shows up here. The page is glue and is checked by the
// pytest wrapper and in a real browser.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const R = require(path.join(root, "static", "improv", "recognize.js"));
const theory = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "theory.json"), "utf8"));

const scales = theory.scales.map((s, index) => ({
  slug: s.slug,
  name: s.name,
  intervals: s.intervals,
  family: s.family,
  order: index,
}));

const fits = (notes, options) => R.scaleFits(notes, scales, options);
const names = (notes, options) => fits(notes, options).fits.map((f) => f.name);

// ------------------------------------------------------- not enough to go on yet

test("three notes fit a dozen scales, so nothing is claimed until five have been heard", () => {
  for (const notes of [[], [60], [60, 62], [60, 62, 64], [60, 62, 64, 65]]) {
    const got = fits(notes);
    assert.equal(got.ready, false, `${notes} should not be enough`);
    assert.deepEqual(got.fits, []);
  }
  assert.equal(fits([60, 62, 64, 65]).needed, 1, "it says how many more notes it wants");
  assert.equal(fits([]).needed, 5);
});

test("the same note in several octaves is still one note, so it does not count towards the five", () => {
  assert.equal(fits([60, 72, 84, 62, 74]).ready, false);
  assert.equal(fits([60, 72, 84, 62, 74]).needed, 3);
});

// ------------------------------------------------------------------- the answer

test("five notes of a major scale name it, with the root that was played first", () => {
  const got = fits([60, 62, 64, 65, 67]);
  assert.equal(got.ready, true);
  assert.ok(got.fits.length > 0);
  assert.equal(got.fits[0].name, "C Major (Ionian)", "the name is the theory table's own");
  assert.equal(got.fits[0].root, "C");
  assert.equal(got.fits[0].slug, "major");
});

test("a pentatonic run is named as the pentatonic, not as the seven-note scale it sits in", () => {
  assert.equal(names([60, 62, 64, 67, 69])[0], "C Major pentatonic", "C D E G A is the pentatonic itself");
  assert.equal(names([60, 63, 65, 67, 70])[0], "C Minor pentatonic");
});

test("the blues scale is found when the blue note is played", () => {
  assert.equal(names([60, 63, 65, 66, 67, 70])[0], "C Blues");
});

test("the fits that are offered all really contain every note played", () => {
  const played = [62, 64, 65, 67, 69, 72];
  const pcs = new Set(played.map((n) => ((n % 12) + 12) % 12));
  const got = fits(played);
  assert.ok(got.fits.length > 0);
  for (const fit of got.fits) {
    const row = scales.find((s) => s.slug === fit.slug);
    const covered = new Set(row.intervals.map((i) => (fit.rootPc + i) % 12));
    for (const pc of pcs) assert.ok(covered.has(pc), `${fit.name} does not contain every note played`);
  }
});

test("a scale that leaves fewer of its own notes unplayed is the better fit", () => {
  const got = fits([60, 62, 64, 67, 69]);
  const unused = got.fits.map((f) => f.unused.length);
  assert.deepEqual(unused, [...unused].sort((a, b) => a - b), "the closest fit comes first");
  assert.equal(got.fits[0].unused.length, 0, "C major pentatonic is exactly those five notes");
});

test("only a few fits are offered, because a list of twenty is not an answer", () => {
  assert.ok(fits([60, 62, 64, 65, 67]).fits.length <= 3);
});

test("notes that fit no scale in the table say so plainly", () => {
  const got = fits([60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71]);
  assert.equal(got.ready, true);
  assert.deepEqual(got.fits, [], "all twelve notes are no scale at all");
});

// ------------------------------------------------------------------- spelling

test("a scale is spelled the way the player asked", () => {
  assert.equal(names([61, 63, 65, 66, 68], { spelling: "sharps" })[0].startsWith("C#"), true);
  assert.equal(names([61, 63, 65, 66, 68], { spelling: "flats" })[0].startsWith("Db"), true);
});

// --------------------------------------------------------- the last few seconds

test("only the notes of the last few seconds count, because a run moves on", () => {
  const events = [
    { note: 60, at: 0.0 },
    { note: 62, at: 0.5 },
    { note: 64, at: 1.0 },
    { note: 65, at: 5.0 },
    { note: 67, at: 5.5 },
    { note: 69, at: 6.0 },
    { note: 71, at: 6.5 },
    { note: 72, at: 7.0 },
  ];
  assert.deepEqual(R.recentNotes(events, 7.0, 3), [65, 67, 69, 71, 72], "the first three notes have gone by");
  assert.deepEqual(R.recentNotes(events, 1.0, 3), [60, 62, 64]);
  assert.deepEqual(R.recentNotes(events, 20, 3), [], "nothing was played in the last three seconds");
  assert.deepEqual(R.recentNotes([], 1, 3), []);
  assert.deepEqual(R.recentNotes(events, 7.0, 3).length, 5);
});

test("a window keeps the notes in the order they were played, repeats and all", () => {
  const events = [
    { note: 60, at: 1 },
    { note: 62, at: 2 },
    { note: 60, at: 3 },
  ];
  assert.deepEqual(R.recentNotes(events, 3, 5), [60, 62, 60]);
});

// ---------------------------------------------------------------- a quiet table

test("with no scale table nothing is claimed, and nothing throws", () => {
  assert.deepEqual(R.scaleFits([60, 62, 64, 65, 67], []).fits, []);
  assert.deepEqual(R.scaleFits([60, 62, 64, 65, 67], null).fits, []);
  assert.equal(R.scaleFits(null, scales).ready, false);
});
