// SPR-I.2.2 improv: every progression in the seed parses with the real parser.
// The chart text is the only copy of the harmony, and the server never parses it,
// so this is the guard that a preset cannot ship unplayable.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const chart = require(path.join(root, "static", "improv", "chart.js"));
const theory = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "theory.json"), "utf8"));
const library = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "library.json"), "utf8"));
const qualities = theory.chord_qualities.map((q) => ({ symbol: q.symbol, aliases: q.aliases }));

for (const p of library.progressions) {
  const beatsPerBar = Number(p.time_signature.split("/")[0]);

  test(`${p.slug} parses`, () => {
    const result = chart.parseChart(p.chart, qualities, { beatsPerBar, homeKey: p.home_key });
    assert.equal(result.ok, true, JSON.stringify(result.error));
    assert.ok(result.bars.length >= 4, "a progression is at least four bars once played");
    assert.ok(result.bars.length <= 128, "a preset should not be a whole song");
  });

  test(`${p.slug} uses its home key as a chord root somewhere`, () => {
    const result = chart.parseChart(p.chart, qualities, { beatsPerBar, homeKey: p.home_key });
    const home = chart.parseKey(p.home_key);
    const everyRoot = new Set();
    for (const bar of result.bars) for (const c of bar.chords) everyRoot.add(c.root);
    assert.ok(everyRoot.has(home.pc), `the home key ${p.home_key} never appears as a chord root`);
  });

  test(`${p.slug} survives a trip through every key`, () => {
    const result = chart.parseChart(p.chart, qualities, { beatsPerBar, homeKey: p.home_key });
    for (const key of ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]) {
      const moved = chart.transposeToKey(result, p.home_key, key);
      assert.equal(moved.bars.length, result.bars.length);
    }
  });
}
