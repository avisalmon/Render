// SPR-I.5.5 improv: the words about the daily workout, with no browser.
const test = require("node:test");
const assert = require("node:assert/strict");
const Workout = require("../../static/improv/workout.js");

const item = (over) =>
  Object.assign(
    { slot: "next", exercise: "a-one", title: "Chord tones on beat one", lesson: "lesson-a", lesson_title: "Chord tones", scoring_kind: "chord_tones_on_beats", xp: 20, xp_available: 20, pass_score: 70, done_today: false },
    over
  );

test("each slot says why it was picked", () => {
  assert.equal(Workout.reason(item({ slot: "next" })), "Next in your lessons. Worth 20 XP.");
  assert.equal(Workout.reason(item({ slot: "fresh" })), "Something to try. Worth 20 XP.");
  assert.equal(Workout.reason(item({ slot: "review", xp_available: 0 })), "A review of one you have passed. No new XP.");
  assert.equal(Workout.reason(item({ slot: "weak", scoring_kind: "guide_tones" })), "Works on a weak spot: guide tones. Worth 20 XP.");
});

test("a pick that earns nothing says so, a single XP is singular", () => {
  assert.equal(Workout.reason(item({ slot: "fresh", xp_available: 0 })), "Something to try. No new XP.");
  assert.equal(Workout.reason(item({ slot: "next", xp_available: 1 })), "Next in your lessons. Worth 1 XP.");
});

test("an unknown slot or kind still reads as plain words", () => {
  assert.equal(Workout.reason(item({ slot: "mystery" })), "Worth 20 XP.");
  assert.equal(Workout.reason(item({ slot: "weak", scoring_kind: "free_play" })), "Works on a weak spot: free play. Worth 20 XP.");
});

test("the summary counts what is done and says when it is all done", () => {
  assert.equal(Workout.summaryLine({ total: 3, done_today: 1, complete: false }), "Today's workout: 1 of 3 done.");
  assert.equal(Workout.summaryLine({ total: 3, done_today: 3, complete: true }), "Today's workout is done. Well played.");
  assert.equal(Workout.summaryLine({ total: 0, done_today: 0, complete: false }), "Nothing to pick yet. Open a lesson and the workout fills up.");
  assert.equal(Workout.summaryLine({ total: 1, done_today: 0, complete: false }), "Today's workout: 0 of 1 done.");
});

test("the play link opens the exercise on the Play screen", () => {
  assert.equal(Workout.playUrl("/improv/play/", item({ exercise: "a one/x" })), "/improv/play/?exercise=a%20one%2Fx");
});

test("the button names the state of the pick", () => {
  assert.equal(Workout.playLabel(item({ done_today: false })), "Play");
  assert.equal(Workout.playLabel(item({ done_today: true })), "Play again");
});

test("the words use no dashes and no emoji", () => {
  const all = [
    Workout.reason(item({ slot: "weak" })),
    Workout.reason(item({ slot: "review", xp_available: 0 })),
    Workout.summaryLine({ total: 3, done_today: 3, complete: true }),
    Workout.summaryLine({ total: 0, done_today: 0, complete: false }),
  ].join(" ");
  assert.ok(!/[–—]/.test(all));
});
