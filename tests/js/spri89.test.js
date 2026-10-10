// SPR-I.8.9 improv: "Show me", the demonstration of what an exercise expects. Pure, no browser.
// Run by tests/test_spri_8_9.py (node --test).

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const Chart = require(path.join(root, "static", "improv", "chart.js"));
const Judge = require(path.join(root, "static", "improv", "judge.js"));
const Demo = require(path.join(root, "static", "improv", "demo.js"));
const theory = require(path.join(root, "improv", "seed_data", "theory.json"));
const library = require(path.join(root, "improv", "seed_data", "library.json"));
const lessons = require(path.join(root, "improv", "seed_data", "lessons.json"));
const challenges = require(path.join(root, "improv", "seed_data", "challenges.json"));

const scaleBySlug = new Map(theory.scales.map((s) => [s.slug, s]));
const qualities = theory.chord_qualities.map((q) => ({
  ...q,
  scales: theory.chord_scales
    .filter((cs) => cs.quality === q.symbol)
    .sort((a, b) => a.preference - b.preference)
    .map((cs) => ({ slug: cs.scale, intervals: scaleBySlug.get(cs.scale).intervals })),
}));

function progressionOf(slug) {
  const found = (library.progressions || []).find((p) => p.slug === slug);
  assert.ok(found, `the seed library has ${slug}`);
  return found;
}

function swingFor(exercise) {
  const style = (library.styles || []).find((st) => st.slug === progressionOf(exercise.progression).default_style);
  return style && style.swing_ratio !== undefined ? Number(style.swing_ratio) : 0.5;
}

function chartFor(exercise) {
  const p = progressionOf(exercise.progression);
  const beatsPerBar = Number(String(p.time_signature).split("/")[0]);
  const parsed = Chart.parseChart(p.chart, qualities, { beatsPerBar, homeKey: p.home_key });
  assert.ok(parsed.ok, `${exercise.slug} parses`);
  return exercise.key === p.home_key ? parsed : Chart.transposeToKey(parsed, p.home_key, exercise.key);
}

function demoFor(exercise, extra) {
  const chart = chartFor(exercise);
  const to = Math.min(exercise.bars, chart.bars.length);
  return Demo.build({
    scoring: { kind: exercise.scoring_kind, params: exercise.scoring_params },
    chart,
    from: 0,
    to,
    qualities,
    beatsPerBar: chart.beatsPerBar,
    bpm: exercise.tempo,
    downbeat: 10,
    swingRatio: swingFor(exercise),
    ...extra,
  });
}

const all = [
  ...challenges.challenges,
  ...lessons.lessons.flatMap((l) => l.exercises.map((e) => ({ ...e, progression: e.progression || l.progression }))),
];

// ----------------------------------------------------------- the demo passes its own exercise

test("every seeded exercise that can be shown is shown, and only free play has nothing to show", () => {
  assert.ok(all.length >= 20, "the check found the seeded exercises");
  for (const ex of all) {
    const demo = demoFor(ex);
    if (ex.scoring_kind === "free_play") assert.equal(demo.ok, false, ex.slug);
    else assert.equal(demo.ok, true, `${ex.slug}: ${demo.reason}`);
  }
});

test("what the demo plays is judged as a pass by the real judge, for every seeded exercise", () => {
  for (const ex of all) {
    if (ex.scoring_kind === "free_play") continue;
    const demo = demoFor(ex);
    const chart = chartFor(ex);
    const events = [];
    for (const n of demo.notes) {
      const ms = (n.when - 10) * 1000;
      events.push({ t_ms: Math.round(ms), type: "on", note: n.note, velocity: Math.round(n.velocity * 127) });
      events.push({ t_ms: Math.round(ms + n.seconds * 1000), type: "off", note: n.note, velocity: 0 });
    }
    const judged = Judge.judge({
      events,
      chart,
      from: 0,
      to: Math.min(ex.bars, chart.bars.length),
      bpm: ex.tempo,
      swingRatio: swingFor(ex),
      qualities,
      scoring: { kind: ex.scoring_kind, params: ex.scoring_params },
      latencyOffsetMs: 0,
      grid: "beat",
    });
    if (process.env.SHOW_SCORES) console.log(ex.slug, judged.score);
    assert.ok(judged.score >= ex.pass_score, `${ex.slug}: the demo scores ${judged.score}, needs ${ex.pass_score}`);
  }
});

test("the bossa demo is a perfect score: four chord tones in every bar, on the exact beats", () => {
  const ex = challenges.challenges.find((c) => c.slug === "challenge-bossa-rhythm");
  const demo = demoFor(ex);
  assert.equal(demo.notes.length, 16);
  const beatSeconds = 60 / ex.tempo;
  demo.notes.forEach((n, i) => {
    const bar = Math.floor(i / 4);
    const beat = ex.scoring_params.pattern[i % 4];
    assert.ok(Math.abs(n.when - (10 + (bar * 4 + beat) * beatSeconds)) < 1e-9, `note ${i} is on its beat`);
  });
});

// --------------------------------------------------------------------- the notes themselves

test("every note is playable, in a comfortable range, and sounds for a moment", () => {
  for (const ex of all) {
    const demo = demoFor(ex);
    if (!demo.ok) continue;
    for (const n of demo.notes) {
      assert.ok(Number.isInteger(n.note) && n.note >= 48 && n.note <= 84, `${ex.slug}: note ${n.note}`);
      assert.ok(n.velocity > 0 && n.velocity <= 1, ex.slug);
      assert.ok(n.seconds >= 0.05, ex.slug);
      assert.ok(n.when >= 10 - 1, `${ex.slug}: nothing starts before the count-in`);
    }
  }
});

test("a line that is meant to be smooth moves by steps and small skips, not leaps", () => {
  const ex = challenges.challenges.find((c) => c.slug === "challenge-bossa-rhythm");
  const notes = demoFor(ex).notes;
  for (let i = 1; i < notes.length; i++) assert.ok(Math.abs(notes[i].note - notes[i - 1].note) <= 7, `leap at ${i}`);
});

test("the demo follows the tempo it is given", () => {
  const ex = challenges.challenges.find((c) => c.slug === "challenge-bossa-rhythm");
  const slow = demoFor(ex, { bpm: 60 }).notes;
  const fast = demoFor(ex, { bpm: 120 }).notes;
  assert.ok(Math.abs(slow[1].when - 10 - 2 * (fast[1].when - 10)) < 1e-9);
});

test("a free play exercise says there is nothing to show, and why", () => {
  const demo = Demo.build({ scoring: { kind: "free_play", params: {} }, chart: { bars: [], beatsPerBar: 4 }, from: 0, to: 0, qualities, beatsPerBar: 4, bpm: 100, downbeat: 0 });
  assert.equal(demo.ok, false);
  assert.match(demo.reason, /no set answer|nothing to show/i);
  assert.equal(Demo.canShow("free_play"), false);
  assert.equal(Demo.canShow("rhythm_motif"), true);
  assert.equal(Demo.canShow(undefined), false);
});

test("a rhythm with no pattern is refused rather than guessed", () => {
  const chart = Chart.parseChart("| Dm7 | G7 |", qualities, { beatsPerBar: 4, homeKey: "C" });
  const demo = Demo.build({ scoring: { kind: "rhythm_motif", params: {} }, chart, from: 0, to: 2, qualities, beatsPerBar: 4, bpm: 100, downbeat: 0 });
  assert.equal(demo.ok, false);
});

// --------------------------------------------------------------------------- the words

test("beats are named the way a player says them", () => {
  assert.equal(Demo.beatWords(0), "beat 1");
  assert.equal(Demo.beatWords(2), "beat 3");
  assert.equal(Demo.beatWords(1.5), "the and of 2");
  assert.equal(Demo.beatWords(3.5), "the and of 4");
  assert.equal(Demo.beatWords(0.25), "a quarter of the way into beat 1");
});

test("the line under the button says what is about to be shown", () => {
  const bossa = challenges.challenges.find((c) => c.slug === "challenge-bossa-rhythm");
  const line = demoFor(bossa).line;
  assert.match(line, /beat 1, the and of 2, beat 3 and the and of 4/);
  assert.match(line, /every bar/);
  const blues = challenges.challenges.find((c) => c.slug === "challenge-blues-chord-tones");
  assert.match(demoFor(blues).line, /beat 1 and beat 3/);
  const scale = challenges.challenges.find((c) => c.slug === "challenge-turnaround-scale");
  assert.match(demoFor(scale).line, /scale/i);
  const guide = challenges.challenges.find((c) => c.slug === "challenge-jazz-blues-guide-tones");
  assert.match(demoFor(guide).line, /third|seventh/i);
  const approach = challenges.challenges.find((c) => c.slug === "challenge-minor-blues-approach");
  assert.match(demoFor(approach).line, /half step|semitone/i);
});

test("the demo lasts the bars of the exercise and reports when it is over", () => {
  const ex = challenges.challenges.find((c) => c.slug === "challenge-bossa-rhythm");
  const demo = demoFor(ex);
  const bar = (60 / ex.tempo) * 4;
  assert.ok(Math.abs(demo.endsAt - (10 + 4 * bar)) < 1e-9);
});

test("the module reaches for no browser API", () => {
  const text = require("node:fs").readFileSync(path.join(root, "static", "improv", "demo.js"), "utf8").replace(/\/\/[^\n]*/g, "");
  for (const word of ["document.", "window.", "navigator.", "fetch(", "Math.random", "setTimeout", "localStorage", "innerHTML"]) {
    assert.ok(!text.includes(word), `demo.js uses ${word}`);
  }
});
