// SPR-I.10.1 improv: the path with no locks. What is proved here is the part with no page in it: the
// order of the path, the lessons grouped by level, and the words a lesson ahead of the player carries.

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const L = require(path.join(root, "static", "improv", "lessons.js"));

const lesson = (slug, extra) => ({ slug, title: slug, track: "chord_tones", order: 1, level: 1, status: "published", prerequisite: null, path_order: null, state: "open", exercises_done: 0, exercises_total: 3, current: false, ...extra });

test("a numbered lesson comes before every unnumbered one, and unnumbered ones go by level, track and position", () => {
  const rows = [
    lesson("late", { level: 1, track: "chord_tones", order: 1 }),
    lesson("second", { path_order: 2 }),
    lesson("first", { path_order: 1, level: 3 }),
    lesson("scales", { level: 1, track: "scales_modes", order: 1 }),
    lesson("level-two", { level: 2, track: "chord_tones", order: 1 }),
  ];
  assert.deepEqual([...rows].sort(L.byPath).map((l) => l.slug), ["first", "second", "late", "scales", "level-two"]);
});

test("lessons are grouped by level, lowest first, each level in the order of the path", () => {
  const groups = L.groupByLevel([
    lesson("c", { level: 2, path_order: 3 }),
    lesson("b", { level: 1, path_order: 2 }),
    lesson("a", { level: 1, path_order: 1 }),
    lesson("x", { level: 3, path_order: 9 }),
  ]);
  assert.deepEqual(groups.map((g) => g.level), [1, 2, 3]);
  assert.deepEqual(groups[0].lessons.map((l) => l.slug), ["a", "b"]);
  assert.equal(groups[0].label, "Level 1, beginner");
  assert.equal(groups[1].label, "Level 2, moving on");
  assert.equal(groups[2].label, "Level 3, intermediate");
});

test("a lesson with a level the page does not know goes under Other, last", () => {
  const groups = L.groupByLevel([lesson("odd", { level: 0 }), lesson("ok", { level: 1 })]);
  assert.deepEqual(groups.map((g) => g.label), ["Level 1, beginner", "Other"]);
});

test("the small line names the track and what the lesson builds on", () => {
  const first = lesson("chord-tones", { title: "Chord tones on the beat" });
  const second = lesson("guide", { track: "guide_tones", prerequisite: "chord-tones" });
  assert.equal(L.describe(first, [first, second]), "Chord tones.");
  assert.equal(L.describe(second, [first, second]), "Guide tones, after Chord tones on the beat.");
});

test("a lesson ahead of the player says so and says it can still be started", () => {
  assert.equal(L.stateLabel(lesson("b", { state: "ahead" })), "Ahead of you");
  const all = [lesson("a", { title: "Chord tones" }), lesson("b", { prerequisite: "a", state: "ahead" })];
  assert.equal(L.aheadNote(all[1], all), "Builds on Chord tones, which you have not finished. You can start here anyway: plays count, and Today will follow you.");
  assert.match(L.aheadNote(lesson("b", { prerequisite: "gone" }), all), /^Builds on the lesson before it/);
});

test("nothing in the lessons words is locked any more", () => {
  const fs = require("node:fs");
  for (const name of ["lessons.js", "lessons-page.js", "lesson-page.js"]) {
    const src = fs.readFileSync(path.join(root, "static", "improv", name), "utf8");
    assert.doesNotMatch(src, /locked/i, name);
  }
  assert.equal(L.exerciseMark({ completed: false, ahead: true }), "");
  assert.equal(L.exerciseMark({ completed: true }), "Passed");
});
