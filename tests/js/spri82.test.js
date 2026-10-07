// SPR-I.8.2 improv: the scale judge. Pure, no browser.
// Run by tests/test_spri_8_2.py (node --test).
//
// Times are milliseconds from the moment the first step is due. At 60 bpm and 2 notes a beat a step
// is 500 ms, so a step is due at 0, 500, 1000 ...

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Scale = require(path.join("..", "..", "static", "improv", "scale.js"));

const STEPS = Scale.buildSteps(0, 2);
const base = { steps: STEPS, tempo: 60, perBeat: 2 };
const stepMs = 500;

// A perfect run: both hands on every step, `offset` ms from the due time.
function perfect(offset = 0, steps = STEPS) {
  const events = [];
  steps.forEach((s, i) => {
    events.push({ t_ms: i * stepMs + offset, type: "on", note: s.left, velocity: 80 });
    events.push({ t_ms: i * stepMs + offset + 3, type: "on", note: s.right, velocity: 80 });
    events.push({ t_ms: i * stepMs + offset + 300, type: "off", note: s.left, velocity: 0 });
    events.push({ t_ms: i * stepMs + offset + 301, type: "off", note: s.right, velocity: 0 });
  });
  return events;
}

const run = (events, extra = {}) => Scale.judge({ ...base, events, ...extra });

// ------------------------------------------------------------------ the numbers

test("the step length follows the tempo and the notes per beat", () => {
  assert.equal(Scale.stepMs(60, 2), 500);
  assert.equal(Scale.stepMs(120, 4), 125);
  assert.equal(Scale.stepMs(60, 3), 1000 / 3);
});

test("the timing tolerance is 40% of a step, held between 50 and 120 ms", () => {
  assert.equal(Scale.toleranceMs(500), 120);
  assert.equal(Scale.toleranceMs(250), 100);
  assert.equal(Scale.toleranceMs(100), 50);
  assert.equal(Scale.toleranceMs(30), 50);
});

test("the judge has a version, the pass line is 80 and the score is 70% pitch and 30% timing", () => {
  assert.equal(Scale.JUDGE_VERSION, 1);
  assert.equal(Scale.PASS_SCORE, 80);
  assert.equal(Scale.PITCH_WEIGHT + Scale.TIMING_WEIGHT, 1);
  assert.equal(Scale.PITCH_WEIGHT, 0.7);
});

// ------------------------------------------------------------------ a clean run

test("a perfect run scores 100 and passes", () => {
  const r = run(perfect());
  assert.equal(r.score, 100);
  assert.equal(r.passed, true);
  assert.equal(r.pitchAccuracy, 1);
  assert.equal(r.timingAccuracy, 1);
  assert.equal(r.extras, 0);
  assert.equal(r.matched, 58);
  assert.equal(r.expected, 58);
  assert.deepEqual(r.missedSteps, []);
  assert.equal(r.version, 1);
  assert.ok(r.steps.every((s) => s.state === "hit"));
});

test("the offset is the average of how early or late the notes were, negative is early", () => {
  assert.ok(Math.abs(run(perfect(20)).meanOffsetMs - 21.5) <= 1);
  assert.ok(Math.abs(run(perfect(-30)).meanOffsetMs + 28.5) <= 1);
});

test("the player's latency offset is taken off the times before judging", () => {
  const r = run(perfect(90), { latencyMs: 90 });
  assert.equal(r.timingAccuracy, 1);
  assert.ok(Math.abs(r.meanOffsetMs - 1.5) <= 1);
});

test("notes inside the tolerance are on time, notes outside it are matched but late", () => {
  const r = run(perfect(110));
  assert.equal(r.pitchAccuracy, 1);
  assert.equal(r.timingAccuracy, 1);
  const late = run(perfect(180));
  assert.equal(late.pitchAccuracy, 1);
  assert.equal(late.timingAccuracy, 0);
  assert.equal(late.score, 70);
  assert.equal(late.passed, false);
  assert.equal(late.steps[0].left.timing, "late");
  assert.equal(run(perfect(-180)).steps[0].left.timing, "early");
  assert.equal(run(perfect(10)).steps[0].left.timing, "ontime");
});

// ------------------------------------------------------------------ pitch

test("a note more than half a step away does not match the step", () => {
  const events = perfect().filter((e) => !(e.type === "on" && Math.abs(e.t_ms - 5 * stepMs) < 50 && e.note === STEPS[5].left));
  events.push({ t_ms: 5 * stepMs + 260, type: "on", note: STEPS[5].left, velocity: 80 });
  const r = run(events);
  assert.equal(r.steps[5].left.state, "missed");
  assert.equal(r.steps[5].right.state, "hit");
  assert.equal(r.steps[5].state, "partial");
  assert.equal(r.extras, 1);
  assert.deepEqual(r.missedSteps, [5]);
});

test("a missing hand is a miss: only the left hand played", () => {
  const onlyLeft = STEPS.map((s, i) => ({ t_ms: i * stepMs, type: "on", note: s.left, velocity: 80 }));
  const r = run(onlyLeft);
  assert.equal(r.matched, 29);
  assert.equal(r.pitchAccuracy, 0.5);
  assert.equal(r.steps[4].state, "partial");
  assert.equal(r.steps[4].right.state, "missed");
  assert.equal(r.missedSteps.length, 29);
});

test("a wrong note is an extra and lowers the accuracy", () => {
  const events = perfect();
  events.push({ t_ms: 1234, type: "on", note: STEPS[0].left + 1, velocity: 80 });
  const r = run(events);
  assert.equal(r.extras, 1);
  assert.equal(r.matched, 58);
  assert.equal(r.pitchAccuracy, 58 / 59);
  assert.ok(r.score < 100);
});

test("a wrong note in the wrong place never takes the place of the right one", () => {
  const events = perfect().filter((e) => !(e.type === "on" && Math.abs(e.t_ms - 2 * stepMs) < 50 && e.note === STEPS[2].right));
  events.push({ t_ms: 2 * stepMs, type: "on", note: STEPS[2].right + 1, velocity: 80 });
  const r = run(events);
  assert.equal(r.steps[2].right.state, "missed");
  assert.equal(r.extras, 1);
});

test("playing a note twice counts the second as an extra", () => {
  const events = perfect();
  events.push({ t_ms: 3 * stepMs + 40, type: "on", note: STEPS[3].left, velocity: 80 });
  const r = run(events);
  assert.equal(r.extras, 1);
  assert.equal(r.matched, 58);
});

test("the same pitch asked of the two hands at different steps goes to the nearest one", () => {
  const three = Scale.buildSteps(0, 3);
  // Step 7's left note is the same key as step 0's right note.
  assert.equal(three[7].left, three[0].right);
  const events = [{ t_ms: 7 * (1000 / 3), type: "on", note: three[7].left, velocity: 80 }];
  const r = Scale.judge({ steps: three, tempo: 60, perBeat: 3, events });
  assert.equal(r.steps[7].left.state, "hit");
  assert.equal(r.steps[0].right.state, "missed");
  assert.equal(r.matched, 1);
});

test("the control keys are left out: pressing them is neither a note nor a mistake", () => {
  const events = perfect();
  events.push({ t_ms: 400, type: "on", note: 108, velocity: 90 });
  events.push({ t_ms: 450, type: "on", note: 107, velocity: 90 });
  events.push({ t_ms: 480, type: "on", note: 106, velocity: 90 });
  const r = run(events);
  assert.equal(r.extras, 0);
  assert.equal(r.score, 100);
});

test("only note-ons count: releases are ignored", () => {
  const r = run(perfect());
  assert.equal(r.matched + r.extras, 58);
});

test("a note played long before the start is an extra", () => {
  const events = perfect();
  events.push({ t_ms: -2000, type: "on", note: STEPS[0].left, velocity: 80 });
  assert.equal(run(events).extras, 1);
});

test("playing nothing scores 0 and nothing is made up", () => {
  const r = run([]);
  assert.equal(r.score, 0);
  assert.equal(r.pitchAccuracy, 0);
  assert.equal(r.timingAccuracy, 0);
  assert.equal(r.meanOffsetMs, 0);
  assert.equal(r.passed, false);
  assert.equal(r.missedSteps.length, 29);
});

test("the pass line is 80: a run missing a few steps can still pass", () => {
  const events = perfect().filter((e) => {
    const i = Math.round(e.t_ms / stepMs);
    return !(e.type === "on" && [3, 4, 5].includes(i));
  });
  const r = run(events);
  assert.deepEqual(r.missedSteps, [3, 4, 5]);
  assert.equal(r.matched, 52);
  assert.equal(r.passed, true);
  assert.ok(r.score >= 80 && r.score < 100);
});

// ------------------------------------------------------------------ the feel

test("the feel says early, late or steady", () => {
  assert.equal(run(perfect(0)).feel, "steady");
  assert.equal(run(perfect(60)).feel, "late");
  assert.equal(run(perfect(-60)).feel, "early");
});

// ------------------------------------------------------------------ live

test("while it is playing, steps not yet due are pending and nothing is counted against the player", () => {
  const events = perfect().filter((e) => e.t_ms <= 4 * stepMs + 10);
  const live = run(events, { now: 4 * stepMs + 100 });
  assert.equal(live.done, false);
  assert.equal(live.steps[0].state, "hit");
  assert.equal(live.steps[4].state, "hit");
  assert.equal(live.steps[6].state, "pending");
  assert.equal(live.score, 100);
  assert.deepEqual(live.missedSteps, []);
});

test("a step stays open for half a step after it is due, then a silent step is missed", () => {
  const events = perfect().filter((e) => e.t_ms < 2 * stepMs);
  const open = run(events, { now: 2 * stepMs + 200 });
  assert.equal(open.steps[2].state, "pending");
  const closed = run(events, { now: 2 * stepMs + 260 });
  assert.equal(closed.steps[2].state, "missed");
  assert.deepEqual(closed.missedSteps.slice(0, 1), [2]);
});

test("the run is over when the last step has closed", () => {
  const withoutLast = perfect().filter((e) => e.t_ms < 28 * stepMs);
  assert.equal(run(withoutLast, { now: 28 * stepMs + 100 }).done, false);
  assert.equal(run(withoutLast, { now: 28 * stepMs + 260 }).done, true);
  assert.equal(run(perfect(), { now: 28 * stepMs + 10 }).done, true);
  assert.equal(run(perfect()).done, true);
});

test("live and final agree: the same events at the end give the same answer", () => {
  const events = perfect(15);
  const live = run(events, { now: 100000 });
  const final = run(events);
  assert.equal(live.score, final.score);
  assert.deepEqual(live.steps, final.steps);
});

test("events that have not happened yet are not judged", () => {
  const live = run(perfect(), { now: 2 * stepMs });
  assert.equal(live.steps[10].state, "pending");
  assert.equal(live.extras, 0);
});

// ------------------------------------------------------------------ all levels

test("every level is judged on its own step length and passes when played cleanly", () => {
  for (const [octaves, perBeat] of [[2, 2], [3, 3], [4, 4]]) {
    const steps = Scale.buildSteps(7, octaves);
    const ms = Scale.stepMs(60, perBeat);
    const events = [];
    steps.forEach((s, i) => {
      events.push({ t_ms: i * ms, type: "on", note: s.left, velocity: 70 });
      events.push({ t_ms: i * ms, type: "on", note: s.right, velocity: 70 });
    });
    const r = Scale.judge({ steps, tempo: 60, perBeat, events });
    assert.equal(r.score, 100, `${octaves} octaves`);
    assert.equal(r.expected, 2 * (14 * octaves + 1));
  }
});

// ------------------------------------------------------------------ the record

test("the record to save has the fields of a ScaleRun", () => {
  const r = run(perfect(20));
  const rec = Scale.toRecord(r, { rootPc: 0, octaves: 2, perBeat: 2, tempo: 60 });
  assert.deepEqual(Object.keys(rec).sort(), [
    "judge_version", "mean_offset_ms", "missed_steps", "notes_per_beat", "octaves", "passed",
    "pitch_accuracy", "root_pc", "score", "tempo_bpm", "timing_accuracy",
  ]);
  assert.equal(rec.score, 100);
  assert.equal(rec.tempo_bpm, 60);
  assert.equal(rec.root_pc, 0);
  assert.equal(rec.judge_version, 1);
  assert.equal(rec.passed, true);
  assert.equal(Number.isInteger(rec.mean_offset_ms), true);
});
