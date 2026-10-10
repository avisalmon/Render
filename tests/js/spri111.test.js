// SPR-I.11.1 improv: the chord guide. For a chord the guide names its notes, the scale around it, and lays
// the chord in its first three positions on a five-octave keyboard: root position in the darkest shade, the
// inversions in lighter ones, the scale in a quiet tint. A player who does not know "Dm7" sees the keys.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const G = require(path.join(root, "static", "improv", "chord-guide.js"));
const Chart = require(path.join(root, "static", "improv", "chart.js"));
const read = (...parts) => JSON.parse(fs.readFileSync(path.join(root, ...parts), "utf8"));
const theory = read("improv", "seed_data", "theory.json");
const library = read("improv", "seed_data", "library.json");

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

const chord = (typed, key) => {
  const chart = Chart.parseChart(typed, qualities, { homeKey: key || "C" });
  assert.equal(chart.ok, true, typed);
  return chart.bars[0].chords[0];
};
const notesOf = (guide, role) => [...guide.keys].filter(([, v]) => v.role === role).map(([n]) => n).sort((a, b) => a - b);

test("Cmaj7 in root position is C E G B, the first inversion starts on E, the second on G", () => {
  const g = G.guideFor(chord("Cmaj7"), qualities, "sharps");
  assert.deepEqual(g.tones, ["C", "E", "G", "B"]);
  assert.deepEqual(g.positions.map((p) => p.names), [["C", "E", "G", "B"], ["E", "G", "B", "C"], ["G", "B", "C", "E"]]);
  assert.deepEqual(g.positions.map((p) => p.notes[0] % 12), [0, 4, 7]);
  assert.deepEqual(g.positions.map((p) => p.word), ["Root position", "First inversion", "Second inversion"]);
});

test("the three positions sit in separate octaves, so none hides another", () => {
  const g = G.guideFor(chord("Cmaj7"), qualities, "sharps");
  const all = g.positions.flatMap((p) => p.notes);
  assert.equal(new Set(all).size, all.length);
  for (const p of g.positions) assert.deepEqual(p.notes, [...p.notes].sort((a, b) => a - b));
  assert.ok(g.positions[0].notes[0] < g.positions[1].notes[0] && g.positions[1].notes[0] < g.positions[2].notes[0]);
});

test("the keys carry the roles: root position p1, inversions p2 and p3, the rest of the scale quiet", () => {
  const g = G.guideFor(chord("Cmaj7"), qualities, "sharps");
  assert.deepEqual(notesOf(g, "p1"), g.positions[0].notes);
  assert.deepEqual(notesOf(g, "p2"), g.positions[1].notes);
  assert.deepEqual(notesOf(g, "p3"), g.positions[2].notes);
  const scale = notesOf(g, "scale");
  assert.ok(scale.length > 20);
  for (const n of scale) assert.ok([0, 2, 4, 5, 7, 9, 11].includes(n % 12), `${n} is not in C major`);
  assert.ok(g.keys.get(g.positions[0].notes[0]).label === "C");
  assert.equal(g.keys.get(scale[0]).label, "");
});

test("the scale is named after the chord's first-ranked scale", () => {
  const g = G.guideFor(chord("Dm7"), qualities, "sharps");
  assert.match(g.scaleName, /^D /);
  assert.equal(g.scaleNotes[0], "D");
  assert.equal(g.scaleNotes.length, 7);
});

test("the player's spelling decides the names: Bbmaj7 in flats, A#maj7 in sharps", () => {
  const flat = G.guideFor(chord("Bbmaj7"), qualities, "flats");
  const sharp = G.guideFor(chord("Bbmaj7"), qualities, "sharps");
  assert.deepEqual(flat.tones, ["Bb", "D", "F", "A"]);
  assert.deepEqual(sharp.tones, ["A#", "D", "F", "A"]);
  assert.equal(flat.keys.get(flat.positions[0].notes[0]).label, "Bb");
});

test("a chord with a quality the library does not know gets no guide, and nothing gets none", () => {
  assert.equal(G.guideFor(null, qualities, "sharps"), null);
  assert.equal(G.guideFor({ root: 0, quality: "nope", name: "C?" }, qualities, "sharps"), null);
});

test("every quality in the library, on every root, gets a guide that fits the keyboard", () => {
  for (const q of qualities) {
    for (let root = 0; root < 12; root++) {
      const g = G.guideFor({ name: "x", root, quality: q.symbol }, qualities, "sharps");
      assert.ok(g, `${q.symbol} on ${root}`);
      assert.ok(g.positions.length >= 1, `${q.symbol} on ${root} has no position`);
      for (const p of g.positions) for (const n of p.notes) assert.ok(n >= G.FIRST && n <= G.LAST, `${q.symbol} on ${root}: ${n} is off the keyboard`);
      for (const [n] of g.keys) assert.ok(n >= g.from && n <= g.to);
    }
  }
});

test("the chord in a bar is the last one that has started", () => {
  const chart = Chart.parseChart("Dm7 G7 | Cmaj7", qualities, { homeKey: "C" });
  const bar = chart.bars[0];
  assert.equal(G.chordInBar(bar, 0).name, bar.chords[0].name);
  assert.equal(G.chordInBar(bar, 1.9).name, bar.chords[0].name);
  assert.equal(G.chordInBar(bar, 2).name, bar.chords[1].name);
  assert.equal(G.chordInBar(bar, 3.5).name, bar.chords[1].name);
  assert.equal(G.chordInBar(null, 0), null);
});

test("every chord of every seeded progression gets a guide", () => {
  for (const p of library.progressions) {
    const chart = Chart.parseChart(p.chart, qualities, { homeKey: p.home_key });
    assert.equal(chart.ok, true, p.slug);
    for (const bar of chart.bars) for (const c of bar.chords) assert.ok(G.guideFor(c, qualities, "flats"), `${p.slug}: ${c.name}`);
  }
});
