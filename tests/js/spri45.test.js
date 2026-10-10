// SPR-I.4.5 improv: the remaining scoring kinds. Guide tones, approach notes, rhythm motif
// and call and response, each a rule the exercises of Epic I.5 will name. The golden cases
// in fixtures/scoring.json are the test, over the same chart and theory table as the judge's
// own. Comping voicings is v2 and is refused, not scored as nought.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const J = require(path.join(root, "static", "improv", "judge.js"));
const Chart = require(path.join(root, "static", "improv", "chart.js"));
const theory = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "theory.json"), "utf8"));
const golden = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "scoring.json"), "utf8"));

const scalesBySlug = new Map(theory.scales.map((s) => [s.slug, s]));
const qualities = theory.chord_qualities.map((q) => ({
  symbol: q.symbol,
  intervals: q.intervals,
  roles: q.roles,
  family: q.family,
  scales: theory.chord_scales
    .filter((cs) => cs.quality === q.symbol)
    .sort((a, b) => a.preference - b.preference)
    .map((cs) => ({ slug: cs.scale, intervals: scalesBySlug.get(cs.scale).intervals, preference: cs.preference })),
}));
const chart = Chart.parseChart(golden.chart, qualities, { homeKey: golden.key });
assert.equal(chart.ok, true);

function run(item, extra) {
  const events = [];
  for (const [t, note] of item.events) {
    events.push({ t_ms: t, type: "on", note, velocity: 90 });
    events.push({ t_ms: t + 150, type: "off", note, velocity: 0 });
  }
  return J.judge({
    events,
    chart,
    from: 0,
    to: chart.bars.length,
    bpm: golden.bpm,
    swingRatio: 0.5,
    qualities,
    scoring: item.scoring,
    latencyOffsetMs: 0,
    grid: "beat",
    ...(extra || {}),
  });
}

test("every golden case scores the way a teacher would score it", () => {
  assert.ok(golden.cases.length >= 15);
  const wrong = [];
  for (const item of golden.cases) {
    if (item.throws) {
      try {
        run(item);
        wrong.push(`${item.name}: was scored instead of refused`);
      } catch (e) {
        if (!/scoring kind/.test(e.message)) wrong.push(`${item.name}: refused for the wrong reason: ${e.message}`);
      }
      continue;
    }
    const got = run(item);
    if (got.score !== item.score) wrong.push(`${item.name}: the score is ${got.score}, not ${item.score}`);
  }
  assert.deepEqual(wrong, [], wrong.join(" | "));
});

test("every kind the spec names for version 1 is a kind the judge scores, and comping voicings waits for v2", () => {
  assert.deepEqual(
    [...J.SCORING_KINDS].sort(),
    ["approach_notes", "call_and_response", "chord_tones_on_beats", "free_play", "guide_tones", "rhythm_motif", "scale_only"]
  );
  assert.ok(!J.SCORING_KINDS.includes("comping_voicings"));
});

test("adding kinds did not change what the first kinds say", () => {
  assert.equal(J.JUDGE_VERSION, 2);
  const first = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "takes.json"), "utf8"));
  const sample = first.cases.find((c) => c.name.startsWith("every note a chord tone"));
  assert.equal(run(sample).score, 100);
});

test("a rhythm pattern that is not a list of beats inside the bar is refused", () => {
  for (const bad of [undefined, [], [5], ["x"], [-1]]) {
    assert.throws(() => run({ events: [[0, 60]], scoring: { kind: "rhythm_motif", params: { pattern: bad } } }), /pattern/, String(bad));
  }
});

test("a call-and-response phrase that is not notes on beats is refused", () => {
  for (const bad of [undefined, [], [[0]], [["x", 60]]]) {
    assert.throws(() => run({ events: [[0, 60]], scoring: { kind: "call_and_response", params: { phrase: bad } } }), /phrase/, JSON.stringify(bad));
  }
});

test("the scoring details say what was counted, so a lesson can explain the mark", () => {
  const guide = run(golden.cases[1]);
  assert.deepEqual(guide.scoring, { kind: "guide_tones", guideTones: 3, notes: 4, connections: 1, changes: 2 });
  const approach = run(golden.cases[5]);
  assert.deepEqual(approach.scoring, { kind: "approach_notes", targets: 3, reached: 2 });
  const rhythm = run(golden.cases[10]);
  assert.deepEqual(rhythm.scoring, { kind: "rhythm_motif", expected: 16, matched: 16, played: 32 });
  const call = run(golden.cases[13]);
  assert.deepEqual(call.scoring, { kind: "call_and_response", onsets: 3, onsetsMatched: 3, shapes: 2, shapesMatched: 1, exact: false });
  assert.deepEqual(run(golden.cases[0]).scoring.kind, "guide_tones");
  assert.equal(run({ events: [[0, 62]], scoring: { kind: "free_play", params: {} } }).scoring.kind, "free_play");
});
