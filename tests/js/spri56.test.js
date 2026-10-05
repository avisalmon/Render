// SPR-I.5.6 improv: the judge keeps its counts per kind of chord, and the words of the weakness
// panel and the Challenges screen.
//
// The weakness report on the server reads metrics.byQuality, so the shape is the contract between
// the two: a symbol for each chord quality heard, with the notes played over it and how each was
// judged. Everything else in the metrics is unchanged, and the judge version stays at 1 because a
// new key changes no score.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const J = require(path.join(root, "static", "improv", "judge.js"));
const Chart = require(path.join(root, "static", "improv", "chart.js"));
const Weakness = require(path.join(root, "static", "improv", "weakness.js"));
const Bests = require(path.join(root, "static", "improv", "bests.js"));
const theory = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "theory.json"), "utf8"));

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

const chart = Chart.parseChart("| Dm7 | G7 | Cmaj7 | % |", qualities, { homeKey: "C" });
assert.equal(chart.ok, true);

function judge(pairs, extra) {
  const events = [];
  for (const [t, note] of pairs) {
    events.push({ t_ms: t, type: "on", note, velocity: 90 });
    events.push({ t_ms: t + 200, type: "off", note, velocity: 0 });
  }
  return J.judge({
    events, chart, from: 0, to: chart.bars.length, bpm: 120, swingRatio: 0.5, qualities,
    scoring: { kind: "free_play", params: {} }, latencyOffsetMs: 0, grid: "beat", ...(extra || {}),
  });
}

// ------------------------------------------------------------------- the judge

test("the metrics count the notes, and how each was judged, per kind of chord", () => {
  const result = judge([[0, 62], [500, 64], [1000, 63], [1500, 69], [2000, 67], [2500, 60]]);
  assert.deepEqual(result.metrics.byQuality, {
    m7: { notes: 4, chord: 2, scale: 1, approach: 0, outside: 1 },
    7: { notes: 2, chord: 1, scale: 1, approach: 0, outside: 0 },
  });
});

test("the per-quality counts add up to the notes played over a chord", () => {
  const result = judge([[0, 62], [500, 64], [1000, 63], [1500, 69], [2000, 67], [2500, 60], [4000, 72], [4500, 61]]);
  const rows = Object.values(result.metrics.byQuality);
  assert.equal(rows.reduce((sum, r) => sum + r.notes, 0), result.metrics.notes);
  for (const row of rows) assert.equal(row.chord + row.scale + row.approach + row.outside, row.notes);
});

test("a note still waiting on its approach is counted as outside, as the overall share does", () => {
  const result = judge([[0, 62], [500, 61]], { now: 600 });
  assert.equal(result.metrics.outsidePct, 50);
  assert.equal(result.metrics.byQuality.m7.outside, 1);
});

test("no notes means no counts, and every other metric is where it was", () => {
  const result = judge([]);
  assert.deepEqual(result.metrics.byQuality, {});
  assert.equal(result.metrics.notes, 0);
  for (const key of ["ignored", "chordTonePct", "scalePct", "approachPct", "outsidePct", "guideTonePct", "meanOffsetMs", "spreadMs", "withinPct"]) {
    assert.ok(key in result.metrics, key);
  }
  assert.equal(result.version, 1);
});

test("the counts survive being sent as JSON and read back", () => {
  const result = judge([[0, 62], [2000, 67]]);
  assert.deepEqual(JSON.parse(JSON.stringify(result.metrics)).byQuality, result.metrics.byQuality);
});

// ------------------------------------------------------------------- the words of the weakness panel

const report = (over) => ({ days: 30, floor: 20, notes: 0, enough: false, notes_needed: 20, claims: [], ...over });
const claim = (over) => ({
  area: "timing", family: "", family_label: "", percent: 40, notes: 55, kinds: ["rhythm_motif"],
  exercise: "bossa-rhythm", exercise_title: "A bossa rhythm", lesson_title: "", ...over,
});

test("before the floor it says how far there is to go, never what is wrong", () => {
  assert.equal(
    Weakness.statusLine(report({ notes: 7, notes_needed: 13 })),
    "So far 7 of the 20 notes it needs from the last 30 days. Play 13 more and it will say where to work.",
  );
  assert.equal(
    Weakness.statusLine(report({ notes: 19, notes_needed: 1 })),
    "So far 19 of the 20 notes it needs from the last 30 days. Play 1 more note and it will say where to work.",
  );
  assert.equal(
    Weakness.statusLine(report()),
    "No notes in the last 30 days yet. Play 20 over the band and it will say where to work.",
  );
});

test("with enough notes and nothing wrong it says so, and with something wrong it leads in", () => {
  assert.equal(Weakness.statusLine(report({ notes: 80, enough: true, notes_needed: 0 })), "Nothing stands out in the last 30 days. Keep playing.");
  assert.equal(
    Weakness.statusLine(report({ notes: 80, enough: true, notes_needed: 0, claims: [claim()] })),
    "Where to work, from the last 30 days:",
  );
});

test("each area is said in its own plain words, with the number behind it", () => {
  assert.equal(Weakness.claimLine(claim()), "Timing: 40% of your notes were close to the beat.");
  assert.equal(Weakness.claimLine(claim({ area: "chord_tones", percent: 12 })), "Chord tones: 12% of your notes were chord tones.");
  assert.equal(Weakness.claimLine(claim({ area: "outside", percent: 45 })), "Outside notes: 45% of your notes were outside the chord and its scale.");
  assert.equal(
    Weakness.claimLine(claim({ area: "family", family: "half_diminished", family_label: "half-diminished", percent: 80 })),
    "Over half-diminished chords: 80% of your notes went outside.",
  );
  assert.equal(Weakness.evidenceLine(claim()), "From 55 notes.");
});

test("a claim with an exercise offers it, and one without says nothing is open", () => {
  assert.equal(Weakness.playLabel(claim()), "Work on it: A bossa rhythm");
  assert.equal(Weakness.playLabel(claim({ exercise: null, exercise_title: "" })), "");
  assert.equal(Weakness.noExerciseLine(claim({ exercise: null })), "Nothing open to work on this yet. Finish the lesson before it and one appears.");
  assert.equal(Weakness.noExerciseLine(claim()), "");
  assert.equal(Weakness.playUrl("/improv/play/", claim()), "/improv/play/?exercise=bossa-rhythm");
  assert.equal(Weakness.playUrl("/improv/play/", claim({ exercise: "a b" })), "/improv/play/?exercise=a%20b");
});

// ------------------------------------------------------------------- the words of the Challenges screen

const item = (over) => ({
  exercise: "blues", title: "Blues", lesson: null, lesson_title: "", scoring_kind: "chord_tones_on_beats", pass_score: 70, xp: 40,
  is_challenge: true, best_score: null, best_take: null, best_at: null, attempts: 0, passed: false, ...over,
});

test("a best reads as played, passed or not, and an unplayed one says so", () => {
  assert.equal(Bests.scoreLine(item()), "Not played yet. Pass mark 70.");
  assert.equal(Bests.scoreLine(item({ best_score: 55, attempts: 2 })), "Best 55. Pass mark 70.");
  assert.equal(Bests.scoreLine(item({ best_score: 88, attempts: 3, passed: true })), "Best 88, past the 70 mark.");
  assert.equal(Bests.scoreLine(item({ best_score: 70, attempts: 1, passed: true })), "Best 70, past the 70 mark.");
});

test("tries are counted in plain words", () => {
  assert.equal(Bests.attemptsLine(item()), "");
  assert.equal(Bests.attemptsLine(item({ attempts: 1 })), "1 try");
  assert.equal(Bests.attemptsLine(item({ attempts: 4 })), "4 tries");
});

test("the list splits into the challenges and the bests in lessons, keeping the order", () => {
  const rows = [item({ exercise: "a", is_challenge: false, lesson: "l" }), item({ exercise: "b" }), item({ exercise: "c", is_challenge: false, lesson: "l" }), item({ exercise: "d" })];
  const parts = Bests.split(rows);
  assert.deepEqual(parts.challenges.map((r) => r.exercise), ["b", "d"]);
  assert.deepEqual(parts.lessons.map((r) => r.exercise), ["a", "c"]);
});

test("the status line counts the challenges passed", () => {
  assert.equal(Bests.statusLine([]), "No challenges yet.");
  const rows = [item({ passed: true, best_score: 90, attempts: 1 }), item({ exercise: "x" }), item({ exercise: "y", is_challenge: false, passed: true })];
  assert.equal(Bests.statusLine(rows), "1 of 2 challenges passed.");
  assert.equal(Bests.statusLine([item({ passed: true, best_score: 90, attempts: 1 })]), "1 of 1 challenge passed.");
});

test("the play link opens the exercise, and offers a replay once there is a try", () => {
  assert.equal(Bests.playUrl("/improv/play/", item()), "/improv/play/?exercise=blues");
  assert.equal(Bests.playLabel(item()), "Play");
  assert.equal(Bests.playLabel(item({ attempts: 2 })), "Play again");
  assert.equal(Bests.kindWords(item()), "chord tones on beats");
});
