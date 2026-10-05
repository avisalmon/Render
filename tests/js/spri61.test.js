// SPR-I.6.1 improv: the words and shapes of the Today and Progress screens.
//
// The server says where the player stands; today.js turns that into the goal ring, the lesson to
// go on with, the level bar and the five-week calendar. Dates are read as calendar dates and never
// through the machine's timezone, which is what the calendar tests pin down.

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const T = require(path.join(root, "static", "improv", "today.js"));
const Bests = require(path.join(root, "static", "improv", "bests.js"));
const Lessons = require(path.join(root, "static", "improv", "lessons.js"));

const report = (over) => ({
  today: "2026-10-05",
  goal_minutes: 15,
  today_seconds: 0,
  today_minutes: 0,
  goal_met: false,
  streak: 0,
  best_streak: 0,
  log: [],
  ...over,
});

// ---------------------------------------------------------------- the ring

test("the ring is how much of the goal is done, held between 0 and 1", () => {
  assert.equal(T.ringFraction(report()), 0);
  assert.equal(T.ringFraction(report({ today_seconds: 450 })), 0.5);
  assert.equal(T.ringFraction(report({ today_seconds: 900 })), 1);
  assert.equal(T.ringFraction(report({ today_seconds: 5000 })), 1);
  assert.equal(T.ringFraction(report({ today_seconds: -5 })), 0);
});

test("a goal of nothing reads as met and never divides by zero", () => {
  assert.equal(T.ringFraction(report({ goal_minutes: 0 })), 1);
});

test("the ring says the minutes, or that the goal is met", () => {
  assert.equal(T.ringLabel(report({ today_minutes: 7 })), "7 of 15 min");
  assert.equal(T.ringLabel(report({ goal_met: true, today_minutes: 16 })), "Goal met");
});

// ---------------------------------------------------------------- where to go on

test("the lesson line says where the player stands", () => {
  const next = { state: "continue", lesson: "a", title: "Chord tones", exercises_done: 1, exercises_total: 3 };
  assert.equal(T.continueLine(next), "Chord tones: 1 of 3 passed.");
  assert.equal(T.continueLine({ ...next, state: "start", exercises_done: 0 }), "Next up: Chord tones.");
  assert.match(T.continueLine({ state: "finished" }), /Every lesson is done/);
  assert.equal(T.continueLine({ state: "none" }), "No lessons are open yet.");
  assert.equal(T.continueLine(null), "No lessons are open yet.");
});

test("the button says Continue only for a lesson already begun", () => {
  assert.equal(T.continueLabel({ state: "continue" }), "Continue");
  assert.equal(T.continueLabel({ state: "start" }), "Start");
});

test("the lesson address is the lessons page and the slug, encoded", () => {
  assert.equal(T.lessonUrl("/improv/lessons/", { lesson: "chord-tones-1" }), "/improv/lessons/chord-tones-1/");
  assert.equal(T.lessonUrl("/improv/lessons/", { lesson: "a b" }), "/improv/lessons/a%20b/");
});

// ---------------------------------------------------------------- the level

test("the level line and bar", () => {
  const s = { level: 2, xp: 80, level_floor: 50, next_level_at: 150, exercises_done: 4, lessons_done: 1, lessons_total: 6 };
  assert.equal(T.levelLine(s), "Level 2, 80 XP. 70 XP to level 3.");
  assert.deepEqual(T.levelBar(s), { value: 30, max: 100 });
  assert.equal(T.lessonsLine(s), "1 of 6 lessons done, 4 exercises passed.");
});

test("at the top level there is no bar and no next level", () => {
  const s = { level: 50, xp: 61250, level_floor: 61250, next_level_at: null, exercises_done: 1, lessons_done: 1, lessons_total: 1 };
  assert.equal(T.levelLine(s), "Level 50, 61250 XP.");
  assert.equal(T.levelBar(s), null);
  assert.equal(T.lessonsLine(s), "1 of 1 lesson done, 1 exercise passed.");
});

test("nothing loaded gives empty words, not a crash", () => {
  assert.equal(T.levelLine(null), "");
  assert.equal(T.levelBar(null), null);
  assert.equal(T.lessonsLine({ lessons_total: 0 }), "");
});

test("Today and Lessons say the level in the same words", () => {
  for (const s of [
    { level: 1, xp: 0, next_level_at: 50 },
    { level: 3, xp: 200, next_level_at: 300 },
    { level: 50, xp: 100, next_level_at: null },
  ]) {
    assert.equal(T.levelLine(s), Lessons.levelLine(s));
  }
});

// ---------------------------------------------------------------- the calendar

test("the calendar is five weeks, Monday first, the last one holding today", () => {
  // 2026-10-05 is a Monday.
  const weeks = T.calendar(report());
  assert.equal(weeks.length, 5);
  assert.ok(weeks.every((w) => w.length === 7));
  assert.equal(weeks[0][0].date, "2026-09-07");
  assert.equal(weeks[4][0].date, "2026-10-05");
  assert.equal(weeks[4][0].today, true);
  assert.equal(weeks.flat().filter((c) => c.today).length, 1);
});

test("a day later in the week than today is the future and has no state of its own", () => {
  const weeks = T.calendar(report({ today: "2026-10-07" })); // a Wednesday
  assert.equal(weeks[4][2].today, true);
  assert.deepEqual(weeks[4].map((c) => c.state), ["rest", "rest", "rest", "future", "future", "future", "future"]);
  assert.equal(weeks[4][0].date, "2026-10-05");
  assert.equal(weeks[0][0].date, "2026-09-07");
});

test("a Sunday today ends the last week", () => {
  const weeks = T.calendar(report({ today: "2026-10-11" }));
  assert.equal(weeks[4][6].date, "2026-10-11");
  assert.equal(weeks[4][6].today, true);
  assert.equal(weeks[0][0].date, "2026-09-07");
});

test("days are met, practised or rest by the log", () => {
  const log = [
    { date: "2026-10-05", seconds: 30, minutes: 0, goal_met: false, sessions: 1 },
    { date: "2026-10-04", seconds: 1000, minutes: 16, goal_met: true, sessions: 2 },
    { date: "2026-10-03", seconds: 300, minutes: 5, goal_met: false, sessions: 1 },
    { date: "2026-10-02", seconds: 0, minutes: 0, goal_met: false, sessions: 0 },
  ];
  const cells = new Map(T.calendar(report({ log })).flat().map((c) => [c.date, c]));
  assert.equal(cells.get("2026-10-05").state, "practised");
  assert.equal(cells.get("2026-10-04").state, "met");
  assert.equal(cells.get("2026-10-03").state, "practised");
  assert.equal(cells.get("2026-10-02").state, "rest");
  assert.equal(cells.get("2026-10-01").state, "rest");
});

test("the labels read as a sentence for a screen reader", () => {
  const log = [
    { date: "2026-10-04", seconds: 1000, minutes: 16, goal_met: true, sessions: 2 },
    { date: "2026-10-03", seconds: 300, minutes: 5, goal_met: false, sessions: 1 },
    { date: "2026-10-02", seconds: 40, minutes: 0, goal_met: false, sessions: 1 },
  ];
  const cells = new Map(T.calendar(report({ log, today: "2026-10-07" })).flat().map((c) => [c.date, c]));
  assert.equal(cells.get("2026-10-04").label, "Sun 4 Oct: goal met, 16 min");
  assert.equal(cells.get("2026-10-03").label, "Sat 3 Oct: 5 min");
  assert.equal(cells.get("2026-10-02").label, "Fri 2 Oct: 40 sec");
  assert.equal(cells.get("2026-10-01").label, "Thu 1 Oct: no practice");
  assert.equal(cells.get("2026-10-08").label, "Thu 8 Oct");
});

test("the calendar crosses a month and a year without a gap", () => {
  const weeks = T.calendar(report({ today: "2027-01-03" })); // a Sunday
  const dates = weeks.flat().map((c) => c.date);
  assert.equal(dates[0], "2026-11-30");
  assert.equal(dates.length, 35);
  assert.equal(new Set(dates).size, 35);
  assert.ok(dates.includes("2026-12-31") && dates.includes("2027-01-01"));
  assert.equal(dates[34], "2027-01-03");
});

test("the line under the calendar counts only the days that have happened", () => {
  const log = [
    { date: "2026-10-04", seconds: 1000, minutes: 16, goal_met: true, sessions: 2 },
    { date: "2026-10-03", seconds: 1000, minutes: 16, goal_met: true, sessions: 2 },
  ];
  assert.equal(T.calendarLine(T.calendar(report({ log }))), "2 of the last 29 days met the goal.");
  assert.equal(T.calendarLine(T.calendar(report({ log, today: "2026-10-07" }))), "2 of the last 31 days met the goal.");
});

// ---------------------------------------------------------------- the best takes

const item = (slug, best, attempts, over) => ({
  exercise: slug, title: slug, best_score: best, attempts, pass_score: 70, passed: best >= 70, is_challenge: true, ...over,
});

test("the best takes are the highest scores, never an exercise not played", () => {
  const items = [item("a", null, 0), item("b", 60, 2), item("c", 90, 1), item("d", 90, 4), item("e", 75, 1)];
  assert.deepEqual(Bests.top(items, 3).map((i) => i.exercise), ["d", "c", "e"]);
  assert.deepEqual(Bests.top(items, 10).map((i) => i.exercise), ["d", "c", "e", "b"]);
  assert.deepEqual(Bests.top([item("a", null, 0)], 5), []);
});

test("a tie in score and tries keeps the order the server gave", () => {
  const items = [item("x", 80, 1), item("y", 80, 1), item("z", 80, 1)];
  assert.deepEqual(Bests.top(items, 3).map((i) => i.exercise), ["x", "y", "z"]);
});
