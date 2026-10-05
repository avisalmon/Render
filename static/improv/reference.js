// improv: any chord or scale in any key, worked out for the Reference screen. Pure: no
// browser, runs under Node. Everything comes from the theory table, so the screen cannot
// disagree with the recognizer, the judge or the lessons about what is in a chord.
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./chart.js"));
  } else {
    root.ImprovReference = factory(root.ImprovChart);
  }
})(typeof self !== "undefined" ? self : this, function (Chart) {
  // The jazz shorthand for a note's distance from the root. It is the same list for a chord
  // and for a scale, which is the point: b3 means the same thing in both.
  const STEPS = ["1", "b2", "2", "b3", "3", "4", "b5", "5", "b6", "6", "b7", "7"];
  const MIDDLE_C = 60;

  const pcOf = (note) => ((note % 12) + 12) % 12;

  function spell(note, spelling) {
    const names = spelling === "flats" ? Chart.FLAT_NAMES : Chart.SHARP_NAMES;
    return names[pcOf(note)];
  }

  function label(note, spelling) {
    return spell(note, spelling) + (Math.floor(note / 12) - 1);
  }

  function keyChoices(spelling) {
    const choices = [];
    for (let pc = 0; pc < 12; pc++) choices.push([pc, spell(pc, spelling)]);
    return choices;
  }

  // Twelve roots over middle C would run off the top of a two-octave keyboard, so the root
  // is taken from the octave that keeps the whole shape inside the keys the screen draws.
  function startNote(rootPc) {
    return MIDDLE_C + rootPc;
  }

  function chordView(quality, rootPc, options) {
    if (!quality || !(quality.intervals || []).length) return null;
    const spelling = (options || {}).spelling === "flats" ? "flats" : "sharps";
    const roles = quality.roles || {};
    const start = startNote(rootPc);
    const notes = quality.intervals.map((step) => ({
      midi: start + step,
      label: label(start + step, spelling),
      step: STEPS[pcOf(step)],
      role: String(roles[String(step)] || "").replace(/_/g, " "),
    }));
    const ranked = [...(quality.scales || [])].sort((a, b) => (a.preference || 0) - (b.preference || 0));
    return {
      kind: "chord",
      name: Chart.chordName(spell(rootPc, spelling), quality.symbol, ""),
      rootPc,
      symbol: quality.symbol,
      intervals: quality.intervals,
      notes,
      pcs: notes.map((n) => pcOf(n.midi)),
      scales: ranked.map((s) => ({
        slug: s.slug,
        name: `${spell(rootPc, spelling)} ${s.name}`,
        note: s.note || "",
        preference: s.preference,
      })),
    };
  }

  // `fits` is the chord-scale rows for this scale, if the page has them, exactly as the API
  // sends them (`quality_symbol`, `preference`, `note`): which chords the scale goes with.
  // The scale closes on its own root an octave up, because that is how it is played and heard.
  function scaleView(scale, rootPc, options, fits) {
    if (!scale || !(scale.intervals || []).length) return null;
    const spelling = (options || {}).spelling === "flats" ? "flats" : "sharps";
    const start = startNote(rootPc);
    const notes = scale.intervals.map((step) => ({
      midi: start + step,
      label: label(start + step, spelling),
      step: STEPS[pcOf(step)],
      octave: false,
    }));
    notes.push({ midi: start + 12, label: label(start + 12, spelling), step: STEPS[0], octave: true });
    const ranked = [...(fits || [])].sort((a, b) => (a.preference || 0) - (b.preference || 0));
    return {
      kind: "scale",
      name: `${spell(rootPc, spelling)} ${scale.name}`,
      rootPc,
      slug: scale.slug,
      intervals: scale.intervals,
      notes,
      pcs: scale.intervals.map((step) => pcOf(rootPc + step)),
      chords: ranked.map((row) => ({
        symbol: row.quality_symbol,
        name: Chart.chordName(spell(rootPc, spelling), row.quality_symbol, ""),
        note: row.note || "",
        preference: row.preference,
      })),
    };
  }

  // The keys to draw: whole octaves, starting on the C at or below the lowest note, and
  // always wide enough for the shape plus the octave above it.
  function keyboardRange(view) {
    const lowest = view ? view.notes[0].midi : MIDDLE_C;
    const highest = view ? view.notes[view.notes.length - 1].midi : MIDDLE_C + 12;
    const from = Math.floor(lowest / 12) * 12;
    let to = from + 24;
    while (to < highest) to += 12;
    return { from, to };
  }

  return { keyChoices, chordView, scaleView, keyboardRange, STEPS };
});
