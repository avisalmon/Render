// SPR-I.5.4 improv: the practice timer and the words about practice, with no browser.
const test = require("node:test");
const assert = require("node:assert/strict");
const Practice = require("../../static/improv/practice.js");

const S = 1000;
const MIN = 60 * S;

test("nothing is counted while the band is stopped and nothing is played", () => {
  const clock = Practice.createClock();
  assert.equal(clock.seconds(0), 0);
  assert.equal(clock.seconds(5 * MIN), 0);
});

test("the band running counts every second of it", () => {
  const clock = Practice.createClock();
  clock.bandStarted(1 * S);
  assert.equal(clock.seconds(31 * S), 30);
  clock.bandStopped(61 * S);
  assert.equal(clock.seconds(5 * MIN), 60);
});

test("a note played with the band stopped counts for ten seconds and no more", () => {
  const clock = Practice.createClock();
  clock.notePlayed(100 * S);
  assert.equal(clock.seconds(104 * S), 4);
  assert.equal(clock.seconds(200 * S), 10);
});

test("notes played ten seconds apart count the whole stretch, notes far apart count ten each", () => {
  const clock = Practice.createClock();
  clock.notePlayed(0);
  clock.notePlayed(8 * S);
  clock.notePlayed(16 * S);
  assert.equal(clock.seconds(60 * S), 26);
  clock.notePlayed(100 * S);
  assert.equal(clock.seconds(300 * S), 36);
});

test("a note played while the band runs does not count twice", () => {
  const clock = Practice.createClock();
  clock.bandStarted(0);
  clock.notePlayed(15 * S);
  clock.bandStopped(20 * S);
  assert.equal(clock.seconds(20 * S), 20);
  assert.equal(clock.seconds(25 * S), 25, "the last note keeps the clock going for ten seconds after the band stops");
  assert.equal(clock.seconds(60 * S), 25);
});

test("the clock is whole seconds, rounded, so the server column is an integer", () => {
  const clock = Practice.createClock();
  clock.bandStarted(0);
  clock.bandStopped(1500);
  assert.equal(clock.seconds(2000), 2);
});

test("a sitting ends after thirty idle minutes and not before", () => {
  assert.equal(Practice.sittingIsOver(0, 29 * MIN + 59 * S), false);
  assert.equal(Practice.sittingIsOver(0, 30 * MIN), true);
});

test("the constants are the spec's: ten seconds, thirty seconds, thirty minutes", () => {
  assert.equal(Practice.ACTIVE_WINDOW_MS, 10 * S);
  assert.equal(Practice.REPORT_EVERY_MS, 30 * S);
  assert.equal(Practice.IDLE_MS, 30 * MIN);
});

const report = (over) =>
  Object.assign(
    { timezone: "Asia/Jerusalem", today: "2026-10-05", goal_minutes: 15, today_seconds: 0, today_minutes: 0, goal_met: false, streak: 0, best_streak: 0, log: [] },
    over
  );

test("the goal line says how far today is", () => {
  assert.equal(Practice.goalLine(report({ today_seconds: 300, today_minutes: 5 })), "Today: 5 of 15 minutes.");
  assert.equal(Practice.goalLine(report({ today_seconds: 0 })), "Today: 0 of 15 minutes.");
  assert.equal(Practice.goalLine(report({ today_seconds: 900, today_minutes: 15, goal_met: true })), "Today: goal met, 15 minutes.");
  assert.equal(Practice.goalLine(report({ today_seconds: 1500, today_minutes: 25, goal_met: true })), "Today: goal met, 25 minutes.");
});

test("a minute is one minute", () => {
  assert.equal(Practice.goalLine(report({ today_seconds: 60, today_minutes: 1, goal_minutes: 1, goal_met: true })), "Today: goal met, 1 minute.");
});

test("the streak line is plain about a day that is still open", () => {
  assert.equal(Practice.streakLine(report({ streak: 0 })), "No streak yet. Meet the goal today to start one.");
  assert.equal(Practice.streakLine(report({ streak: 3, goal_met: true })), "Streak: 3 days.");
  assert.equal(Practice.streakLine(report({ streak: 1, goal_met: true })), "Streak: 1 day.");
  assert.equal(Practice.streakLine(report({ streak: 3, goal_met: false })), "Streak: 3 days. Meet the goal today to keep it.");
});

test("the best streak is only mentioned when it beats the current one", () => {
  assert.equal(Practice.bestLine(report({ streak: 3, best_streak: 3 })), "");
  assert.equal(Practice.bestLine(report({ streak: 3, best_streak: 9 })), "Best streak: 9 days.");
  assert.equal(Practice.bestLine(report({ streak: 0, best_streak: 0 })), "");
});

test("a log row reads as a weekday, a date and minutes, with a mark for a goal day", () => {
  const row = { date: "2026-10-05", seconds: 1230, minutes: 20, goal_met: true, sessions: 2 };
  assert.deepEqual(Practice.logRow(row), { day: "Mon 5 Oct", minutes: "20 min", sessions: "2 sittings", met: true });
  const short = { date: "2026-09-30", seconds: 60, minutes: 1, goal_met: false, sessions: 1 };
  assert.deepEqual(Practice.logRow(short), { day: "Wed 30 Sep", minutes: "1 min", sessions: "1 sitting", met: false });
});

test("a day with less than a minute still shows its seconds", () => {
  const row = { date: "2026-10-05", seconds: 40, minutes: 0, goal_met: false, sessions: 1 };
  assert.equal(Practice.logRow(row).minutes, "40 sec");
  const none = { date: "2026-10-05", seconds: 0, minutes: 0, goal_met: false, sessions: 0 };
  assert.equal(Practice.logRow(none).minutes, "0 min");
  assert.equal(Practice.logRow(none).sessions, "");
});

test("the words use no dashes and no emoji", () => {
  const all = [
    Practice.goalLine(report({})),
    Practice.streakLine(report({})),
    Practice.streakLine(report({ streak: 2 })),
    Practice.bestLine(report({ streak: 1, best_streak: 4 })),
    JSON.stringify(Practice.logRow({ date: "2026-10-05", seconds: 90, minutes: 1, goal_met: true, sessions: 1 })),
  ].join(" ");
  assert.ok(!/[–—]/.test(all));
});
