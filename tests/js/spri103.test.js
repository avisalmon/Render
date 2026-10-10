// SPR-I.10.3 improv: the judge reads a swung rhythm. A pattern is written in straight eighths; when the
// feel is swung the off-beats sound where the band puts them, so the same pattern is on time swung and
// a straight take is late. Pure, no browser. Run by tests/test_spri_10_3.py (node --test).

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const J = require(path.join(root, "static", "improv", "judge.js"));
const Band = require(path.join(root, "static", "improv", "band.js"));
const Chart = require(path.join(root, "static", "improv", "chart.js"));
const Demo = require(path.join(root, "static", "improv", "demo.js"));
const theory = require(path.join(root, "improv", "seed_data", "theory.json"));

const scaleBySlug = new Map(theory.scales.map((s) => [s.slug, s]));
const qualities = theory.chord_qualities.map((q) => ({
  ...q,
  scales: theory.chord_scales
    .filter((cs) => cs.quality === q.symbol)
    .sort((a, b) => a.preference - b.preference)
    .map((cs) => ({ slug: cs.scale, intervals: scaleBySlug.get(cs.scale).intervals })),
}));

const chart = Chart.parseChart("| Dm7 | G7 | Cmaj7 | Cmaj7 |", qualities, { beatsPerBar: 4, homeKey: "C" });
const BPM = 100;
const BEAT_MS = 60000 / BPM;
const PATTERN = [0, 1.5, 2, 3.5];

function take(beats, swingRatio, note = 62) {
  const events = beats.map((b) => ({ t_ms: Math.round(b * BEAT_MS), type: "on", note, velocity: 90 }));
  return J.judge({
    events, chart, from: 0, to: 2, bpm: BPM, swingRatio, qualities,
    scoring: { kind: "rhythm_motif", params: { pattern: PATTERN } }, latencyOffsetMs: 0, grid: "beat",
  });
}

const written = (bars, shift) => {
  const out = [];
  for (let b = 0; b < bars; b++) for (const p of PATTERN) out.push(b * 4 + shift(p));
  return out;
};

test("the judge warps a beat the way the band does, at every ratio", () => {
  for (const ratio of [0.5, 0.58, 0.62, 0.67, 0.75]) {
    for (const beat of [0, 0.25, 0.5, 0.75, 1, 1.5, 2.25, 3.5, 3.75]) {
      assert.ok(Math.abs(J.swingBeat(beat, ratio) - Band.swingBeat(beat, ratio)) < 1e-9, `${beat} at ${ratio}`);
    }
  }
  assert.equal(J.swingBeat(1.5, 0.5), 1.5);
});

test("a swung motif played swung is a perfect score", () => {
  const got = take(written(2, (p) => J.swingBeat(p, 0.67)), 0.67);
  assert.equal(got.score, 100);
  assert.deepEqual(got.scoring, { kind: "rhythm_motif", expected: 8, matched: 8, played: 8 });
});

test("a motif played in straight eighths over a swung feel is late and does not pass", () => {
  const got = take(written(2, (p) => p), 0.67);
  assert.ok(got.score < 80, `scored ${got.score}`);
  assert.equal(got.scoring.matched, 4, "only the on-beat notes line up");
});

test("a straight feel is judged as before", () => {
  assert.equal(take(written(2, (p) => p), 0.5).score, 100);
  assert.equal(take(written(2, (p) => J.swingBeat(p, 0.67)), 0.5).scoring.matched, 4);
});

test("with no swing ratio given the judge is straight", () => {
  const got = take(written(2, (p) => p), undefined);
  assert.equal(got.score, 100);
});

test("a swung light swing (0.58) is within the tolerance of straight, so both are on time", () => {
  assert.equal(take(written(2, (p) => p), 0.58).score, 100);
});

test("call and response: the swung answer is on time swung", () => {
  const phrase = [[0, 62], [1.5, 65], [2, 69], [3.5, 67]];
  const events = [];
  for (const [beat, note] of phrase) events.push({ t_ms: Math.round((4 + J.swingBeat(beat, 0.67)) * BEAT_MS), type: "on", note, velocity: 90 });
  const input = (evs, ratio) => J.judge({
    events: evs, chart, from: 0, to: 2, bpm: BPM, swingRatio: ratio, qualities,
    scoring: { kind: "call_and_response", params: { phrase, answerBar: 1, exact: true } }, latencyOffsetMs: 0, grid: "beat",
  });
  assert.equal(input(events, 0.67).score, 100);
  assert.ok(input(events, 0.67).scoring.onsetsMatched === 4);
  assert.ok(input(events, 0.5).scoring.onsetsMatched === 2, "read as straight, the swung off-beats are late");
});

test("call and response: an answer ending on the last off-beat of its bar still counts as that bar", () => {
  const phrase = [[0, 62], [2, 65], [3.5, 69]];
  const events = phrase.map(([beat, note]) => ({ t_ms: Math.round((4 + beat) * BEAT_MS), type: "on", note, velocity: 90 }));
  for (const answerBar of [1]) {
    const got = J.judge({
      events, chart, from: 0, to: 2, bpm: BPM, swingRatio: 0.5, qualities,
      scoring: { kind: "call_and_response", params: { phrase, answerBar, exact: true } }, latencyOffsetMs: 0, grid: "beat",
    });
    assert.equal(got.score, 100);
  }
});

test("a rhythm with only whole beats is scored the same swung or straight", () => {
  const whole = [0, 2];
  for (const ratio of [0.5, 0.67]) {
    const events = [0, 2, 4, 6].map((b) => ({ t_ms: Math.round(b * BEAT_MS), type: "on", note: 62, velocity: 90 }));
    const got = J.judge({
      events, chart, from: 0, to: 2, bpm: BPM, swingRatio: ratio, qualities,
      scoring: { kind: "rhythm_motif", params: { pattern: whole } }, latencyOffsetMs: 0, grid: "beat",
    });
    assert.equal(got.score, 100);
  }
});

test("Show me swings with the feel and the real judge passes what it plays", () => {
  const params = { pattern: PATTERN };
  for (const ratio of [0.5, 0.62, 0.67]) {
    const demo = Demo.build({
      scoring: { kind: "rhythm_motif", params }, chart, from: 0, to: 2, qualities, beatsPerBar: 4, bpm: BPM, downbeat: 10, swingRatio: ratio,
    });
    assert.equal(demo.ok, true);
    const events = demo.notes.map((n) => ({ t_ms: Math.round((n.when - 10) * 1000), type: "on", note: n.note, velocity: 90 }));
    const got = J.judge({
      events, chart, from: 0, to: 2, bpm: BPM, swingRatio: ratio, qualities,
      scoring: { kind: "rhythm_motif", params }, latencyOffsetMs: 0, grid: "beat",
    });
    assert.equal(got.score, 100, `at ${ratio}`);
  }
  const straight = Demo.build({ scoring: { kind: "rhythm_motif", params }, chart, from: 0, to: 2, qualities, beatsPerBar: 4, bpm: BPM, downbeat: 0 });
  const swung = Demo.build({ scoring: { kind: "rhythm_motif", params }, chart, from: 0, to: 2, qualities, beatsPerBar: 4, bpm: BPM, downbeat: 0, swingRatio: 0.67 });
  assert.ok(swung.notes[1].when > straight.notes[1].when, "the swung off-beat comes later than the straight one");
});

test("the judge says it is version two", () => {
  assert.equal(J.JUDGE_VERSION, 2);
  assert.equal(take(written(2, (p) => p), 0.5).version, 2);
});
