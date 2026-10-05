// improv: the words of the weakness panel. Pure: no browser, runs under Node.
//
// The server decides what is weak and how many notes it takes to say so. This file only says it in
// plain words: how far there is to go before the report can speak, what stands out when it can, and
// which exercise to try.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovWeakness = factory();
})(typeof self !== "undefined" ? self : this, function () {
  function statusLine(report) {
    if (!report.enough) {
      if (!report.notes) return `No notes in the last ${report.days} days yet. Play ${report.floor} over the band and it will say where to work.`;
      const more = report.notes_needed === 1 ? "1 more note" : `${report.notes_needed} more`;
      return `So far ${report.notes} of the ${report.floor} notes it needs from the last ${report.days} days. Play ${more} and it will say where to work.`;
    }
    if (!report.claims.length) return `Nothing stands out in the last ${report.days} days. Keep playing.`;
    return `Where to work, from the last ${report.days} days:`;
  }

  function claimLine(claim) {
    const pct = `${claim.percent}%`;
    switch (claim.area) {
      case "timing":
        return `Timing: ${pct} of your notes were close to the beat.`;
      case "chord_tones":
        return `Chord tones: ${pct} of your notes were chord tones.`;
      case "outside":
        return `Outside notes: ${pct} of your notes were outside the chord and its scale.`;
      case "family":
        return `Over ${claim.family_label} chords: ${pct} of your notes went outside.`;
      default:
        return "";
    }
  }

  function evidenceLine(claim) {
    return `From ${claim.notes} notes.`;
  }

  function playLabel(claim) {
    return claim.exercise ? `Work on it: ${claim.exercise_title}` : "";
  }

  function noExerciseLine(claim) {
    return claim.exercise ? "" : "Nothing open to work on this yet. Finish the lesson before it and one appears.";
  }

  function playUrl(base, claim) {
    return `${base}?exercise=${encodeURIComponent(claim.exercise)}`;
  }

  return { statusLine, claimLine, evidenceLine, playLabel, noExerciseLine, playUrl };
});
