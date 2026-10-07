// improv: the "work on this" line of the two trainer screens, from the trainer read. Pure: runs under Node.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(require("./scale.js"));
  else root.ImprovWork = factory(root.ImprovScale);
})(typeof self !== "undefined" ? self : this, function (Scale) {
  const CIRCLE = Scale.CIRCLE;
  const OCTAVES = [2, 3, 4];

  function seconds(ms) {
    return `${(ms / 1000).toFixed(1)} s`;
  }

  // The weakest scale not yet passed; if all played have passed, the next key of the circle, two octaves
  // first, then three, then four.
  function scaleWork(read, spelling) {
    const rows = read.scales || [];
    if (!rows.length) return `No scale run yet. Start with ${Scale.keyName(CIRCLE[0], spelling)} at 2 octaves.`;
    const unpassed = rows.filter((r) => !r.passed).sort((a, b) => a.score - b.score || a.octaves - b.octaves);
    if (unpassed.length) {
      const r = unpassed[0];
      return `Work on this: ${Scale.keyName(r.root_pc, spelling)} at ${r.octaves} octaves, best so far ${r.score}.`;
    }
    const done = new Set(rows.map((r) => `${r.root_pc}-${r.octaves}`));
    for (const octaves of OCTAVES) {
      for (const pc of CIRCLE) {
        if (!done.has(`${pc}-${octaves}`)) return `Passed so far. Next: ${Scale.keyName(pc, spelling)} at ${octaves} octaves.`;
      }
    }
    return "Passed every key at every length. Raise the tempo.";
  }

  function chordWork(read, spelling) {
    const totals = read.totals || {};
    if (!totals.attempts) return "No chord answers yet. Start a drill in G.";
    const parts = [];
    const slow = (read.slowest_chords || [])[0];
    if (slow) parts.push(`Slowest: ${slow.title}, ${seconds(slow.median_ms)}.`);
    const weak = (read.weakest_keys || []).find((k) => k.missed > 0);
    if (weak) parts.push(`${Scale.keyName(weak.key_pc, spelling)} is missed most: ${Math.round(weak.miss_share * 100)}% of prompts.`);
    if (!parts.length) return "Not enough answers yet to say what to work on: a chord needs 3, a key needs 5.";
    return `Work on this: ${parts.join(" ")}`;
  }

  return { CIRCLE, scaleWork, chordWork };
});
