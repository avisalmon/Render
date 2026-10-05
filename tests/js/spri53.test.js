// SPR-I.5.3 improv: the seeded lessons can be passed. A lesson nobody can pass is worse than no
// lesson, so for every seeded exercise a model player plays the take the exercise asks for, exactly
// on the grid, and the real judge has to score it at or above the pass mark. A take of wrong notes
// has to fall short, so an exercise is not passed just by turning up.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const J = require(path.join(root, "static", "improv", "judge.js"));
const Chart = require(path.join(root, "static", "improv", "chart.js"));
const read = (...parts) => JSON.parse(fs.readFileSync(path.join(root, ...parts), "utf8"));
const theory = read("improv", "seed_data", "theory.json");
const library = read("improv", "seed_data", "library.json");
const lessons = read("improv", "seed_data", "lessons.json");

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
const qualityBySymbol = new Map(qualities.map((q) => [q.symbol, q]));
const stylesBySlug = new Map(library.styles.map((s) => [s.slug, s]));
const progressionsBySlug = new Map(library.progressions.map((p) => [p.slug, p]));

const exercises = [];
for (const lesson of lessons.lessons) {
  for (const ex of lesson.exercises) {
    const progression = progressionsBySlug.get(ex.progression_slug || lesson.progression);
    exercises.push({ ...ex, lesson, progression });
  }
}

const BEATS = 4;
const mod = (n, m) => ((n % m) + m) % m;

function chordAt(chart, bar, beat) {
  const b = chart.bars[bar % chart.bars.length];
  return b.chords.find((c) => beat >= c.beat && beat < c.beat + c.beats);
}
const tonesOf = (chord) => qualityBySymbol.get(chord.quality).intervals.map((i) => mod(chord.root + i, 12));
const scaleOf = (chord) => {
  const first = qualityBySymbol.get(chord.quality).scales[0];
  return first ? first.intervals.map((i) => mod(chord.root + i, 12)) : tonesOf(chord);
};
const guidesOf = (chord) => {
  const q = qualityBySymbol.get(chord.quality);
  return Object.entries(q.roles)
    .filter(([, role]) => /third|seventh/.test(role))
    .map(([interval]) => mod(chord.root + Number(interval), 12));
};
const nearest = (pcs, from) => {
  let best = null;
  for (let n = 52; n <= 84; n++) if (pcs.includes(mod(n, 12)) && (best === null || Math.abs(n - from) < Math.abs(best - from))) best = n;
  return best;
};

function setup(ex) {
  const chart = Chart.parseChart(ex.progression.chart, qualities, { homeKey: ex.progression.home_key });
  assert.equal(chart.ok, true, `${ex.slug}: the chart has to parse`);
  return chart;
}

// The notes a model player plays for an exercise: [beat counted from the first downbeat, midi].
function modelTake(ex, chart) {
  const out = [];
  const params = ex.scoring_params;
  let last = 65;
  for (let bar = 0; bar < ex.bars; bar++) {
    const at = (beat) => bar * BEATS + beat;
    if (ex.scoring_kind === "chord_tones_on_beats" || ex.scoring_kind === "scale_only") {
      const named = ex.scoring_kind === "scale_only" ? [1, 2, 3, 4] : params.beats;
      named.forEach((b, i) => {
        const tones = tonesOf(chordAt(chart, bar, b - 1));
        out.push([at(b - 1), 60 + tones[(i + bar) % tones.length]]);
      });
    } else if (ex.scoring_kind === "guide_tones") {
      for (const b of [0, 2]) {
        last = nearest(guidesOf(chordAt(chart, bar, b)), last);
        out.push([at(b), last]);
      }
    } else if (ex.scoring_kind === "approach_notes") {
      for (const b of params.beats) {
        if (bar === 0 && b === 1) continue;
        const chord = chordAt(chart, bar, b - 1);
        const inside = new Set([...tonesOf(chord), ...scaleOf(chord)]);
        for (const target of tonesOf(chord)) {
          const way = [target - 1, target + 1].map((pc) => mod(pc, 12)).find((pc) => !inside.has(pc));
          if (way === undefined) continue;
          const goal = 60 + target;
          const step = mod(target - way, 12) === 1 ? -1 : 1;
          out.push([at(b - 1) - 0.5, goal + step * 1]);
          out.push([at(b - 1), goal]);
          break;
        }
      }
    } else if (ex.scoring_kind === "rhythm_motif") {
      for (const p of params.pattern) out.push([at(p), 60 + Math.round(p * 2)]);
    } else if (ex.scoring_kind === "call_and_response" && bar === params.answerBar) {
      for (const [beat, note] of params.phrase) out.push([at(beat), note]);
    }
  }
  return out;
}

function judgeTake(ex, chart, notes) {
  const beatMs = 60000 / ex.tempo;
  const events = [];
  for (const [beat, note] of notes) {
    events.push({ t_ms: Math.round(beat * beatMs), type: "on", note, velocity: 90 });
    events.push({ t_ms: Math.round(beat * beatMs) + 200, type: "off", note, velocity: 0 });
  }
  const style = stylesBySlug.get(ex.progression.default_style);
  return J.judge({
    events,
    chart,
    from: 0,
    to: ex.bars,
    bpm: ex.tempo,
    swingRatio: style.swing_ratio === undefined ? 0.5 : style.swing_ratio,
    qualities,
    scoring: { kind: ex.scoring_kind, params: ex.scoring_params },
    latencyOffsetMs: 0,
    grid: "beat",
  });
}

test("the seed has the lessons the sprint promises", () => {
  assert.equal(lessons.lessons.length, 6);
  assert.ok(exercises.length >= 10 && exercises.length <= 20, `${exercises.length} exercises`);
});

test("a model player passes every seeded exercise", () => {
  const failures = [];
  for (const ex of exercises) {
    const chart = setup(ex);
    const got = judgeTake(ex, chart, modelTake(ex, chart));
    if (!(got.score >= ex.pass_score)) failures.push(`${ex.slug}: scored ${got.score}, pass mark ${ex.pass_score}`);
  }
  assert.deepEqual(failures, []);
});

test("playing nothing passes no exercise", () => {
  for (const ex of exercises) {
    const chart = setup(ex);
    const got = judgeTake(ex, chart, []);
    assert.ok(!(got.score >= ex.pass_score), `${ex.slug} passed with an empty take`);
  }
});

test("wrong notes on the beats pass none of the pitch exercises", () => {
  const pitched = ["chord_tones_on_beats", "scale_only", "guide_tones", "approach_notes"];
  for (const ex of exercises.filter((e) => pitched.includes(e.scoring_kind))) {
    const chart = setup(ex);
    const notes = [];
    for (let beat = 0; beat < ex.bars * BEATS; beat++) notes.push([beat, 63]);
    const got = judgeTake(ex, chart, notes);
    assert.ok(!(got.score >= ex.pass_score), `${ex.slug} passed with a note that fits no chord (score ${got.score})`);
  }
});

test("a rhythm that is the wrong shape does not pass a rhythm motif", () => {
  for (const ex of exercises.filter((e) => e.scoring_kind === "rhythm_motif")) {
    const chart = setup(ex);
    const notes = [];
    for (let beat = 0; beat < ex.bars * BEATS; beat += 0.5) notes.push([beat, 60]);
    const got = judgeTake(ex, chart, notes);
    assert.ok(!(got.score >= ex.pass_score), `${ex.slug} passed by playing every eighth (score ${got.score})`);
  }
});
