// SPR-I.5.2 improv: progress. What is proved here is the part with no page in it: the words a
// lesson card and an exercise carry for where the player stands, the level line, and what the Play
// screen says about an exercise and about a take the server has just scored.

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const L = require(path.join(root, "static", "improv", "lessons.js"));
const P = require(path.join(root, "static", "improv", "play.js"));

const lesson = (extra) => ({ slug: "b", title: "Guide tones", state: "open", exercises_done: 0, exercises_total: 3, prerequisite: "a", ...extra });

test("a locked lesson says Locked, whatever it holds", () => {
  assert.equal(L.stateLabel(lesson({ state: "locked" })), "Locked");
  assert.equal(L.stateLabel(lesson({ state: "locked", exercises_total: 0 })), "Locked");
});

test("an open lesson says how many of its exercises are passed", () => {
  assert.equal(L.stateLabel(lesson({ exercises_done: 0 })), "0 of 3 passed");
  assert.equal(L.stateLabel(lesson({ exercises_done: 2 })), "2 of 3 passed");
});

test("a finished lesson says Done", () => {
  assert.equal(L.stateLabel(lesson({ state: "done", exercises_done: 3 })), "Done");
});

test("a lesson with nothing to play carries no tag", () => {
  assert.equal(L.stateLabel(lesson({ exercises_total: 0 })), "");
});

test("the reason a lesson is shut names the lesson that opens it", () => {
  const all = [{ slug: "a", title: "Chord tones" }, lesson({})];
  assert.equal(L.lockedReason(lesson({}), all), "Pass every exercise in Chord tones to open this.");
  assert.equal(L.lockedReason(lesson({ prerequisite: "gone" }), all), "Pass the lesson before this one to open it.");
  assert.equal(L.lockedReason(lesson({ prerequisite: null }), all), "Pass the lesson before this one to open it.");
});

test("the level line gives level, XP and the distance to the next level", () => {
  assert.equal(L.levelLine({ level: 1, xp: 0, level_floor: 0, next_level_at: 50 }), "Level 1, 0 XP. 50 XP to level 2.");
  assert.equal(L.levelLine({ level: 3, xp: 180, level_floor: 150, next_level_at: 300 }), "Level 3, 180 XP. 120 XP to level 4.");
});

test("at the top level there is no next level to name", () => {
  assert.equal(L.levelLine({ level: 50, xp: 61250, level_floor: 61250, next_level_at: null }), "Level 50, 61250 XP.");
});

test("no summary, no line", () => {
  assert.equal(L.levelLine(null), "");
  assert.equal(L.lessonsDoneLine(null), "");
});

test("the lessons line counts the published lessons the player has finished", () => {
  assert.equal(L.lessonsDoneLine({ lessons_done: 2, lessons_total: 6 }), "2 of 6 lessons done.");
  assert.equal(L.lessonsDoneLine({ lessons_done: 0, lessons_total: 1 }), "0 of 1 lesson done.");
  assert.equal(L.lessonsDoneLine({ lessons_done: 0, lessons_total: 0 }), "");
});

test("an exercise is marked passed, locked, or left plain", () => {
  assert.equal(L.exerciseMark({ completed: true, locked: false }), "Passed");
  assert.equal(L.exerciseMark({ completed: false, locked: true }), "Locked");
  assert.equal(L.exerciseMark({ completed: false, locked: false }), "");
});

const exercise = (extra) => ({ bars: 4, pass_score: 70, xp: 20, completed: false, locked: false, ...extra });

test("the Play screen states what an exercise asks and what it pays", () => {
  assert.equal(P.exerciseGoalLine(exercise({}), true), "4 bars, pass at 70, worth 20 XP.");
  assert.equal(P.exerciseGoalLine(exercise({ bars: 1 }), true), "1 bar, pass at 70, worth 20 XP.");
});

test("an exercise already passed says it earns no more", () => {
  const line = P.exerciseGoalLine(exercise({ completed: true }), true);
  assert.match(line, /passed this one already/);
  assert.doesNotMatch(line, /worth/);
});

test("an exercise in a locked lesson says a take earns nothing yet", () => {
  assert.match(P.exerciseGoalLine(exercise({ locked: true }), true), /locked.*earns nothing yet/);
});

test("changing the chart or the bars makes it free play, whatever else is true", () => {
  for (const extra of [{}, { completed: true }, { locked: true }]) {
    assert.match(P.exerciseGoalLine(exercise(extra), false), /free play and will not count/);
  }
});

test("a take the server scored as a pass reports the XP it earned", () => {
  assert.equal(P.completionNote({ id: 9, completion: { id: 1, xp_awarded: 40 } }), "Passed. +40 XP.");
});

test("a take that earned nothing says nothing extra", () => {
  assert.equal(P.completionNote({ id: 9, completion: null }), "");
  assert.equal(P.completionNote({ id: 9 }), "");
  assert.equal(P.completionNote(null), "");
});
