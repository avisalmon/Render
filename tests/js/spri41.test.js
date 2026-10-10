// SPR-I.4.1 improv: the judge. One pure function, the notes played and the chart in, the
// classes, the timing and the score out. The golden takes in fixtures/takes.json are the
// real test: hand-checked musical judgements over a real chart with the app's own theory
// table, so a change to the rules shows up as a fixture diff and a deliberate version bump.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const J = require(path.join(root, "static", "improv", "judge.js"));
const Chart = require(path.join(root, "static", "improv", "chart.js"));
const theory = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "theory.json"), "utf8"));
const golden = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "takes.json"), "utf8"));

// The qualities as the API sends them: each with its scales, first choice first.
const scalesBySlug = new Map(theory.scales.map((s) => [s.slug, s]));
const qualities = theory.chord_qualities.map((q) => ({
  symbol: q.symbol,
  intervals: q.intervals,
  roles: q.roles,
  family: q.family,
  scales: theory.chord_scales
    .filter((cs) => cs.quality === q.symbol)
    .sort((a, b) => a.preference - b.preference)
    .map((cs) => ({ slug: cs.scale, name: scalesBySlug.get(cs.scale).name, intervals: scalesBySlug.get(cs.scale).intervals, preference: cs.preference })),
}));

const chart = Chart.parseChart(golden.chart, qualities, { homeKey: golden.key });
assert.equal(chart.ok, true, "the golden chart has to parse");

function events(pairs) {
  const out = [];
  for (const [t, note] of pairs) {
    out.push({ t_ms: t, type: "on", note, velocity: 90 });
    out.push({ t_ms: t + 200, type: "off", note, velocity: 0 });
  }
  return out;
}

function run(item, extra) {
  return J.judge({
    events: events(item.events),
    chart,
    from: 0,
    to: chart.bars.length,
    bpm: golden.bpm,
    swingRatio: item.swingRatio === undefined ? 0.5 : item.swingRatio,
    qualities,
    scoring: item.scoring || { kind: "free_play", params: {} },
    latencyOffsetMs: 0,
    grid: item.grid || "beat",
    ...(extra || {}),
  });
}

// ------------------------------------------------------------------- the golden takes

test("every golden take is judged the way a teacher would judge it", () => {
  assert.ok(golden.cases.length >= 15, "the fixtures are the test; there have to be enough of them");
  const wrong = [];
  for (const item of golden.cases) {
    const got = run(item);
    const complain = (what, had, wanted) => wrong.push(`${item.name}: ${what} is ${JSON.stringify(had)}, not ${JSON.stringify(wanted)}`);
    const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

    if (item.classes && !same(got.notes.map((n) => n.class), item.classes)) complain("the classes", got.notes.map((n) => n.class), item.classes);
    if (item.guides && !same(got.notes.map((n) => n.guide), item.guides)) complain("the guide tones", got.notes.map((n) => n.guide), item.guides);
    if (item.chords && !same(got.notes.map((n) => n.chord), item.chords)) complain("the chords", got.notes.map((n) => n.chord), item.chords);
    if (item.onBeat && !same(got.notes.map((n) => n.onBeat), item.onBeat)) complain("on the named beats", got.notes.map((n) => n.onBeat), item.onBeat);
    if (item.score !== undefined && got.score !== item.score) complain("the score", got.score, item.score);
    if (item.ignored !== undefined && got.metrics.ignored !== item.ignored) complain("ignored", got.metrics.ignored, item.ignored);
    for (const [key, value] of Object.entries(item.metrics || {})) {
      if (got.metrics[key] !== value) complain(`metrics.${key}`, got.metrics[key], value);
    }
    for (const [key, value] of Object.entries(item.timing || {})) {
      if (got.timing[key] !== value) complain(`timing.${key}`, got.timing[key], value);
    }
    if (item.withOffset) {
      const again = run(item, { latencyOffsetMs: item.withOffset.latencyOffsetMs });
      for (const [key, value] of Object.entries(item.withOffset.timing)) {
        if (again.timing[key] !== value) complain(`with the offset, timing.${key}`, again.timing[key], value);
      }
    }
    if (item.onOtherGrid) {
      const again = run(item, { grid: item.onOtherGrid.grid });
      if (again.timing.meanMs !== item.onOtherGrid.meanMs) complain(`on the ${item.onOtherGrid.grid} grid, timing.meanMs`, again.timing.meanMs, item.onOtherGrid.meanMs);
    }
  }
  assert.deepEqual(wrong, [], wrong.join(" | "));
});

// --------------------------------------------------------------------- the contract

test("the result says which version of the rules made it", () => {
  assert.equal(J.JUDGE_VERSION, 2);
  assert.equal(run(golden.cases[0]).version, 2);
});

test("every note-on comes back with what the player needs to see, and note-offs do not", () => {
  const got = run(golden.cases[1]);
  assert.equal(got.notes.length, 4);
  for (const n of got.notes) {
    assert.ok(Number.isInteger(n.note));
    assert.ok(["chord", "scale", "approach", "outside", "pending"].includes(n.class));
    assert.equal(typeof n.guide, "boolean");
    assert.equal(typeof n.chord, "string");
    assert.equal(typeof n.offsetMs, "number");
    assert.equal(typeof n.tMs, "number");
  }
});

test("the metrics add up to the notes judged", () => {
  const got = run(golden.cases[1]);
  const m = got.metrics;
  assert.equal(m.notes, 4);
  assert.equal(m.chordTonePct + m.scalePct + m.approachPct + m.outsidePct, 100);
});

// ----------------------------------------------------------------- live judging

test("live, an outside note is pending until the next note lands or the beat runs out", () => {
  const pairs = [[0, 62], [1000, 63]];
  const early = run({ events: pairs }, { now: 1100 });
  assert.equal(early.notes[1].class, "pending", "100 ms after an outside note, nobody knows yet");
  const later = run({ events: pairs }, { now: 1600 });
  assert.equal(later.notes[1].class, "outside", "a beat has gone by with no chord tone after it");
  const settled = run({ events: [[0, 62], [1000, 63], [1400, 62]] }, { now: 1450 });
  assert.equal(settled.notes[1].class, "approach");
});

test("the final judgement, with no now, settles everything", () => {
  const got = run({ events: [[0, 62], [1000, 63]] });
  assert.equal(got.notes[1].class, "outside");
  assert.ok(!got.notes.some((n) => n.class === "pending"));
});

test("judging the same take live and at the end gives the same classes once everything has settled", () => {
  const item = golden.cases[3];
  const live = run(item, { now: 100000 });
  const final = run(item);
  assert.deepEqual(live.notes.map((n) => n.class), final.notes.map((n) => n.class));
  assert.equal(live.score, final.score);
});

// --------------------------------------------------------------------- the chord

test("the chord sounding at a moment is found with the half-beat look-ahead, loop included", () => {
  const at = (ms) => J.chordAt(chart, 0, chart.bars.length, golden.bpm, ms);
  assert.equal(at(0).name, "Dm7");
  assert.equal(at(1999).name, "G7", "1 ms before the change, and the look-ahead says G7");
  assert.equal(at(1700).name, "Dm7");
  assert.equal(at(6500).name, "Cmaj7", "the % bar repeats");
  assert.equal(at(8000).name, "Dm7", "and round the loop it goes");
});

test("a bar with two chords changes chord in the middle of the bar", () => {
  const split = Chart.parseChart("| Dm7 G7 | Cmaj7 |", qualities, { homeKey: "C" });
  const at = (ms) => J.chordAt(split, 0, 2, 120, ms);
  assert.equal(at(0).name, "Dm7");
  assert.equal(at(600).name, "Dm7");
  assert.equal(at(1000).name, "G7");
  assert.equal(at(2100).name, "Cmaj7");
});

// --------------------------------------------------------------------- scoring

test("a scoring kind the judge does not know is refused, not scored as zero", () => {
  assert.throws(() => run({ events: [[0, 62]], scoring: { kind: "telepathy", params: {} } }), /scoring kind/);
});

test("the three first scoring kinds are the ones the backlog names for this sprint", () => {
  for (const kind of ["chord_tones_on_beats", "free_play", "scale_only"]) assert.ok(J.SCORING_KINDS.includes(kind), kind);
});

test("the tolerance scales with the tempo: a tenth of a beat", () => {
  assert.equal(J.toleranceMs(120), 50);
  assert.equal(J.toleranceMs(60), 100);
});

test("the words about timing are words, not a sign to work out", () => {
  assert.equal(J.timingWords({ meanMs: -18, spreadMs: 10, withinPct: 90, notes: 10 }), "you rush by 18 ms");
  assert.equal(J.timingWords({ meanMs: 25, spreadMs: 10, withinPct: 90, notes: 10 }), "you drag by 25 ms");
  assert.equal(J.timingWords({ meanMs: 3, spreadMs: 10, withinPct: 90, notes: 10 }), "right on the beat");
  assert.match(J.timingWords({ meanMs: 3, spreadMs: 60, withinPct: 40, notes: 10 }), /uneven|spread/);
  assert.equal(J.timingWords({ meanMs: null, notes: 0 }), "no notes yet");
});

// ------------------------------------------------------------------- bad input

test("junk in, nothing judged, nothing thrown", () => {
  const got = J.judge({ events: null, chart, from: 0, to: 4, bpm: 120, qualities, scoring: { kind: "free_play", params: {} } });
  assert.deepEqual(got.notes, []);
  assert.equal(got.score, null);
  const odd = J.judge({ events: [{ t_ms: 0, type: "on", note: 62 }, null, { type: "on" }], chart, from: 0, to: 4, bpm: 120, qualities, scoring: { kind: "scale_only", params: {} } });
  assert.equal(odd.notes.length, 1);
});
